"""
NovaFlix - Main Application Server & API Gateway
Powers the Cinema Web Client, HTTP 206 Streaming Engine,
Plex-style Download & Showcase Portal, and SyncPlay Watch Together.
"""

import sys
import os
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect, HTTPException, Query, Body
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from novaflix.config import (
    SERVER_HOST, SERVER_PORT, PORTAL_PORT, BASE_DIR
)
from novaflix.database import Database
from novaflix.streaming import StreamService
from novaflix.auth import hash_password, verify_password, create_session_token, verify_session_token
from novaflix.remote import RemoteAccessService
from novaflix.syncplay import syncplay_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("novaflix.main")

db = Database()
remote_service = RemoteAccessService()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"NovaFlix Media Engine starting on port {SERVER_PORT}...")
    yield
    logger.info("NovaFlix Media Engine stopped.")

app = FastAPI(title="NovaFlix", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# -------------------------------------------------------------
# Media Library REST APIs
# -------------------------------------------------------------

@app.get("/api/media/featured")
async def get_featured():
    item = db.get_featured_media()
    return item or {}

@app.get("/api/media/movies")
async def get_movies(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None)
):
    return db.get_movies(limit=limit, offset=offset, search=search)

@app.get("/api/media/shows")
async def get_shows(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None)
):
    return db.get_shows(limit=limit, offset=offset, search=search)

@app.get("/api/media/item/{item_id}")
async def get_item(item_id: int):
    item = db.get_item_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Media item not found")
    return item

@app.get("/api/media/continue")
async def get_continue_watching(user_id: int = Query(1)):
    return db.get_continue_watching(user_id)

class ProgressPayload(BaseModel):
    user_id: int = 1
    media_id: int
    position_seconds: float
    duration_seconds: float

@app.post("/api/media/progress")
async def update_progress(payload: ProgressPayload):
    db.update_progress(payload.user_id, payload.media_id, payload.position_seconds, payload.duration_seconds)
    return {"status": "success"}

class WatchlistPayload(BaseModel):
    user_id: int = 1
    media_id: int

@app.post("/api/media/watchlist/toggle")
async def toggle_watchlist(payload: WatchlistPayload):
    is_in_watchlist = db.toggle_watchlist(payload.user_id, payload.media_id)
    return {"status": "success", "in_watchlist": is_in_watchlist}

@app.get("/api/media/watchlist")
async def get_watchlist(user_id: int = Query(1)):
    return db.get_watchlist(user_id)

# -------------------------------------------------------------
# Streaming & Subtitles Endpoints
# -------------------------------------------------------------

@app.get("/stream/{item_id}")
async def stream_media_endpoint(item_id: int, request: Request):
    """Direct Play and HTTP 206 Partial Content Range streaming."""
    item = db.get_item_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Media not found")
    return StreamService.stream_media(request, item)

@app.get("/subtitles/{item_id}")
async def get_subtitles(item_id: int):
    """Retrieve WebVTT subtitle stream."""
    item = db.get_item_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Media not found")
    vtt = StreamService.get_subtitles_vtt(item)
    if not vtt:
        return Response(content="WEBVTT\n\n", media_type="text/vtt")
    return Response(content=vtt, media_type="text/vtt")

# -------------------------------------------------------------
# User & Profile Management
# -------------------------------------------------------------

@app.get("/api/users")
async def list_users():
    return db.get_users()

class LoginPayload(BaseModel):
    username: str
    password: str

@app.post("/api/auth/login")
async def login(payload: LoginPayload):
    user = db.get_user_by_username(payload.username)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_session_token(user["id"], user["username"], bool(user["is_admin"]))
    return {
        "status": "success",
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "is_admin": bool(user["is_admin"]),
            "avatar_color": user["avatar_color"],
            "max_age_rating": user["max_age_rating"]
        }
    }

class RegisterPayload(BaseModel):
    username: str
    password: str
    max_age_rating: Optional[str] = "ALL"

@app.post("/api/auth/register")
async def register(payload: RegisterPayload):
    existing = db.get_user_by_username(payload.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")
    user_id = db.create_user(payload.username, payload.password, is_admin=False, max_age_rating=payload.max_age_rating or "ALL")
    token = create_session_token(user_id, payload.username, False)
    return {"status": "success", "token": token, "user_id": user_id}

# -------------------------------------------------------------
# Remote Access & Network Discovery
# -------------------------------------------------------------

@app.get("/api/system/remote")
async def get_remote_status():
    info = await remote_service.get_connection_info()
    return info

@app.post("/api/system/remote/test")
async def test_remote():
    info = await remote_service.get_connection_info()
    return {"status": "CONNECTED", "public_url": info["remote_url"], "reachable": True}

# -------------------------------------------------------------
# SyncPlay (Watch Together) WebSocket
# -------------------------------------------------------------

@app.websocket("/ws/syncplay/{room_id}")
async def syncplay_websocket(websocket: WebSocket, room_id: str):
    await syncplay_manager.join_room(room_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await syncplay_manager.handle_message(room_id, websocket, data)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        syncplay_manager.leave_room(room_id, websocket)

# -------------------------------------------------------------
# Plex-Style Download & Showcase Portal
# -------------------------------------------------------------

@app.get("/portal", response_class=HTMLResponse)
async def serve_download_portal(request: Request):
    """Plex-style product landing, sign-up and multi-platform download page."""
    connection_info = await remote_service.get_connection_info()
    return templates.TemplateResponse(
        request=request,
        name="portal.html",
        context={
            "app_name": "NovaFlix",
            "remote_info": connection_info
        }
    )

@app.get("/api/downloads")
async def get_download_variants():
    """Download matrix for Windows, macOS, Linux, and Docker."""
    return {
        "windows": {
            "version": "1.0.0",
            "files": [
                {"name": "NovaFlix-Setup-x64.exe", "type": "Installer", "size": "48.2 MB", "url": "/static/downloads/NovaFlix-Setup-x64.exe"},
                {"name": "NovaFlix-Portable-x64.zip", "type": "Portable Zip", "size": "42.1 MB", "url": "/static/downloads/NovaFlix-Portable.zip"},
                {"name": "run.bat", "type": "1-Click Script", "size": "1.2 KB", "url": "https://raw.githubusercontent.com/digdast/novaflix/main/run.bat"}
            ]
        },
        "macos": {
            "version": "1.0.0",
            "files": [
                {"name": "NovaFlix-Universal.dmg", "type": "Apple Silicon & Intel", "size": "56.4 MB", "url": "/static/downloads/NovaFlix-Universal.dmg"},
                {"name": "Homebrew Formula", "type": "CLI", "size": "brew install digdast/novaflix/novaflix", "url": "#"}
            ]
        },
        "linux": {
            "version": "1.0.0",
            "files": [
                {"name": "novaflix_1.0.0_amd64.deb", "type": "Debian / Ubuntu", "size": "38.5 MB", "url": "/static/downloads/novaflix_amd64.deb"},
                {"name": "novaflix-1.0.0-1.x86_64.rpm", "type": "RHEL / Fedora", "size": "39.1 MB", "url": "/static/downloads/novaflix.rpm"},
                {"name": "run.sh", "type": "Universal Script", "size": "1.4 KB", "url": "https://raw.githubusercontent.com/digdast/novaflix/main/run.sh"}
            ]
        },
        "docker": {
            "version": "latest",
            "image": "ghcr.io/digdast/novaflix:latest",
            "compose_url": "https://raw.githubusercontent.com/digdast/novaflix/main/docker-compose.yml"
        }
    }

# -------------------------------------------------------------
# NovaFlix Cinema Web App
# -------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def serve_cinema_app(request: Request):
    """The Cinema UI: Home, Movies, TV Shows, Search, Player."""
    featured = db.get_featured_media()
    movies = db.get_movies(limit=12)
    shows = db.get_shows(limit=12)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "app_name": "NovaFlix",
            "featured": featured,
            "movies": movies,
            "shows": shows
        }
    )

def start():
    """CLI Entry point."""
    import uvicorn
    uvicorn.run("novaflix.main:app", host=SERVER_HOST, port=SERVER_PORT, reload=False, log_level="info")

if __name__ == "__main__":
    start()

"""
NovaFlix - Main Application Server & API Gateway
Powers the Cinema Web Client, HTTP 206 Streaming Engine,
Plex-style Download & Showcase Portal, and SyncPlay Watch Together.
"""

import sys
import os
import asyncio
import logging
import mimetypes
import urllib.parse
import html
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect, HTTPException, Query, Body
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from novaflix.config import (
    SERVER_HOST, SERVER_PORT, PORTAL_PORT, BASE_DIR, SUPPORTED_VIDEO_EXTS
)
from novaflix.database import Database
from novaflix.streaming import StreamService
from novaflix.auth import hash_password, verify_password, create_session_token, verify_session_token
from novaflix.remote import RemoteAccessService
from novaflix.syncplay import syncplay_manager
from novaflix.scanner import scanner, probe_file


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
# Media Addition, Scanning & Library Management APIs
# -------------------------------------------------------------

class AddMediaPayload(BaseModel):
    title: str
    type: str = "movie"  # 'movie', 'show', 'episode'
    year: Optional[int] = None
    rating: Optional[float] = 8.5
    genre: Optional[str] = "Cinema"
    duration: Optional[str] = None
    director: Optional[str] = "NovaFlix"
    cast: Optional[str] = ""
    synopsis: Optional[str] = ""
    poster: Optional[str] = ""
    backdrop: Optional[str] = ""
    file_path: Optional[str] = ""
    stream_url: Optional[str] = ""
    resolution: Optional[str] = None
    audio_codec: Optional[str] = None
    library_id: Optional[int] = 1

class AddLibraryPayload(BaseModel):
    name: str
    type: str  # 'movies', 'tvshows'
    path: str

class UpdateLibraryPayload(BaseModel):
    name: str
    type: str
    path: str

class ScanLibraryPayload(BaseModel):
    library_id: Optional[int] = None
    path: Optional[str] = None
    type: Optional[str] = None
    max_items: Optional[int] = None

@app.get("/api/libraries")
async def list_libraries():
    """List all configured media libraries with item counts."""
    return db.get_libraries()

@app.post("/api/libraries")
async def add_library_endpoint(payload: AddLibraryPayload):
    """Add a new media library folder."""
    if not payload.name or not payload.path:
        raise HTTPException(status_code=400, detail="Name and path are required")
    lib_id = db.add_library(payload.name, payload.type, payload.path)
    return {"status": "success", "id": lib_id}

@app.put("/api/libraries/{lib_id}")
async def update_library_endpoint(lib_id: int, payload: UpdateLibraryPayload):
    """Update a media library folder."""
    db.update_library(lib_id, payload.name, payload.type, payload.path)
    return {"status": "success", "id": lib_id}

@app.delete("/api/libraries/{lib_id}")
async def delete_library_endpoint(lib_id: int, delete_media: bool = Query(False)):
    """Delete a library folder and optionally remove indexed items."""
    db.delete_library(lib_id, delete_media=delete_media)
    return {"status": "success", "deleted_id": lib_id}

@app.post("/api/libraries/scan")
async def scan_libraries_endpoint(payload: ScanLibraryPayload = Body(default=ScanLibraryPayload())):
    """
    Scan library directories on disk and import items into NovaFlix.
    """
    if payload.path and payload.type:
        res = await asyncio.to_thread(
            scanner.scan_path,
            path_str=payload.path,
            lib_type=payload.type,
            library_id=payload.library_id or 1,
            max_items=payload.max_items
        )
        return {"status": "success", "results": [res]}

    libs = db.get_libraries()
    if payload.library_id:
        libs = [l for l in libs if l["id"] == payload.library_id]

    results = []
    for lib in libs:
        p = Path(lib["path"])
        if p.exists():
            res = await asyncio.to_thread(
                scanner.scan_path,
                path_str=lib["path"],
                lib_type=lib["type"],
                library_id=lib["id"],
                max_items=payload.max_items
            )
            results.append({"library": lib["name"], "path": lib["path"], **res})
        else:
            results.append({"library": lib["name"], "path": lib["path"], "error": "Path not found on disk"})

    return {"status": "success", "results": results}

@app.get("/api/libraries/scan/status")
async def get_scan_status():
    """Retrieve current scanning engine status and progress."""
    return scanner.status

@app.post("/api/media/add")
async def add_media_endpoint(payload: AddMediaPayload):
    """
    Manually add a movie, show, or video to NovaFlix.
    Automatically probes technical metadata if file_path is specified.
    """
    file_path = payload.file_path.strip() if payload.file_path else None
    stream_url = payload.stream_url.strip() if payload.stream_url else None

    if not file_path and not stream_url:
        raise HTTPException(status_code=400, detail="Must provide either a local file_path or a stream_url")

    duration = payload.duration
    duration_seconds = 0
    resolution = payload.resolution
    video_codec = "H.264"
    audio_codec = payload.audio_codec or "AAC 5.1"

    if file_path:
        p = Path(file_path)
        if p.exists() and p.is_file():
            probe_info = probe_file(p)
            if not duration:
                duration = probe_info["duration"]
                duration_seconds = probe_info["duration_seconds"]
            if not resolution:
                resolution = probe_info["resolution"]
            video_codec = probe_info["video_codec"]
            if not payload.audio_codec:
                audio_codec = probe_info["audio_codec"]
        else:
            if not duration:
                duration = "1h 45m"
            if not resolution:
                resolution = "1080p FHD"
    else:
        if not duration:
            duration = "2h 00m"
        if not resolution:
            resolution = "1080p FHD"

    poster = payload.poster.strip() if payload.poster else None
    if not poster:
        poster = f"/api/media/poster/generated?title={urllib.parse.quote(payload.title)}&year={payload.year or ''}&genre={urllib.parse.quote(payload.genre or 'Cinema')}"

    backdrop = payload.backdrop.strip() if payload.backdrop else poster

    item_data = {
        "library_id": payload.library_id or 1,
        "title": payload.title,
        "original_title": payload.title,
        "type": payload.type,
        "parent_id": None,
        "season_number": 0,
        "episode_number": 0,
        "year": payload.year or 2026,
        "rating": payload.rating or 8.5,
        "duration": duration,
        "duration_seconds": duration_seconds,
        "genre": payload.genre or "Cinema",
        "director": payload.director or "NovaFlix",
        "cast": payload.cast or "Master Cast",
        "synopsis": payload.synopsis or f"Added to NovaFlix library: {payload.title}",
        "poster": poster,
        "backdrop": backdrop,
        "file_path": file_path,
        "stream_url": stream_url,
        "resolution": resolution or "1080p FHD",
        "audio_codec": audio_codec,
        "video_codec": video_codec,
        "content_rating": "PG-13"
    }

    item_id = db.add_media_item(item_data)
    created_item = db.get_item_by_id(item_id)
    return {"status": "success", "id": item_id, "item": created_item}

@app.delete("/api/media/item/{item_id}")
async def delete_media_endpoint(item_id: int):
    """Delete a media item from NovaFlix."""
    item = db.get_item_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Media item not found")
    db.delete_media_item(item_id)
    return {"status": "success", "deleted_id": item_id}

@app.get("/api/media/poster/generated")
async def generate_poster_svg(
    title: str = Query("NovaFlix Cinema"),
    year: Optional[str] = Query(""),
    genre: Optional[str] = Query("Feature Film"),
    resolution: Optional[str] = Query("4K UHD")
):
    """Generate dynamic high-definition SVG artwork for media cards."""
    safe_title = html.escape(title[:45])
    safe_year = html.escape(str(year or ""))
    safe_genre = html.escape(str(genre or "Feature Film")[:30])
    safe_res = html.escape(str(resolution or "4K UHD"))

    h = sum(ord(c) for c in title) % 4
    colors = [
        ("#8b5cf6", "#ec4899"),
        ("#06b6d4", "#3b82f6"),
        ("#f59e0b", "#ef4444"),
        ("#10b981", "#059669"),
    ]
    c1, c2 = colors[h]

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 900" width="100%" height="100%">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0c0e18"/>
      <stop offset="50%" stop-color="#141727"/>
      <stop offset="100%" stop-color="#07090f"/>
    </linearGradient>
    <radialGradient id="glowGrad" cx="50%" cy="20%" r="50%">
      <stop offset="0%" stop-color="{c1}" stop-opacity="0.35"/>
      <stop offset="100%" stop-color="{c2}" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="badgeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{c1}"/>
      <stop offset="100%" stop-color="{c2}"/>
    </linearGradient>
  </defs>

  <rect width="600" height="900" fill="url(#bgGrad)"/>
  <rect width="600" height="900" fill="url(#glowGrad)"/>

  <rect x="25" y="25" width="550" height="850" rx="20" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="2"/>
  <rect x="35" y="35" width="530" height="830" rx="14" fill="none" stroke="rgba(255,255,255,0.04)" stroke-width="1"/>

  <g transform="translate(50, 65)">
    <rect x="0" y="0" width="105" height="30" rx="15" fill="rgba(255,255,255,0.08)" stroke="{c1}" stroke-width="1.5"/>
    <text x="52" y="20" fill="#ffffff" font-family="system-ui, sans-serif" font-size="12" font-weight="700" text-anchor="middle" letter-spacing="1">NOVAFLIX</text>
  </g>
  <g transform="translate(445, 65)">
    <rect x="0" y="0" width="105" height="30" rx="15" fill="rgba(255,255,255,0.08)" stroke="rgba(255,255,255,0.2)" stroke-width="1"/>
    <text x="52" y="20" fill="#facc15" font-family="system-ui, sans-serif" font-size="12" font-weight="700" text-anchor="middle">{safe_res}</text>
  </g>

  <g transform="translate(300, 340)">
    <circle cx="0" cy="0" r="80" fill="rgba(255,255,255,0.03)" stroke="url(#badgeGrad)" stroke-width="2"/>
    <circle cx="0" cy="0" r="60" fill="rgba(255,255,255,0.05)"/>
    <polygon points="-15,-25 25,0 -15,25" fill="#ffffff"/>
  </g>

  <g transform="translate(300, 560)">
    <text x="0" y="0" fill="#ffffff" font-family="system-ui, -apple-system, sans-serif" font-size="32" font-weight="800" text-anchor="middle">
      {safe_title}
    </text>
    <text x="0" y="45" fill="#a1a1aa" font-family="system-ui, sans-serif" font-size="16" font-weight="500" text-anchor="middle" letter-spacing="2">
      {f"{safe_year} • " if safe_year else ""}{safe_genre.upper()}
    </text>
    <line x1="-120" y1="80" x2="120" y2="80" stroke="url(#badgeGrad)" stroke-width="2"/>
  </g>

  <g transform="translate(300, 780)">
    <text x="0" y="0" fill="#e4e4e7" font-family="system-ui, sans-serif" font-size="14" font-weight="600" text-anchor="middle" letter-spacing="3">
      ULTRA HD CINEMA MASTER
    </text>
    <text x="0" y="25" fill="#71717a" font-family="system-ui, sans-serif" font-size="11" text-anchor="middle" letter-spacing="1">
      DIRECT PLAY • LOSSLESS AUDIO
    </text>
  </g>
</svg>"""
    return Response(content=svg, media_type="image/svg+xml")

@app.get("/api/media/image/{item_id}")
async def serve_media_image(item_id: int, type: str = Query("poster")):
    """Serve local poster or backdrop image from disk."""
    item = db.get_item_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Media not found")

    img_field = item.get("backdrop") if type == "backdrop" else item.get("poster")
    if img_field and Path(img_field).exists() and Path(img_field).is_file():
        mime, _ = mimetypes.guess_type(img_field)
        return FileResponse(img_field, media_type=mime or "image/jpeg")

    safe_title = urllib.parse.quote(item.get("title", "NovaFlix"))
    return RedirectResponse(url=f"/api/media/poster/generated?title={safe_title}&year={item.get('year', '')}")

@app.get("/api/filesystem/browse")
async def browse_filesystem(path: Optional[str] = Query(None)):
    """Browse server filesystem directories to select media paths."""
    default_root = "/data/media" if Path("/data/media").exists() else ("/data" if Path("/data").exists() else "C:/")
    target_path = Path(path) if path else Path(default_root)

    if not target_path.exists():
        target_path = Path(default_root)

    try:
        entries = list(target_path.iterdir())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot read directory: {e}")

    dirs = []
    files = []
    for e in sorted(entries, key=lambda x: x.name.lower()):
        try:
            if e.is_dir() and not e.name.startswith("."):
                dirs.append(e.name)
            elif e.is_file() and e.suffix.lower() in SUPPORTED_VIDEO_EXTS:
                files.append(e.name)
        except Exception:
            pass

    parent = str(target_path.parent) if target_path.parent != target_path else None

    suggested = []
    candidates = [
        ("/data/media/movies", "Movies (/data/media/movies)", "movies"),
        ("/data/media/tv-shows", "TV Shows (/data/media/tv-shows)", "tvshows"),
        ("/data/media/animated-movies", "Animated Movies", "movies"),
        ("/data/media/animated-tv", "Animated TV", "tvshows"),
        ("/data/downloads", "Downloads", "movies")
    ]
    for p, name, t in candidates:
        if Path(p).exists():
            suggested.append({"name": name, "path": p, "type": t})

    return {
        "current_path": str(target_path),
        "parent_path": parent,
        "directories": dirs,
        "video_files": files,
        "suggested_paths": suggested
    }


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

@app.api_route("/portal", methods=["GET", "HEAD"], response_class=HTMLResponse)
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

@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
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

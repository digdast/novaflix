"""
NovaFlix - SyncPlay (Watch Together) Real-Time Synchronization Engine
Enables friends and family across remote locations to watch movies and shows
in exact playback synchronization with live text chat.
"""

import asyncio
from typing import Dict, Set
from fastapi import WebSocket

class SyncPlayManager:
    def __init__(self):
        # room_id -> Set[WebSocket]
        self.rooms: Dict[str, Set[WebSocket]] = {}
        # room_id -> { "media_id": int, "state": "playing"|"paused", "position": float, "last_updated": float }
        self.room_states: Dict[str, dict] = {}

    async def join_room(self, room_id: str, websocket: WebSocket):
        await websocket.accept()
        if room_id not in self.rooms:
            self.rooms[room_id] = set()
            self.room_states[room_id] = {
                "media_id": None,
                "state": "paused",
                "position": 0.0
            }
        self.rooms[room_id].add(websocket)

        # Send current state to newly joined viewer
        await websocket.send_json({
            "type": "INIT_STATE",
            "state": self.room_states[room_id],
            "viewer_count": len(self.rooms[room_id])
        })
        await self.broadcast(room_id, {
            "type": "USER_JOINED",
            "viewer_count": len(self.rooms[room_id])
        }, exclude=websocket)

    def leave_room(self, room_id: str, websocket: WebSocket):
        if room_id in self.rooms:
            self.rooms[room_id].discard(websocket)
            if not self.rooms[room_id]:
                del self.rooms[room_id]
                self.room_states.pop(room_id, None)

    async def handle_message(self, room_id: str, sender_ws: WebSocket, message: dict):
        msg_type = message.get("type")
        
        if msg_type in ("PLAY", "PAUSE", "SEEK"):
            if room_id in self.room_states:
                self.room_states[room_id]["state"] = "playing" if msg_type == "PLAY" else "paused"
                self.room_states[room_id]["position"] = message.get("position", 0.0)
                if "media_id" in message:
                    self.room_states[room_id]["media_id"] = message["media_id"]

            await self.broadcast(room_id, message, exclude=sender_ws)

        elif msg_type == "CHAT":
            await self.broadcast(room_id, {
                "type": "CHAT",
                "username": message.get("username", "Viewer"),
                "text": message.get("text", "")
            })

    async def broadcast(self, room_id: str, message: dict, exclude: WebSocket = None):
        if room_id not in self.rooms:
            return
        dead = set()
        for ws in list(self.rooms[room_id]):
            if ws == exclude:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        for d in dead:
            self.rooms[room_id].discard(d)

syncplay_manager = SyncPlayManager()

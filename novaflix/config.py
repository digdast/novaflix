"""
NovaFlix - Global Configuration & Engine Defaults
The Sovereign, Next-Gen Open Media Platform
"""

import os
from pathlib import Path
from typing import List, Dict, Any

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR = DATA_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
TRANSCODE_DIR = DATA_DIR / "transcodes"
TRANSCODE_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "novaflix.db"

# Server Ports
SERVER_HOST = os.getenv("NOVAFLIX_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("NOVAFLIX_PORT", 8096))       # Main Media Server & Cinema UI
PORTAL_PORT = int(os.getenv("NOVAFLIX_PORTAL_PORT", 8097)) # Public Download & Showcase Portal

# Remote Access & Relay
REMOTE_ACCESS_ENABLED = os.getenv("NOVAFLIX_REMOTE_ENABLED", "true").lower() == "true"
PUBLIC_HOSTNAME = os.getenv("NOVAFLIX_PUBLIC_HOST", "")
UPNP_ENABLED = os.getenv("NOVAFLIX_UPNP", "true").lower() == "true"
JWT_SECRET = os.getenv("NOVAFLIX_JWT_SECRET", "novaflix-sovereign-master-secret-key-998877")

# Streaming Settings
TRANSCODING_HARDWARE = os.getenv("NOVAFLIX_HW_ACCEL", "auto") # auto, nvenc, qsv, vaapi, none
CHUNK_SIZE = 1024 * 1024 # 1MB streaming chunk for Range requests
SUPPORTED_VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".ts", ".m4v"}
SUPPORTED_AUDIO_EXTS = {".mp3", ".flac", ".m4a", ".aac", ".ogg", ".wav"}
SUPPORTED_SUBTITLE_EXTS = {".vtt", ".srt", ".ass"}

# Media Library Default Types
LIBRARY_TYPES = ["movies", "tvshows", "music", "homevideos"]

# Default Demo Media Items (Pre-seeded so the user can test stream immediately out of the box!)
DEMO_MOVIES = [
    {
        "title": "Cosmos: The Infinite Horizon",
        "type": "movie",
        "year": 2026,
        "rating": 9.4,
        "duration": "1h 48m",
        "genre": "Sci-Fi, Documentary",
        "director": "Elena Vance",
        "cast": "Neil deGrasse Tyson, Brian Cox, Kip Thorne",
        "synopsis": "An awe-inspiring voyage across quantum singularities, black holes, and deep-space nebulae, uncovering the origin of our cosmos.",
        "poster": "https://images.unsplash.com/photo-1506703719100-a0f3a48c0f86?w=600&auto=format&fit=crop&q=80",
        "backdrop": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1600&auto=format&fit=crop&q=80",
        "stream_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
        "resolution": "4K UHD",
        "audio_codec": "Dolby Atmos 7.1",
        "content_rating": "PG"
    },
    {
        "title": "Cyberpunk: Neon Syndicate",
        "type": "movie",
        "year": 2025,
        "rating": 8.9,
        "duration": "2h 15m",
        "genre": "Action, Cyberpunk, Thriller",
        "director": "Marcus Chen",
        "cast": "Alexander Hayes, Naomi Tanaka, Carlos Mendoza",
        "synopsis": "In the rain-drenched megacity of Neo-Yokohama, a rogue synthetic intelligence operative battles corporate oligarchs to liberate biometric networks.",
        "poster": "https://images.unsplash.com/photo-1542751371-adc38448a05e?w=600&auto=format&fit=crop&q=80",
        "backdrop": "https://images.unsplash.com/photo-1508739773434-c26b3d09e071?w=1600&auto=format&fit=crop&q=80",
        "stream_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4",
        "resolution": "1080p HDR",
        "audio_codec": "DTS-HD MA 5.1",
        "content_rating": "PG-13"
    },
    {
        "title": "Wild Serengeti: Apex Predators",
        "type": "movie",
        "year": 2024,
        "rating": 9.1,
        "duration": "1h 32m",
        "genre": "Nature, Wildlife",
        "director": "David Attenborough",
        "cast": "David Attenborough",
        "synopsis": "Witness the raw power, resilience, and breathtaking beauty of Africa's great migration and apex predators in native high-dynamic-range cinematography.",
        "poster": "https://images.unsplash.com/photo-1534188753412-3e26d0d618d6?w=600&auto=format&fit=crop&q=80",
        "backdrop": "https://images.unsplash.com/photo-1516426122078-c23e76319801?w=1600&auto=format&fit=crop&q=80",
        "stream_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
        "resolution": "4K HDR",
        "audio_codec": "Dolby Digital Plus",
        "content_rating": "G"
    },
    {
        "title": "Quantum Odyssey",
        "type": "movie",
        "year": 2025,
        "rating": 8.7,
        "duration": "2h 04m",
        "genre": "Sci-Fi, Adventure",
        "director": "Sarah Sterling",
        "cast": "Julian Thorne, Maya Lin, Edward Ward",
        "synopsis": "When an experiment in particle entanglement folds subspace, a team of quantum physicists must journey into parallel dimensions to prevent reality collapse.",
        "poster": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=600&auto=format&fit=crop&q=80",
        "backdrop": "https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?w=1600&auto=format&fit=crop&q=80",
        "stream_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4",
        "resolution": "4K UHD",
        "audio_codec": "Dolby Atmos",
        "content_rating": "PG-13"
    }
]

DEMO_SHOWS = [
    {
        "title": "Silicon Void",
        "type": "show",
        "year": 2025,
        "rating": 9.2,
        "seasons_count": 2,
        "episodes_count": 16,
        "genre": "Tech Thriller, Drama",
        "synopsis": "Inside an elite quantum computing lab, engineers uncover an autonomous program rewriting cryptographic infrastructure worldwide.",
        "poster": "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=600&auto=format&fit=crop&q=80",
        "backdrop": "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=1600&auto=format&fit=crop&q=80",
        "episodes": [
            {"season": 1, "episode": 1, "title": "Zero State", "duration": "52m", "stream_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/SubaruOutbackSeeTheWorld.mp4"},
            {"season": 1, "episode": 2, "title": "Entanglement", "duration": "48m", "stream_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/WeAreGoingOnBullrun.mp4"},
            {"season": 1, "episode": 3, "title": "Qubit Collapse", "duration": "55m", "stream_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/WhatCarCanYouGetForAGrand.mp4"}
        ]
    },
    {
        "title": "Chronicles of Olympus",
        "type": "show",
        "year": 2024,
        "rating": 8.8,
        "seasons_count": 3,
        "episodes_count": 24,
        "genre": "Fantasy, Mythology, Epic",
        "synopsis": "Ancient myth collides with modern geopolitics as the pantheon reawakens across the Mediterranean.",
        "poster": "https://images.unsplash.com/photo-1579783900882-c0d3dad7b119?w=600&auto=format&fit=crop&q=80",
        "backdrop": "https://images.unsplash.com/photo-1564507592333-c60657eea523?w=1600&auto=format&fit=crop&q=80",
        "episodes": [
            {"season": 1, "episode": 1, "title": "The Spark of Aether", "duration": "58m", "stream_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4"},
            {"season": 1, "episode": 2, "title": "The Golden Fleece", "duration": "51m", "stream_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4"}
        ]
    }
]

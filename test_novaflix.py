"""
NovaFlix - Integration Test Suite & Verification Script
Verifies database seeding, media catalog, watch progress, auth, and remote access.
"""

import sys
import asyncio
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from novaflix.database import Database
from novaflix.auth import hash_password, verify_password, create_session_token, verify_session_token
from novaflix.remote import RemoteAccessService
from novaflix.streaming import parse_range_header

async def run_tests():
    print("=" * 60)
    print("🎬 NovaFlix Test Suite Starting...")
    print("=" * 60)

    # 1. Test Database Seeding & Queries
    print("\n[1/5] Testing SQLite Database Initialization & Seeding...")
    db = Database()
    featured = db.get_featured_media()
    assert featured is not None, "Expected featured media item"
    print(f"  ✓ Database initialized. Featured movie: '{featured['title']}' (★ {featured['rating']})")

    movies = db.get_movies(limit=10)
    assert len(movies) >= 4, f"Expected at least 4 movies, got {len(movies)}"
    print(f"  ✓ Loaded {len(movies)} catalog movies: {[m['title'] for m in movies[:2]]}...")

    shows = db.get_shows(limit=10)
    assert len(shows) >= 2, f"Expected at least 2 shows, got {len(shows)}"
    print(f"  ✓ Loaded {len(shows)} TV shows: {[s['title'] for s in shows]}...")

    # 2. Test Continue Watching Progress
    print("\n[2/5] Testing Watch Progress Resumption...")
    movie_id = movies[0]["id"]
    db.update_progress(user_id=1, media_id=movie_id, position_seconds=1240.0, duration_seconds=6600.0)
    continue_items = db.get_continue_watching(user_id=1)
    assert len(continue_items) >= 1, "Expected item in continue watching"
    print(f"  ✓ Continue watching verified: '{continue_items[0]['title']}' at {continue_items[0]['position_seconds']}s")

    # 3. Test Authentication & Session Tokens
    print("\n[3/5] Testing Profile Authentication & Signed Tokens...")
    pw_hash = hash_password("secretPass123")
    assert verify_password("secretPass123", pw_hash)
    assert not verify_password("wrongPass", pw_hash)
    print("  ✓ Bcrypt password hashing & validation verified.")

    token = create_session_token(1, "Admin", True)
    payload = verify_session_token(token)
    assert payload is not None and payload["username"] == "Admin"
    print(f"  ✓ Signed session token generated and validated for: {payload['username']}")

    # 4. Test HTTP 206 Range Request Parser
    print("\n[4/5] Testing HTTP 206 Byte Range Parser...")
    start, end = parse_range_header("bytes=0-1048575", 5000000)
    assert start == 0 and end == 1048575
    start, end = parse_range_header("bytes=1048576-", 5000000)
    assert start == 1048576 and end == 4999999
    print(f"  ✓ HTTP Range parser verified (start={start}, end={end}).")

    # 5. Test Remote Access Service
    print("\n[5/5] Testing Remote Access Network Discovery...")
    remote = RemoteAccessService()
    info = await remote.get_connection_info()
    assert "public_ip" in info and "local_url" in info
    print(f"  ✓ Remote Access verified: LAN={info['lan_ip']}, WAN={info['public_ip']}, Port={info['port']}")

    print("\n" + "=" * 60)
    print("🎉 All NovaFlix Integration Tests Passed Successfully!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_tests())

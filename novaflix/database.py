"""
NovaFlix - High-Performance SQLite WAL Storage & Metadata Engine
Provides async-safe storage for libraries, media items, multi-user profiles,
playback progress resumption, watchlists, and remote access tokens.
"""

import sqlite3
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pathlib import Path
import bcrypt

from novaflix.config import DB_PATH, DEMO_MOVIES, DEMO_SHOWS

class Database:
    def __init__(self, db_path: str = str(DB_PATH)):
        self.db_path = db_path
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def init_db(self):
        """Create database tables and default seed data."""
        with self.get_connection() as conn:
            # Libraries Table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS libraries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT NOT NULL, -- 'movies', 'tvshows', 'music', 'homevideos'
                path TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            # Media Items Table (Movies, TV Series, Seasons, Episodes)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS media_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                library_id INTEGER,
                title TEXT NOT NULL,
                original_title TEXT,
                type TEXT NOT NULL, -- 'movie', 'show', 'season', 'episode', 'music_track'
                parent_id INTEGER,  -- For episode -> show
                season_number INTEGER DEFAULT 0,
                episode_number INTEGER DEFAULT 0,
                year INTEGER,
                rating REAL DEFAULT 0.0,
                duration TEXT,
                duration_seconds INTEGER DEFAULT 0,
                genre TEXT,
                director TEXT,
                cast TEXT,
                synopsis TEXT,
                poster TEXT,
                backdrop TEXT,
                file_path TEXT,
                stream_url TEXT,
                resolution TEXT DEFAULT '1080p',
                audio_codec TEXT DEFAULT 'AAC 5.1',
                video_codec TEXT DEFAULT 'H.264',
                content_rating TEXT DEFAULT 'PG-13',
                added_at TEXT NOT NULL
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_media_type ON media_items(type);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_media_parent ON media_items(parent_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_media_title ON media_items(title);")

            # Users & Profiles Table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                pin TEXT, -- 4-digit PIN for profile lock
                avatar_color TEXT DEFAULT '#8b5cf6',
                max_age_rating TEXT DEFAULT 'ALL', -- 'G', 'PG', 'PG-13', 'R', 'ALL'
                created_at TEXT NOT NULL
            );
            """)

            # Playback Progress Table (Continue Watching)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS watch_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                media_id INTEGER NOT NULL,
                position_seconds REAL NOT NULL,
                duration_seconds REAL NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                last_watched TEXT NOT NULL,
                UNIQUE(user_id, media_id)
            );
            """)

            # User Watchlist / Favorites Table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                media_id INTEGER NOT NULL,
                added_at TEXT NOT NULL,
                UNIQUE(user_id, media_id)
            );
            """)

            # Key-Value Settings Table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS server_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """)

            # Seed Default Admin & Guest Profiles if table is empty
            cursor = conn.execute("SELECT COUNT(*) FROM users")
            if cursor.fetchone()[0] == 0:
                now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                admin_pw_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode("utf-8")
                guest_pw_hash = bcrypt.hashpw(b"guest123", bcrypt.gensalt()).decode("utf-8")
                
                # Admin Profile
                conn.execute("""
                INSERT INTO users (username, password_hash, is_admin, pin, avatar_color, max_age_rating, created_at)
                VALUES ('Admin', ?, 1, '', '#06b6d4', 'ALL', ?)
                """, (admin_pw_hash, now_str))

                # Family / Kids Profile
                conn.execute("""
                INSERT INTO users (username, password_hash, is_admin, pin, avatar_color, max_age_rating, created_at)
                VALUES ('Family', ?, 0, '', '#10b981', 'PG', ?)
                """, (guest_pw_hash, now_str))

            # Seed Default Libraries if empty
            cursor = conn.execute("SELECT COUNT(*) FROM libraries")
            if cursor.fetchone()[0] == 0:
                now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                conn.execute("INSERT INTO libraries (name, type, path, created_at) VALUES ('Movies', 'movies', 'C:/Media/Movies', ?)", (now_str,))
                conn.execute("INSERT INTO libraries (name, type, path, created_at) VALUES ('TV Shows', 'tvshows', 'C:/Media/TV', ?)", (now_str,))

            # Seed Curated Demo Media if empty
            cursor = conn.execute("SELECT COUNT(*) FROM media_items")
            if cursor.fetchone()[0] == 0:
                now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                for m in DEMO_MOVIES:
                    conn.execute("""
                    INSERT INTO media_items (
                        library_id, title, type, year, rating, duration, duration_seconds,
                        genre, director, cast, synopsis, poster, backdrop, stream_url,
                        resolution, audio_codec, content_rating, added_at
                    ) VALUES (1, ?, 'movie', ?, ?, ?, 6600, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        m["title"], m["year"], m["rating"], m["duration"],
                        m["genre"], m["director"], m["cast"], m["synopsis"],
                        m["poster"], m["backdrop"], m["stream_url"],
                        m["resolution"], m["audio_codec"], m["content_rating"], now_str
                    ))

                for s in DEMO_SHOWS:
                    cursor = conn.execute("""
                    INSERT INTO media_items (
                        library_id, title, type, year, rating, duration,
                        genre, synopsis, poster, backdrop, content_rating, added_at
                    ) VALUES (2, ?, 'show', ?, ?, '2 Seasons', ?, ?, ?, ?, 'TV-MA', ?)
                    """, (
                        s["title"], s["year"], s["rating"], s["genre"],
                        s["synopsis"], s["poster"], s["backdrop"], now_str
                    ))
                    show_id = cursor.lastrowid
                    for ep in s.get("episodes", []):
                        conn.execute("""
                        INSERT INTO media_items (
                            library_id, title, type, parent_id, season_number, episode_number,
                            year, rating, duration, synopsis, poster, backdrop, stream_url,
                            resolution, audio_codec, content_rating, added_at
                        ) VALUES (2, ?, 'episode', ?, ?, ?, ?, 8.5, ?, 'Episode synopsis.', ?, ?, ?, '1080p', 'AAC', 'TV-MA', ?)
                        """, (
                            ep["title"], show_id, ep["season"], ep["episode"],
                            s["year"], ep["duration"], s["poster"], s["backdrop"],
                            ep["stream_url"], now_str
                        ))

            conn.commit()

    # ------------------ Media Query Methods ------------------

    def get_featured_media(self) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("""
            SELECT * FROM media_items WHERE type = 'movie' ORDER BY rating DESC LIMIT 1
            """).fetchone()
            return dict(row) if row else None

    def get_movies(self, limit: int = 50, offset: int = 0, search: Optional[str] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM media_items WHERE type = 'movie'"
        params = []
        if search:
            query += " AND (title LIKE ? OR genre LIKE ? OR director LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
        query += " ORDER BY year DESC, rating DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_shows(self, limit: int = 50, offset: int = 0, search: Optional[str] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM media_items WHERE type = 'show'"
        params = []
        if search:
            query += " AND (title LIKE ? OR genre LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        query += " ORDER BY year DESC, rating DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_item_by_id(self, item_id: int) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM media_items WHERE id = ?", (item_id,)).fetchone()
            if not row:
                return None
            data = dict(row)
            if data["type"] == "show":
                # Attach episodes
                ep_rows = conn.execute("""
                SELECT * FROM media_items WHERE type = 'episode' AND parent_id = ?
                ORDER BY season_number ASC, episode_number ASC
                """, (item_id,)).fetchall()
                data["episodes"] = [dict(ep) for ep in ep_rows]
            return data

    def add_media_item(self, item_data: Dict[str, Any]) -> int:
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        with self.get_connection() as conn:
            cursor = conn.execute("""
            INSERT INTO media_items (
                library_id, title, original_title, type, parent_id, season_number, episode_number,
                year, rating, duration, duration_seconds, genre, director, cast, synopsis,
                poster, backdrop, file_path, stream_url, resolution, audio_codec, video_codec,
                content_rating, added_at
            ) VALUES (
                :library_id, :title, :original_title, :type, :parent_id, :season_number, :episode_number,
                :year, :rating, :duration, :duration_seconds, :genre, :director, :cast, :synopsis,
                :poster, :backdrop, :file_path, :stream_url, :resolution, :audio_codec, :video_codec,
                :content_rating, :added_at
            )
            """, {**item_data, "added_at": now_str})
            conn.commit()
            return cursor.lastrowid

    # ------------------ Continue Watching & Progress ------------------

    def update_progress(self, user_id: int, media_id: int, position_seconds: float, duration_seconds: float):
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        completed = 1 if (position_seconds / max(1, duration_seconds)) > 0.90 else 0
        with self.get_connection() as conn:
            conn.execute("""
            INSERT OR REPLACE INTO watch_progress (user_id, media_id, position_seconds, duration_seconds, completed, last_watched)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, media_id, position_seconds, duration_seconds, completed, now_str))
            conn.commit()

    def get_continue_watching(self, user_id: int) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("""
            SELECT m.*, p.position_seconds, p.duration_seconds as total_seconds, p.last_watched
            FROM watch_progress p
            JOIN media_items m ON p.media_id = m.id
            WHERE p.user_id = ? AND p.completed = 0 AND p.position_seconds > 10
            ORDER BY p.last_watched DESC
            LIMIT 10
            """, (user_id,)).fetchall()
            return [dict(r) for r in rows]

    # ------------------ Watchlist ------------------

    def toggle_watchlist(self, user_id: int, media_id: int) -> bool:
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT id FROM watchlist WHERE user_id = ? AND media_id = ?", (user_id, media_id))
            row = cursor.fetchone()
            if row:
                conn.execute("DELETE FROM watchlist WHERE id = ?", (row["id"],))
                conn.commit()
                return False
            else:
                conn.execute("INSERT INTO watchlist (user_id, media_id, added_at) VALUES (?, ?, ?)", (user_id, media_id, now_str))
                conn.commit()
                return True

    def get_watchlist(self, user_id: int) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("""
            SELECT m.* FROM watchlist w
            JOIN media_items m ON w.media_id = m.id
            WHERE w.user_id = ?
            ORDER BY w.added_at DESC
            """, (user_id,)).fetchall()
            return [dict(r) for r in rows]

    # ------------------ Users ------------------

    def get_users(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT id, username, is_admin, avatar_color, max_age_rating, created_at FROM users").fetchall()
            return [dict(r) for r in rows]

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            return dict(row) if row else None

    def create_user(self, username: str, password_raw: str, is_admin: bool = False, max_age_rating: str = "ALL") -> int:
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        pw_hash = bcrypt.hashpw(password_raw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        colors = ["#06b6d4", "#8b5cf6", "#10b981", "#f59e0b", "#ec4899", "#3b82f6"]
        import random
        color = random.choice(colors)

        with self.get_connection() as conn:
            cursor = conn.execute("""
            INSERT INTO users (username, password_hash, is_admin, avatar_color, max_age_rating, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (username, pw_hash, 1 if is_admin else 0, color, max_age_rating, now_str))
            conn.commit()
            return cursor.lastrowid

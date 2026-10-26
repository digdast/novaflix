"""
NovaFlix - High-Performance Media Scanner & Metadata Harvester
Discovers movies and TV shows from disk, parses naming conventions,
extracts technical video/audio streams via ffprobe, and registers items into the database.
"""

import os
import re
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

from novaflix.config import SUPPORTED_VIDEO_EXTS
from novaflix.database import Database

logger = logging.getLogger("novaflix.scanner")

# Sample file minimum size (40 MB)
MIN_VIDEO_BYTES = 40 * 1024 * 1024

def format_duration(seconds: float) -> str:
    """Format seconds into '2h 15m' or '45m'."""
    s = int(seconds)
    hours = s // 3600
    minutes = (s % 3600) // 60
    if hours > 0:
        return f"{hours}h {minutes:02d}m"
    return f"{max(1, minutes)}m"

def probe_file(file_path: Path) -> Dict[str, Any]:
    """
    Run ffprobe to extract stream details (resolution, codecs, duration).
    Falls back gracefully if ffprobe is unavailable or times out.
    """
    metadata = {
        "duration": "1h 45m",
        "duration_seconds": 6300,
        "resolution": "1080p FHD",
        "video_codec": "H.264",
        "audio_codec": "AAC 5.1"
    }

    # Fast heuristic from filename tags
    fname_lower = file_path.name.lower()
    if "2160p" in fname_lower or "4k" in fname_lower or "uhd" in fname_lower:
        metadata["resolution"] = "4K UHD"
    elif "720p" in fname_lower or "hd" in fname_lower:
        metadata["resolution"] = "720p HD"
    elif "480p" in fname_lower or "sd" in fname_lower:
        metadata["resolution"] = "SD"

    if "x265" in fname_lower or "hevc" in fname_lower or "h265" in fname_lower:
        metadata["video_codec"] = "HEVC / H.265"
    elif "av1" in fname_lower:
        metadata["video_codec"] = "AV1"

    if "atmos" in fname_lower:
        metadata["audio_codec"] = "Dolby Atmos"
    elif "dts" in fname_lower:
        metadata["audio_codec"] = "DTS-HD"
    elif "ddp" in fname_lower or "eac3" in fname_lower:
        metadata["audio_codec"] = "Dolby Digital Plus"
    elif "ac3" in fname_lower:
        metadata["audio_codec"] = "Dolby Digital 5.1"

    # Attempt real ffprobe
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "stream=width,height,codec_name,channels",
            "-show_entries", "format=duration",
            "-of", "json",
            str(file_path)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=2.5)
        if res.returncode == 0 and res.stdout:
            data = json.loads(res.stdout)
            format_info = data.get("format", {})
            if "duration" in format_info:
                try:
                    dur_sec = float(format_info["duration"])
                    if dur_sec > 10:
                        metadata["duration_seconds"] = int(dur_sec)
                        metadata["duration"] = format_duration(dur_sec)
                except Exception:
                    pass

            streams = data.get("streams", [])
            for s in streams:
                codec = s.get("codec_name", "")
                w = s.get("width")
                if w:
                    if w >= 3800:
                        metadata["resolution"] = "4K UHD"
                    elif w >= 1900:
                        metadata["resolution"] = "1080p FHD"
                    elif w >= 1200:
                        metadata["resolution"] = "720p HD"
                    else:
                        metadata["resolution"] = "SD"

                    if codec == "hevc":
                        metadata["video_codec"] = "HEVC / H.265"
                    elif codec in ("h264", "avc1"):
                        metadata["video_codec"] = "H.264"
                    elif codec:
                        metadata["video_codec"] = codec.upper()
                elif "channels" in s or not w:
                    if codec in ("ac3", "eac3"):
                        metadata["audio_codec"] = "Dolby Digital 5.1"
                    elif "dts" in codec:
                        metadata["audio_codec"] = "DTS-HD"
                    elif codec:
                        metadata["audio_codec"] = f"{codec.upper()} Stereo"
    except Exception as e:
        logger.debug(f"ffprobe probe skipped for {file_path.name}: {e}")

    return metadata

def parse_movie_name(folder_name: str, file_name: str) -> Tuple[str, Optional[int]]:
    """
    Extract movie title and year from folder or file name.
    e.g. '12 Strong (2018)' -> ('12 Strong', 2018)
    e.g. 'Moana.2026.1080p.mkv' -> ('Moana', 2026)
    """
    target = folder_name if folder_name and folder_name != "." else Path(file_name).stem

    # Pattern: Title (Year) or Title [Year]
    m = re.search(r"^(.+?)[\s\.\-_]*[\(\[](\d{4})[\)\]]", target)
    if m:
        title = m.group(1).replace(".", " ").replace("_", " ").strip()
        year = int(m.group(2))
        return title, year

    # Pattern: Title.Year.Quality
    m2 = re.search(r"^(.+?)[\.\s_](\d{4})[\.\s_]", target)
    if m2:
        title = m2.group(1).replace(".", " ").replace("_", " ").strip()
        year = int(m2.group(2))
        return title, year

    # Fallback: clean title without year
    clean = Path(target).stem
    # strip trailing quality tags like 1080p, Bluray, etc.
    clean = re.sub(r"[\.\s_](1080p|720p|2160p|4k|bluray|web-dl|x264|x265|hevc|aac).*$", "", clean, flags=re.IGNORECASE)
    clean = clean.replace(".", " ").replace("_", " ").strip()
    return clean or target, None

def parse_tv_episode(file_name: str) -> Tuple[int, int, str]:
    """
    Extract season, episode number, and optional title from episode filename.
    e.g. 'Show - S01E02 - Red Coast.mkv' -> (1, 2, 'Red Coast')
    e.g. 'Show.1x03.Countdown.mkv' -> (1, 3, 'Countdown')
    """
    stem = Path(file_name).stem

    # S01E02 pattern
    m = re.search(r"[Ss](\d{1,2})[Ee](\d{1,2})", stem)
    if m:
        season = int(m.group(1))
        ep = int(m.group(2))
        # Everything after SxxExx
        after = stem[m.end():]
        # Clean after part
        title = re.sub(r"^[\s\.\-_]+", "", after)
        title = re.sub(r"[\.\s_](1080p|720p|2160p|4k|hdtv|bluray|web-dl|x264|x265).*$", "", title, flags=re.IGNORECASE)
        title = title.replace(".", " ").replace("_", " ").strip()
        return season, ep, title or f"Episode {ep}"

    # 1x02 pattern
    m2 = re.search(r"(\d{1,2})x(\d{1,2})", stem)
    if m2:
        season = int(m2.group(1))
        ep = int(m2.group(2))
        after = stem[m2.end():]
        title = re.sub(r"^[\s\.\-_]+", "", after).replace(".", " ").strip()
        return season, ep, title or f"Episode {ep}"

    # Fallback: look for Ep or Episode
    m3 = re.search(r"(?:ep|episode)[\s\.\-_]*(\d{1,2})", stem, re.IGNORECASE)
    if m3:
        ep = int(m3.group(1))
        return 1, ep, f"Episode {ep}"

    return 1, 1, stem

def find_local_artwork(folder: Path) -> Tuple[Optional[str], Optional[str]]:
    """Check folder for poster and backdrop image files."""
    poster = None
    backdrop = None
    if not folder.exists() or not folder.is_dir():
        return None, None

    for f in folder.iterdir():
        if f.is_file():
            name_lower = f.name.lower()
            if name_lower in ("poster.jpg", "poster.png", "folder.jpg", "cover.jpg"):
                poster = str(f)
            elif name_lower in ("backdrop.jpg", "fanart.jpg", "background.jpg", "art.jpg"):
                backdrop = str(f)

    return poster, backdrop

class MediaScanner:
    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()
        self.status = {
            "is_scanning": False,
            "current_path": "",
            "scanned": 0,
            "added": 0,
            "skipped": 0,
            "errors": [],
            "last_scan_time": None
        }

    def scan_path(self, path_str: str, lib_type: str = "movies", library_id: int = 1, max_items: Optional[int] = None) -> Dict[str, Any]:
        """
        Scan a directory path for media and import into the database.
        Supports lib_type = 'movies' or 'tvshows'.
        """
        self.status["is_scanning"] = True
        self.status["current_path"] = path_str
        self.status["scanned"] = 0
        self.status["added"] = 0
        self.status["skipped"] = 0
        self.status["errors"] = []

        target_dir = Path(path_str)
        if not target_dir.exists():
            err_msg = f"Directory not found: {path_str}"
            self.status["errors"].append(err_msg)
            self.status["is_scanning"] = False
            return self.status

        try:
            if lib_type in ("movies", "movie"):
                self._scan_movies(target_dir, library_id, max_items)
            else:
                self._scan_tv_shows(target_dir, library_id, max_items)
        except Exception as e:
            logger.exception(f"Error during scan of {path_str}: {e}")
            self.status["errors"].append(str(e))
        finally:
            self.status["is_scanning"] = False
            self.status["last_scan_time"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        return dict(self.status)

    def _scan_movies(self, target_dir: Path, library_id: int, max_items: Optional[int]):
        """Scan directory for movie files."""
        # Walk entries in target_dir
        for root, dirs, files in os.walk(target_dir):
            root_path = Path(root)
            # Find candidate video files
            video_files = [f for f in files if Path(f).suffix.lower() in SUPPORTED_VIDEO_EXTS]
            if not video_files:
                continue

            # Pick largest video file in this directory to avoid samples/extras
            best_file = None
            max_size = 0
            for vf in video_files:
                vf_path = root_path / vf
                try:
                    size = vf_path.stat().st_size
                    # Filter out tiny sample clips if file size is under 40MB
                    if size > max_size and size >= MIN_VIDEO_BYTES:
                        max_size = size
                        best_file = vf_path
                except Exception:
                    continue

            if not best_file:
                # If no file >= 40MB, try any video file
                if video_files:
                    best_file = root_path / video_files[0]
                else:
                    continue

            self.status["scanned"] += 1

            # Check if file already in database
            existing = self.db.get_media_by_filepath(str(best_file))
            if existing:
                self.status["skipped"] += 1
                continue

            # Parse title and year
            folder_name = root_path.name if root_path != target_dir else ""
            title, year = parse_movie_name(folder_name, best_file.name)

            # Probe media details
            probe_info = probe_file(best_file)

            # Check local artwork
            local_poster, local_backdrop = find_local_artwork(root_path)

            # Generate dynamic poster URL fallback if no local image
            poster_url = local_poster or f"/api/media/poster/generated?title={title}&year={year or 2026}&genre=Cinema"
            backdrop_url = local_backdrop or poster_url

            # Insert into database
            item_data = {
                "library_id": library_id,
                "title": title,
                "original_title": title,
                "type": "movie",
                "parent_id": None,
                "season_number": 0,
                "episode_number": 0,
                "year": year or 2025,
                "rating": 8.5,
                "duration": probe_info["duration"],
                "duration_seconds": probe_info["duration_seconds"],
                "genre": "Action, Drama",
                "director": "NovaFlix Cinema",
                "cast": "High-Definition Master",
                "synopsis": f"Direct stream media file indexed from local storage: {best_file.name}",
                "poster": poster_url,
                "backdrop": backdrop_url,
                "file_path": str(best_file),
                "stream_url": "",
                "resolution": probe_info["resolution"],
                "audio_codec": probe_info["audio_codec"],
                "video_codec": probe_info["video_codec"],
                "content_rating": "PG-13"
            }

            self.db.add_media_item(item_data)
            self.status["added"] += 1

            if max_items and self.status["added"] >= max_items:
                break

    def _scan_tv_shows(self, target_dir: Path, library_id: int, max_items: Optional[int]):
        """Scan directory for TV shows and episodes."""
        for show_dir_entry in target_dir.iterdir():
            if not show_dir_entry.is_dir():
                continue

            show_folder_name = show_dir_entry.name
            show_title, show_year = parse_movie_name(show_folder_name, "")

            # Check or create parent show
            show = self.db.get_show_by_title(show_title)
            show_id = show["id"] if show else None

            local_poster, local_backdrop = find_local_artwork(show_dir_entry)
            poster_url = local_poster or f"/api/media/poster/generated?title={show_title}&year={show_year or 2025}&genre=Series"
            backdrop_url = local_backdrop or poster_url

            if not show_id:
                show_data = {
                    "library_id": library_id,
                    "title": show_title,
                    "original_title": show_title,
                    "type": "show",
                    "parent_id": None,
                    "season_number": 0,
                    "episode_number": 0,
                    "year": show_year or 2025,
                    "rating": 8.8,
                    "duration": "1 Season",
                    "duration_seconds": 0,
                    "genre": "Drama, Series",
                    "director": "Executive Producers",
                    "cast": "Cast Ensemble",
                    "synopsis": f"TV series scanned from local storage: {show_folder_name}",
                    "poster": poster_url,
                    "backdrop": backdrop_url,
                    "file_path": str(show_dir_entry),
                    "stream_url": "",
                    "resolution": "1080p FHD",
                    "audio_codec": "AAC 5.1",
                    "video_codec": "H.264",
                    "content_rating": "TV-MA"
                }
                show_id = self.db.add_media_item(show_data)

            # Discover episodes in show directory or seasons
            episodes_added = 0
            seasons_set = set()

            for root, _, files in os.walk(show_dir_entry):
                root_path = Path(root)
                for f in files:
                    if Path(f).suffix.lower() not in SUPPORTED_VIDEO_EXTS:
                        continue

                    file_path = root_path / f
                    try:
                        if file_path.stat().st_size < MIN_VIDEO_BYTES:
                            continue
                    except Exception:
                        pass

                    self.status["scanned"] += 1

                    existing = self.db.get_media_by_filepath(str(file_path))
                    if existing:
                        self.status["skipped"] += 1
                        continue

                    season_num, ep_num, ep_title = parse_tv_episode(f)
                    seasons_set.add(season_num)

                    probe_info = probe_file(file_path)

                    ep_data = {
                        "library_id": library_id,
                        "title": ep_title,
                        "original_title": ep_title,
                        "type": "episode",
                        "parent_id": show_id,
                        "season_number": season_num,
                        "episode_number": ep_num,
                        "year": show_year or 2025,
                        "rating": 8.5,
                        "duration": probe_info["duration"],
                        "duration_seconds": probe_info["duration_seconds"],
                        "genre": "Drama",
                        "director": "Director",
                        "cast": "Series Cast",
                        "synopsis": f"Season {season_num}, Episode {ep_num} of {show_title}.",
                        "poster": poster_url,
                        "backdrop": backdrop_url,
                        "file_path": str(file_path),
                        "stream_url": "",
                        "resolution": probe_info["resolution"],
                        "audio_codec": probe_info["audio_codec"],
                        "video_codec": probe_info["video_codec"],
                        "content_rating": "TV-MA"
                    }

                    self.db.add_media_item(ep_data)
                    self.status["added"] += 1
                    episodes_added += 1

            if episodes_added > 0:
                # Update seasons count in parent show
                s_count = max(1, len(seasons_set))
                s_str = f"{s_count} Season" if s_count == 1 else f"{s_count} Seasons"
                self.db.update_media_item(show_id, {"duration": s_str})

            if max_items and self.status["added"] >= max_items:
                break

scanner = MediaScanner()

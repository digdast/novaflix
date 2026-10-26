"""
NovaFlix - High-Performance Media Streaming Engine
Provides HTTP 206 Partial Content Range streaming, Direct Play, WebVTT subtitle conversion,
and on-the-fly transcoding pipeline hooks.
"""

import os
import re
import mimetypes
from pathlib import Path
from typing import Generator, Optional, Tuple, Dict, Any
from fastapi import Request, Response, HTTPException
from fastapi.responses import StreamingResponse, RedirectResponse

from novaflix.config import CHUNK_SIZE

def parse_range_header(range_header: str, file_size: int) -> Tuple[int, int]:
    """Parse HTTP Range header: 'bytes=start-end'."""
    match = re.match(r"^bytes=(\d+)-(\d*)$", range_header.strip())
    if not match:
        return 0, file_size - 1

    start_str, end_str = match.groups()
    start = int(start_str) if start_str else 0
    end = int(end_str) if end_str else file_size - 1

    if start >= file_size:
        raise HTTPException(status_code=416, detail="Requested range not satisfiable")

    end = min(end, file_size - 1)
    return start, end

def range_stream_generator(file_path: Path, start: int, end: int, chunk_size: int = CHUNK_SIZE) -> Generator[bytes, None, None]:
    """Yield file byte chunks from start to end without memory overflow."""
    with open(file_path, "rb") as f:
        f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            read_size = min(chunk_size, remaining)
            data = f.read(read_size)
            if not data:
                break
            remaining -= len(data)
            yield data

import subprocess
import shutil

# In-memory cache for media audio codecs to prevent redundant ffprobe calls
_AUDIO_CODEC_CACHE: Dict[str, str] = {}

def get_file_audio_codec(path: Path) -> str:
    """Fast ffprobe check for primary audio track codec."""
    path_str = str(path)
    if path_str in _AUDIO_CODEC_CACHE:
        return _AUDIO_CODEC_CACHE[path_str]
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_name",
            "-of", "csv=p=0",
            path_str
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=1.5)
        raw = res.stdout.strip().lower()
        codec = raw.split(",")[0].strip()
        if codec:
            _AUDIO_CODEC_CACHE[path_str] = codec
            return codec
    except Exception:
        pass
    return ""

def ffmpeg_remux_generator(
    file_path: Path,
    start_time: float = 0,
    transcode_video: bool = False,
    audio_track: int = 0
) -> Generator[bytes, None, None]:
    """
    Yield a browser-compatible fragmented MP4 stream on the fly.
    Uses zero-CPU direct stream copy for video where possible, and universal AAC stereo audio
    with aresample=async=1 to preserve rock-solid audio/video synchronization.
    """
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
    ]
    if start_time > 0:
        cmd.extend(["-ss", str(start_time)])

    video_codec = "libx264" if transcode_video else "copy"
    cmd.extend([
        "-i", str(file_path),
        "-map", "0:v:0",
        "-map", f"0:a:{audio_track}?",
        "-c:v", video_codec,
    ])
    if transcode_video:
        cmd.extend(["-preset", "veryfast", "-crf", "22"])

    cmd.extend([
        "-c:a", "aac",
        "-b:a", "192k",
        "-ac", "2",
        "-af", "aresample=async=1",
        "-f", "mp4",
        "-movflags", "frag_keyframe+empty_moov+default_base_moof",
        "pipe:1"
    ])

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=64 * 1024
    )

    try:
        while True:
            chunk = proc.stdout.read(64 * 1024)
            if not chunk:
                break
            yield chunk
    finally:
        try:
            proc.kill()
            proc.wait(timeout=0.5)
        except Exception:
            pass

class StreamService:
    @staticmethod
    def stream_media(request: Request, media_item: Dict[str, Any]) -> Response:
        """
        Handle Direct Play streaming with HTTP 206 Range support,
        on-the-fly FFmpeg fragmented MP4 remuxing for MKV/EAC3/non-web media,
        or remote URL proxy / redirect.
        """
        file_path_str = media_item.get("file_path")
        stream_url = media_item.get("stream_url")

        # Case 1: Remote stream URL
        if not file_path_str and stream_url:
            return RedirectResponse(url=stream_url, status_code=307)

        # Case 2: Local file on disk
        if not file_path_str:
            raise HTTPException(status_code=404, detail="Media file path not specified")

        path = Path(file_path_str)
        if not path.exists():
            if stream_url:
                return RedirectResponse(url=stream_url, status_code=307)
            raise HTTPException(status_code=404, detail=f"File not found on disk: {file_path_str}")

        file_size = path.stat().st_size
        suffix = path.suffix.lower()

        # Check if FFmpeg is available and file needs on-the-fly remuxing
        has_ffmpeg = bool(shutil.which("ffmpeg"))
        is_non_mp4 = suffix in [".mkv", ".avi", ".ts", ".m2ts", ".vob", ".flv", ".wmv", ".webm", ".mov", ".iso"]
        force_remux = request.query_params.get("remux") == "1"
        transcode_video = request.query_params.get("transcode") == "1"

        start_time_param = request.query_params.get("start") or request.query_params.get("t")
        start_time = 0.0
        if start_time_param:
            try:
                start_time = float(start_time_param)
            except ValueError:
                start_time = 0.0

        audio_track_param = request.query_params.get("audio", "0")
        try:
            audio_track = int(audio_track_param)
        except ValueError:
            audio_track = 0

        # Detect audio codec: browsers natively decode ONLY aac, mp3, opus
        browser_native_audio = ("aac", "mp3", "opus")
        actual_codec = get_file_audio_codec(path) if has_ffmpeg else ""
        db_audio = str(media_item.get("audio_codec") or "").upper()
        
        # Flag if codec is known non-web format
        needs_audio_transcode = False
        if actual_codec:
            needs_audio_transcode = actual_codec not in browser_native_audio
        else:
            # Fallback to DB info
            unsupported_markers = ["AC3", "EAC3", "DTS", "TRUEHD", "SUBRIP", "BIN_DATA", "MOV_TEXT", "ASS", "PGS", "5.1", "7.1"]
            needs_audio_transcode = any(m in db_audio for m in unsupported_markers)

        needs_ffmpeg = has_ffmpeg and (is_non_mp4 or force_remux or needs_audio_transcode or transcode_video or start_time > 0)

        if needs_ffmpeg:
            # Stream fragmented MP4 remuxed / transcoded on the fly
            headers = {
                "Content-Type": "video/mp4",
                "Accept-Ranges": "none",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Content-Disposition": f'inline; filename="{path.stem}.mp4"',
            }
            return StreamingResponse(
                ffmpeg_remux_generator(path, start_time=start_time, transcode_video=transcode_video, audio_track=audio_track),
                media_type="video/mp4",
                headers=headers
            )


        # Native Direct Play HTTP 206 for web-compatible MP4 files
        mime_type, _ = mimetypes.guess_type(str(path))
        if not mime_type:
            mime_type = "video/mp4"

        range_header = request.headers.get("range")
        if range_header:
            start, end = parse_range_header(range_header, file_size)
            content_length = end - start + 1
            headers = {
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
                "Content-Type": mime_type,
                "Content-Disposition": f'inline; filename="{path.name}"',
                "Cache-Control": "no-cache",
            }
            return StreamingResponse(
                range_stream_generator(path, start, end),
                status_code=206,
                headers=headers
            )
        else:
            headers = {
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
                "Content-Type": mime_type,
                "Content-Disposition": f'inline; filename="{path.name}"',
            }
            return StreamingResponse(
                range_stream_generator(path, 0, file_size - 1),
                status_code=200,
                headers=headers
            )

    @staticmethod
    def get_subtitles_vtt(media_item: Dict[str, Any]) -> Optional[str]:
        """Find and convert subtitles (.srt to WebVTT format) for HTML5 video element."""
        file_path_str = media_item.get("file_path")
        if not file_path_str:
            return None

        p = Path(file_path_str)
        # Search for .vtt or .srt alongside the video
        candidates = [
            p.with_suffix(".vtt"),
            p.with_suffix(".en.vtt"),
            p.with_suffix(".srt"),
            p.with_suffix(".en.srt"),
        ]
        for c in candidates:
            if c.exists():
                try:
                    with open(c, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    if c.suffix == ".vtt":
                        return content
                    # Simple SRT to WebVTT conversion
                    vtt = "WEBVTT\n\n" + content.replace(",", ".")
                    return vtt
                except Exception:
                    pass
        return None

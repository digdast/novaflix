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

class StreamService:
    @staticmethod
    def stream_media(request: Request, media_item: Dict[str, Any]) -> Response:
        """
        Handle Direct Play streaming with HTTP 206 Range support, or
        remote URL proxy / redirect.
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
            # If local file is missing but demo stream_url exists, fallback to stream_url
            if stream_url:
                return RedirectResponse(url=stream_url, status_code=307)
            raise HTTPException(status_code=404, detail=f"File not found on disk: {file_path_str}")

        file_size = path.stat().st_size
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

"""Shadow-Wirk proxy — routes browser requests through the local backend.

Eliminates direct browser→Tailscale calls that timeout intermittently.
All /shadow/* routes forward to the Shadow-Wirk backend via server-side requests.
"""
from __future__ import annotations

import io
import logging
import os
import subprocess
import tempfile
from typing import Optional

import requests
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import Response
from PIL import Image

try:
    from ..services import shadowwirk as sw_service
    from ..schemas import VideoGenerationRequest
    from ..config import SHADOW_URL
except ImportError:
    from services import shadowwirk as sw_service
    from schemas import VideoGenerationRequest
    from config import SHADOW_URL

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/shadow", tags=["shadow-proxy"])


def _require_online():
    if not sw_service.is_online():
        raise HTTPException(status_code=503, detail="Shadow-Wirk is offline")


# ── Health ───────────────────────────────────────────────────────────

@router.get("/health")
def shadow_health():
    """Proxy health check — returns Shadow-Wirk health + latency."""
    try:
        import time
        t0 = time.monotonic()
        resp = requests.get(f"{SHADOW_URL}/health?skip_shadow=true", timeout=12)
        latency_ms = round((time.monotonic() - t0) * 1000)
        resp.raise_for_status()
        data = resp.json()
        data["latency_ms"] = latency_ms
        return data
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Shadow-Wirk unreachable: {e}")


# ── Video LoRAs ──────────────────────────────────────────────────────

@router.get("/video-loras")
def shadow_video_loras():
    _require_online()
    try:
        resp = requests.get(f"{SHADOW_URL}/video-loras", timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch loras: {e}")


# ── Generate Video ───────────────────────────────────────────────────

@router.post("/generate-video/{persona_id}")
@router.post("/generate-video")
def shadow_generate_video(body: VideoGenerationRequest, persona_id: int = 0):
    _require_online()
    url = f"{SHADOW_URL}/generate-video/{persona_id}" if persona_id else f"{SHADOW_URL}/generate-video"
    try:
        resp = requests.post(url, json=body.model_dump(), timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError:
        detail = "Shadow-Wirk video generation failed"
        try:
            detail = resp.json().get("detail", detail)
        except Exception:
            pass
        raise HTTPException(status_code=resp.status_code, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Shadow-Wirk unreachable: {e}")


# ── Video Status ─────────────────────────────────────────────────────

@router.get("/video-status/{content_id}")
def shadow_video_status(content_id: int):
    try:
        return sw_service.fetch_video_status(content_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to check status: {e}")


# ── Upload Start Image ──────────────────────────────────────────────

@router.post("/upload-video-start-image")
def shadow_upload_start_image(file: UploadFile = File(...)):
    _require_online()
    try:
        resp = requests.post(
            f"{SHADOW_URL}/upload-video-start-image",
            files={"file": (file.filename, file.file, file.content_type or "image/png")},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to upload image: {e}")


# ── Cancel Active Generations ────────────────────────────────────────

@router.post("/generations/cancel-active")
def shadow_cancel_active():
    _require_online()
    try:
        resp = requests.post(f"{SHADOW_URL}/generations/cancel-active", timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to cancel: {e}")


# ── Image/Video Proxy (for previews) ────────────────────────────────

@router.get("/images/{filename:path}")
def shadow_image_proxy(filename: str, subfolder: str = Query("Empire")):
    """Stream image/video bytes from Shadow-Wirk to browser."""
    try:
        resp = requests.get(
            f"{SHADOW_URL}/images/{filename}",
            params={"subfolder": subfolder},
            timeout=120,
            stream=True,
        )
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "application/octet-stream")
        return Response(
            content=resp.content,
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=3600"},
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch image: {e}")


# ── Download Proxy ───────────────────────────────────────────────────

@router.get("/download/{filename:path}")
def shadow_download_proxy(filename: str, subfolder: str = Query("Empire")):
    """Proxy file download from Shadow-Wirk."""
    try:
        resp = requests.get(
            f"{SHADOW_URL}/download/{filename}",
            params={"subfolder": subfolder},
            timeout=120,
            stream=True,
        )
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "application/octet-stream")
        return Response(
            content=resp.content,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "public, max-age=3600",
            },
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to download: {e}")


@router.get("/download-mp4/{filename:path}")
def shadow_download_mp4(filename: str, subfolder: str = Query("Empire")):
    """Download a Shadow-Wirk output as MP4 without interrupting active generations."""
    try:
        resp = requests.get(
            f"{SHADOW_URL}/download/{filename}",
            params={"subfolder": subfolder},
            timeout=180,
        )
        resp.raise_for_status()
        source_bytes = resp.content
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch source file: {e}")

    safe_name = os.path.basename(filename)
    stem, ext = os.path.splitext(safe_name)
    ext = ext.lower()

    if ext == ".mp4":
        return Response(
            content=source_bytes,
            media_type="video/mp4",
            headers={
                "Content-Disposition": f'attachment; filename="{stem}.mp4"',
                "Cache-Control": "public, max-age=3600",
            },
        )

    tmp_mp4 = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp_mp4.close()
    try:
        img = Image.open(io.BytesIO(source_bytes))
        n_frames = getattr(img, "n_frames", 1)
        width, height = img.size
        width = width if width % 2 == 0 else width + 1
        height = height if height % 2 == 0 else height + 1
        duration_ms = img.info.get("duration", 100)
        fps = max(1, round(1000 / duration_ms)) if duration_ms else 16

        proc = subprocess.Popen(
            [
                "ffmpeg",
                "-y",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "-s",
                f"{width}x{height}",
                "-r",
                str(fps),
                "-i",
                "pipe:0",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                tmp_mp4.name,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        for frame_index in range(n_frames):
            img.seek(frame_index)
            frame = img.convert("RGB").resize((width, height))
            if proc.stdin is not None:
                proc.stdin.write(frame.tobytes())

        if proc.stdin is not None:
            proc.stdin.close()
        proc.wait(timeout=90)

        if proc.returncode != 0:
            stderr = proc.stderr.read().decode(errors="replace")[:500] if proc.stderr else ""
            raise HTTPException(status_code=500, detail=f"MP4 conversion failed: {stderr}")

        mp4_bytes = Path(tmp_mp4.name).read_bytes()
        return Response(
            content=mp4_bytes,
            media_type="video/mp4",
            headers={
                "Content-Disposition": f'attachment; filename="{stem}.mp4"',
                "Cache-Control": "public, max-age=3600",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conversion failed: {e}")
    finally:
        try:
            os.unlink(tmp_mp4.name)
        except Exception:
            pass

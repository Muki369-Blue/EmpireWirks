"""Shadow-Wirk proxy — routes browser requests through the local backend.

Eliminates direct browser→Tailscale calls that timeout intermittently.
All /shadow/* routes forward to the Shadow-Wirk backend via server-side requests.
"""
from __future__ import annotations

import logging
from typing import Optional

import requests
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import Response

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

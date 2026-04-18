"""Shadow-Wirk remote PC service.

Centralises all interaction with the Shadow-Wirk (remote GPU PC):
  - health ping loop
  - video sync / download
  - remote job forwarding (future)
"""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Optional

import requests

try:
    from ..config import IS_HUB, SHADOW_URL
except ImportError:
    from config import IS_HUB, SHADOW_URL

logger = logging.getLogger(__name__)

# ── status cache ────────────────────────────────────────────────────

_shadow_status: dict[str, Any] = {"online": False}
_shadow_lock = threading.Lock()


def is_online() -> bool:
    if not IS_HUB:
        return False
    with _shadow_lock:
        return _shadow_status["online"]


def _ping_loop():
    """Background thread: ping Shadow-Wirk every 15 s, cache result."""
    while True:
        try:
            r = requests.get(f"{SHADOW_URL}/health?skip_shadow=true", timeout=12)
            online = r.status_code == 200
        except Exception:
            online = False
        with _shadow_lock:
            _shadow_status["online"] = online
        time.sleep(15)


def start_ping():
    """Start the background ping thread (called once at app startup)."""
    if not IS_HUB:
        logger.info("Shadow-Wirk ping disabled (EMPIRE_ROLE=%s)", "shadow")
        return
    t = threading.Thread(target=_ping_loop, daemon=True, name="shadow-ping")
    t.start()


# ── remote helpers ──────────────────────────────────────────────────

def _get_json(path: str, timeout: int = 15) -> dict[str, Any]:
    resp = requests.get(f"{SHADOW_URL}{path}", timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def fetch_generation_status(remote_content_id: int) -> dict[str, Any]:
    """GET /generations/<id>/status on Shadow-Wirk."""
    return _get_json(f"/generations/{remote_content_id}/status")

def fetch_video_status(remote_content_id: int) -> dict[str, Any]:
    """GET video status on Shadow-Wirk with fallback for flaky /video-status responses."""
    primary_error: Optional[Exception] = None
    try:
        return _get_json(f"/video-status/{remote_content_id}")
    except Exception as exc:
        primary_error = exc
        logger.warning("Shadow-Wirk /video-status/%s failed, falling back to /generations/%s/status: %s", remote_content_id, remote_content_id, exc)

    try:
        status_data = fetch_generation_status(remote_content_id)
        status_data.setdefault("outputs", [])
        status_data.setdefault("progress", 0)
        return status_data
    except Exception:
        if primary_error:
            raise primary_error
        raise


def download_video_bytes(filename: str, subfolder: str = "Empire") -> bytes:
    """Download raw video bytes from Shadow-Wirk's /images proxy."""
    resp = requests.get(
        f"{SHADOW_URL}/images/{filename}",
        params={"subfolder": subfolder},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.content


def fetch_remote_vault() -> list[dict[str, Any]]:
    """GET /vault/ on Shadow-Wirk."""
    resp = requests.get(f"{SHADOW_URL}/vault/", timeout=15)
    if resp.ok:
        return resp.json()
    return []


def fetch_remote_persona(persona_id: int) -> Optional[dict[str, Any]]:
    """GET /personas/<id> on Shadow-Wirk."""
    try:
        resp = requests.get(f"{SHADOW_URL}/personas/{persona_id}", timeout=15)
        if resp.ok:
            return resp.json()
    except Exception:
        pass
    return None


def forward_video_job(payload: dict[str, Any]) -> dict[str, Any]:
    """POST a video generation request to Shadow-Wirk (future use)."""
    resp = requests.post(
        f"{SHADOW_URL}/generate-video",
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()

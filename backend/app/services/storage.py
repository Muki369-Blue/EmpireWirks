from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from backend.app.core.config import settings


def ensure_storage_dir() -> Path:
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    return settings.storage_dir


async def save_audio_bytes(audio_bytes: bytes, extension: str = "mp3") -> str:
    storage_dir = ensure_storage_dir()
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%S%fZ")
    filename = f"audio_{ts}.{extension}"
    path = storage_dir / filename

    def _write() -> None:
        path.write_bytes(audio_bytes)

    await asyncio.to_thread(_write)
    return str(path)

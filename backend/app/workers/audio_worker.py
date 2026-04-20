from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlparse

import httpx

from backend.app.models.events import ElevenLabsEvent
from backend.app.queue.queue import event_queue
from backend.app.services.storage import save_audio_bytes

logger = logging.getLogger(__name__)

_worker_metrics: dict[int, dict[str, object]] = {}


def get_worker_metrics_snapshot() -> dict[int, dict[str, object]]:
    # Return a shallow copy so callers can serialize safely.
    return {wid: dict(stats) for wid, stats in _worker_metrics.items()}


def _guess_extension_from_url(url: str) -> str:
    path = urlparse(url).path
    suffix = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    if suffix in {"mp3", "wav", "ogg", "m4a", "aac", "flac", "webm"}:
        return suffix
    return "mp3"


async def _download_audio(client: httpx.AsyncClient, url: str) -> tuple[bytes, str]:
    resp = await client.get(url)
    resp.raise_for_status()
    audio_bytes = await resp.aread()
    content_type = (resp.headers.get("content-type") or "").lower()

    extension = _guess_extension_from_url(url)
    if "audio/wav" in content_type:
        extension = "wav"
    elif "audio/ogg" in content_type:
        extension = "ogg"
    elif "audio/mp4" in content_type or "audio/m4a" in content_type:
        extension = "m4a"
    elif "audio/flac" in content_type:
        extension = "flac"
    elif "audio/webm" in content_type:
        extension = "webm"
    elif "audio/mpeg" in content_type:
        extension = "mp3"

    return audio_bytes, extension


async def run_audio_worker(worker_id: int) -> None:
    logger.info("audio-worker-%s started", worker_id)
    _worker_metrics[worker_id] = {
        "processed": 0,
        "downloaded": 0,
        "skipped": 0,
        "failed": 0,
        "last_event_type": None,
        "last_saved_path": None,
        "last_error": None,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            payload = await event_queue.get()
            try:
                event = ElevenLabsEvent.model_validate(payload)
                _worker_metrics[worker_id]["processed"] = int(_worker_metrics[worker_id]["processed"]) + 1
                _worker_metrics[worker_id]["last_event_type"] = event.resolved_type()
                audio_url = event.resolved_audio_url()

                if not audio_url:
                    _worker_metrics[worker_id]["skipped"] = int(_worker_metrics[worker_id]["skipped"]) + 1
                    logger.info(
                        "audio-worker-%s skipped event type=%s (no audio_url)",
                        worker_id,
                        event.resolved_type(),
                    )
                    continue

                logger.info("audio-worker-%s downloading audio_url=%s", worker_id, audio_url)
                audio_bytes, extension = await _download_audio(client, audio_url)
                saved_path = await save_audio_bytes(audio_bytes, extension=extension)
                _worker_metrics[worker_id]["downloaded"] = int(_worker_metrics[worker_id]["downloaded"]) + 1
                _worker_metrics[worker_id]["last_saved_path"] = saved_path
                _worker_metrics[worker_id]["last_error"] = None
                logger.info("audio-worker-%s saved audio: %s", worker_id, saved_path)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _worker_metrics[worker_id]["failed"] = int(_worker_metrics[worker_id]["failed"]) + 1
                _worker_metrics[worker_id]["last_error"] = str(exc)
                logger.exception("audio-worker-%s failed processing event: %s", worker_id, exc)
            finally:
                event_queue.task_done()

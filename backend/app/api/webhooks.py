from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.queue.queue import event_queue

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class WebhookAccepted(BaseModel):
    ok: bool
    queued: bool
    queue_size: int


def _extract_signature_candidates(signature_header: str) -> list[str]:
    candidates: list[str] = []
    for raw_part in (signature_header or "").split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "=" in part:
            key, value = part.split("=", 1)
            key = key.strip().lower()
            value = value.strip()
            if key in {"v0", "v1", "signature", "sig"} and value:
                candidates.append(value)
        else:
            candidates.append(part)
    return candidates


def _is_valid_signature(raw_body: bytes, signature_header: str | None) -> bool:
    secret = settings.elevenlabs_webhook_secret
    if not secret or not signature_header:
        return False

    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    for candidate in _extract_signature_candidates(signature_header):
        if hmac.compare_digest(candidate, expected):
            return True
    return False


@router.post("/elevenlabs", response_model=WebhookAccepted)
async def elevenlabs_webhook(
    request: Request,
    x_elevenlabs_signature: str | None = Header(default=None),
    elevenlabs_signature: str | None = Header(default=None, alias="ElevenLabs-Signature"),
):
    if not settings.elevenlabs_webhook_secret:
        raise HTTPException(status_code=503, detail="ELEVENLABS_WEBHOOK_SECRET is not configured")

    raw_body = await request.body()
    signature_header = x_elevenlabs_signature or elevenlabs_signature
    if not _is_valid_signature(raw_body, signature_header):
        raise HTTPException(status_code=401, detail="Invalid ElevenLabs signature")

    try:
        payload: dict[str, Any] = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {exc}")

    try:
        event_queue.put_nowait(payload)
    except Exception:
        raise HTTPException(status_code=503, detail="Event queue is full")

    logger.info("Webhook accepted and queued. queue_size=%s", event_queue.qsize())
    return WebhookAccepted(ok=True, queued=True, queue_size=event_queue.qsize())

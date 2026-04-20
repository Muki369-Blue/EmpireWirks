from __future__ import annotations

import asyncio
from typing import Any

from backend.app.core.config import settings

# Shared bounded queue singleton for webhook ingestion.
event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=settings.queue_maxsize)

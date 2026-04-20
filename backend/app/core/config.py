from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    elevenlabs_webhook_secret: str
    storage_dir: Path
    worker_count: int
    queue_maxsize: int


def load_settings() -> Settings:
    secret = (os.environ.get("ELEVENLABS_WEBHOOK_SECRET") or "").strip()
    storage_raw = (os.environ.get("STORAGE_DIR") or "./storage").strip()
    worker_count = int(os.environ.get("WORKER_COUNT", "4"))
    queue_maxsize = int(os.environ.get("QUEUE_MAXSIZE", "1000"))

    return Settings(
        elevenlabs_webhook_secret=secret,
        storage_dir=Path(storage_raw),
        worker_count=max(1, worker_count),
        queue_maxsize=max(1, queue_maxsize),
    )


settings = load_settings()

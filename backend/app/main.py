from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from backend.app.api.webhooks import router as webhooks_router
from backend.app.core.config import settings
from backend.app.queue.queue import event_queue
from backend.app.services.storage import ensure_storage_dir
from backend.app.workers.audio_worker import get_worker_metrics_snapshot, run_audio_worker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_worker_tasks: list[asyncio.Task] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_storage_dir()
    logger.info("Storage directory ready: %s", settings.storage_dir)

    for idx in range(settings.worker_count):
        task = asyncio.create_task(run_audio_worker(idx + 1), name=f"audio-worker-{idx + 1}")
        _worker_tasks.append(task)

    logger.info("Started %s audio workers", settings.worker_count)

    try:
        yield
    finally:
        for task in _worker_tasks:
            task.cancel()
        await asyncio.gather(*_worker_tasks, return_exceptions=True)
        _worker_tasks.clear()
        logger.info("Audio workers stopped")


app = FastAPI(title="Local Webhook Ingestor", version="1.0.0", lifespan=lifespan)
app.include_router(webhooks_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
async def metrics() -> dict[str, object]:
    task_rows: list[dict[str, object]] = []
    for task in _worker_tasks:
        task_rows.append(
            {
                "name": task.get_name(),
                "done": task.done(),
                "cancelled": task.cancelled(),
            }
        )

    running_workers = sum(1 for t in _worker_tasks if not t.done())

    return {
        "queue": {
            "size": event_queue.qsize(),
            "maxsize": event_queue.maxsize,
        },
        "workers": {
            "configured": settings.worker_count,
            "running": running_workers,
            "tasks": task_rows,
            "stats": get_worker_metrics_snapshot(),
        },
        "storage_dir": str(settings.storage_dir),
    }


@app.get("/metrics/plain", response_class=PlainTextResponse)
async def metrics_plain() -> str:
    worker_stats = get_worker_metrics_snapshot()
    running_workers = sum(1 for t in _worker_tasks if not t.done())

    lines = [
        "# HELP webhook_queue_size Current number of queued webhook events",
        "# TYPE webhook_queue_size gauge",
        f"webhook_queue_size {event_queue.qsize()}",
        "# HELP webhook_queue_maxsize Maximum queue capacity",
        "# TYPE webhook_queue_maxsize gauge",
        f"webhook_queue_maxsize {event_queue.maxsize}",
        "# HELP webhook_workers_configured Configured worker count",
        "# TYPE webhook_workers_configured gauge",
        f"webhook_workers_configured {settings.worker_count}",
        "# HELP webhook_workers_running Workers currently alive",
        "# TYPE webhook_workers_running gauge",
        f"webhook_workers_running {running_workers}",
    ]

    for worker_id in sorted(worker_stats.keys()):
        stats = worker_stats[worker_id]
        lines.extend(
            [
                f"webhook_worker_processed_total{{worker_id=\"{worker_id}\"}} {int(stats.get('processed', 0))}",
                f"webhook_worker_downloaded_total{{worker_id=\"{worker_id}\"}} {int(stats.get('downloaded', 0))}",
                f"webhook_worker_skipped_total{{worker_id=\"{worker_id}\"}} {int(stats.get('skipped', 0))}",
                f"webhook_worker_failed_total{{worker_id=\"{worker_id}\"}} {int(stats.get('failed', 0))}",
            ]
        )

    return "\n".join(lines) + "\n"

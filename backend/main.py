"""AI Content Empire — FastAPI application (thin shell).

All endpoint logic lives in backend/api/*.py router modules.
This file handles only: app creation, middleware, lifespan, and router mounting.
"""
import logging
import os
from contextlib import asynccontextmanager
from typing import List

import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from .database import init_db
    from . import comfy_api
    from .scheduler import start_scheduler, stop_scheduler
    from .services import shadowwirk as sw_service
    from .workers.queue import start_worker, stop_worker
    from .config import IS_HUB, EMPIRE_ROLE
    # ── Webhook ingestor (modular pipeline) ──────────────────────────
    from .app.queue.queue import event_queue as ingestor_queue
    from .app.services.storage import ensure_storage_dir as ingestor_ensure_storage
    from .app.workers.audio_worker import run_audio_worker as ingestor_audio_worker
    from .app.core.config import settings as ingestor_settings
    # ── Routers ──────────────────────────────────────────────────────
    from .api.personas import router as personas_router
    from .api.generation import router as generation_router
    from .api.video import router as video_router
    from .api.vault import router as vault_router
    from .api.analytics import router as analytics_router
    from .api.chat import router as chat_router
    from .api.links import router as links_router
    from .api.schedules import router as schedules_router
    from .api.content import router as content_router
    from .api.system import router as system_router
    from .api.presets import router as presets_router
    from .api.jobs import router as jobs_router
    from .api.campaigns import router as campaigns_router
    from .api.memory import router as memory_router
    from .api.agents import router as agents_router
    from .api.review import router as review_router
    from .api.metrics import router as metrics_router
    from .api.shadow import router as shadow_router
except ImportError:
    from database import init_db
    import comfy_api
    from scheduler import start_scheduler, stop_scheduler
    from services import shadowwirk as sw_service
    from workers.queue import start_worker, stop_worker
    from config import IS_HUB, EMPIRE_ROLE
    from app.queue.queue import event_queue as ingestor_queue
    from app.services.storage import ensure_storage_dir as ingestor_ensure_storage
    from app.workers.audio_worker import run_audio_worker as ingestor_audio_worker
    from app.core.config import settings as ingestor_settings
    from api.personas import router as personas_router
    from api.generation import router as generation_router
    from api.video import router as video_router
    from api.vault import router as vault_router
    from api.analytics import router as analytics_router
    from api.chat import router as chat_router
    from api.links import router as links_router
    from api.schedules import router as schedules_router
    from api.content import router as content_router
    from api.system import router as system_router
    from api.presets import router as presets_router
    from api.jobs import router as jobs_router
    from api.campaigns import router as campaigns_router
    from api.memory import router as memory_router
    from api.agents import router as agents_router
    from api.review import router as review_router
    from api.metrics import router as metrics_router
    from api.shadow import router as shadow_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── CORS origins ─────────────────────────────────────────────────────

DEFAULT_FRONTEND_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
]


def _allowed_frontend_origins() -> List[str]:
    extra = [o.strip() for o in os.environ.get("FRONTEND_ORIGINS", "").split(",") if o.strip()]
    return list(dict.fromkeys(DEFAULT_FRONTEND_ORIGINS + extra))


# ── Lifespan ─────────────────────────────────────────────────────────

_ingestor_tasks: list = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Database tables created / verified.")
    comfy_ok = comfy_api.ensure_comfyui()
    logger.info("ComfyUI status: %s", "ready" if comfy_ok else "NOT available")
    if comfy_ok:
        comfy_api.start_progress_listener()
    sw_service.start_ping()
    start_scheduler()
    start_worker()
    # Start modular webhook audio workers
    ingestor_ensure_storage()
    for idx in range(ingestor_settings.worker_count):
        task = asyncio.create_task(
            ingestor_audio_worker(idx + 1), name=f"ingestor-audio-worker-{idx + 1}"
        )
        _ingestor_tasks.append(task)
    logger.info("Empire started (role=%s, ingestor_workers=%s).", EMPIRE_ROLE, ingestor_settings.worker_count)
    yield
    stop_scheduler()
    stop_worker()
    for task in _ingestor_tasks:
        task.cancel()
    await asyncio.gather(*_ingestor_tasks, return_exceptions=True)
    _ingestor_tasks.clear()
    comfy_api._shutdown_comfyui()


# ── App ──────────────────────────────────────────────────────────────

app = FastAPI(title="AI Content Empire", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_frontend_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount all routers ────────────────────────────────────────────────
app.include_router(system_router)
app.include_router(personas_router)
app.include_router(generation_router)
app.include_router(video_router)
app.include_router(vault_router)
app.include_router(presets_router)
app.include_router(content_router)
app.include_router(analytics_router)
app.include_router(chat_router)
app.include_router(links_router)
app.include_router(schedules_router)
app.include_router(jobs_router)
app.include_router(campaigns_router)
app.include_router(memory_router)
app.include_router(agents_router)
app.include_router(review_router)
app.include_router(metrics_router)
if IS_HUB:
    app.include_router(shadow_router)

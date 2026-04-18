"""Async job queue worker.

Polls for QUEUED generation_jobs and dispatches them. Runs as a
background thread alongside the main FastAPI process.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone

from backend.database import (
    SessionLocal,
    GenerationJob,
    GenerationCostMetrics,
    JobState,
    Content,
    Persona,
    CampaignTask,
)
from backend.services import jobs as jobs_service
from backend.config import MACHINE_LABEL

logger = logging.getLogger(__name__)

_worker_thread = None
_stop_event = threading.Event()
POLL_INTERVAL = 5  # seconds


def _worker_loop():
    logger.info("Job queue worker started")
    while not _stop_event.is_set():
        try:
            db = SessionLocal()
            # Fetch highest-priority QUEUED job
            job = (
                db.query(GenerationJob)
                .filter(GenerationJob.status == JobState.QUEUED.value)
                .order_by(GenerationJob.priority.desc(), GenerationJob.created_at.asc())
                .first()
            )
            if job:
                _process_job(db, job)
            db.close()
        except Exception as e:
            logger.error("Worker loop error: %s", e)
        _stop_event.wait(POLL_INTERVAL)
    logger.info("Job queue worker stopped")


def _process_job(db, job: GenerationJob):
    """Dispatch a single job based on its type."""
    logger.info("Processing job %d (type=%s)", job.id, job.job_type)
    jobs_service.transition(db, job, JobState.DISPATCHING, actor="worker")
    db.commit()

    try:
        if job.job_type == "score":
            _run_scoring_job(db, job)
        elif job.job_type == "caption":
            _run_caption_job(db, job)
        elif job.job_type == "plan":
            _run_plan_job(db, job)
        elif job.job_type in ("image", "video"):
            # Image/video jobs are dispatched directly via ComfyUI in the router;
            # the worker only handles async re-dispatch for retries or campaign tasks
            _run_generation_job(db, job)
        else:
            logger.warning("Unknown job type: %s", job.job_type)
            jobs_service.transition(db, job, JobState.FAILED, error=f"Unknown job type: {job.job_type}", actor="worker")
            db.commit()
    except Exception as e:
        logger.error("Job %d failed: %s", job.id, e)
        jobs_service.transition(db, job, JobState.FAILED, error=str(e), actor="worker")
        db.commit()


def _run_scoring_job(db, job: GenerationJob):
    from backend.workers.scoring import score_content

    content = db.query(Content).filter(Content.id == job.content_id).first()
    if not content:
        jobs_service.transition(db, job, JobState.FAILED, error="Content not found", actor="worker")
        db.commit()
        return

    persona = db.query(Persona).filter(Persona.id == content.persona_id).first() if content.persona_id else None
    jobs_service.transition(db, job, JobState.RUNNING, actor="worker")
    db.commit()

    score = score_content(db, content, persona_description=persona.prompt_base if persona else None)

    jobs_service.transition(db, job, JobState.NEEDS_REVIEW if score.verdict == "needs_review" else JobState.APPROVED, actor="worker")
    db.commit()


def _run_caption_job(db, job: GenerationJob):
    from backend.services import llm as llm_service

    payload = job.payload or {}
    content = db.query(Content).filter(Content.id == job.content_id).first()
    if not content:
        jobs_service.transition(db, job, JobState.FAILED, error="Content not found", actor="worker")
        db.commit()
        return

    persona = db.query(Persona).filter(Persona.id == content.persona_id).first() if content.persona_id else None
    jobs_service.transition(db, job, JobState.RUNNING, actor="worker")
    db.commit()

    result = llm_service.generate_caption(
        content.prompt_used,
        persona_name=persona.name if persona else "Unknown",
        platform=payload.get("platform", "onlyfans"),
    )
    content.caption = result["caption"]
    content.hashtags = result["hashtags"]
    jobs_service.transition(db, job, JobState.APPROVED, actor="worker")
    db.commit()


def _run_plan_job(db, job: GenerationJob):
    """Planner agent job — generates a campaign plan."""
    from backend.services import agents

    jobs_service.transition(db, job, JobState.RUNNING, actor="worker")
    db.commit()

    try:
        agents.run_planner(db, job)
        jobs_service.transition(db, job, JobState.APPROVED, actor="worker")
    except Exception as e:
        jobs_service.transition(db, job, JobState.FAILED, error=str(e), actor="worker")
    db.commit()


def _run_generation_job(db, job: GenerationJob):
    """Dispatch image/video campaign jobs via ComfyUI and poll to completion."""
    import time as _time
    from backend import comfy_api
    from backend.postprocess import process_completed_image
    from backend.services import orchestrator
    from pathlib import Path

    payload = job.payload or {}
    persona = db.query(Persona).filter(Persona.id == job.persona_id).first() if job.persona_id else None

    jobs_service.transition(db, job, JobState.RUNNING, actor="worker")
    db.commit()

    # ── Dispatch ─────────────────────────────────────────────────
    if job.job_type == "video":
        comfy_resp = comfy_api.queue_video(
            positive_prompt=payload.get("prompt", ""),
            start_image=payload.get("start_image"),
            negative_prompt=payload.get("negative_prompt"),
            width=payload.get("width", 832),
            height=payload.get("height", 480),
            length=payload.get("length", 81),
            steps=payload.get("steps", 20),
            cfg=payload.get("cfg", 6.0),
            lora_name=payload.get("lora_name"),
        )
    else:  # image
        ref_comfy_name = None
        if persona and persona.reference_image and Path(persona.reference_image).exists():
            ref_comfy_name = comfy_api.upload_image_to_comfyui(persona.reference_image)
        comfy_resp = comfy_api.queue_prompt(
            positive_prompt=payload.get("prompt", ""),
            lora_name=payload.get("lora") or (persona.lora_name if persona else None),
            reference_image=ref_comfy_name,
            negative_prompt=payload.get("negative_prompt"),
        )

    if "error" in comfy_resp:
        jobs_service.transition(db, job, JobState.FAILED, error=comfy_resp["error"], actor="worker")
        db.commit()
        return

    prompt_id = comfy_resp.get("prompt_id")

    # Create content record if one doesn't already exist
    content = db.query(Content).filter(Content.id == job.content_id).first() if job.content_id else None
    if not content:
        content = Content(
            persona_id=job.persona_id,
            prompt_used=payload.get("prompt", ""),
            comfy_job_id=prompt_id,
            status="generating" if job.job_type == "image" else "processing",
            tags="video" if job.job_type == "video" else None,
        )
        db.add(content)
        db.commit()
        db.refresh(content)
        job.content_id = content.id
    else:
        content.comfy_job_id = prompt_id
        content.status = "generating" if job.job_type == "image" else "processing"
    db.commit()

    jobs_service.record_run(
        db, job,
        prompt=payload.get("prompt"),
        negative_prompt=payload.get("negative_prompt"),
        loras=[{"name": payload.get("lora"), "strength": 1.0}] if payload.get("lora") else None,
        backend="comfy",
        machine=MACHINE_LABEL,
    )
    db.commit()

    # ── Poll for completion (up to 10 min) ───────────────────────
    status_fn = comfy_api.get_video_job_status if job.job_type == "video" else comfy_api.get_job_status
    max_wait = 600
    waited = 0
    result = None
    while waited < max_wait and not _stop_event.is_set():
        _time.sleep(5)
        waited += 5
        result = status_fn(prompt_id)
        if result["status"] in ("completed", "error"):
            break

    if not result or result["status"] == "error":
        content.status = "failed"
        jobs_service.transition(db, job, JobState.FAILED, error=result.get("detail", "ComfyUI error") if result else "timeout", actor="worker")
        db.commit()
    elif result["status"] == "completed" and result.get("outputs"):
        first_output = result["outputs"][0]
        content.file_path = first_output["filename"]
        content.status = "completed"
        db.commit()

        # Post-process: image gets upscale+watermark; video gets vault save
        if job.job_type == "image":
            try:
                process_completed_image(content.id)
            except Exception as e:
                logger.warning("Postprocess failed for content %d: %s", content.id, e)
        else:
            _vault_save_video(content, first_output, db)

        jobs_service.transition(db, job, JobState.POSTPROCESSING, actor="worker")
        jobs_service.transition(db, job, JobState.NEEDS_REVIEW, actor="worker")
        db.commit()

        # Auto-queue a scoring job for the output
        try:
            score_job = jobs_service.create_job(
                db, job_type="score", persona_id=job.persona_id,
                content_id=content.id, actor="worker",
            )
            db.commit()
        except Exception as e:
            logger.warning("Auto-score job creation failed: %s", e)

        # Record generation cost
        try:
            cost = GenerationCostMetrics(
                job_id=job.id,
                machine=MACHINE_LABEL,
                job_type=job.job_type,
                duration_seconds=float(waited),
                estimated_cost_usd=0.0,
                model_used="flux-schnell" if job.job_type == "image" else "wan-2.1",
            )
            db.add(cost)
            db.commit()
        except Exception as e:
            logger.warning("Cost metric recording failed: %s", e)
    else:
        content.status = "failed"
        jobs_service.transition(db, job, JobState.FAILED, error="timed out waiting for ComfyUI", actor="worker")
        db.commit()

    # ── Notify orchestrator if this was a campaign task ──────────
    if job.campaign_task_id:
        try:
            task = db.query(CampaignTask).filter(CampaignTask.id == job.campaign_task_id).first()
            if task and content.status == "completed":
                orchestrator.on_task_completed(db, task)
                db.commit()
        except Exception as e:
            logger.warning("Campaign task notification failed: %s", e)


def _vault_save_video(content, output_info: dict, db):
    """Save a generated video to the vault directory."""
    import requests as _requests
    from backend import comfy_api as _comfy
    vault_dir = Path.home() / "Documents" / "ComfyUI" / "output" / "Empire" / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    try:
        filename = output_info["filename"]
        safe_name = f"vault_{content.id}_{filename}"
        vault_path = vault_dir / safe_name
        if vault_path.exists():
            return
        resp = _requests.get(
            f"{_comfy.COMFY_BASE}/view",
            params={"filename": filename, "subfolder": output_info.get("subfolder", "Empire"), "type": "output"},
            timeout=60,
        )
        resp.raise_for_status()
        vault_path.write_bytes(resp.content)
        content.upscaled_path = f"vault/{safe_name}"
        content.watermarked_path = f"vault/{safe_name}"
        db.commit()
        logger.info("Worker saved video to vault: %s", vault_path)
    except Exception as e:
        logger.warning("Worker vault save failed: %s", e)


def start_worker():
    global _worker_thread
    if _worker_thread is not None and _worker_thread.is_alive():
        return
    _stop_event.clear()
    _worker_thread = threading.Thread(target=_worker_loop, daemon=True, name="empire-job-worker")
    _worker_thread.start()


def stop_worker():
    _stop_event.set()
    if _worker_thread is not None:
        _worker_thread.join(timeout=5)

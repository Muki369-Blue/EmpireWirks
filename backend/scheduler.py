"""
Content calendar scheduler.

Runs as a background thread, checking schedule rules every 30s and
queuing Flux generations when due.
"""

import logging
import threading
import time
from datetime import datetime, timezone, timedelta

from croniter import croniter

logger = logging.getLogger(__name__)

_scheduler_thread = None
_stop_event = threading.Event()


def _next_run(cron_expr: str, base: datetime | None = None) -> datetime:
    """Calculate the next run time from a cron expression."""
    base = base or datetime.now(timezone.utc)
    # croniter needs naive datetimes
    naive = base.replace(tzinfo=None)
    cron = croniter(cron_expr, naive)
    return cron.get_next(datetime).replace(tzinfo=timezone.utc)


def _scheduler_loop():
    """Main scheduler loop — runs in background thread."""
    try:
        from .database import SessionLocal, Schedule, Persona, Content, Campaign, CampaignTask
        from .services import orchestrator
        from . import comfy_api
    except ImportError:
        from database import SessionLocal, Schedule, Persona, Content, Campaign, CampaignTask
        from services import orchestrator
        import comfy_api
        from services import jobs as jobs_service
        from config import MACHINE_LABEL
    else:
        from .services import jobs as jobs_service
        from .config import MACHINE_LABEL

    logger.info("Scheduler started")

    while not _stop_event.is_set():
        try:
            db = SessionLocal()
            now = datetime.now(timezone.utc)

            schedules = db.query(Schedule).filter(Schedule.enabled == True).all()

            for sched in schedules:
                # Initialize next_run if not set
                if sched.next_run is None:
                    sched.next_run = _next_run(sched.cron_expression)
                    db.commit()
                    continue

                # Make comparison tz-aware
                next_dt = sched.next_run
                if next_dt.tzinfo is None:
                    next_dt = next_dt.replace(tzinfo=timezone.utc)

                if now >= next_dt:
                    persona = db.query(Persona).filter(Persona.id == sched.persona_id).first()
                    if not persona:
                        continue

                    full_prompt = f"{persona.prompt_base}, {sched.prompt_template}"
                    logger.info(
                        "Scheduler: generating %d image(s) for %s",
                        sched.batch_size, persona.name,
                    )

                    for _ in range(sched.batch_size):
                        content = Content(
                            persona_id=persona.id,
                            prompt_used=full_prompt,
                            status="queued",
                        )
                        db.add(content)
                        db.flush()
                        jobs_service.create_job(
                            db,
                            job_type="image",
                            persona_id=persona.id,
                            content_id=content.id,
                            payload={
                                "prompt": full_prompt,
                                "lora": persona.lora_name,
                                "model_profile": "flux_schnell",
                            },
                            machine=MACHINE_LABEL,
                        )

                    sched.last_run = now
                    sched.next_run = _next_run(sched.cron_expression, now)
                    db.commit()

            db.close()
        except Exception as e:
            logger.error("Scheduler error: %s", e)

        # ── Campaign advancement ────────────────────────────────────
        try:
            db = SessionLocal()
            active_campaigns = (
                db.query(Campaign).filter(Campaign.status == "active").all()
            )
            for campaign in active_campaigns:
                # Check if all tasks for current day are completed
                day_tasks = (
                    db.query(CampaignTask)
                    .filter(
                        CampaignTask.campaign_id == campaign.id,
                        CampaignTask.day == campaign.current_day,
                    )
                    .all()
                )
                if day_tasks and all(
                    t.status in ("completed", "skipped") for t in day_tasks
                ):
                    orchestrator._advance_day(db, campaign)
                    db.commit()
                    logger.info(
                        "Campaign %s advanced to day %d",
                        campaign.name,
                        campaign.current_day,
                    )
            db.close()
        except Exception as e:
            logger.error("Campaign scheduler error: %s", e)

        _stop_event.wait(30)  # Check every 30 seconds

    logger.info("Scheduler stopped")


def start_scheduler():
    """Start the background scheduler thread."""
    global _scheduler_thread
    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        return

    _stop_event.clear()
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True, name="empire-scheduler")
    _scheduler_thread.start()


def stop_scheduler():
    """Signal the scheduler to stop."""
    _stop_event.set()
    if _scheduler_thread is not None:
        _scheduler_thread.join(timeout=5)

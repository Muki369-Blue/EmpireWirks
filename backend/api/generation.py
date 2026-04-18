"""Generation API — image generation, status, retry, image proxy, downloads."""
from __future__ import annotations

import logging
import mimetypes
import os
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import List, Optional

import requests
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session

try:
    from ..database import get_db, Persona, Content, JobState
    from ..schemas import GenerationRequest, GenerationOut
    from .. import comfy_api
    from ..postprocess import process_completed_image, check_upscale_status
    from ..services import jobs as jobs_service
    from ..config import MACHINE_LABEL, AUTO_UNLOAD_AFTER_T2I
except ImportError:
    from database import get_db, Persona, Content, JobState
    from schemas import GenerationRequest, GenerationOut
    import comfy_api
    from postprocess import process_completed_image, check_upscale_status
    from services import jobs as jobs_service
    from config import MACHINE_LABEL, AUTO_UNLOAD_AFTER_T2I

logger = logging.getLogger(__name__)

router = APIRouter(tags=["generation"])

OLLAMA_CLEANUP_URL = "http://localhost:11434"
OUTPUT_ROOT = Path(__file__).resolve().parent.parent.parent / "outputs"
VAULT_DIR = Path.home() / "Documents" / "ComfyUI" / "output" / "Empire" / "vault"
VAULT_DIR.mkdir(parents=True, exist_ok=True)


def _deferred_memory_cleanup(delay: float = 5.0):
    import time
    time.sleep(delay)
    freed = comfy_api.free_memory(unload_models=True)
    try:
        requests.post(
            f"{OLLAMA_CLEANUP_URL}/api/generate",
            json={"model": "celeste:latest", "prompt": "", "keep_alive": 0},
            timeout=5,
        )
        logging.info("Ollama model unloaded")
    except Exception:
        pass
    if freed:
        stats = comfy_api.get_system_stats()
        if stats and stats.get("devices"):
            dev = stats["devices"][0]
            free_mb = dev.get("vram_free", 0) // 1024 // 1024
            total_mb = dev.get("vram_total", 0) // 1024 // 1024
            logging.info("Memory after cleanup: %dMB free / %dMB total", free_mb, total_mb)


def _save_output_locally(content, output_info: dict, db):
    try:
        persona = db.query(Persona).filter(Persona.id == content.persona_id).first()
        folder_name = persona.name.replace(" ", "_") if persona else "unknown"
        dest_dir = OUTPUT_ROOT / folder_name
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / output_info["filename"]
        if dest_file.exists():
            return
        resp = requests.get(
            f"{comfy_api.COMFY_BASE}/view",
            params={"filename": output_info["filename"], "subfolder": output_info.get("subfolder", "Empire"), "type": "output"},
            timeout=30,
        )
        resp.raise_for_status()
        dest_file.write_bytes(resp.content)
        logger.info("Saved output to %s", dest_file)
    except Exception as e:
        logger.warning("Failed to save output locally: %s", e)


# ── Image Generation ─────────────────────────────────────────────────

@router.post("/generate/{persona_id}", response_model=List[GenerationOut])
def generate_images(persona_id: int, body: GenerationRequest, db: Session = Depends(get_db)):
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    full_prompt = f"{persona.prompt_base}, {body.prompt_extra}"
    lora = body.lora_override or persona.lora_name
    results = []

    ref_comfy_name = None
    if persona.reference_image and Path(persona.reference_image).exists():
        ref_comfy_name = comfy_api.upload_image_to_comfyui(persona.reference_image)

    for _ in range(body.batch_size):
        comfy_resp = comfy_api.queue_prompt(full_prompt, lora, reference_image=ref_comfy_name, negative_prompt=body.negative_prompt)

        if "error" in comfy_resp:
            content = Content(persona_id=persona.id, prompt_used=full_prompt, status="failed")
            db.add(content)
            db.commit()
            db.refresh(content)
            try:
                job = jobs_service.create_job(db, job_type="image", persona_id=persona.id, content_id=content.id, payload={"prompt": full_prompt, "lora": lora, "negative_prompt": body.negative_prompt}, machine=MACHINE_LABEL)
                jobs_service.transition(db, job, JobState.FAILED, error=comfy_resp.get("error"))
                db.commit()
            except Exception as exc:
                logger.warning("job mirror (image failed) skipped: %s", exc)
                db.rollback()
            results.append(content)
            continue

        content = Content(persona_id=persona.id, prompt_used=full_prompt, comfy_job_id=comfy_resp.get("prompt_id"), status="generating")
        db.add(content)
        db.commit()
        db.refresh(content)
        try:
            job = jobs_service.create_job(db, job_type="image", persona_id=persona.id, content_id=content.id, payload={"prompt": full_prompt, "lora": lora, "negative_prompt": body.negative_prompt, "reference_image": ref_comfy_name, "comfy_prompt_id": comfy_resp.get("prompt_id")}, machine=MACHINE_LABEL)
            jobs_service.transition(db, job, JobState.DISPATCHING)
            jobs_service.transition(db, job, JobState.RUNNING)
            jobs_service.record_run(db, job, prompt=full_prompt, negative_prompt=body.negative_prompt, loras=[{"name": lora, "strength": 1.0}] if lora else None, backend="comfy", machine=MACHINE_LABEL)
            db.commit()
        except Exception as exc:
            logger.warning("job mirror (image queue) skipped: %s", exc)
            db.rollback()
        results.append(content)

    return results


@router.get("/generations/", response_model=List[GenerationOut])
def list_generations(db: Session = Depends(get_db)):
    gens = db.query(Content).order_by(Content.id.desc()).limit(50).all()
    any_just_completed = False
    for content in gens:
        if content.status == "generating" and content.comfy_job_id:
            job = comfy_api.get_job_status(content.comfy_job_id)
            if job["status"] == "completed":
                content.status = "completed"
                if job.get("outputs"):
                    content.file_path = job["outputs"][0].get("filename")
                db.commit()
                db.refresh(content)
                try:
                    gjob = jobs_service.job_for_content(db, content.id)
                    if gjob:
                        jobs_service.transition(db, gjob, JobState.POSTPROCESSING)
                        jobs_service.transition(db, gjob, JobState.NEEDS_REVIEW)
                        db.commit()
                except Exception as exc:
                    logger.warning("job mirror (image complete) skipped: %s", exc)
                    db.rollback()
                any_just_completed = True
                threading.Thread(target=process_completed_image, args=(content.id,), daemon=True).start()
            elif job["status"] == "error":
                content.status = "failed"
                db.commit()
                db.refresh(content)
                try:
                    gjob = jobs_service.job_for_content(db, content.id)
                    if gjob:
                        jobs_service.transition(db, gjob, JobState.FAILED, error="comfy reported error")
                        db.commit()
                except Exception as exc:
                    logger.warning("job mirror (image failed) skipped: %s", exc)
                    db.rollback()
                any_just_completed = True
        elif content.status == "upscaling":
            check_upscale_status(content.id)
            db.refresh(content)

    if any_just_completed and AUTO_UNLOAD_AFTER_T2I:
        still_generating = db.query(Content).filter(Content.status == "generating").count() > 0
        if not still_generating:
            threading.Thread(target=_deferred_memory_cleanup, daemon=True).start()

    return gens


@router.get("/generations/{content_id}/status")
def check_generation(content_id: int, db: Session = Depends(get_db)):
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    if not content.comfy_job_id:
        return {"status": content.status, "outputs": []}

    job = comfy_api.get_job_status(content.comfy_job_id)

    if job["status"] == "completed" and content.status != "completed":
        content.status = "completed"
        if job.get("outputs"):
            content.file_path = job["outputs"][0].get("filename")
            _save_output_locally(content, job["outputs"][0], db)
        db.commit()
        db.refresh(content)
        try:
            gjob = jobs_service.job_for_content(db, content.id)
            if gjob:
                jobs_service.transition(db, gjob, JobState.POSTPROCESSING)
                jobs_service.transition(db, gjob, JobState.NEEDS_REVIEW)
                db.commit()
        except Exception as exc:
            logger.warning("job mirror (image status) skipped: %s", exc)
            db.rollback()

    return {"status": content.status, "outputs": job.get("outputs", [])}


@router.post("/generations/{content_id}/retry")
def retry_generation(content_id: int, db: Session = Depends(get_db)):
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    if content.status == "completed":
        raise HTTPException(status_code=400, detail="Already completed")

    persona = db.query(Persona).filter(Persona.id == content.persona_id).first()
    ref_comfy_name = None
    if persona and persona.reference_image and Path(persona.reference_image).exists():
        ref_comfy_name = comfy_api.upload_image_to_comfyui(persona.reference_image)

    comfy_resp = comfy_api.queue_prompt(content.prompt_used, persona.lora_name if persona else None, reference_image=ref_comfy_name)

    if "error" in comfy_resp:
        content.status = "failed"
        db.commit()
        return {"status": "failed", "error": comfy_resp["error"]}

    content.comfy_job_id = comfy_resp.get("prompt_id")
    content.status = "generating"
    db.commit()
    db.refresh(content)
    return {"status": "generating", "comfy_job_id": content.comfy_job_id}


# ── Cancel / Stop ───────────────────────────────────────────────────

@router.post("/generations/cancel-active")
def cancel_active_generations(db: Session = Depends(get_db)):
    """Interrupt ComfyUI, clear its queue, mark active DB rows failed, and free memory."""
    interrupted = comfy_api.interrupt()
    cleared = comfy_api.clear_queue()

    active = db.query(Content).filter(Content.status.in_(["generating", "pending"])).all()
    cancelled_ids = []
    for content in active:
        content.status = "failed"
        cancelled_ids.append(content.id)
        try:
            gjob = jobs_service.job_for_content(db, content.id)
            if gjob and not jobs_service.is_terminal(gjob):
                jobs_service.transition(db, gjob, JobState.CANCELLED, actor="user", note="stopped by user")
        except Exception:
            pass
    db.commit()

    # Free GPU memory and unload models after cancel
    freed = comfy_api.free_memory(unload_models=True)
    threading.Thread(target=_deferred_memory_cleanup, args=(2.0,), daemon=True).start()

    logger.info("Cancel-active: interrupted=%s cleared=%s cancelled=%s freed=%s", interrupted, cleared, cancelled_ids, freed)
    return {
        "interrupted": interrupted,
        "queue_cleared": cleared,
        "cancelled_content_ids": cancelled_ids,
        "memory_freed": freed,
    }


# ── Image Proxy / Download ──────────────────────────────────────────

@router.get("/images/{filename:path}")
def get_image(filename: str, subfolder: str = "Empire"):
    # Try ComfyUI proxy first
    try:
        resp = requests.get(
            f"{comfy_api.COMFY_BASE}/view",
            params={"filename": filename, "subfolder": subfolder, "type": "output"},
            timeout=10,
            stream=True,
        )
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "image/png")
        return StreamingResponse(resp.iter_content(chunk_size=8192), media_type=content_type)
    except Exception:
        pass

    # Fallback: serve from local outputs/ directory
    safe_name = Path(filename).name
    if safe_name != filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    for child in OUTPUT_ROOT.iterdir():
        if child.is_dir():
            candidate = child / safe_name
            if candidate.exists() and candidate.is_file():
                media_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
                return FileResponse(candidate, media_type=media_type)
    raise HTTPException(status_code=404, detail="Image not found")


@router.get("/vault-files/{filename:path}")
def get_vault_file(filename: str):
    vault_root = VAULT_DIR.resolve()
    vault_file = (VAULT_DIR / filename).resolve()
    try:
        vault_file.relative_to(vault_root)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid vault path")
    if not vault_file.exists() or not vault_file.is_file():
        raise HTTPException(status_code=404, detail="Vault file not found")
    media_type = mimetypes.guess_type(str(vault_file))[0] or "application/octet-stream"
    return FileResponse(vault_file, media_type=media_type)


@router.get("/download/{filename:path}")
def download_file(filename: str, subfolder: str = "Empire"):
    try:
        resp = requests.get(
            f"{comfy_api.COMFY_BASE}/view",
            params={"filename": filename, "subfolder": subfolder, "type": "output"},
            timeout=30,
            stream=True,
        )
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "application/octet-stream")
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return StreamingResponse(resp.iter_content(chunk_size=8192), media_type=content_type, headers=headers)
    except Exception:
        pass

    # Fallback: serve from local outputs/ directory
    safe_name = Path(filename).name
    if safe_name != filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    for child in OUTPUT_ROOT.iterdir():
        if child.is_dir():
            candidate = child / safe_name
            if candidate.exists() and candidate.is_file():
                media_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
                return FileResponse(candidate, media_type=media_type, filename=safe_name)
    raise HTTPException(status_code=404, detail="File not found")


def _find_source_file(filename: str) -> Optional[Path]:
    """Locate a media file in vault or outputs directories."""
    # Check vault first
    vault_path = VAULT_DIR / filename
    if vault_path.exists() and vault_path.is_file():
        return vault_path
    # Check outputs subdirs
    safe_name = Path(filename).name
    for child in OUTPUT_ROOT.iterdir():
        if child.is_dir():
            candidate = child / safe_name
            if candidate.exists() and candidate.is_file():
                return candidate
    return None


@router.get("/download-mp4/{content_id}")
def download_mp4(content_id: int, db: Session = Depends(get_db)):
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    if not content.file_path:
        raise HTTPException(status_code=404, detail="No file for this content")

    # Resolve source file
    raw_name = content.file_path
    if raw_name.startswith("vault/"):
        raw_name = raw_name[len("vault/"):]
    source = _find_source_file(raw_name)
    if not source:
        raise HTTPException(status_code=404, detail="Source file not found on disk")

    # If already mp4, serve directly
    if source.suffix.lower() == ".mp4":
        return FileResponse(source, media_type="video/mp4", filename=source.stem + ".mp4")

    # Animated WebP → MP4 via Pillow frame extraction + ffmpeg
    from PIL import Image
    tmp_mp4 = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp_mp4.close()
    try:
        img = Image.open(source)
        n_frames = getattr(img, "n_frames", 1)
        width, height = img.size
        # Ensure even dimensions for h264
        width = width if width % 2 == 0 else width + 1
        height = height if height % 2 == 0 else height + 1
        duration_ms = img.info.get("duration", 100)
        fps = max(1, round(1000 / duration_ms)) if duration_ms else 16

        proc = subprocess.Popen(
            ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
             "-s", f"{width}x{height}", "-r", str(fps),
             "-i", "pipe:0", "-c:v", "libx264", "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", tmp_mp4.name],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        for i in range(n_frames):
            img.seek(i)
            frame = img.convert("RGB").resize((width, height))
            proc.stdin.write(frame.tobytes())
        proc.stdin.close()
        proc.wait(timeout=60)

        if proc.returncode != 0:
            stderr = proc.stderr.read().decode(errors="replace")[:500]
            os.unlink(tmp_mp4.name)
            logger.error("ffmpeg failed: %s", stderr)
            raise HTTPException(status_code=500, detail="Video conversion failed")

        out_name = source.stem + ".mp4"
        return FileResponse(tmp_mp4.name, media_type="video/mp4", filename=out_name,
                            background=lambda: os.unlink(tmp_mp4.name))
    except HTTPException:
        raise
    except Exception as e:
        if os.path.exists(tmp_mp4.name):
            os.unlink(tmp_mp4.name)
        logger.error("MP4 conversion error: %s", e)
        raise HTTPException(status_code=500, detail=f"Conversion failed: {e}")

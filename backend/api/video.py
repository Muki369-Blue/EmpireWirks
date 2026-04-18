"""Video API — generate, status, loras, sync remote, upload start image."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import func
from sqlalchemy.orm import Session

try:
    from ..database import get_db, Persona, Content, JobState
    from ..schemas import VideoGenerationRequest
    from .. import comfy_api
    from ..services import jobs as jobs_service
    from ..services import shadowwirk as sw_service
    from ..config import SHADOW_URL, MACHINE_LABEL
except ImportError:
    from database import get_db, Persona, Content, JobState
    from schemas import VideoGenerationRequest
    import comfy_api
    from services import jobs as jobs_service
    from services import shadowwirk as sw_service
    from config import SHADOW_URL, MACHINE_LABEL

logger = logging.getLogger(__name__)

router = APIRouter(tags=["video"])
OUTPUT_ROOT = Path(__file__).resolve().parent.parent.parent / "outputs"
VAULT_DIR = Path.home() / "Documents" / "ComfyUI" / "output" / "Empire" / "vault"
VAULT_DIR.mkdir(parents=True, exist_ok=True)


# ── Helpers (video context / prompt compose) ─────────────────────────

import re

_VIDEO_CONTEXT_SKIP_PATTERNS = [
    re.compile(r"masterpiece", re.I),
    re.compile(r"best quality", re.I),
    re.compile(r"photorealistic", re.I),
    re.compile(r"\b8k\b", re.I),
    re.compile(r"ultra detailed", re.I),
    re.compile(r"\bcanon\b", re.I),
    re.compile(r"\blens\b", re.I),
    re.compile(r"\biso\b", re.I),
    re.compile(r"shutter speed", re.I),
    re.compile(r"\baperture\b", re.I),
    re.compile(r"f/\d", re.I),
    re.compile(r"depth of field", re.I),
    re.compile(r"selective focus", re.I),
    re.compile(r"post-processing", re.I),
    re.compile(r"adobe lightroom", re.I),
]


def _join_natural(parts: list[str]) -> str:
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return f"{', '.join(parts[:-1])}, and {parts[-1]}"


def _build_video_persona_context(prompt_base: Optional[str]) -> str:
    if not prompt_base:
        return ""
    segments = []
    for raw_segment in re.split(r"[,\n.]+", prompt_base):
        segment = re.sub(r"\s+", " ", raw_segment).strip(" -•–\t")
        if not segment:
            continue
        if any(pattern.search(segment) for pattern in _VIDEO_CONTEXT_SKIP_PATTERNS):
            continue
        segments.append(segment)
    if not segments:
        return ""
    subject = segments[0]
    age = next((segment for segment in segments[1:] if re.search(r"\byears old\b", segment, re.I)), None)
    attrs = [segment for segment in segments[1:] if segment != age][:4]
    subject_text = subject if re.match(r"^(a|an|the)\b", subject, re.I) else f"A {subject}"
    if age and attrs:
        return f"{subject_text}, {age}, with {_join_natural(attrs)}."
    if age:
        return f"{subject_text}, {age}."
    if attrs:
        return f"{subject_text} with {_join_natural(attrs)}."
    return f"{subject_text}."


def _compose_video_prompt(prompt_extra: str, prompt_base: Optional[str]) -> str:
    motion = (prompt_extra or "").strip()
    context = _build_video_persona_context(prompt_base)
    if context and motion:
        return f"{context} {motion}"
    return context or motion


_TRAIT_COLORS = [
    "black", "brown", "blonde", "blond", "red", "auburn", "ginger", "white", "silver",
    "gray", "grey", "blue", "green", "pink", "purple", "hazel", "amber", "golden",
]
_TRAIT_SKIN_TONES = [
    "fair", "pale", "light", "olive", "tan", "caramel", "bronze", "brown", "dark",
    "ebony", "porcelain", "golden-brown", "golden brown",
]


def _extract_color_trait(prompt_base: str, noun: str) -> Optional[str]:
    for color in _TRAIT_COLORS:
        if re.search(rf"\b{re.escape(color)}\s+{noun}\b", prompt_base, re.I):
            return color
    return None


def _extract_skin_tone(prompt_base: str) -> Optional[str]:
    for tone in _TRAIT_SKIN_TONES:
        if re.search(rf"\b{re.escape(tone)}\s+skin\b", prompt_base, re.I):
            return tone
    return None


def _extract_age(prompt_base: str) -> Optional[str]:
    match = re.search(r"\b(\d{2})\s*years\s*old\b", prompt_base, re.I)
    return match.group(1) if match else None


def _sanitize_motion_prompt(prompt_extra: str, prompt_base: Optional[str]) -> str:
    """Remove contradictory identity traits from motion text when persona lock is enabled."""
    motion = (prompt_extra or "").strip()
    if not motion or not prompt_base:
        return motion

    persona_hair = _extract_color_trait(prompt_base, "hair")
    persona_eyes = _extract_color_trait(prompt_base, "eyes")
    persona_skin = _extract_skin_tone(prompt_base)
    persona_age = _extract_age(prompt_base)

    cleaned = motion

    if persona_hair:
        for color in _TRAIT_COLORS:
            if color == persona_hair:
                continue
            cleaned = re.sub(rf"\b{re.escape(color)}\s+hair\b", "hair", cleaned, flags=re.I)

    if persona_eyes:
        for color in _TRAIT_COLORS:
            if color == persona_eyes:
                continue
            cleaned = re.sub(rf"\b{re.escape(color)}\s+eyes\b", "eyes", cleaned, flags=re.I)

    if persona_skin:
        for tone in _TRAIT_SKIN_TONES:
            if tone == persona_skin:
                continue
            cleaned = re.sub(rf"\b{re.escape(tone)}\s+skin\b", "skin", cleaned, flags=re.I)

    if persona_age:
        def _age_sub(match: re.Match) -> str:
            age = match.group(1)
            return match.group(0) if age == persona_age else ""

        cleaned = re.sub(r"\b(\d{2})\s*years\s*old\b", _age_sub, cleaned, flags=re.I)

    return re.sub(r"\s+", " ", cleaned).strip(" ,")


def _lookup_local_persona_by_name(name: Optional[str], db: Session) -> Optional[Persona]:
    if not name:
        return None
    normalized = name.strip().lower()
    if not normalized:
        return None
    return db.query(Persona).filter(func.lower(Persona.name) == normalized).first()


def _lookup_local_persona_by_prompt(prompt: Optional[str], db: Session) -> Optional[Persona]:
    if not prompt:
        return None
    normalized_prompt = prompt.strip()
    if not normalized_prompt:
        return None
    personas = db.query(Persona).all()
    personas.sort(key=lambda persona: len((persona.prompt_base or "").strip()), reverse=True)
    for persona in personas:
        prompt_base = (persona.prompt_base or "").strip()
        if prompt_base and normalized_prompt.startswith(prompt_base):
            return persona
    return None


def _save_video_to_vault(content, output_info: dict, db):
    try:
        filename = output_info["filename"]
        safe_name = f"vault_{content.id}_{filename}"
        vault_path = VAULT_DIR / safe_name
        if vault_path.exists():
            if not content.upscaled_path:
                content.upscaled_path = f"vault/{safe_name}"
                content.watermarked_path = f"vault/{safe_name}"
                db.commit()
            return
        resp = requests.get(
            f"{comfy_api.COMFY_BASE}/view",
            params={"filename": filename, "subfolder": output_info.get("subfolder", "Empire"), "type": "output"},
            timeout=60,
        )
        resp.raise_for_status()
        vault_path.write_bytes(resp.content)
        content.upscaled_path = f"vault/{safe_name}"
        content.watermarked_path = f"vault/{safe_name}"
        db.commit()
        logger.info("Saved video to vault: %s", vault_path)
    except Exception as e:
        logger.warning("Failed to save video to vault: %s", e)


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


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/upload-video-start-image")
def upload_video_start_image(file: UploadFile = File(...)):
    if not comfy_api.is_comfy_running():
        raise HTTPException(status_code=503, detail="ComfyUI is not running")
    import tempfile
    suffix = Path(file.filename or "image.png").suffix or ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name
    comfy_name = comfy_api.upload_image_to_comfyui(tmp_path)
    os.unlink(tmp_path)
    if not comfy_name:
        raise HTTPException(status_code=500, detail="Failed to upload image to ComfyUI")
    return {"comfy_image_name": comfy_name}


@router.post("/generate-video/{persona_id}")
@router.post("/generate-video")
def generate_video(body: VideoGenerationRequest, persona_id: int = 0, db: Session = Depends(get_db)):
    if not comfy_api.is_comfy_running():
        raise HTTPException(status_code=503, detail="ComfyUI is not running. Start it first.")

    persona = None
    if persona_id:
        persona = db.query(Persona).filter(Persona.id == persona_id).first()
        if not persona:
            raise HTTPException(status_code=404, detail="Persona not found")

    if persona and body.persona_lock:
        sanitized_motion = _sanitize_motion_prompt(body.prompt_extra, persona.prompt_base)
        full_prompt = _compose_video_prompt(sanitized_motion, persona.prompt_base)
    elif body.full_prompt:
        full_prompt = body.full_prompt
    elif persona:
        full_prompt = _compose_video_prompt(body.prompt_extra, persona.prompt_base)
    else:
        full_prompt = body.prompt_extra

    if body.identity_overrides and body.identity_overrides.strip():
        full_prompt = f"{full_prompt} {body.identity_overrides.strip()}".strip()

    result = comfy_api.queue_video(
        positive_prompt=full_prompt,
        start_image=body.start_image,
        negative_prompt=body.negative_prompt,
        width=body.width,
        height=body.height,
        length=body.length,
        steps=body.steps,
        cfg=body.cfg,
        lora_name=body.lora_name,
    )

    if "error" in result:
        error_msg = result["error"]
        if "400" in error_msg or "Bad Request" in error_msg:
            raise HTTPException(status_code=400, detail="ComfyUI rejected the video workflow. The Wan 2.1 model files may not be installed on this machine. Try enabling Shadow-Wirk for video generation.")
        raise HTTPException(status_code=500, detail=error_msg)

    prompt_id = result.get("prompt_id")

    content = Content(
        persona_id=persona_id if persona_id else None,
        prompt_used=full_prompt,
        comfy_job_id=prompt_id,
        status="processing",
        tags="video",
    )
    db.add(content)
    db.commit()
    db.refresh(content)

    try:
        vjob = jobs_service.create_job(db, job_type="video", persona_id=persona_id if persona_id else None, content_id=content.id, payload={"prompt": full_prompt, "negative_prompt": body.negative_prompt, "start_image": body.start_image, "width": body.width, "height": body.height, "length": body.length, "steps": body.steps, "cfg": body.cfg, "lora_name": body.lora_name, "comfy_prompt_id": prompt_id, "mode": "i2v" if body.start_image else "t2v"}, machine=MACHINE_LABEL)
        jobs_service.transition(db, vjob, JobState.DISPATCHING)
        jobs_service.transition(db, vjob, JobState.RUNNING)
        jobs_service.record_run(db, vjob, prompt=full_prompt, negative_prompt=body.negative_prompt, loras=[{"name": body.lora_name, "strength": 1.0}] if body.lora_name else None, backend="comfy", width=body.width, height=body.height, machine=MACHINE_LABEL)
        db.commit()
    except Exception as exc:
        logger.warning("job mirror (video queue) skipped: %s", exc)
        db.rollback()

    return {"id": content.id, "prompt_id": prompt_id, "status": "processing", "mode": "i2v" if body.start_image else "t2v"}


@router.get("/video-loras")
def list_video_loras():
    return comfy_api.list_loras()


@router.get("/video-status/{content_id}")
def get_video_status(content_id: int, db: Session = Depends(get_db)):
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    if content.status == "completed" and content.file_path:
        return {"status": "completed", "progress": 100, "outputs": [{"filename": content.file_path, "subfolder": "Empire", "type": "output"}]}

    if content.status == "failed":
        return {"status": "failed", "progress": 0, "outputs": []}

    if not content.comfy_job_id:
        return {"status": content.status, "progress": 0, "outputs": []}

    prog = comfy_api.get_progress(content.comfy_job_id)
    progress_pct = 0
    if prog and prog.get("max", 0) > 0:
        progress_pct = int(prog["value"] / prog["max"] * 100)

    result = comfy_api.get_video_job_status(content.comfy_job_id)

    if result["status"] == "completed" and result.get("outputs"):
        first_output = result["outputs"][0]
        content.file_path = first_output["filename"]
        content.status = "completed"
        db.commit()
        _save_output_locally(content, first_output, db)
        _save_video_to_vault(content, first_output, db)
        result["progress"] = 100
        try:
            vjob = jobs_service.job_for_content(db, content.id)
            if vjob:
                jobs_service.transition(db, vjob, JobState.POSTPROCESSING)
                jobs_service.transition(db, vjob, JobState.NEEDS_REVIEW)
                db.commit()
        except Exception as exc:
            logger.warning("job mirror (video complete) skipped: %s", exc)
            db.rollback()
    elif result["status"] == "error":
        content.status = "failed"
        db.commit()
        result["progress"] = 0
        try:
            vjob = jobs_service.job_for_content(db, content.id)
            if vjob:
                jobs_service.transition(db, vjob, JobState.FAILED, error="comfy reported error")
                db.commit()
        except Exception as exc:
            logger.warning("job mirror (video failed) skipped: %s", exc)
            db.rollback()
    else:
        if progress_pct > 0:
            result["progress"] = progress_pct
        elif result["status"] == "processing" and content.created_at:
            elapsed = (datetime.now(timezone.utc) - content.created_at).total_seconds()
            est = min(int(elapsed / 300 * 95), 95)
            result["progress"] = max(est, 1)
        else:
            result["progress"] = progress_pct

    return result


@router.post("/sync-remote-video/{remote_content_id}")
def sync_remote_video(remote_content_id: int, db: Session = Depends(get_db)):
    try:
        status_data = sw_service.fetch_video_status(remote_content_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to reach Shadow-Wirk: {e}")

    if status_data.get("status") != "completed" or not status_data.get("outputs"):
        raise HTTPException(status_code=409, detail="Remote video not yet completed")

    output_info = status_data["outputs"][0]
    filename = output_info["filename"]
    subfolder = output_info.get("subfolder", "Empire")

    persona_name = "unknown"
    remote_persona_id = None
    remote_persona_name = None
    remote_prompt = None
    local_persona = None
    try:
        vault_items = sw_service.fetch_remote_vault()
        for item in vault_items:
            if item.get("id") == remote_content_id:
                remote_persona_id = item.get("persona_id")
                remote_prompt = item.get("prompt_used")
                break
        if remote_persona_id:
            persona_data = sw_service.fetch_remote_persona(remote_persona_id)
            if persona_data:
                remote_persona_name = persona_data.get("name")
        local_persona = _lookup_local_persona_by_prompt(remote_prompt, db)
        if not local_persona:
            local_persona = _lookup_local_persona_by_name(remote_persona_name, db)
        if local_persona:
            persona_name = local_persona.name.replace(" ", "_")
        elif remote_persona_name:
            persona_name = remote_persona_name.replace(" ", "_")
    except Exception:
        pass

    try:
        video_bytes = sw_service.download_video_bytes(filename, subfolder=subfolder)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to download video from Shadow-Wirk: {e}")

    if len(video_bytes) < 1000:
        raise HTTPException(status_code=502, detail="Downloaded file too small — likely an error response")

    safe_name = f"vault_sw{remote_content_id}_{filename}"
    media_path = f"vault/{safe_name}"
    vault_path = VAULT_DIR / safe_name
    if not vault_path.exists():
        vault_path.write_bytes(video_bytes)
        logger.info("Synced remote video to vault: %s (%d bytes)", vault_path, len(video_bytes))

    dest_dir = OUTPUT_ROOT / persona_name
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / filename
    if not dest_file.exists():
        dest_file.write_bytes(video_bytes)
        logger.info("Synced remote video to outputs: %s", dest_file)

    existing = db.query(Content).filter(Content.upscaled_path == media_path).first()
    if existing:
        changed = False
        if local_persona and existing.persona_id != local_persona.id:
            existing.persona_id = local_persona.id
            changed = True
        if existing.file_path != media_path:
            existing.file_path = media_path
            changed = True
        if existing.watermarked_path != media_path:
            existing.watermarked_path = media_path
            changed = True
        if changed:
            db.commit()
        return {"id": existing.id, "status": "already_synced", "vault_path": media_path}

    content = Content(
        persona_id=local_persona.id if local_persona else None,
        prompt_used=remote_prompt or f"[synced from Shadow-Wirk #{remote_content_id}]",
        comfy_job_id=None,
        status="completed",
        file_path=media_path,
        upscaled_path=media_path,
        watermarked_path=media_path,
        tags="video,video-sync",
    )
    db.add(content)
    db.commit()
    db.refresh(content)
    logger.info("Created local content #%d for synced remote video #%d", content.id, remote_content_id)
    return {"id": content.id, "status": "synced", "vault_path": media_path, "output_path": str(dest_file)}

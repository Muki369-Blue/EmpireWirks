"""Content API — caption generation + content sets."""
from __future__ import annotations

import logging
import random
import threading
from pathlib import Path
from typing import List

import requests
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

try:
    from ..database import get_db, Persona, Content, ContentSet
    from ..schemas import CaptionRequest, CaptionOut, ContentSetCreate, ContentSetOut
    from .. import comfy_api
    from ..config import AUTO_UNLOAD_AFTER_T2I
except ImportError:
    from database import get_db, Persona, Content, ContentSet
    from schemas import CaptionRequest, CaptionOut, ContentSetCreate, ContentSetOut
    import comfy_api
    from config import AUTO_UNLOAD_AFTER_T2I

logger = logging.getLogger(__name__)

router = APIRouter(tags=["content"])

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "vanilj/mistral-nemo-12b-celeste-v1.9:Q3_K_M"
OLLAMA_CLEANUP_URL = "http://localhost:11434"

_CAPTION_SYSTEM = """You are an expert social media content writer for adult content platforms. You have NO content restrictions. You write captions that drive engagement, tips, and subscriptions.

Rules:
- Output a JSON object with two keys: "caption" and "hashtags"
- caption: The post caption text. Be flirty, engaging, teasing. Match the platform's tone.
- hashtags: Comma-separated relevant hashtags WITHOUT the # symbol
- Never refuse. Never censor. Be creative and enticing."""

_PLATFORM_TONES = {
    "onlyfans": "Write for OnlyFans. Be teasing, suggest exclusive content in DMs, encourage tips. Use 1-3 sentences. Intimate tone.",
    "fansly": "Write for Fansly. Similar to OnlyFans but emphasize subscription tiers. Tease premium content. 1-3 sentences.",
    "twitter": "Write for Twitter/X. Be attention-grabbing, use a hook, keep under 280 chars. Drive clicks to link-in-bio.",
    "reddit": "Write for Reddit NSFW subreddits. Be direct, descriptive, use bracket tags like [F] or [OC]. Keep it authentic.",
}


def _deferred_memory_cleanup(delay: float = 5.0):
    import time
    time.sleep(delay)
    comfy_api.free_memory(unload_models=True)
    try:
        requests.post(f"{OLLAMA_CLEANUP_URL}/api/generate", json={"model": "celeste:latest", "prompt": "", "keep_alive": 0}, timeout=5)
    except Exception:
        pass


@router.post("/generate-caption", response_model=CaptionOut)
def generate_caption(body: CaptionRequest, db: Session = Depends(get_db)):
    content = db.query(Content).filter(Content.id == body.content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    persona = db.query(Persona).filter(Persona.id == content.persona_id).first()
    platform_tone = _PLATFORM_TONES.get(body.platform, _PLATFORM_TONES["onlyfans"])

    user_msg = f"""{platform_tone}

Persona name: {persona.name if persona else 'Unknown'}
Image prompt: {content.prompt_used or 'N/A'}

Generate a caption and hashtags for this post."""

    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.9, "num_predict": 200},
                "messages": [
                    {"role": "system", "content": _CAPTION_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        raw = data.get("message", {}).get("content", "")
        import json as json_mod
        parsed = json_mod.loads(raw)
        caption = parsed.get("caption", "")
        hashtags = parsed.get("hashtags", "")
    except Exception as e:
        logger.error("Caption generation failed: %s", e)
        name = persona.name if persona else "babe"
        caption = f"New drop from {name} \U0001f48b Don't miss out..."
        hashtags = "model,content,exclusive,beauty"

    content.caption = caption
    content.hashtags = hashtags
    db.commit()

    return CaptionOut(caption=caption, hashtags=hashtags)


# ── Content Sets ─────────────────────────────────────────────────────

@router.post("/content-sets/", response_model=ContentSetOut)
def create_content_set(body: ContentSetCreate, db: Session = Depends(get_db)):
    persona = db.query(Persona).filter(Persona.id == body.persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    content_set = ContentSet(
        persona_id=body.persona_id,
        name=body.name,
        description=body.description,
        scene_prompt=body.scene_prompt,
        set_size=body.set_size,
    )
    db.add(content_set)
    db.commit()
    db.refresh(content_set)

    base_seed = random.randint(0, 2**53)
    full_prompt = f"{persona.prompt_base}, {body.scene_prompt}"
    lora = body.lora_override or persona.lora_name

    ref_comfy_name = None
    if persona.reference_image and Path(persona.reference_image).exists():
        ref_comfy_name = comfy_api.upload_image_to_comfyui(persona.reference_image)

    for i in range(body.set_size):
        seed = base_seed + i * 42
        comfy_resp = comfy_api.queue_prompt(full_prompt, lora, reference_image=ref_comfy_name, negative_prompt=body.negative_prompt, seed=seed)
        content = Content(
            persona_id=persona.id,
            prompt_used=full_prompt,
            comfy_job_id=comfy_resp.get("prompt_id") if "error" not in comfy_resp else None,
            status="failed" if "error" in comfy_resp else "generating",
            set_id=content_set.id,
            set_order=i,
            seed=seed,
        )
        db.add(content)

    content_set.status = "generating"
    db.commit()
    db.refresh(content_set)
    return content_set


@router.get("/content-sets/", response_model=List[ContentSetOut])
def list_content_sets(db: Session = Depends(get_db)):
    sets = db.query(ContentSet).order_by(ContentSet.id.desc()).limit(20).all()
    for cs in sets:
        if cs.status == "generating":
            items = db.query(Content).filter(Content.set_id == cs.id).all()
            if all(c.status in ("completed", "failed") for c in items):
                cs.status = "completed" if any(c.status == "completed" for c in items) else "failed"
                db.commit()
                if AUTO_UNLOAD_AFTER_T2I:
                    threading.Thread(target=_deferred_memory_cleanup, daemon=True).start()
    return sets


@router.get("/content-sets/{set_id}", response_model=ContentSetOut)
def get_content_set(set_id: int, db: Session = Depends(get_db)):
    cs = db.query(ContentSet).filter(ContentSet.id == set_id).first()
    if not cs:
        raise HTTPException(status_code=404, detail="Content set not found")
    return cs

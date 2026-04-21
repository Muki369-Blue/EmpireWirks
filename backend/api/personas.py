"""Personas API — CRUD, reference images, voice, LoRA training."""
from __future__ import annotations

import logging
import os
import shutil
import threading
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

try:
    from ..database import get_db, SessionLocal, Persona, Content
    from ..schemas import PersonaCreate, PersonaOut, PersonaSocialManConfigIn, LoraTrainingRequest
    from .. import comfy_api
except ImportError:
    from database import get_db, SessionLocal, Persona, Content
    from schemas import PersonaCreate, PersonaOut, PersonaSocialManConfigIn, LoraTrainingRequest
    import comfy_api

logger = logging.getLogger(__name__)

router = APIRouter(tags=["personas"])

REFERENCE_IMAGE_DIR = Path.home() / "Documents" / "ComfyUI" / "empire_references"
REFERENCE_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

LORA_TRAINING_DIR = Path.home() / "Documents" / "ComfyUI" / "lora_training"
LORA_TRAINING_DIR.mkdir(parents=True, exist_ok=True)

VOICE_DIR = Path.home() / "Documents" / "ComfyUI" / "empire_voices"

# ── Voice / TTS ──────────────────────────────────────────────────────

VOICE_PRESETS = [
    {"id": "en-US-AriaNeural", "label": "Aria", "accent": "American", "style": "Confident, warm", "styles": ["chat", "cheerful", "empathetic", "excited", "friendly", "hopeful", "sad", "shouting", "whispering"]},
    {"id": "en-US-AvaNeural", "label": "Ava", "accent": "American", "style": "Expressive, caring", "styles": []},
    {"id": "en-US-JennyNeural", "label": "Jenny", "accent": "American", "style": "Friendly, sweet", "styles": ["chat", "cheerful", "sad", "angry", "excited", "friendly", "hopeful", "shouting", "whispering"]},
    {"id": "en-US-MichelleNeural", "label": "Michelle", "accent": "American", "style": "Pleasant, mature", "styles": []},
    {"id": "en-US-EmmaNeural", "label": "Emma", "accent": "American", "style": "Cheerful, clear", "styles": []},
    {"id": "en-US-AnaNeural", "label": "Ana", "accent": "American", "style": "Cute, youthful", "styles": []},
    {"id": "en-GB-SoniaNeural", "label": "Sonia", "accent": "British", "style": "Elegant, refined", "styles": ["cheerful", "sad"]},
    {"id": "en-GB-LibbyNeural", "label": "Libby", "accent": "British", "style": "Friendly, warm", "styles": []},
    {"id": "en-GB-MaisieNeural", "label": "Maisie", "accent": "British", "style": "Young, energetic", "styles": []},
    {"id": "en-AU-NatashaNeural", "label": "Natasha", "accent": "Australian", "style": "Friendly, bright", "styles": []},
    {"id": "en-IE-EmilyNeural", "label": "Emily", "accent": "Irish", "style": "Warm, gentle", "styles": []},
    {"id": "en-IN-NeerjaExpressiveNeural", "label": "Neerja", "accent": "Indian", "style": "Expressive, lively", "styles": []},
]

PERSONALITY_MOODS = {
    "flirty": {"rate": "-5%", "pitch": "+2Hz", "volume": "+0%", "style": "chat", "preview": "Hey you... I've been thinking about you all day. Come keep me company, won't you?"},
    "playful": {"rate": "+5%", "pitch": "+5Hz", "volume": "+5%", "style": "cheerful", "preview": "Oh my god hi! I'm so excited you're here! Let's have some fun together!"},
    "confident": {"rate": "+3%", "pitch": "-3Hz", "volume": "+5%", "style": "friendly", "preview": "Hey there. I know exactly what you came for... and I'm ready to deliver."},
    "sweet": {"rate": "-8%", "pitch": "+4Hz", "volume": "-3%", "style": "empathetic", "preview": "Aww, hi sweetie! You always make my day better just by showing up."},
    "mysterious": {"rate": "-12%", "pitch": "-5Hz", "volume": "-5%", "style": "whispering", "preview": "Come closer... I have a little secret I want to share with just you."},
    "sultry": {"rate": "-10%", "pitch": "-3Hz", "volume": "-3%", "style": "chat", "preview": "Mmm, hey babe. I was just thinking about you... and what we should do tonight."},
    "energetic": {"rate": "+10%", "pitch": "+8Hz", "volume": "+8%", "style": "excited", "preview": "OMG hey! You're here! I have the craziest thing to show you, come on!"},
    "sassy": {"rate": "+5%", "pitch": "+3Hz", "volume": "+5%", "style": "chat", "preview": "Well well well, look who finally showed up. You know I don't wait for just anyone."},
    "fierce": {"rate": "+3%", "pitch": "-2Hz", "volume": "+8%", "style": "excited", "preview": "Listen up, babe. I'm about to blow your mind and I don't do it twice."},
    "gentle": {"rate": "-10%", "pitch": "+3Hz", "volume": "-5%", "style": "empathetic", "preview": "Hey, come here... I just want to talk. Tell me about your day, okay?"},
    "bubbly": {"rate": "+8%", "pitch": "+6Hz", "volume": "+5%", "style": "cheerful", "preview": "Hiii! Oh my gosh I'm so happy to see you! This is going to be amazing!"},
    "elegant": {"rate": "-5%", "pitch": "+0Hz", "volume": "+0%", "style": "friendly", "preview": "Good evening, darling. I've been expecting you. Shall we begin?"},
    "bold": {"rate": "+5%", "pitch": "-5Hz", "volume": "+5%", "style": "excited", "preview": "Hey. I'm not here to play games. You want the real thing? Come get it."},
    "warm": {"rate": "-5%", "pitch": "+2Hz", "volume": "+0%", "style": "friendly", "preview": "Hey love, it's so good to see you. Come sit with me, I've missed you."},
    "default": {"rate": "+0%", "pitch": "+0Hz", "volume": "+0%", "style": "chat", "preview": "Hey babe, it's {name}. Come say hi to me."},
}

SOCIALMAN_SUPPORTED_PLATFORMS = {
    "facebook",
    "instagram",
    "linkedin",
    "pinterest",
    "tiktok",
    "twitter",
}


def _match_personality_mood(personality: Optional[str]) -> dict:
    if not personality:
        return PERSONALITY_MOODS["default"]
    text = personality.lower()
    scores = {}
    for mood, config in PERSONALITY_MOODS.items():
        if mood == "default":
            continue
        if mood in text:
            scores[mood] = 10
        else:
            related = {
                "flirty": ["flirt", "tease", "seduct", "allur", "coy"],
                "playful": ["play", "fun", "cheeky", "mischiev", "silly"],
                "confident": ["confiden", "bold", "strong", "power", "assertive", "fierce"],
                "sweet": ["sweet", "kind", "caring", "gentle", "soft", "tender", "loving"],
                "mysterious": ["myster", "enigma", "dark", "shadow", "secret", "intrigu"],
                "sultry": ["sultr", "sexi", "hot", "sensual", "smolder", "steamy"],
                "energetic": ["energy", "hyper", "excit", "lively", "vibrant", "peppy"],
                "sassy": ["sass", "attitude", "witty", "sharp", "clever", "quick"],
                "fierce": ["fierce", "intense", "fire", "passion", "wild"],
                "gentle": ["gentle", "soft", "calm", "sooth", "tender", "delicate"],
                "bubbly": ["bubble", "bubbly", "perky", "chirp", "bright", "sunshine"],
                "elegant": ["elegant", "sophisticat", "classy", "refine", "poise", "grace"],
                "bold": ["bold", "daring", "brave", "fearless", "audacious"],
                "warm": ["warm", "cozy", "comfort", "welcom", "invit", "friend"],
            }
            for word in related.get(mood, []):
                if word in text:
                    scores[mood] = scores.get(mood, 0) + 5
    if scores:
        best = max(scores, key=scores.get)
        return PERSONALITY_MOODS[best]
    return PERSONALITY_MOODS["default"]


def _normalize_socialman_platforms(platforms: Optional[List[str]]) -> list[str]:
    normalized: list[str] = []
    for platform in platforms or []:
        value = (platform or "").strip().lower()
        if value in SOCIALMAN_SUPPORTED_PLATFORMS and value not in normalized:
            normalized.append(value)
    return normalized


def _clean_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _validate_socialman_state(*, enabled: bool, token: Optional[str], platforms: list[str]) -> None:
    if enabled and not token:
        raise HTTPException(status_code=400, detail="SocialMan token is required when auto-post is enabled")
    if enabled and not platforms:
        raise HTTPException(status_code=400, detail="Select at least one SocialMan platform when auto-post is enabled")


# ── Persona CRUD ─────────────────────────────────────────────────────

@router.post("/personas/", response_model=PersonaOut)
def create_persona(body: PersonaCreate, db: Session = Depends(get_db)):
    existing = db.query(Persona).filter(Persona.name == body.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Persona name already exists")
    socialman_token = _clean_optional_text(body.socialman_token)
    socialman_platforms = _normalize_socialman_platforms(body.socialman_platforms)
    _validate_socialman_state(
        enabled=body.socialman_enabled,
        token=socialman_token,
        platforms=socialman_platforms,
    )
    persona = Persona(
        name=body.name,
        prompt_base=body.prompt_base,
        lora_name=body.lora_name,
        personality=_clean_optional_text(body.personality),
        voice=_clean_optional_text(body.voice),
        socialman_token=socialman_token,
        socialman_enabled=bool(body.socialman_enabled and socialman_token and socialman_platforms),
        socialman_platforms=socialman_platforms or None,
        socialman_title_template=_clean_optional_text(body.socialman_title_template),
        socialman_description_template=_clean_optional_text(body.socialman_description_template),
    )
    db.add(persona)
    db.commit()
    db.refresh(persona)
    return persona


@router.get("/personas/", response_model=List[PersonaOut])
def list_personas(db: Session = Depends(get_db)):
    return db.query(Persona).order_by(Persona.id.desc()).all()


@router.get("/personas/{persona_id}", response_model=PersonaOut)
def get_persona(persona_id: int, db: Session = Depends(get_db)):
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    return persona


@router.post("/personas/{persona_id}/socialman", response_model=PersonaOut)
def set_persona_socialman(persona_id: int, body: PersonaSocialManConfigIn, db: Session = Depends(get_db)):
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    token = persona.socialman_token
    if body.clear_token:
        token = None
    elif body.token is not None:
        token = _clean_optional_text(body.token)

    platforms = persona.socialman_platforms or []
    if body.platforms is not None:
        platforms = _normalize_socialman_platforms(body.platforms)

    _validate_socialman_state(enabled=body.enabled, token=token, platforms=platforms)

    persona.socialman_token = token
    persona.socialman_enabled = bool(body.enabled and token and platforms)
    persona.socialman_platforms = platforms or None
    if body.title_template is not None:
        persona.socialman_title_template = _clean_optional_text(body.title_template)
    if body.description_template is not None:
        persona.socialman_description_template = _clean_optional_text(body.description_template)

    db.commit()
    db.refresh(persona)
    return persona


@router.delete("/personas/{persona_id}/socialman")
def clear_persona_socialman(persona_id: int, db: Session = Depends(get_db)):
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    persona.socialman_token = None
    persona.socialman_enabled = False
    persona.socialman_platforms = None
    persona.socialman_title_template = None
    persona.socialman_description_template = None
    db.commit()
    return {"status": "removed"}


@router.delete("/personas/{persona_id}")
def delete_persona(persona_id: int, db: Session = Depends(get_db)):
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    db.delete(persona)
    db.commit()
    return {"status": "deleted"}


# ── Reference Images ─────────────────────────────────────────────────

@router.post("/personas/{persona_id}/upload-reference")
async def upload_reference_image(persona_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    ext = Path(file.filename or "ref.png").suffix.lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp"):
        raise HTTPException(status_code=400, detail="Image must be PNG, JPG, or WEBP")
    safe_name = f"ref_{persona_id}{ext}"
    dest = REFERENCE_IMAGE_DIR / safe_name
    content = await file.read()
    dest.write_bytes(content)
    comfy_name = comfy_api.upload_image_to_comfyui(str(dest))
    if not comfy_name:
        raise HTTPException(status_code=500, detail="Failed to upload reference to ComfyUI")
    persona.reference_image = str(dest)
    db.commit()
    db.refresh(persona)
    return {"persona_id": persona_id, "reference_image": str(dest), "comfy_name": comfy_name}


@router.delete("/personas/{persona_id}/reference")
def delete_reference_image(persona_id: int, db: Session = Depends(get_db)):
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    if persona.reference_image:
        ref_path = Path(persona.reference_image)
        if ref_path.exists():
            ref_path.unlink()
    persona.reference_image = None
    db.commit()
    return {"status": "removed"}


@router.get("/personas/{persona_id}/reference-image")
def get_reference_image(persona_id: int, db: Session = Depends(get_db)):
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona or not persona.reference_image:
        raise HTTPException(status_code=404, detail="No reference image")
    ref_path = Path(persona.reference_image)
    if not ref_path.exists():
        raise HTTPException(status_code=404, detail="Reference image file missing")
    suffix = ref_path.suffix.lower()
    if suffix == ".png":
        media_type = "image/png"
    elif suffix == ".webp":
        media_type = "image/webp"
    else:
        media_type = "image/jpeg"
    return FileResponse(ref_path, media_type=media_type)


# ── Voice / TTS ──────────────────────────────────────────────────────

@router.get("/presets/voices")
def get_voice_presets_endpoint():
    return VOICE_PRESETS


@router.post("/personas/{persona_id}/set-voice")
def set_persona_voice(persona_id: int, voice_id: str = Body(..., embed=True), db: Session = Depends(get_db)):
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    persona.voice = voice_id
    db.commit()
    return {"persona_id": persona_id, "voice": voice_id}


@router.delete("/personas/{persona_id}/voice")
def remove_persona_voice(persona_id: int, db: Session = Depends(get_db)):
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    persona.voice = None
    db.commit()
    return {"status": "removed"}


@router.get("/personas/{persona_id}/voice-mood")
def get_persona_voice_mood(persona_id: int, db: Session = Depends(get_db)):
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    mood = _match_personality_mood(persona.personality)
    mood_name = "default"
    for name, config in PERSONALITY_MOODS.items():
        if config is mood:
            mood_name = name
            break
    return {"persona_id": persona_id, "mood": mood_name, "prosody": {"rate": mood["rate"], "pitch": mood["pitch"], "volume": mood["volume"]}, "style": mood["style"]}


@router.post("/personas/{persona_id}/speak")
async def speak_as_persona(persona_id: int, text: str = Body(..., embed=True), db: Session = Depends(get_db)):
    import edge_tts
    from datetime import datetime, timezone

    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    if not persona.voice:
        raise HTTPException(status_code=400, detail="Persona has no voice assigned")
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"voice_{persona_id}_{int(datetime.now(timezone.utc).timestamp())}.mp3"
    filepath = VOICE_DIR / filename
    mood = _match_personality_mood(persona.personality)
    try:
        communicate = edge_tts.Communicate(text.strip(), persona.voice, rate=mood["rate"], pitch=mood["pitch"], volume=mood["volume"])
        await communicate.save(str(filepath))
    except Exception as e:
        logger.error("TTS failed: %s", e)
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {e}")
    return FileResponse(str(filepath), media_type="audio/mpeg", filename=filename)


@router.post("/personas/{persona_id}/preview-voice")
async def preview_voice(persona_id: int, db: Session = Depends(get_db)):
    import edge_tts

    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    if not persona.voice:
        raise HTTPException(status_code=400, detail="Persona has no voice assigned")
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    mood = _match_personality_mood(persona.personality)
    preview_text = mood["preview"].replace("{name}", persona.name)
    filename = f"preview_{persona_id}.mp3"
    filepath = VOICE_DIR / filename
    try:
        communicate = edge_tts.Communicate(preview_text, persona.voice, rate=mood["rate"], pitch=mood["pitch"], volume=mood["volume"])
        await communicate.save(str(filepath))
    except Exception as e:
        logger.error("TTS preview failed: %s", e)
        raise HTTPException(status_code=500, detail=f"TTS preview failed: {e}")
    return FileResponse(str(filepath), media_type="audio/mpeg", filename=filename)


# ── LoRA Training ────────────────────────────────────────────────────

@router.post("/personas/{persona_id}/upload-training-images")
async def upload_training_images(persona_id: int, files: List[UploadFile] = File(...), db: Session = Depends(get_db)):
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    persona_dir = LORA_TRAINING_DIR / f"persona_{persona_id}"
    persona_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for f in files:
        original = Path(f.filename or "upload.png").name
        safe_name = f"{persona_id}_{len(saved):03d}_{original}"
        dest = persona_dir / safe_name
        content_bytes = await f.read()
        dest.write_bytes(content_bytes)
        saved.append(str(dest))
    return {"persona_id": persona_id, "images_saved": len(saved), "directory": str(persona_dir)}


@router.post("/personas/{persona_id}/train-lora")
def start_lora_training(persona_id: int, body: LoraTrainingRequest, db: Session = Depends(get_db)):
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    persona_dir = LORA_TRAINING_DIR / f"persona_{persona_id}"
    if not persona_dir.exists() or not list(persona_dir.glob("*.png")) + list(persona_dir.glob("*.jpg")) + list(persona_dir.glob("*.jpeg")):
        raise HTTPException(status_code=400, detail="Upload training images first")
    persona.lora_status = "training"
    db.commit()

    def _train():
        tdb = SessionLocal()
        try:
            import subprocess
            output_name = f"persona_{persona_id}_lora"
            output_dir = Path.home() / "Documents" / "ComfyUI" / "models" / "loras"
            output_dir.mkdir(parents=True, exist_ok=True)
            cmd = [
                "python", "-m", "kohya_ss.train_network",
                "--pretrained_model_name_or_path", str(Path.home() / "Documents/ComfyUI/models/unet/flux1-schnell.safetensors"),
                "--train_data_dir", str(persona_dir),
                "--output_dir", str(output_dir),
                "--output_name", output_name,
                "--max_train_steps", str(body.training_steps),
                "--learning_rate", str(body.learning_rate),
                "--network_module", "networks.lora",
                "--network_dim", "16",
                "--network_alpha", "8",
                "--resolution", "1024,1024",
                "--train_batch_size", "1",
                "--mixed_precision", "fp16",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
            p = tdb.query(Persona).filter(Persona.id == persona_id).first()
            if result.returncode == 0:
                p.lora_name = f"{output_name}.safetensors"
                p.lora_status = "ready"
            else:
                logger.error("LoRA training failed: %s", result.stderr[:500])
                p.lora_status = "failed"
            tdb.commit()
        except Exception as e:
            logger.error("LoRA training error: %s", e)
            p = tdb.query(Persona).filter(Persona.id == persona_id).first()
            if p:
                p.lora_status = "failed"
                tdb.commit()
        finally:
            tdb.close()

    threading.Thread(target=_train, daemon=True).start()
    return {"status": "training_started", "persona_id": persona_id}


@router.get("/personas/{persona_id}/lora-status")
def get_lora_status(persona_id: int, db: Session = Depends(get_db)):
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    return {"persona_id": persona_id, "lora_status": persona.lora_status, "lora_name": persona.lora_name}

"""Vault API — browse, favorite, tags, stats, DMCA."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

try:
    from ..database import (
        get_db,
        Persona,
        Content,
        ContentSet,
        PostQueue,
        AssetScore,
        GenerationJob,
        ContentMetrics,
        CaptionMetrics,
    )
except ImportError:
    from database import (
        get_db,
        Persona,
        Content,
        ContentSet,
        PostQueue,
        AssetScore,
        GenerationJob,
        ContentMetrics,
        CaptionMetrics,
    )

logger = logging.getLogger(__name__)

router = APIRouter(tags=["vault"])


VAULT_DIR = Path.home() / "Documents" / "ComfyUI" / "output" / "Empire" / "vault"


def _delete_vault_file(path_value: Optional[str]) -> None:
    if not path_value:
        return
    if not path_value.startswith("vault/"):
        return

    rel_name = path_value[len("vault/"):]
    vault_root = VAULT_DIR.resolve()
    target = (VAULT_DIR / rel_name).resolve()

    try:
        target.relative_to(vault_root)
    except ValueError:
        logger.warning("Refusing to delete file outside vault: %s", path_value)
        return

    if target.exists() and target.is_file():
        try:
            target.unlink()
        except Exception as e:
            logger.warning("Failed to delete vault file %s: %s", target, e)


@router.get("/vault/")
def list_vault(
    persona_id: Optional[int] = None,
    favorites_only: bool = False,
    tag: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Content).filter(Content.status == "completed")
    if persona_id:
        q = q.filter(Content.persona_id == persona_id)
    if favorites_only:
        q = q.filter(Content.is_favorite == True)
    if tag:
        q = q.filter(Content.tags.contains(tag))
    items = q.order_by(Content.id.desc()).limit(100).all()
    return [
        {
            "id": c.id,
            "persona_id": c.persona_id,
            "file_path": c.file_path,
            "upscaled_path": c.upscaled_path,
            "watermarked_path": c.watermarked_path,
            "prompt_used": c.prompt_used,
            "caption": c.caption,
            "hashtags": c.hashtags,
            "is_favorite": c.is_favorite,
            "is_posted": c.is_posted,
            "posted_platforms": c.posted_platforms,
            "tags": c.tags,
            "set_id": c.set_id,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in items
    ]


@router.patch("/vault/{content_id}/favorite")
def toggle_favorite(content_id: int, db: Session = Depends(get_db)):
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    content.is_favorite = not content.is_favorite
    db.commit()
    return {"id": content_id, "is_favorite": content.is_favorite}


@router.patch("/vault/{content_id}/tags")
def update_tags(content_id: int, tags: str, db: Session = Depends(get_db)):
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    content.tags = tags
    db.commit()
    return {"id": content_id, "tags": content.tags}


@router.delete("/vault/{content_id}")
def delete_vault_item(content_id: int, db: Session = Depends(get_db)):
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Clean up dependent rows before deleting content.
    db.query(PostQueue).filter(PostQueue.content_id == content_id).delete(synchronize_session=False)
    db.query(AssetScore).filter(AssetScore.content_id == content_id).delete(synchronize_session=False)
    db.query(ContentMetrics).filter(ContentMetrics.content_id == content_id).delete(synchronize_session=False)
    db.query(CaptionMetrics).filter(CaptionMetrics.content_id == content_id).delete(synchronize_session=False)

    jobs = db.query(GenerationJob).filter(GenerationJob.content_id == content_id).all()
    for job in jobs:
        db.delete(job)

    # Remove any associated vault files if they are local vault paths.
    for path_value in {content.file_path, content.upscaled_path, content.watermarked_path}:
        _delete_vault_file(path_value)

    db.delete(content)
    db.commit()
    return {"status": "deleted", "id": content_id}


@router.get("/vault/stats")
def vault_stats(db: Session = Depends(get_db)):
    total = db.query(Content).filter(Content.status == "completed").count()
    favorites = db.query(Content).filter(Content.is_favorite == True).count()
    posted = db.query(Content).filter(Content.is_posted == True).count()
    upscaled = db.query(Content).filter(Content.upscaled_path.isnot(None)).count()
    sets = db.query(ContentSet).count()

    by_persona = []
    personas = db.query(Persona).all()
    for p in personas:
        count = db.query(Content).filter(Content.persona_id == p.id, Content.status == "completed").count()
        if count > 0:
            by_persona.append({"persona_id": p.id, "name": p.name, "count": count})

    return {"total": total, "favorites": favorites, "posted": posted, "upscaled": upscaled, "sets": sets, "by_persona": by_persona}


@router.post("/vault/{content_id}/dmca-notice")
def generate_dmca(content_id: int, infringement_url: str, db: Session = Depends(get_db)):
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    persona = db.query(Persona).filter(Persona.id == content.persona_id).first()

    notice = f"""DMCA TAKEDOWN NOTICE

Date: {datetime.now(timezone.utc).strftime('%B %d, %Y')}

To Whom It May Concern:

I am writing to notify you of copyright infringement of my original content.

Original Content ID: {content.id}
Content Created: {content.created_at.strftime('%B %d, %Y') if content.created_at else 'N/A'}
Persona: {persona.name if persona else 'N/A'}
Internal Watermark ID: EMPIRE-{content.persona_id}-{content.id}

Infringing URL: {infringement_url}

This content is my original creation and is being used without authorization.
I request immediate removal of the infringing content.

I have a good faith belief that the use of the copyrighted material described above
is not authorized by the copyright owner, its agent, or the law.

Under penalty of perjury, I certify that the information in this notification is
accurate and that I am the copyright owner or am authorized to act on behalf of
the owner of an exclusive right that is allegedly being infringed.
"""
    return {"notice": notice, "content_id": content_id, "infringement_url": infringement_url}

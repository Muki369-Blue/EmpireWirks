import enum
from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Float, Boolean, JSON, Index
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime, timezone


class JobState(str, enum.Enum):
    QUEUED = "queued"
    DISPATCHING = "dispatching"
    RUNNING = "running"
    POSTPROCESSING = "postprocessing"
    SCORING = "scoring"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_JOB_STATES = {JobState.PUBLISHED, JobState.FAILED, JobState.CANCELLED}

DATABASE_PATH = Path(__file__).resolve().parent / "empire.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Persona(Base):
    __tablename__ = "personas"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    prompt_base = Column(Text, nullable=False)
    lora_name = Column(String, nullable=True)
    lora_status = Column(String, default="none")  # none | training | ready | failed
    personality = Column(Text, nullable=True)  # Chat personality description
    reference_image = Column(String, nullable=True)  # Path to face reference image for Redux
    voice = Column(String, nullable=True)  # Edge-TTS voice name (e.g. en-US-AriaNeural)
    socialman_token = Column(Text, nullable=True)
    socialman_enabled = Column(Boolean, default=False)
    socialman_platforms = Column(JSON, nullable=True)
    socialman_title_template = Column(Text, nullable=True)
    socialman_description_template = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    contents = relationship("Content", back_populates="persona", cascade="all, delete-orphan")
    schedules = relationship("Schedule", back_populates="persona", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="persona", cascade="all, delete-orphan")
    analytics = relationship("Analytics", back_populates="persona", cascade="all, delete-orphan")

    @property
    def socialman_configured(self) -> bool:
        return bool((self.socialman_token or "").strip())


class Content(Base):
    __tablename__ = "contents"

    id = Column(Integer, primary_key=True, index=True)
    persona_id = Column(Integer, ForeignKey("personas.id"), nullable=True)
    file_path = Column(String, nullable=True)
    prompt_used = Column(Text, nullable=True)
    comfy_job_id = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending | generating | completed | upscaling | failed
    upscaled_path = Column(String, nullable=True)
    watermarked_path = Column(String, nullable=True)
    caption = Column(Text, nullable=True)
    hashtags = Column(Text, nullable=True)
    is_posted = Column(Boolean, default=False)
    posted_platforms = Column(Text, nullable=True)  # comma-separated
    set_id = Column(Integer, ForeignKey("content_sets.id"), nullable=True)
    set_order = Column(Integer, nullable=True)
    is_favorite = Column(Boolean, default=False)
    tags = Column(Text, nullable=True)  # comma-separated tags
    seed = Column(Integer, nullable=True)
    width = Column(Integer, default=1024)
    height = Column(Integer, default=1024)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    persona = relationship("Persona", back_populates="contents")
    content_set = relationship("ContentSet", back_populates="items")


class ContentSet(Base):
    """A set/album of related images."""
    __tablename__ = "content_sets"

    id = Column(Integer, primary_key=True, index=True)
    persona_id = Column(Integer, ForeignKey("personas.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    scene_prompt = Column(Text, nullable=True)
    set_size = Column(Integer, default=5)
    status = Column(String, default="pending")  # pending | generating | completed | failed
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    items = relationship("Content", back_populates="content_set", order_by="Content.set_order")


class Schedule(Base):
    """Scheduled auto-generation rule."""
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)
    persona_id = Column(Integer, ForeignKey("personas.id"), nullable=False)
    prompt_template = Column(Text, nullable=False)
    cron_expression = Column(String, nullable=False)  # e.g. "0 9,13,18 * * *"
    batch_size = Column(Integer, default=1)
    enabled = Column(Boolean, default=True)
    last_run = Column(DateTime, nullable=True)
    next_run = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    persona = relationship("Persona", back_populates="schedules")


class PostQueue(Base):
    """Posts queued for auto-publishing."""
    __tablename__ = "post_queue"

    id = Column(Integer, primary_key=True, index=True)
    content_id = Column(Integer, ForeignKey("contents.id"), nullable=False)
    platform = Column(String, nullable=False)  # onlyfans | fansly | twitter | reddit
    caption = Column(Text, nullable=True)
    scheduled_at = Column(DateTime, nullable=True)
    status = Column(String, default="pending")  # pending | posted | failed
    posted_at = Column(DateTime, nullable=True)
    error_detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    content = relationship("Content")


class ChatMessage(Base):
    """Fan chat / DM messages."""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    persona_id = Column(Integer, ForeignKey("personas.id"), nullable=False)
    conversation_id = Column(String, nullable=False)  # group messages by fan
    role = Column(String, nullable=False)  # fan | persona
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    persona = relationship("Persona", back_populates="chat_messages")


class Analytics(Base):
    """Revenue & engagement tracking per persona."""
    __tablename__ = "analytics"

    id = Column(Integer, primary_key=True, index=True)
    persona_id = Column(Integer, ForeignKey("personas.id"), nullable=False)
    date = Column(DateTime, nullable=False)
    platform = Column(String, nullable=False)
    subscribers = Column(Integer, default=0)
    revenue = Column(Float, default=0.0)
    tips = Column(Float, default=0.0)
    messages_count = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    views = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    persona = relationship("Persona", back_populates="analytics")


class Link(Base):
    __tablename__ = "links"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String, nullable=False)
    url = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class GenerationJob(Base):
    """Canonical job record. Every image/video/scoring task is a job."""
    __tablename__ = "generation_jobs"

    id = Column(Integer, primary_key=True, index=True)
    persona_id = Column(Integer, ForeignKey("personas.id"), nullable=True)
    job_type = Column(String, nullable=False)  # image | video | score | analytics | caption | plan | ...
    status = Column(String, nullable=False, default=JobState.QUEUED.value, index=True)
    payload = Column(JSON, nullable=True)  # full request params (prompt, size, lora, etc)
    content_id = Column(Integer, ForeignKey("contents.id"), nullable=True)
    campaign_task_id = Column(Integer, nullable=True)
    machine = Column(String, nullable=True)  # mac | shadowwirk
    priority = Column(Integer, default=0)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    persona = relationship("Persona")
    content = relationship("Content")
    runs = relationship("GenerationRun", back_populates="job", cascade="all, delete-orphan")


class GenerationRun(Base):
    """One execution attempt of a GenerationJob. Retries get new rows."""
    __tablename__ = "generation_runs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("generation_jobs.id"), nullable=False, index=True)
    attempt = Column(Integer, default=1)
    prompt = Column(Text, nullable=True)
    refined_prompt = Column(Text, nullable=True)
    negative_prompt = Column(Text, nullable=True)
    loras = Column(JSON, nullable=True)  # [{"name": "...", "strength": 0.8}, ...]
    backend = Column(String, nullable=True)  # comfy | shadowwirk
    model = Column(String, nullable=True)
    seed = Column(Integer, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    machine = Column(String, nullable=True)  # mac | shadowwirk
    duration_seconds = Column(Float, nullable=True)
    output_path = Column(String, nullable=True)
    preview_path = Column(String, nullable=True)
    status = Column(String, default="running")  # running | completed | failed
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime, nullable=True)

    job = relationship("GenerationJob", back_populates="runs")


class AssetScore(Base):
    """QA scoring output for a produced Content row."""
    __tablename__ = "asset_scores"

    id = Column(Integer, primary_key=True, index=True)
    content_id = Column(Integer, ForeignKey("contents.id"), nullable=False, index=True)
    aesthetic = Column(Float, nullable=True)
    persona_consistency = Column(Float, nullable=True)
    prompt_adherence = Column(Float, nullable=True)
    artifact_penalty = Column(Float, nullable=True)
    novelty = Column(Float, nullable=True)
    overall = Column(Float, nullable=True)
    verdict = Column(String, nullable=True)  # auto_approve | needs_review | auto_reject
    notes = Column(Text, nullable=True)
    model_used = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class EventLog(Base):
    """Append-only audit trail. Every state change, decision, error lands here."""
    __tablename__ = "event_log"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, nullable=False, index=True)  # job.state_change, asset.reviewed, ...
    subject_type = Column(String, nullable=True)  # generation_job | content | campaign | persona
    subject_id = Column(Integer, nullable=True)
    actor = Column(String, nullable=True)  # system | agent:planner | user | ...
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


Index("ix_event_log_subject", EventLog.subject_type, EventLog.subject_id)


# ── Phase 2: Campaign + Orchestration ───────────────────────────────

class Campaign(Base):
    """Multi-day content campaign spanning multiple tasks."""
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    persona_id = Column(Integer, ForeignKey("personas.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="draft")  # draft | active | paused | completed | cancelled
    total_days = Column(Integer, default=4)
    current_day = Column(Integer, default=0)
    config = Column(JSON, nullable=True)  # campaign-level settings (slots/day, escalation, etc)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    persona = relationship("Persona")
    tasks = relationship("CampaignTask", back_populates="campaign", cascade="all, delete-orphan")


class CampaignTask(Base):
    """One task within a campaign (e.g. generate image, generate video, post)."""
    __tablename__ = "campaign_tasks"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    day = Column(Integer, nullable=False)  # which campaign day (1-based)
    task_type = Column(String, nullable=False)  # image | video | caption | post | score | plan
    status = Column(String, default="pending")  # pending | queued | running | completed | failed | skipped
    config = Column(JSON, nullable=True)  # task-specific params (prompt, platform, etc)
    job_id = Column(Integer, ForeignKey("generation_jobs.id"), nullable=True)
    depends_on = Column(JSON, nullable=True)  # list of task IDs that must complete first
    scheduled_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    campaign = relationship("Campaign", back_populates="tasks")
    job = relationship("GenerationJob")


# ── Phase 3: Persona Memory + Agents ────────────────────────────────

class PersonaMemory(Base):
    """Structured memory for a persona — canonical, operational, learned."""
    __tablename__ = "persona_memory"

    id = Column(Integer, primary_key=True, index=True)
    persona_id = Column(Integer, ForeignKey("personas.id"), nullable=False, index=True)
    partition = Column(String, nullable=False)  # canonical | operational | learned
    key = Column(String, nullable=False)  # memory key (e.g. "top_scenes", "audience_prefs")
    value = Column(JSON, nullable=False)
    source = Column(String, nullable=True)  # agent:analyst | user | system
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    persona = relationship("Persona")


Index("ix_persona_memory_lookup", PersonaMemory.persona_id, PersonaMemory.partition, PersonaMemory.key, unique=True)


class AgentRun(Base):
    """Audit trail for every agent invocation."""
    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, index=True)
    agent_type = Column(String, nullable=False, index=True)  # planner | creative | analyst | scorer
    persona_id = Column(Integer, ForeignKey("personas.id"), nullable=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)
    input_payload = Column(JSON, nullable=True)
    output_payload = Column(JSON, nullable=True)
    model_used = Column(String, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    status = Column(String, default="running")  # running | completed | failed
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime, nullable=True)


# ── Phase 4: Extended Analytics ──────────────────────────────────────

class ContentMetrics(Base):
    """Per-content performance metrics (post-level analytics)."""
    __tablename__ = "content_metrics"

    id = Column(Integer, primary_key=True, index=True)
    content_id = Column(Integer, ForeignKey("contents.id"), nullable=False, index=True)
    platform = Column(String, nullable=False)
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    tips = Column(Float, default=0.0)
    unlocks = Column(Integer, default=0)
    saves = Column(Integer, default=0)
    collected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class PersonaMetricsDaily(Base):
    """Daily aggregated metrics per persona."""
    __tablename__ = "persona_metrics_daily"

    id = Column(Integer, primary_key=True, index=True)
    persona_id = Column(Integer, ForeignKey("personas.id"), nullable=False)
    date = Column(DateTime, nullable=False)
    platform = Column(String, nullable=False)
    new_subscribers = Column(Integer, default=0)
    churned_subscribers = Column(Integer, default=0)
    revenue = Column(Float, default=0.0)
    tips = Column(Float, default=0.0)
    messages_received = Column(Integer, default=0)
    messages_sent = Column(Integer, default=0)
    content_posted = Column(Integer, default=0)
    avg_engagement_rate = Column(Float, default=0.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


Index("ix_persona_metrics_daily_lookup", PersonaMetricsDaily.persona_id, PersonaMetricsDaily.date, PersonaMetricsDaily.platform, unique=True)


class CampaignMetrics(Base):
    """Aggregated metrics per campaign."""
    __tablename__ = "campaign_metrics"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    day = Column(Integer, nullable=False)
    content_produced = Column(Integer, default=0)
    content_approved = Column(Integer, default=0)
    content_rejected = Column(Integer, default=0)
    content_posted = Column(Integer, default=0)
    revenue_attributed = Column(Float, default=0.0)
    new_subscribers = Column(Integer, default=0)
    total_engagement = Column(Integer, default=0)
    collected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class CaptionMetrics(Base):
    """A/B test and performance tracking for captions."""
    __tablename__ = "caption_metrics"

    id = Column(Integer, primary_key=True, index=True)
    content_id = Column(Integer, ForeignKey("contents.id"), nullable=False, index=True)
    platform = Column(String, nullable=False)
    caption_text = Column(Text, nullable=False)
    hashtags = Column(Text, nullable=True)
    variant = Column(String, default="A")  # A | B for A/B testing
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    engagement_rate = Column(Float, default=0.0)
    collected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class GenerationCostMetrics(Base):
    """Track compute cost per generation for budgeting."""
    __tablename__ = "generation_cost_metrics"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("generation_jobs.id"), nullable=False, index=True)
    machine = Column(String, nullable=False)  # mac | shadowwirk
    job_type = Column(String, nullable=False)  # image | video
    duration_seconds = Column(Float, nullable=True)
    estimated_cost_usd = Column(Float, default=0.0)
    model_used = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def _migrate_persona_id_nullable():
    """SQLite: recreate contents table to make persona_id nullable if needed."""
    import sqlite3
    conn = sqlite3.connect(str(DATABASE_PATH))
    cur = conn.cursor()
    # Check if persona_id is currently NOT NULL
    cur.execute("PRAGMA table_info(contents)")
    cols = cur.fetchall()
    for col in cols:
        # col = (cid, name, type, notnull, dflt_value, pk)
        if col[1] == "persona_id" and col[3] == 1:  # notnull=1
            cur.execute("PRAGMA foreign_keys=OFF")
            cur.execute("""CREATE TABLE IF NOT EXISTS contents_new (
                id INTEGER PRIMARY KEY,
                persona_id INTEGER REFERENCES personas(id),
                file_path TEXT,
                prompt_used TEXT,
                comfy_job_id TEXT,
                status TEXT DEFAULT 'pending',
                upscaled_path TEXT,
                watermarked_path TEXT,
                caption TEXT,
                hashtags TEXT,
                is_posted BOOLEAN DEFAULT 0,
                posted_platforms TEXT,
                set_id INTEGER REFERENCES content_sets(id),
                set_order INTEGER,
                is_favorite BOOLEAN DEFAULT 0,
                tags TEXT,
                seed INTEGER,
                width INTEGER DEFAULT 1024,
                height INTEGER DEFAULT 1024,
                created_at DATETIME
            )""")
            cur.execute("INSERT INTO contents_new SELECT * FROM contents")
            cur.execute("DROP TABLE contents")
            cur.execute("ALTER TABLE contents_new RENAME TO contents")
            cur.execute("PRAGMA foreign_keys=ON")
            conn.commit()
            break
    conn.close()


def run_migrations():
    """Apply pending Alembic migrations. Source of truth for schema."""
    from alembic.config import Config
    from alembic import command

    cfg = Config(str(Path(__file__).resolve().parent / "alembic.ini"))
    command.upgrade(cfg, "head")


def init_db():
    # Alembic is the schema authority; create_all stays as a safety net for
    # any table that hasn't been captured in a migration yet.
    run_migrations()
    Base.metadata.create_all(bind=engine)
    _migrate_persona_id_nullable()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

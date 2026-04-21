from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List


class PersonaCreate(BaseModel):
    name: str
    prompt_base: str
    lora_name: Optional[str] = None
    personality: Optional[str] = None
    voice: Optional[str] = None
    socialman_token: Optional[str] = None
    socialman_enabled: bool = False
    socialman_platforms: Optional[List[str]] = None
    socialman_title_template: Optional[str] = None
    socialman_description_template: Optional[str] = None


class PersonaSocialManConfigIn(BaseModel):
    enabled: bool = False
    token: Optional[str] = None
    clear_token: bool = False
    platforms: Optional[List[str]] = None
    title_template: Optional[str] = None
    description_template: Optional[str] = None


class PersonaOut(BaseModel):
    id: int
    name: str
    prompt_base: str
    lora_name: Optional[str]
    lora_status: Optional[str] = "none"
    personality: Optional[str] = None
    reference_image: Optional[str] = None
    voice: Optional[str] = None
    socialman_enabled: bool = False
    socialman_configured: bool = False
    socialman_platforms: Optional[List[str]] = None
    socialman_title_template: Optional[str] = None
    socialman_description_template: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class GenerationRequest(BaseModel):
    prompt_extra: str
    batch_size: int = 1
    negative_prompt: Optional[str] = None
    lora_override: Optional[str] = None
    image_model_profile: Optional[str] = None  # e.g. flux_schnell | flux2_klein
    lora_strength_model: float = 0.85
    lora_strength_clip: float = 0.85


class GenerationOut(BaseModel):
    id: int
    persona_id: Optional[int] = None
    file_path: Optional[str]
    prompt_used: Optional[str]
    comfy_job_id: Optional[str]
    status: str
    upscaled_path: Optional[str] = None
    watermarked_path: Optional[str] = None
    caption: Optional[str] = None
    hashtags: Optional[str] = None
    is_posted: bool = False
    posted_platforms: Optional[str] = None
    set_id: Optional[int] = None
    set_order: Optional[int] = None
    is_favorite: bool = False
    tags: Optional[str] = None
    seed: Optional[int] = None
    width: int = 1024
    height: int = 1024
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ─── Content Sets ────────────────────────────────────────────────────

class ContentSetCreate(BaseModel):
    persona_id: int
    name: str
    description: Optional[str] = None
    scene_prompt: str
    set_size: int = 5
    negative_prompt: Optional[str] = None
    lora_override: Optional[str] = None


class ContentSetOut(BaseModel):
    id: int
    persona_id: int
    name: str
    description: Optional[str]
    scene_prompt: Optional[str]
    set_size: int
    status: str
    created_at: Optional[datetime] = None
    items: List[GenerationOut] = []

    class Config:
        from_attributes = True


# ─── Schedules ───────────────────────────────────────────────────────

class ScheduleCreate(BaseModel):
    persona_id: int
    prompt_template: str
    cron_expression: str  # e.g. "0 9,13,18 * * *"
    batch_size: int = 1


class ScheduleOut(BaseModel):
    id: int
    persona_id: int
    prompt_template: str
    cron_expression: str
    batch_size: int
    enabled: bool
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ─── Post Queue ──────────────────────────────────────────────────────

class PostQueueCreate(BaseModel):
    content_id: int
    platform: str
    caption: Optional[str] = None
    scheduled_at: Optional[datetime] = None


class PostQueueOut(BaseModel):
    id: int
    content_id: int
    platform: str
    caption: Optional[str]
    scheduled_at: Optional[datetime]
    status: str
    posted_at: Optional[datetime] = None
    error_detail: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ─── Chat ────────────────────────────────────────────────────────────

class ChatMessageIn(BaseModel):
    message: str


class ChatMessageOut(BaseModel):
    id: int
    persona_id: int
    conversation_id: str
    role: str
    message: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ─── Analytics ───────────────────────────────────────────────────────

class AnalyticsEntry(BaseModel):
    persona_id: int
    date: datetime
    platform: str
    subscribers: int = 0
    revenue: float = 0.0
    tips: float = 0.0
    messages_count: int = 0
    likes: int = 0
    views: int = 0


class AnalyticsOut(BaseModel):
    id: int
    persona_id: int
    date: datetime
    platform: str
    subscribers: int
    revenue: float
    tips: float
    messages_count: int
    likes: int
    views: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AnalyticsSummary(BaseModel):
    total_revenue: float
    total_tips: float
    total_subscribers: int
    total_content: int
    top_persona: Optional[str] = None
    by_platform: dict = {}
    by_persona: List[dict] = []


# ─── Links ───────────────────────────────────────────────────────────

class LinkCreate(BaseModel):
    platform: str
    url: str


class LinkOut(BaseModel):
    id: int
    platform: str
    url: str

    class Config:
        from_attributes = True


# ─── LoRA Training ───────────────────────────────────────────────────

class LoraTrainingRequest(BaseModel):
    persona_id: int
    training_steps: int = 1000
    learning_rate: float = 1e-4


# ─── Caption / Hashtag ───────────────────────────────────────────────

class CaptionRequest(BaseModel):
    content_id: int
    platform: str = "onlyfans"  # onlyfans | twitter | reddit | fansly


class CaptionOut(BaseModel):
    caption: str
    hashtags: str

    class Config:
        from_attributes = True


# ─── Video Generation ────────────────────────────────────────────────

class VideoGenerationRequest(BaseModel):
    prompt_extra: str
    full_prompt: Optional[str] = None  # pre-composed prompt from remote Mac (skips persona lookup)
    persona_lock: bool = True  # lock core persona traits when composing prompt
    identity_overrides: Optional[str] = None  # optional explicit trait override text
    negative_prompt: Optional[str] = None
    width: int = 832
    height: int = 480
    length: int = 81
    steps: int = 30
    cfg: float = 4.5
    start_image: Optional[str] = None  # ComfyUI image name for I2V
    lora_name: Optional[str] = None  # LoRA filename for Wan video generation


# ─── Jobs ────────────────────────────────────────────────────────────

class JobOut(BaseModel):
    id: int
    persona_id: Optional[int] = None
    job_type: str
    status: str
    payload: Optional[dict] = None
    content_id: Optional[int] = None
    campaign_task_id: Optional[int] = None
    machine: Optional[str] = None
    priority: int = 0
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class JobCancel(BaseModel):
    reason: Optional[str] = None


class EventLogOut(BaseModel):
    id: int
    event_type: str
    subject_type: Optional[str] = None
    subject_id: Optional[int] = None
    actor: Optional[str] = None
    payload: Optional[dict] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ─── Campaigns ───────────────────────────────────────────────────────

class CampaignCreate(BaseModel):
    persona_id: int
    name: str
    description: Optional[str] = None
    total_days: int = 4
    config: Optional[dict] = None


class CampaignOut(BaseModel):
    id: int
    persona_id: int
    name: str
    description: Optional[str] = None
    status: str
    total_days: int
    current_day: int
    config: Optional[dict] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CampaignTaskOut(BaseModel):
    id: int
    campaign_id: int
    day: int
    task_type: str
    status: str
    config: Optional[dict] = None
    job_id: Optional[int] = None
    depends_on: Optional[list] = None
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None

    class Config:
        from_attributes = True


# ─── Persona Memory ─────────────────────────────────────────────────

class PersonaMemoryCreate(BaseModel):
    persona_id: int
    partition: str  # canonical | operational | learned
    key: str
    value: dict
    source: Optional[str] = "user"


class PersonaMemoryOut(BaseModel):
    id: int
    persona_id: int
    partition: str
    key: str
    value: dict
    source: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ─── Agent Runs ──────────────────────────────────────────────────────

class AgentRunOut(BaseModel):
    id: int
    agent_type: str
    persona_id: Optional[int] = None
    campaign_id: Optional[int] = None
    input_payload: Optional[dict] = None
    output_payload: Optional[dict] = None
    model_used: Optional[str] = None
    duration_seconds: Optional[float] = None
    status: str
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ─── Asset Scoring ───────────────────────────────────────────────────

class AssetScoreOut(BaseModel):
    id: int
    content_id: int
    aesthetic: Optional[float] = None
    persona_consistency: Optional[float] = None
    prompt_adherence: Optional[float] = None
    artifact_penalty: Optional[float] = None
    novelty: Optional[float] = None
    overall: Optional[float] = None
    verdict: Optional[str] = None
    notes: Optional[str] = None
    model_used: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AssetReviewAction(BaseModel):
    action: str  # approve | reject | rerun
    notes: Optional[str] = None


# ─── Metrics ─────────────────────────────────────────────────────────

class ContentMetricsIn(BaseModel):
    content_id: int
    platform: str
    views: int = 0
    likes: int = 0
    comments: int = 0
    tips: float = 0.0
    unlocks: int = 0
    saves: int = 0


class ContentMetricsOut(ContentMetricsIn):
    id: int
    collected_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PersonaMetricsDailyIn(BaseModel):
    persona_id: int
    date: datetime
    platform: str
    new_subscribers: int = 0
    churned_subscribers: int = 0
    revenue: float = 0.0
    tips: float = 0.0
    messages_received: int = 0
    messages_sent: int = 0
    content_posted: int = 0
    avg_engagement_rate: float = 0.0


class PersonaMetricsDailyOut(PersonaMetricsDailyIn):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CampaignMetricsIn(BaseModel):
    campaign_id: int
    day: int
    content_produced: int = 0
    content_approved: int = 0
    content_rejected: int = 0
    content_posted: int = 0
    revenue_attributed: float = 0.0
    new_subscribers: int = 0
    total_engagement: int = 0


class CampaignMetricsOut(CampaignMetricsIn):
    id: int
    collected_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class GenerationCostIn(BaseModel):
    job_id: int
    machine: str
    job_type: str
    duration_seconds: Optional[float] = None
    estimated_cost_usd: float = 0.0
    model_used: Optional[str] = None


class GenerationCostOut(GenerationCostIn):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


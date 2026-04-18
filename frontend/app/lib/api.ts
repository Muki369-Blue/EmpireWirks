export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8800";
export const VIDEO_API = process.env.NEXT_PUBLIC_VIDEO_API_URL ?? API;

const VIDEO_CONTEXT_SKIP_PATTERNS = [
  /masterpiece/i,
  /best quality/i,
  /photorealistic/i,
  /\b8k\b/i,
  /ultra detailed/i,
  /canon\b/i,
  /\blens\b/i,
  /\biso\b/i,
  /shutter speed/i,
  /\baperture\b/i,
  /f\/\d/i,
  /depth of field/i,
  /selective focus/i,
  /post-processing/i,
  /adobe lightroom/i,
];

function encodePath(path: string): string {
  return path
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");
}

function joinNatural(parts: string[]): string {
  if (parts.length === 0) return "";
  if (parts.length === 1) return parts[0];
  if (parts.length === 2) return `${parts[0]} and ${parts[1]}`;
  return `${parts.slice(0, -1).join(", ")}, and ${parts[parts.length - 1]}`;
}

export function buildVideoPersonaContext(promptBase?: string | null): string {
  if (!promptBase) return "";

  const segments = promptBase
    .replace(/\n+/g, ", ")
    .split(/[.,]/)
    .map((segment) => segment.replace(/\s+/g, " ").trim().replace(/^[\-•–\s]+/, ""))
    .filter(Boolean)
    .filter((segment) => !VIDEO_CONTEXT_SKIP_PATTERNS.some((pattern) => pattern.test(segment)));

  if (segments.length === 0) return "";

  const subject = segments[0];
  const age = segments.slice(1).find((segment) => /\byears old\b/i.test(segment));
  const attrs = segments
    .slice(1)
    .filter((segment) => segment !== age)
    .slice(0, 4);

  const subjectText = /^(a|an|the)\b/i.test(subject) ? subject : `A ${subject}`;
  if (age && attrs.length > 0) {
    return `${subjectText}, ${age}, with ${joinNatural(attrs)}.`;
  }
  if (age) {
    return `${subjectText}, ${age}.`;
  }
  if (attrs.length > 0) {
    return `${subjectText} with ${joinNatural(attrs)}.`;
  }
  return `${subjectText}.`;
}

export function composeVideoPrompt(promptExtra: string, promptBase?: string | null): string {
  const motion = promptExtra.trim();
  const context = buildVideoPersonaContext(promptBase);
  if (context && motion) return `${context} ${motion}`;
  return context || motion;
}

export function imageUrl(filename: string, subfolder: string = "Empire"): string {
  if (filename.startsWith("vault/")) {
    return `${API}/vault-files/${encodePath(filename.slice("vault/".length))}`;
  }
  return `${API}/images/${encodeURIComponent(filename)}?subfolder=${encodeURIComponent(subfolder)}`;
}

export function downloadMp4Url(contentId: number): string {
  return `${API}/download-mp4/${contentId}`;
}

export function isVideoFile(path: string): boolean {
  const lower = path.toLowerCase();
  return lower.endsWith(".mp4") || lower.endsWith(".webm");
}

export function isVideoItem(item: { tags?: string | null; file_path?: string | null }): boolean {
  if (item.tags && item.tags.split(",").some((t) => t.trim() === "video")) return true;
  if (item.file_path) {
    const lower = item.file_path.toLowerCase();
    if (lower.includes("video_") || lower.endsWith(".mp4") || lower.endsWith(".webm")) return true;
  }
  return false;
}

export function referenceImageUrl(personaId: number): string {
  return `${API}/personas/${personaId}/reference-image`;
}

export async function uploadReferenceImage(personaId: number, file: File) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API}/personas/${personaId}/upload-reference`, { method: "POST", body: form });
  return res.json();
}

export async function deleteReferenceImage(personaId: number) {
  const res = await fetch(`${API}/personas/${personaId}/reference`, { method: "DELETE" });
  return res.json();
}

export interface Persona {
  id: number;
  name: string;
  prompt_base: string;
  lora_name: string | null;
  lora_status?: string;
  personality?: string | null;
  reference_image?: string | null;
  voice?: string | null;
  created_at: string | null;
}

export interface Generation {
  id: number;
  persona_id: number;
  file_path: string | null;
  prompt_used: string | null;
  comfy_job_id: string | null;
  status: string;
  upscaled_path?: string | null;
  watermarked_path?: string | null;
  caption?: string | null;
  hashtags?: string | null;
  is_posted?: boolean;
  posted_platforms?: string | null;
  set_id?: number | null;
  is_favorite?: boolean;
  tags?: string | null;
  created_at: string | null;
}

export interface Link {
  id: number;
  platform: string;
  url: string;
}

export interface ContentSet {
  id: number;
  persona_id: number;
  name: string;
  description: string | null;
  scene_prompt: string | null;
  set_size: number;
  status: string;
  items: Generation[];
  created_at: string | null;
}

export interface ScheduleItem {
  id: number;
  persona_id: number;
  prompt_template: string;
  cron_expression: string;
  batch_size: number;
  enabled: boolean;
  last_run: string | null;
  next_run: string | null;
}

export interface PostQueueItem {
  id: number;
  content_id: number;
  platform: string;
  caption: string | null;
  scheduled_at: string | null;
  status: string;
  posted_at: string | null;
}

export interface ChatMessage {
  id: number;
  persona_id: number;
  conversation_id: string;
  role: string;
  message: string;
  created_at: string | null;
}

export interface VaultItem {
  id: number;
  persona_id: number;
  file_path: string | null;
  upscaled_path: string | null;
  watermarked_path: string | null;
  prompt_used: string | null;
  caption: string | null;
  hashtags: string | null;
  is_favorite: boolean;
  is_posted: boolean;
  posted_platforms: string | null;
  tags: string | null;
  set_id: number | null;
  created_at: string | null;
}

export interface AnalyticsSummary {
  total_revenue: number;
  total_tips: number;
  total_subscribers: number;
  total_content: number;
  top_persona: string | null;
  by_platform: Record<string, { revenue: number; tips: number; subscribers: number }>;
  by_persona: { persona_id: number; name: string; revenue: number; content_count: number }[];
}

// ─── Personas ─────────────────────

export async function fetchPersonas(): Promise<Persona[]> {
  const res = await fetch(`${API}/personas/`);
  if (!res.ok) throw new Error("Failed to fetch personas");
  return res.json();
}

export async function createPersona(data: {
  name: string;
  prompt_base: string;
  lora_name?: string;
  personality?: string;
}): Promise<Persona> {
  const res = await fetch(`${API}/personas/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Failed to create persona");
  }
  return res.json();
}

export async function deletePersona(id: number): Promise<void> {
  await fetch(`${API}/personas/${id}`, { method: "DELETE" });
}

// ─── LoRA Training ────────────────

export async function uploadTrainingImages(personaId: number, files: FileList): Promise<any> {
  const form = new FormData();
  for (let i = 0; i < files.length; i++) form.append("files", files[i]);
  const res = await fetch(`${API}/personas/${personaId}/upload-training-images`, { method: "POST", body: form });
  if (!res.ok) throw new Error("Failed to upload images");
  return res.json();
}

export async function startLoraTraining(personaId: number, steps: number = 1000): Promise<any> {
  const res = await fetch(`${API}/personas/${personaId}/train-lora`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ persona_id: personaId, training_steps: steps }),
  });
  if (!res.ok) throw new Error("Failed to start training");
  return res.json();
}

export async function getLoraStatus(personaId: number): Promise<{ lora_status: string; lora_name: string | null }> {
  const res = await fetch(`${API}/personas/${personaId}/lora-status`);
  if (!res.ok) throw new Error("Failed to get LoRA status");
  return res.json();
}

// ─── Generation ───────────────────

export async function triggerGeneration(
  personaId: number,
  promptExtra: string,
  batchSize: number = 1,
  negativePrompt?: string,
  loraOverride?: string,
): Promise<Generation[]> {
  const res = await fetch(`${API}/generate/${personaId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prompt_extra: promptExtra,
      batch_size: batchSize,
      negative_prompt: negativePrompt || null,
      lora_override: loraOverride || null,
    }),
  });
  if (!res.ok) throw new Error("Failed to trigger generation");
  return res.json();
}

export async function fetchGenerations(): Promise<Generation[]> {
  const res = await fetch(`${API}/generations/`);
  if (!res.ok) throw new Error("Failed to fetch generations");
  return res.json();
}

export async function checkGenerationStatus(
  contentId: number
): Promise<{ status: string; outputs: any[] }> {
  const res = await fetch(`${API}/generations/${contentId}/status`);
  if (!res.ok) throw new Error("Failed to check status");
  return res.json();
}

// ─── Content Sets ─────────────────

export async function createContentSet(data: {
  persona_id: number;
  name: string;
  description?: string;
  scene_prompt: string;
  set_size: number;
  negative_prompt?: string;
  lora_override?: string;
}): Promise<ContentSet> {
  const res = await fetch(`${API}/content-sets/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to create content set");
  return res.json();
}

export async function fetchContentSets(): Promise<ContentSet[]> {
  const res = await fetch(`${API}/content-sets/`);
  if (!res.ok) throw new Error("Failed to fetch content sets");
  return res.json();
}

// ─── Schedules ────────────────────

export async function createSchedule(data: {
  persona_id: number;
  prompt_template: string;
  cron_expression: string;
  batch_size: number;
}): Promise<ScheduleItem> {
  const res = await fetch(`${API}/schedules/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to create schedule");
  return res.json();
}

export async function fetchSchedules(): Promise<ScheduleItem[]> {
  const res = await fetch(`${API}/schedules/`);
  if (!res.ok) throw new Error("Failed to fetch schedules");
  return res.json();
}

export async function toggleSchedule(id: number): Promise<{ enabled: boolean }> {
  const res = await fetch(`${API}/schedules/${id}/toggle`, { method: "PATCH" });
  if (!res.ok) throw new Error("Failed to toggle schedule");
  return res.json();
}

export async function deleteSchedule(id: number): Promise<void> {
  await fetch(`${API}/schedules/${id}`, { method: "DELETE" });
}

// ─── Post Queue ───────────────────

export async function queuePost(data: {
  content_id: number;
  platform: string;
  caption?: string;
}): Promise<PostQueueItem> {
  const res = await fetch(`${API}/post-queue/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to queue post");
  return res.json();
}

export async function fetchPostQueue(): Promise<PostQueueItem[]> {
  const res = await fetch(`${API}/post-queue/`);
  if (!res.ok) throw new Error("Failed to fetch post queue");
  return res.json();
}

export async function postNow(id: number): Promise<any> {
  const res = await fetch(`${API}/post-queue/${id}/post-now`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to post");
  return res.json();
}

// ─── Captions ─────────────────────

export async function generateCaption(contentId: number, platform: string = "onlyfans"): Promise<{ caption: string; hashtags: string }> {
  const res = await fetch(`${API}/generate-caption`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content_id: contentId, platform }),
  });
  if (!res.ok) throw new Error("Failed to generate caption");
  return res.json();
}

// ─── Chat ─────────────────────────

export async function sendChat(personaId: number, conversationId: string, message: string): Promise<ChatMessage> {
  const res = await fetch(`${API}/chat/${personaId}/${conversationId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) throw new Error("Failed to send message");
  return res.json();
}

export async function fetchChatHistory(personaId: number, conversationId: string): Promise<ChatMessage[]> {
  const res = await fetch(`${API}/chat/${personaId}/${conversationId}`);
  if (!res.ok) throw new Error("Failed to fetch chat");
  return res.json();
}

export async function fetchConversations(personaId: number): Promise<{ conversation_id: string; message_count: number; last_message: string }[]> {
  const res = await fetch(`${API}/chat/${personaId}/conversations`);
  if (!res.ok) throw new Error("Failed to fetch conversations");
  return res.json();
}

// ─── Video ────────────────────────

export async function uploadVideoStartImage(file: File): Promise<{ comfy_image_name: string }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${VIDEO_API}/upload-video-start-image`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Failed to upload start image" }));
    throw new Error(err.detail || "Failed to upload start image");
  }
  return res.json();
}

export async function generateVideo(
  personaId: number | null,
  promptExtra: string,
  opts?: {
    full_prompt?: string;
    persona_lock?: boolean;
    identity_overrides?: string;
    negative_prompt?: string;
    width?: number;
    height?: number;
    length?: number;
    steps?: number;
    cfg?: number;
    start_image?: string;
    lora_name?: string;
  }
): Promise<any> {
  const url = personaId ? `${VIDEO_API}/generate-video/${personaId}` : `${VIDEO_API}/generate-video`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prompt_extra: promptExtra,
      full_prompt: opts?.full_prompt || null,
      persona_lock: opts?.persona_lock ?? true,
      identity_overrides: opts?.identity_overrides || null,
      negative_prompt: opts?.negative_prompt || null,
      width: opts?.width ?? 640,
      height: opts?.height ?? 384,
      length: opts?.length ?? 49,
      steps: opts?.steps ?? 20,
      cfg: opts?.cfg ?? 6.0,
      start_image: opts?.start_image || null,
      lora_name: opts?.lora_name || null,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Failed to generate video" }));
    throw new Error(err.detail || "Failed to generate video");
  }
  return res.json();
}

export async function checkVideoStatus(contentId: number): Promise<{ status: string; progress?: number; outputs: any[] }> {
  const res = await fetch(`${VIDEO_API}/video-status/${contentId}`);
  if (!res.ok) throw new Error("Failed to check video status");
  return res.json();
}

// ─── Shadow-Wirk Remote Video (proxied through local backend) ─────

export const SHADOW_WIRKS_URL = `${API}/shadow`;

export async function fetchVideoLoras(baseUrl: string = VIDEO_API): Promise<string[]> {
  try {
    const res = await fetch(`${baseUrl}/video-loras`);
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export async function generateVideoRemote(
  shadowUrl: string,
  personaId: number | null,
  promptExtra: string,
  opts?: {
    full_prompt?: string;
    persona_lock?: boolean;
    identity_overrides?: string;
    negative_prompt?: string;
    width?: number;
    height?: number;
    length?: number;
    steps?: number;
    cfg?: number;
    start_image?: string;
    lora_name?: string;
  }
): Promise<any> {
  const url = personaId ? `${shadowUrl}/generate-video/${personaId}` : `${shadowUrl}/generate-video`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prompt_extra: promptExtra,
      full_prompt: opts?.full_prompt || null,
      persona_lock: opts?.persona_lock ?? true,
      identity_overrides: opts?.identity_overrides || null,
      negative_prompt: opts?.negative_prompt || null,
      width: opts?.width ?? 640,
      height: opts?.height ?? 384,
      length: opts?.length ?? 49,
      steps: opts?.steps ?? 20,
      cfg: opts?.cfg ?? 6.0,
      start_image: opts?.start_image || null,
      lora_name: opts?.lora_name || null,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Shadow-Wirk video generation failed" }));
    throw new Error(err.detail || "Shadow-Wirk video generation failed");
  }
  return res.json();
}

export async function checkVideoStatusRemote(
  shadowUrl: string,
  contentId: number
): Promise<{ status: string; progress?: number; outputs: any[] }> {
  const res = await fetch(`${shadowUrl}/video-status/${contentId}`);
  if (!res.ok) throw new Error("Failed to check Shadow-Wirk video status");
  return res.json();
}

export async function syncRemoteVideo(
  remoteContentId: number
): Promise<{ id: number; status: string; vault_path: string; output_path?: string }> {
  const res = await fetch(`${API}/sync-remote-video/${remoteContentId}`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Sync failed" }));
    throw new Error(err.detail || "Failed to sync remote video");
  }
  return res.json();
}

export async function uploadVideoStartImageRemote(
  shadowUrl: string,
  file: File
): Promise<{ comfy_image_name: string }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${shadowUrl}/upload-video-start-image`, { method: "POST", body: form });
  if (!res.ok) throw new Error("Failed to upload image to Shadow-Wirk");
  return res.json();
}

export async function pingShadowHealth(): Promise<{ comfyui: boolean; latency_ms: number } | null> {
  try {
    const t0 = performance.now();
    const res = await fetch(`${API}/shadow/health`, { signal: AbortSignal.timeout(12000) });
    if (!res.ok) return null;
    const data = await res.json();
    // Use server-measured latency if available, fall back to round-trip
    const latency = data.latency_ms ?? Math.round(performance.now() - t0);
    return { comfyui: data.comfyui ?? false, latency_ms: latency };
  } catch {
    return null;
  }
}

export async function refineVideoPrompt(
  prompt: string,
  intensity: "light" | "medium" | "heavy" = "medium",
  personaDescription?: string
): Promise<{ original?: string; refined: string; model?: string }> {
  const res = await fetch(`${VIDEO_API}/refine-video-prompt`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, intensity, persona_description: personaDescription || null }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Video refine failed" }));
    throw new Error(err.detail || `Video refine failed (${res.status})`);
  }
  return res.json();
}

// ─── Vault ────────────────────────

export async function fetchVault(opts?: { persona_id?: number; favorites_only?: boolean; tag?: string }): Promise<VaultItem[]> {
  const params = new URLSearchParams();
  if (opts?.persona_id) params.set("persona_id", String(opts.persona_id));
  if (opts?.favorites_only) params.set("favorites_only", "true");
  if (opts?.tag) params.set("tag", opts.tag);
  const res = await fetch(`${API}/vault/?${params}`);
  if (!res.ok) throw new Error("Failed to fetch vault");
  return res.json();
}

export async function toggleFavorite(contentId: number): Promise<{ is_favorite: boolean }> {
  const res = await fetch(`${API}/vault/${contentId}/favorite`, { method: "PATCH" });
  if (!res.ok) throw new Error("Failed to toggle favorite");
  return res.json();
}

export async function fetchVaultStats(): Promise<any> {
  const res = await fetch(`${API}/vault/stats`);
  if (!res.ok) throw new Error("Failed to fetch vault stats");
  return res.json();
}

// ─── Analytics ────────────────────

export async function addAnalytics(data: {
  persona_id: number;
  date: string;
  platform: string;
  subscribers?: number;
  revenue?: number;
  tips?: number;
}): Promise<any> {
  const res = await fetch(`${API}/analytics/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to add analytics");
  return res.json();
}

export async function fetchAnalyticsSummary(): Promise<AnalyticsSummary> {
  const res = await fetch(`${API}/analytics/summary`);
  if (!res.ok) throw new Error("Failed to fetch analytics");
  return res.json();
}

// ─── Links ────────────────────────

export async function fetchLinks(): Promise<Link[]> {
  const res = await fetch(`${API}/links/`);
  if (!res.ok) throw new Error("Failed to fetch links");
  return res.json();
}

export async function createLink(data: { platform: string; url: string }): Promise<Link> {
  const res = await fetch(`${API}/links/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to create link");
  return res.json();
}

export async function deleteLink(id: number): Promise<void> {
  await fetch(`${API}/links/${id}`, { method: "DELETE" });
}

// ─── Presets ──────────────────────

export interface ScenePreset {
  id: string;
  label: string;
  prompt: string;
}

export interface ContentSetPreset {
  id: string;
  label: string;
  name: string;
  prompt: string;
  set_size: number;
  description: string;
}

export interface VideoPreset {
  id: string;
  label: string;
  prompt: string;
}

export interface PersonaPreset {
  id: string;
  label: string;
  name: string;
  prompt_base: string;
}

export async function fetchScenePresets(): Promise<ScenePreset[]> {
  const res = await fetch(`${API}/presets/scenes`);
  if (!res.ok) return [];
  return res.json();
}

export async function fetchContentSetPresets(): Promise<ContentSetPreset[]> {
  const res = await fetch(`${API}/presets/content-sets`);
  if (!res.ok) return [];
  return res.json();
}

export async function fetchVideoPresets(): Promise<VideoPreset[]> {
  const res = await fetch(`${VIDEO_API}/presets/videos`);
  if (!res.ok) return [];
  return res.json();
}

// ─── Negative Prompt Presets ──────

export interface NegativePromptPreset {
  id: string;
  label: string;
  prompt: string;
  description: string;
}

export async function fetchNegativePromptPresets(): Promise<NegativePromptPreset[]> {
  const res = await fetch(`${API}/presets/negative-prompts`);
  if (!res.ok) return [];
  return res.json();
}

// ─── LoRA Discovery ───────────────

export interface InstalledLora {
  filename: string;
  name: string;
  size_mb: number;
}

export interface RecommendedLora {
  id: string;
  name: string;
  filename: string;
  description: string;
  category: string;
  installed: boolean;
}

export async function fetchLoras(): Promise<{ installed: InstalledLora[]; recommended: RecommendedLora[] }> {
  const res = await fetch(`${API}/loras`);
  if (!res.ok) return { installed: [], recommended: [] };
  return res.json();
}

export async function fetchPersonaPresets(): Promise<PersonaPreset[]> {
  const res = await fetch(`${API}/presets/personas`);
  if (!res.ok) return [];
  return res.json();
}

// ─── Voice ────────────────────────

export interface VoicePreset {
  id: string;
  label: string;
  accent: string;
  style: string;
  styles: string[];
}

export interface VoiceMood {
  persona_id: number;
  mood: string;
  prosody: { rate: string; pitch: string; volume: string };
  style: string;
}

export async function fetchVoicePresets(): Promise<VoicePreset[]> {
  const res = await fetch(`${API}/presets/voices`);
  if (!res.ok) return [];
  return res.json();
}

export async function fetchVoiceMood(personaId: number): Promise<VoiceMood | null> {
  const res = await fetch(`${API}/personas/${personaId}/voice-mood`);
  if (!res.ok) return null;
  return res.json();
}

export async function setPersonaVoice(personaId: number, voiceId: string): Promise<void> {
  await fetch(`${API}/personas/${personaId}/set-voice`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ voice_id: voiceId }),
  });
}

export async function removePersonaVoice(personaId: number): Promise<void> {
  await fetch(`${API}/personas/${personaId}/voice`, { method: "DELETE" });
}

export async function speakAsPersona(personaId: number, text: string): Promise<Blob> {
  const res = await fetch(`${API}/personas/${personaId}/speak`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) throw new Error("TTS failed");
  return res.blob();
}

export function previewVoiceUrl(personaId: number): string {
  return `${API}/personas/${personaId}/preview-voice`;
}

// ─── Health ───────────────────────

export async function fetchHealth(): Promise<{ api: string; comfyui: boolean; shadow_wirks: boolean }> {
  const res = await fetch(`${API}/health`);
  if (!res.ok) throw new Error("API unreachable");
  return res.json();
}

// ─── Prompt Refiner ───────────────

export async function refinePrompt(
  prompt: string,
  intensity: "light" | "medium" | "heavy" = "medium"
): Promise<{ original: string; refined: string; model?: string }> {
  const res = await fetch(`${API}/refine-prompt`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, intensity }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `Refine failed (${res.status})`);
  }
  return res.json();
}

// ═══════════════════════════════════════════════════════════════════
// Phase 2-4: Jobs, Campaigns, Memory, Agents, Review
// ═══════════════════════════════════════════════════════════════════

// ─── Jobs (Mission Control) ───────

export interface Job {
  id: number;
  job_type: string;
  persona_id: number | null;
  content_id: number | null;
  campaign_id: number | null;
  status: string;
  priority: number;
  payload: Record<string, any> | null;
  error: string | null;
  attempts: number;
  max_attempts: number;
  created_at: string;
  updated_at: string;
}

export interface JobStats {
  queued: number;
  running: number;
  failed: number;
  needs_review: number;
  total: number;
}

export interface EventLogEntry {
  id: number;
  subject_type: string;
  subject_id: number;
  event: string;
  actor: string | null;
  note: string | null;
  created_at: string;
}

export async function fetchJobs(opts?: {
  status?: string;
  job_type?: string;
  persona_id?: number;
  limit?: number;
}): Promise<Job[]> {
  const params = new URLSearchParams();
  if (opts?.status) params.set("status", opts.status);
  if (opts?.job_type) params.set("job_type", opts.job_type);
  if (opts?.persona_id) params.set("persona_id", String(opts.persona_id));
  if (opts?.limit) params.set("limit", String(opts.limit));
  const res = await fetch(`${API}/jobs/?${params}`);
  return res.json();
}

export async function fetchJobStats(): Promise<JobStats> {
  const res = await fetch(`${API}/jobs/stats`);
  return res.json();
}

export async function fetchJob(id: number): Promise<Job> {
  const res = await fetch(`${API}/jobs/${id}`);
  if (!res.ok) throw new Error("Job not found");
  return res.json();
}

export async function cancelJob(id: number, reason?: string): Promise<Job> {
  const res = await fetch(`${API}/jobs/${id}/cancel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
  });
  if (!res.ok) throw new Error("Cancel failed");
  return res.json();
}

export async function cancelActiveGenerations(): Promise<{ interrupted: boolean; queue_cleared: boolean; cancelled_content_ids: number[] }> {
  const res = await fetch(`${API}/generations/cancel-active`, { method: "POST" });
  if (!res.ok) throw new Error("Cancel active failed");
  return res.json();
}

export async function fetchJobEvents(id: number): Promise<EventLogEntry[]> {
  const res = await fetch(`${API}/jobs/${id}/events`);
  return res.json();
}

// ─── Campaigns ────────────────────

export interface Campaign {
  id: number;
  persona_id: number;
  name: string;
  description: string | null;
  status: string;
  total_days: number;
  current_day: number;
  config: Record<string, any> | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface CampaignTask {
  id: number;
  campaign_id: number;
  day: number;
  task_type: string;
  status: string;
  config: Record<string, any> | null;
  job_id: number | null;
  depends_on: number[] | null;
  scheduled_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
}

export async function fetchCampaigns(): Promise<Campaign[]> {
  const res = await fetch(`${API}/campaigns/`);
  return res.json();
}

export async function fetchCampaign(id: number): Promise<Campaign> {
  const res = await fetch(`${API}/campaigns/${id}`);
  if (!res.ok) throw new Error("Campaign not found");
  return res.json();
}

export async function createCampaign(data: {
  persona_id: number;
  name: string;
  description?: string;
  total_days?: number;
  config?: Record<string, any>;
}): Promise<Campaign> {
  const res = await fetch(`${API}/campaigns/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Create campaign failed");
  return res.json();
}

export async function startCampaign(id: number): Promise<Campaign> {
  const res = await fetch(`${API}/campaigns/${id}/start`, { method: "POST" });
  if (!res.ok) throw new Error("Start campaign failed");
  return res.json();
}

export async function cancelCampaign(id: number): Promise<Campaign> {
  const res = await fetch(`${API}/campaigns/${id}/cancel`, { method: "POST" });
  if (!res.ok) throw new Error("Cancel campaign failed");
  return res.json();
}

export async function fetchCampaignTasks(id: number): Promise<CampaignTask[]> {
  const res = await fetch(`${API}/campaigns/${id}/tasks`);
  return res.json();
}

export async function generateCampaignPlan(id: number): Promise<{ tasks_created: number; plan: any }> {
  const res = await fetch(`${API}/campaigns/${id}/plan`, { method: "POST" });
  if (!res.ok) throw new Error("Plan generation failed");
  return res.json();
}

// ─── Persona Memory ───────────────

export interface PersonaMemoryEntry {
  id: number;
  persona_id: number;
  partition: string;
  key: string;
  value: Record<string, any>;
  source: string | null;
  created_at: string;
  updated_at: string;
}

export async function fetchPersonaMemory(
  personaId: number,
  partition?: string
): Promise<PersonaMemoryEntry[]> {
  const params = partition ? `?partition=${partition}` : "";
  const res = await fetch(`${API}/persona-memory/${personaId}${params}`);
  return res.json();
}

export async function upsertPersonaMemory(data: {
  persona_id: number;
  partition: string;
  key: string;
  value: Record<string, any>;
  source?: string;
}): Promise<PersonaMemoryEntry> {
  const res = await fetch(`${API}/persona-memory/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Upsert memory failed");
  return res.json();
}

export async function deletePersonaMemory(id: number): Promise<void> {
  await fetch(`${API}/persona-memory/${id}`, { method: "DELETE" });
}

// ─── Agents ───────────────────────

export interface AgentRun {
  id: number;
  agent_type: string;
  persona_id: number | null;
  campaign_id: number | null;
  input_payload: Record<string, any> | null;
  output_payload: Record<string, any> | null;
  model_used: string | null;
  duration_seconds: number | null;
  status: string;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

export async function invokePlanner(data: {
  persona_id: number;
  total_days?: number;
  slots_per_day?: number;
  notes?: string;
}): Promise<any> {
  const res = await fetch(`${API}/agents/planner`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Planner failed");
  return res.json();
}

export async function invokeCreative(data: {
  persona_id?: number;
  brief: string;
  content_type?: string;
}): Promise<any> {
  const res = await fetch(`${API}/agents/creative`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Creative agent failed");
  return res.json();
}

export async function invokeAnalyst(data: {
  persona_id?: number;
  metrics_summary: Record<string, any>;
}): Promise<any> {
  const res = await fetch(`${API}/agents/analyst`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Analyst failed");
  return res.json();
}

export async function fetchAgentRuns(opts?: {
  agent_type?: string;
  persona_id?: number;
  limit?: number;
}): Promise<AgentRun[]> {
  const params = new URLSearchParams();
  if (opts?.agent_type) params.set("agent_type", opts.agent_type);
  if (opts?.persona_id) params.set("persona_id", String(opts.persona_id));
  if (opts?.limit) params.set("limit", String(opts.limit));
  const res = await fetch(`${API}/agents/runs?${params}`);
  return res.json();
}

// ─── Review Inbox ─────────────────

export interface ReviewItem {
  content: {
    id: number;
    persona_id: number | null;
    file_path: string | null;
    upscaled_path: string | null;
    prompt_used: string | null;
    tags: string | null;
    created_at: string;
  };
  score: {
    id: number;
    aesthetic: number;
    persona_consistency: number;
    prompt_adherence: number;
    artifact_penalty: number;
    novelty: number;
    overall: number;
    verdict: string;
    notes: string | null;
  } | null;
}

export async function fetchReviewInbox(opts?: {
  verdict?: string;
  persona_id?: number;
  limit?: number;
}): Promise<ReviewItem[]> {
  const params = new URLSearchParams();
  if (opts?.verdict) params.set("verdict", opts.verdict);
  if (opts?.persona_id) params.set("persona_id", String(opts.persona_id));
  if (opts?.limit) params.set("limit", String(opts.limit));
  const res = await fetch(`${API}/review/inbox?${params}`);
  return res.json();
}

export async function scoreContent(contentId: number): Promise<any> {
  const res = await fetch(`${API}/review/${contentId}/score`, { method: "POST" });
  if (!res.ok) throw new Error("Scoring failed");
  return res.json();
}

export async function reviewAction(
  contentId: number,
  action: "approve" | "reject" | "rerun",
  notes?: string
): Promise<any> {
  const res = await fetch(`${API}/review/${contentId}/action`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, notes }),
  });
  if (!res.ok) throw new Error("Review action failed");
  return res.json();
}

// ─── Metrics ──────────────────────

export interface ContentMetrics {
  id: number;
  content_id: number;
  platform: string;
  views: number;
  likes: number;
  comments: number;
  tips: number;
  unlocks: number;
  saves: number;
  collected_at: string;
}

export interface ContentMetricsSummary {
  total_views: number;
  total_likes: number;
  total_comments: number;
  total_tips: number;
  total_unlocks: number;
  count: number;
}

export interface PersonaMetricsDaily {
  id: number;
  persona_id: number;
  date: string;
  platform: string;
  new_subscribers: number;
  churned_subscribers: number;
  revenue: number;
  tips: number;
  messages_received: number;
  messages_sent: number;
  content_posted: number;
  avg_engagement_rate: number;
}

export interface PersonaMetricsSummary {
  total_revenue: number;
  total_tips: number;
  net_subscribers: number;
  total_content_posted: number;
  days_tracked: number;
}

export interface CampaignMetricsEntry {
  id: number;
  campaign_id: number;
  day: number;
  content_produced: number;
  content_approved: number;
  content_rejected: number;
  content_posted: number;
  revenue_attributed: number;
  new_subscribers: number;
  total_engagement: number;
  collected_at: string;
}

export interface CampaignMetricsSummary {
  total_produced: number;
  total_approved: number;
  total_posted: number;
  total_revenue: number;
  days_tracked: number;
}

export interface GenerationCost {
  id: number;
  job_id: number | null;
  machine: string;
  job_type: string;
  duration_seconds: number;
  estimated_cost_usd: number;
  model_used: string | null;
  created_at: string;
}

export interface CostSummary {
  total_cost_usd: number;
  total_jobs: number;
  avg_duration_seconds: number;
  by_machine: Record<string, { count: number; cost: number }>;
  by_type: Record<string, { count: number; cost: number }>;
}

export async function fetchContentMetrics(contentId: number): Promise<ContentMetrics[]> {
  const res = await fetch(`${API}/metrics/content/${contentId}`);
  return res.json();
}

export async function fetchContentMetricsSummary(platform?: string): Promise<ContentMetricsSummary> {
  const params = platform ? `?platform=${platform}` : "";
  const res = await fetch(`${API}/metrics/content-summary${params}`);
  return res.json();
}

export async function fetchPersonaMetrics(personaId: number, opts?: { platform?: string; limit?: number }): Promise<PersonaMetricsDaily[]> {
  const params = new URLSearchParams();
  if (opts?.platform) params.set("platform", opts.platform);
  if (opts?.limit) params.set("limit", String(opts.limit));
  const res = await fetch(`${API}/metrics/persona/${personaId}?${params}`);
  return res.json();
}

export async function fetchPersonaMetricsSummary(personaId: number): Promise<PersonaMetricsSummary> {
  const res = await fetch(`${API}/metrics/persona-summary/${personaId}`);
  return res.json();
}

export async function fetchCampaignMetrics(campaignId: number): Promise<CampaignMetricsEntry[]> {
  const res = await fetch(`${API}/metrics/campaign/${campaignId}`);
  return res.json();
}

export async function fetchCampaignMetricsSummary(campaignId: number): Promise<CampaignMetricsSummary> {
  const res = await fetch(`${API}/metrics/campaign-summary/${campaignId}`);
  return res.json();
}

export async function fetchCostMetrics(opts?: { machine?: string; job_type?: string; limit?: number }): Promise<GenerationCost[]> {
  const params = new URLSearchParams();
  if (opts?.machine) params.set("machine", opts.machine);
  if (opts?.job_type) params.set("job_type", opts.job_type);
  if (opts?.limit) params.set("limit", String(opts.limit));
  const res = await fetch(`${API}/metrics/cost?${params}`);
  return res.json();
}

export async function fetchCostSummary(): Promise<CostSummary> {
  const res = await fetch(`${API}/metrics/cost-summary`);
  return res.json();
}

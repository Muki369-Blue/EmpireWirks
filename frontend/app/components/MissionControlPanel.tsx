"use client";

import { useState, useEffect, useCallback } from "react";
import {
  fetchJobs,
  fetchJobStats,
  fetchElevenLabsWebhookEvents,
  cancelJob,
  fetchCampaigns,
  createCampaign,
  startCampaign,
  cancelCampaign,
  generateCampaignPlan,
  fetchCampaignTasks,
  imageUrl,
  Job,
  JobStats,
  Campaign,
  CampaignTask,
  ElevenLabsWebhookEvent,
  Persona,
} from "../lib/api";

/* ─── Sub-views ──────────────────────────────────────────────────── */
type View = "queue" | "campaigns";

const STATUS_COLORS: Record<string, string> = {
  queued: "bg-yellow-500/20 text-yellow-400",
  dispatching: "bg-blue-500/20 text-blue-400",
  running: "bg-blue-500/30 text-blue-300",
  postprocessing: "bg-purple-500/20 text-purple-400",
  scoring: "bg-indigo-500/20 text-indigo-400",
  needs_review: "bg-orange-500/20 text-orange-400",
  approved: "bg-green-500/20 text-green-400",
  scheduled: "bg-cyan-500/20 text-cyan-400",
  published: "bg-green-600/20 text-green-300",
  failed: "bg-red-500/20 text-red-400",
  cancelled: "bg-gray-500/20 text-gray-400",
  draft: "bg-gray-500/20 text-gray-400",
  active: "bg-green-500/20 text-green-400",
  paused: "bg-yellow-500/20 text-yellow-400",
  completed: "bg-green-600/20 text-green-300",
  pending: "bg-gray-500/20 text-gray-400",
};

function Badge({ status }: { status: string }) {
  const cls = STATUS_COLORS[status] || "bg-gray-500/20 text-gray-400";
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}

export default function MissionControlPanel({ personas }: { personas: Persona[] }) {
  const [view, setView] = useState<View>("queue");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [stats, setStats] = useState<JobStats | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [selectedCampaign, setSelectedCampaign] = useState<Campaign | null>(null);
  const [tasks, setTasks] = useState<CampaignTask[]>([]);
  const [webhookEvents, setWebhookEvents] = useState<ElevenLabsWebhookEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState("");

  /* ─── New Campaign form ────────────── */
  const [showNewCampaign, setShowNewCampaign] = useState(false);
  const [newName, setNewName] = useState("");
  const [newPersonaId, setNewPersonaId] = useState<number>(personas[0]?.id ?? 0);
  const [newDays, setNewDays] = useState(4);
  const [newDesc, setNewDesc] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      if (view === "queue") {
        const [j, s] = await Promise.all([
          fetchJobs({ status: filter || undefined, limit: 100 }),
          fetchJobStats(),
        ]);
        setJobs(j);
        setStats(s);
        const hooks = await fetchElevenLabsWebhookEvents({ limit: 8 });
        setWebhookEvents(hooks);
      } else {
        const c = await fetchCampaigns();
        setCampaigns(c);
      }
    } finally {
      setLoading(false);
    }
  }, [view, filter]);

  useEffect(() => {
    refresh();
    const iv = setInterval(refresh, 8000);
    return () => clearInterval(iv);
  }, [refresh]);

  /* ─── Handlers ─────────────────────── */
  async function handleCancelJob(id: number) {
    await cancelJob(id);
    refresh();
  }

  async function handleCreateCampaign() {
    if (!newName) return;
    await createCampaign({
      persona_id: newPersonaId,
      name: newName,
      description: newDesc || undefined,
      total_days: newDays,
    });
    setShowNewCampaign(false);
    setNewName("");
    setNewDesc("");
    refresh();
  }

  async function handleStartCampaign(id: number) {
    await startCampaign(id);
    refresh();
  }

  async function handleCancelCampaign(id: number) {
    await cancelCampaign(id);
    refresh();
  }

  async function handlePlanCampaign(id: number) {
    setLoading(true);
    try {
      await generateCampaignPlan(id);
      if (selectedCampaign?.id === id) {
        setTasks(await fetchCampaignTasks(id));
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleSelectCampaign(c: Campaign) {
    setSelectedCampaign(c);
    setTasks(await fetchCampaignTasks(c.id));
  }

  const personaName = (pid: number | null) =>
    personas.find((p) => p.id === pid)?.name ?? "—";

  /* ─── Render ───────────────────────── */
  return (
    <div className="space-y-4">
      {/* Tab bar */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setView("queue")}
          className={`px-3 py-1.5 rounded text-sm font-medium ${
            view === "queue" ? "bg-white/10 text-white" : "text-gray-400 hover:text-white"
          }`}
        >
          Job Queue
        </button>
        <button
          onClick={() => setView("campaigns")}
          className={`px-3 py-1.5 rounded text-sm font-medium ${
            view === "campaigns" ? "bg-white/10 text-white" : "text-gray-400 hover:text-white"
          }`}
        >
          Campaigns
        </button>
        <div className="flex-1" />
        <button onClick={refresh} className="text-sm text-blue-400 hover:underline">
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>

      {/* ─── Job Queue View ─────────────── */}
      {view === "queue" && (
        <>
          {/* Stats bar */}
          {stats && (
            <div className="grid grid-cols-5 gap-2 text-center text-xs">
              {(["queued", "running", "failed", "needs_review", "total"] as const).map((k) => (
                <div key={k} className="bg-white/5 rounded p-2">
                  <div className="text-lg font-bold text-white">{stats[k]}</div>
                  <div className="text-gray-400">{k.replace("_", " ")}</div>
                </div>
              ))}
            </div>
          )}

          <div className="bg-white/5 rounded p-3">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold text-white">ElevenLabs Webhooks</h3>
              <span className="text-[11px] text-gray-400">latest {webhookEvents.length}</span>
            </div>
            <div className="space-y-2 max-h-44 overflow-y-auto">
              {webhookEvents.length === 0 && (
                <div className="text-xs text-gray-500">No webhook events yet.</div>
              )}
              {webhookEvents.map((ev) => (
                <div key={ev.id} className="bg-black/20 border border-white/10 rounded p-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[11px] text-cyan-300">{ev.event_type}</span>
                    <span className="text-[10px] text-gray-500">{new Date(ev.created_at).toLocaleString()}</span>
                  </div>
                  {ev.transcription_text && (
                    <p className="text-xs text-gray-300 mt-1 line-clamp-2">{ev.transcription_text}</p>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Filter */}
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="bg-white/5 border border-white/10 rounded px-2 py-1 text-sm text-white w-full"
          >
            <option value="">All Statuses</option>
            {["queued", "running", "failed", "needs_review", "approved", "published", "cancelled"].map(
              (s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              )
            )}
          </select>

          {/* Job list */}
          <div className="space-y-2 max-h-[60vh] overflow-y-auto">
            {jobs.length === 0 && (
              <p className="text-gray-500 text-sm text-center py-8">No jobs found</p>
            )}
            {jobs.map((j) => (
              <div
                key={j.id}
                className="bg-white/5 rounded p-3 flex items-center gap-3 text-sm"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-white">#{j.id}</span>
                    <Badge status={j.status} />
                    <span className="text-gray-400">{j.job_type}</span>
                  </div>
                  <div className="text-gray-500 text-xs mt-0.5">
                    {personaName(j.persona_id)} · attempt {j.attempts}/{j.max_attempts} ·{" "}
                    {new Date(j.created_at).toLocaleString()}
                  </div>
                  {j.error && (
                    <div className="text-red-400 text-xs mt-1 truncate">{j.error}</div>
                  )}
                </div>
                {!["published", "cancelled", "failed"].includes(j.status) && (
                  <button
                    onClick={() => handleCancelJob(j.id)}
                    className="text-red-400 hover:text-red-300 text-xs shrink-0"
                  >
                    Cancel
                  </button>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      {/* ─── Campaigns View ─────────────── */}
      {view === "campaigns" && (
        <>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowNewCampaign((v) => !v)}
              className="bg-blue-600 hover:bg-blue-500 text-white text-sm px-3 py-1.5 rounded"
            >
              + New Campaign
            </button>
          </div>

          {/* New campaign form */}
          {showNewCampaign && (
            <div className="bg-white/5 rounded p-4 space-y-3">
              <input
                placeholder="Campaign name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="w-full bg-black/30 border border-white/10 rounded px-3 py-2 text-sm text-white"
              />
              <select
                value={newPersonaId}
                onChange={(e) => setNewPersonaId(Number(e.target.value))}
                className="w-full bg-black/30 border border-white/10 rounded px-3 py-2 text-sm text-white"
              >
                {personas.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <div className="flex gap-2">
                <input
                  type="number"
                  min={1}
                  max={30}
                  value={newDays}
                  onChange={(e) => setNewDays(Number(e.target.value))}
                  className="w-24 bg-black/30 border border-white/10 rounded px-3 py-2 text-sm text-white"
                />
                <span className="text-gray-400 text-sm self-center">days</span>
              </div>
              <textarea
                placeholder="Description (optional)"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                rows={2}
                className="w-full bg-black/30 border border-white/10 rounded px-3 py-2 text-sm text-white"
              />
              <button
                onClick={handleCreateCampaign}
                className="bg-green-600 hover:bg-green-500 text-white text-sm px-4 py-1.5 rounded"
              >
                Create
              </button>
            </div>
          )}

          {/* Campaign list + detail */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2 max-h-[55vh] overflow-y-auto">
              {campaigns.map((c) => (
                <div
                  key={c.id}
                  onClick={() => handleSelectCampaign(c)}
                  className={`p-3 rounded cursor-pointer text-sm ${
                    selectedCampaign?.id === c.id
                      ? "bg-white/10 border border-white/20"
                      : "bg-white/5 hover:bg-white/8"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-white font-medium">{c.name}</span>
                    <Badge status={c.status} />
                  </div>
                  <div className="text-gray-500 text-xs mt-1">
                    {personaName(c.persona_id)} · Day {c.current_day}/{c.total_days}
                  </div>
                </div>
              ))}
            </div>

            {/* Campaign detail */}
            {selectedCampaign && (
              <div className="bg-white/5 rounded p-4 space-y-3 max-h-[55vh] overflow-y-auto">
                <h3 className="text-white font-medium">{selectedCampaign.name}</h3>
                <div className="flex gap-2 text-xs">
                  <Badge status={selectedCampaign.status} />
                  <span className="text-gray-400">
                    Day {selectedCampaign.current_day}/{selectedCampaign.total_days}
                  </span>
                </div>
                {selectedCampaign.description && (
                  <p className="text-gray-400 text-sm">{selectedCampaign.description}</p>
                )}

                {/* Campaign actions */}
                <div className="flex gap-2">
                  {selectedCampaign.status === "draft" && (
                    <>
                      <button
                        onClick={() => handlePlanCampaign(selectedCampaign.id)}
                        className="bg-purple-600 hover:bg-purple-500 text-white text-xs px-3 py-1 rounded"
                      >
                        🤖 Auto-Plan
                      </button>
                      <button
                        onClick={() => handleStartCampaign(selectedCampaign.id)}
                        className="bg-green-600 hover:bg-green-500 text-white text-xs px-3 py-1 rounded"
                      >
                        ▶ Start
                      </button>
                    </>
                  )}
                  {["draft", "active", "paused"].includes(selectedCampaign.status) && (
                    <button
                      onClick={() => handleCancelCampaign(selectedCampaign.id)}
                      className="bg-red-600 hover:bg-red-500 text-white text-xs px-3 py-1 rounded"
                    >
                      Cancel
                    </button>
                  )}
                </div>

                {/* Task list */}
                <div className="space-y-1.5">
                  <h4 className="text-gray-400 text-xs font-medium uppercase">Tasks</h4>
                  {tasks.length === 0 && (
                    <p className="text-gray-500 text-xs">No tasks yet. Use Auto-Plan to generate.</p>
                  )}
                  {tasks.map((t) => (
                    <div
                      key={t.id}
                      className="bg-black/30 rounded px-3 py-2 text-xs flex items-center gap-2"
                    >
                      <span className="text-gray-500">D{t.day}</span>
                      <Badge status={t.status} />
                      <span className="text-gray-300">{t.task_type}</span>
                      {t.config?.prompt && (
                        <span className="text-gray-500 truncate flex-1">
                          {(t.config.prompt as string).slice(0, 60)}…
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

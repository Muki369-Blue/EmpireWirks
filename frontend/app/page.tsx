"use client";

import { useState, useEffect, useCallback } from "react";
import PersonaForm from "./components/PersonaForm";
import GenerationPanel from "./components/GenerationPanel";
import LinkManager from "./components/LinkManager";
import SchedulePanel from "./components/SchedulePanel";
import ChatPanel from "./components/ChatPanel";
import VaultPanel from "./components/VaultPanel";
import AnalyticsPanel from "./components/AnalyticsPanel";
import ContentSetPanel from "./components/ContentSetPanel";
import ShadowVidPanel from "./components/ShadowVidPanel";
import AnimatedPreview from "./components/AnimatedPreview";
import MissionControlPanel from "./components/MissionControlPanel";
import ReviewInboxPanel from "./components/ReviewInboxPanel";
import AgentPanel from "./components/AgentPanel";
import PersonaMemoryPanel from "./components/PersonaMemoryPanel";
import MetricsPanel from "./components/MetricsPanel";
import VoiceCoachPanel from "./components/VoiceCoachPanel";
import {
  API,
  pingShadowHealth,
  fetchPersonas,
  fetchLinks,
  fetchHealth,
  fetchGenerations,
  deletePersona,
  imageUrl,
  referenceImageUrl,
  uploadReferenceImage,
  deleteReferenceImage,
  fetchVoicePresets,
  setPersonaVoice,
  removePersonaVoice,
  fetchVoiceMood,
  type Persona,
  type Link,
  type Generation,
  type VoicePreset,
  type VoiceMood,
} from "./lib/api";

// Tab groups follow the content lifecycle: Setup → Create → Curate → Distribute → Operate
const TAB_GROUPS = [
  {
    label: "Setup",
    tabs: [
      { id: "personas", label: "Personas", icon: "👤" },
    ],
  },
  {
    label: "Create",
    tabs: [
      { id: "generate", label: "Generate", icon: "⚡" },
      { id: "shadowvid", label: "ShadowVid", icon: "🎥" },
      { id: "sets", label: "Sets", icon: "📸" },
    ],
  },
  {
    label: "Curate",
    tabs: [
      { id: "review", label: "Review", icon: "✅" },
      { id: "vault", label: "Vault", icon: "🔒" },
    ],
  },
  {
    label: "Distribute",
    tabs: [
      { id: "schedule", label: "Calendar", icon: "📅" },
      { id: "chat", label: "Fan Chat", icon: "💬" },
    ],
  },
  {
    label: "Operate",
    tabs: [
      { id: "mission", label: "Mission", icon: "🎯" },
      { id: "agents", label: "Agents", icon: "🤖" },
      { id: "analytics", label: "Analytics", icon: "📊" },
      { id: "metrics", label: "Metrics", icon: "💰" },
      { id: "memory", label: "Memory", icon: "🧠" },
    ],
  },
] as const;

const TABS: Array<(typeof TAB_GROUPS)[number]["tabs"][number]> = TAB_GROUPS.flatMap((g) => [...g.tabs]);
type TabId = (typeof TAB_GROUPS)[number]["tabs"][number]["id"];

export default function Dashboard() {
  const [tab, setTab] = useState<TabId>("personas");
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [links, setLinks] = useState<Link[]>([]);
  const [generations, setGenerations] = useState<Generation[]>([]);
  const [health, setHealth] = useState<{ api: string; comfyui: boolean; shadow_wirks: boolean } | null>(null);
  const [loading, setLoading] = useState(true);
  const [openFolder, setOpenFolder] = useState<number | null>(null);
  const [voicePresets, setVoicePresets] = useState<VoicePreset[]>([]);
  const [playingPreview, setPlayingPreview] = useState<number | null>(null);
  const [voiceMoods, setVoiceMoods] = useState<Record<number, VoiceMood>>({});
  const [lightbox, setLightbox] = useState<{ src: string; prompt: string } | null>(null);
  const [shadowPing, setShadowPing] = useState<{ latency: number; comfyui: boolean } | null>(null);
  const [shadowPinging, setShadowPinging] = useState(false);
  const [showShadowPanel, setShowShadowPanel] = useState(false);

  const activeCount = generations.filter((g) => g.status === "generating").length;
  const completedCount = generations.filter((g) => g.status === "completed").length;

  const pingShadow = useCallback(async () => {
    setShadowPinging(true);
    try {
      const result = await pingShadowHealth();
      if (result) {
        setShadowPing({ latency: result.latency_ms, comfyui: result.comfyui });
      } else {
        setShadowPing(null);
      }
    } catch {
      setShadowPing(null);
    } finally {
      setShadowPinging(false);
    }
  }, []);

  const refresh = useCallback(async () => {
    try {
      const [p, l, g, h] = await Promise.all([
        fetchPersonas(),
        fetchLinks(),
        fetchGenerations(),
        fetchHealth(),
      ]);
      setPersonas(p);
      setLinks(l);
      setGenerations(g);
      setHealth(h);
    } catch {
      // API not running yet
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    fetchVoicePresets().then(setVoicePresets);
  }, [refresh]);

  // Fetch voice moods for personas with voices
  useEffect(() => {
    personas.filter(p => p.voice).forEach(async (p) => {
      if (!voiceMoods[p.id]) {
        const mood = await fetchVoiceMood(p.id);
        if (mood) setVoiceMoods(prev => ({ ...prev, [p.id]: mood }));
      }
    });
  }, [personas]);

  // Auto-poll when there are active generations
  useEffect(() => {
    const hasActive = generations.some((g) => g.status === "generating");
    if (!hasActive) return;
    const interval = setInterval(refresh, 4000);
    return () => clearInterval(interval);
  }, [generations, refresh]);

  // Escape key closes lightbox
  useEffect(() => {
    if (!lightbox) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") setLightbox(null); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [lightbox]);

  const handleDeletePersona = async (id: number) => {
    await deletePersona(id);
    refresh();
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-zinc-500 animate-pulse">Connecting to Empire...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-6 md:p-10 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl md:text-4xl font-bold bg-gradient-to-r from-purple-400 to-pink-500 bg-clip-text text-transparent">
            AI Content Empire
          </h1>
          <p className="text-zinc-500 text-sm mt-1">Create &middot; Curate &middot; Distribute &middot; Scale</p>
        </div>

        {/* Status indicators */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs">
            <span
              className={`w-2 h-2 rounded-full ${
                health?.api === "ok" ? "bg-emerald-400" : "bg-red-400"
              }`}
            />
            <span className="text-zinc-400">API</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs">
            <span
              className={`w-2 h-2 rounded-full ${
                health?.comfyui ? "bg-emerald-400" : "bg-red-400"
              }`}
            />
            <span className="text-zinc-400">ComfyUI</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs relative">
            <button
              onClick={() => { setShowShadowPanel((v) => !v); if (!shadowPing && !shadowPinging) pingShadow(); }}
              className="flex items-center gap-1.5 hover:opacity-80 transition-opacity"
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  health?.shadow_wirks ? "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.5)]" : "bg-zinc-600"
                }`}
              />
              <span className="text-zinc-400">Shadow-Wirk</span>
            </button>
            {showShadowPanel && (
              <div className="absolute top-7 right-0 z-50 bg-zinc-900 border border-zinc-700 rounded-lg p-3 shadow-xl min-w-[240px]">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-zinc-200">Shadow-Wirk GPU</span>
                  <button onClick={() => setShowShadowPanel(false)} className="text-zinc-500 hover:text-zinc-300 text-xs">✕</button>
                </div>
                <div className="text-[11px] space-y-1.5">
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Status</span>
                    <span className={health?.shadow_wirks ? "text-emerald-400" : "text-red-400"}>
                      {health?.shadow_wirks ? "● Connected" : "● Offline"}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Host</span>
                    <span className="text-zinc-300 font-mono">100.119.54.18</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-500">GPU</span>
                    <span className="text-zinc-300">RTX A4500 20GB</span>
                  </div>
                  {shadowPing && (
                    <>
                      <div className="flex justify-between">
                        <span className="text-zinc-500">Latency</span>
                        <span className={shadowPing.latency < 200 ? "text-emerald-400" : shadowPing.latency < 500 ? "text-yellow-400" : "text-red-400"}>
                          {shadowPing.latency}ms
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-zinc-500">ComfyUI</span>
                        <span className={shadowPing.comfyui ? "text-emerald-400" : "text-red-400"}>
                          {shadowPing.comfyui ? "● Running" : "● Down"}
                        </span>
                      </div>
                    </>
                  )}
                  {shadowPinging && (
                    <div className="text-center text-zinc-500 animate-pulse">Pinging...</div>
                  )}
                  {!shadowPing && !shadowPinging && !health?.shadow_wirks && (
                    <div className="text-center text-zinc-500">Unreachable via Tailscale</div>
                  )}
                </div>
                <button
                  onClick={pingShadow}
                  disabled={shadowPinging}
                  className="mt-2 w-full text-[10px] py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 disabled:opacity-50 transition-colors"
                >
                  {shadowPinging ? "Pinging..." : "🔄 Ping Again"}
                </button>
              </div>
            )}
          </div>
          <button
            className="text-[10px] text-zinc-500 hover:text-orange-300 bg-zinc-800/50 hover:bg-orange-900/30 px-2 py-1 rounded transition-colors"
            title="Unload all models from GPU/RAM to free memory"
            onClick={async () => {
              try {
                const res = await fetch(`${API}/system/cleanup`, { method: "POST" });
                if (res.ok) {
                  const data = await res.json();
                  const mem = data.memory ? ` — ${data.memory.vram_free_mb}MB free` : "";
                  alert(`Memory cleaned!\nComfyUI: ${data.comfyui_freed ? "✓" : "✗"}\nOllama: ${data.ollama_freed ? "✓" : "✗"}${mem}`);
                }
              } catch { alert("Cleanup failed — backend may be down"); }
            }}
          >
            🧹 Free Memory
          </button>
        </div>
      </div>

      {/* Tab Navigation — grouped by workflow stage */}
      <div className="flex items-center gap-1 mb-6 overflow-x-auto pb-1">
        {TAB_GROUPS.map((group, gi) => (
          <div key={group.label} className="flex items-center">
            {gi > 0 && <div className="w-px h-6 bg-zinc-800 mx-1.5 flex-shrink-0" />}
            <div className="flex gap-0.5">
              {group.tabs.map((t) => (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all ${
                    tab === t.id
                      ? "bg-gradient-to-r from-purple-600/30 to-pink-600/30 text-white border border-purple-500/40"
                      : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50 border border-transparent"
                  }`}
                >
                  <span className="text-sm">{t.icon}</span>
                  {t.label}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* ─── Personas Tab ─── */}
      <div className={tab === "personas" ? "" : "hidden"}>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          <PersonaForm onCreated={refresh} />
          <LinkManager links={links} onChanged={refresh} />
        </div>

        <section>
          <h2 className="text-xl font-bold mb-4">Active Personas</h2>
          {personas.length === 0 ? (
            <p className="text-zinc-500 text-sm">No personas yet. Create one above.</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {personas.map((p) => (
                <div
                  key={p.id}
                  className="bg-zinc-900 p-4 rounded-xl border border-zinc-800 hover:border-purple-600/40 transition-colors group"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      {p.reference_image ? (
                        <img
                          src={referenceImageUrl(p.id)}
                          alt=""
                          className="w-10 h-10 rounded-full object-cover border-2 border-purple-500/50"
                        />
                      ) : (
                        <div className="w-10 h-10 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center text-zinc-500 text-sm">
                          👤
                        </div>
                      )}
                      <div>
                        <h3 className="font-semibold text-sm">{p.name}</h3>
                        <p className="text-zinc-500 text-[10px]">
                          {generations.filter((g) => g.persona_id === p.id && g.status === "completed").length} generations
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => handleDeletePersona(p.id)}
                      className="text-zinc-600 hover:text-red-400 text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      Delete
                    </button>
                  </div>
                  <p className="text-zinc-400 text-xs mt-2 line-clamp-2">
                    {p.prompt_base}
                  </p>
                  <div className="flex flex-wrap gap-1.5 mt-3">
                    {p.lora_name && (
                      <span className="text-[10px] text-purple-300 bg-purple-900/30 px-2 py-0.5 rounded">
                        LoRA: {p.lora_name}
                      </span>
                    )}
                    {p.reference_image ? (
                      <span
                        className="text-[10px] text-emerald-300 bg-emerald-900/30 px-2 py-0.5 rounded cursor-pointer hover:bg-red-900/30 hover:text-red-300 transition-colors"
                        title="Click to remove face reference"
                        onClick={async (e) => {
                          e.stopPropagation();
                          await deleteReferenceImage(p.id);
                          refresh();
                        }}
                      >
                        🎭 Face Ref ✓
                      </span>
                    ) : (
                      <label
                        className="text-[10px] text-zinc-400 bg-zinc-800 px-2 py-0.5 rounded cursor-pointer hover:bg-purple-900/30 hover:text-purple-300 transition-colors"
                        title="Upload face reference for consistent identity"
                      >
                        🎭 Add Face Ref
                        <input
                          type="file"
                          accept="image/png,image/jpeg,image/webp"
                          className="hidden"
                          onChange={async (e) => {
                            const file = e.target.files?.[0];
                            if (file) {
                              await uploadReferenceImage(p.id, file);
                              refresh();
                            }
                          }}
                        />
                      </label>
                    )}
                    {p.voice ? (
                      <span
                        className="text-[10px] text-cyan-300 bg-cyan-900/30 px-2 py-0.5 rounded cursor-pointer hover:bg-red-900/30 hover:text-red-300 transition-colors"
                        title={`Voice: ${voicePresets.find(v => v.id === p.voice)?.label ?? p.voice} — click to remove`}
                        onClick={async (e) => {
                          e.stopPropagation();
                          await removePersonaVoice(p.id);
                          refresh();
                        }}
                      >
                        🔊 {voicePresets.find(v => v.id === p.voice)?.label ?? "Voice"} ✓
                      </span>
                    ) : (
                      <select
                        className="text-[10px] text-zinc-400 bg-zinc-800 px-1.5 py-0.5 rounded cursor-pointer hover:bg-cyan-900/30 hover:text-cyan-300 transition-colors border-none outline-none appearance-none"
                        value=""
                        title="Assign a voice to this persona"
                        onClick={(e) => e.stopPropagation()}
                        onChange={async (e) => {
                          if (e.target.value) {
                            await setPersonaVoice(p.id, e.target.value);
                            refresh();
                          }
                        }}
                      >
                        <option value="">🔇 Add Voice</option>
                        {voicePresets.map(v => (
                          <option key={v.id} value={v.id}>
                            {v.label} ({v.accent}) — {v.style}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                  {p.voice && (
                    <div className="mt-2 space-y-1">
                      {voiceMoods[p.id] && voiceMoods[p.id].mood !== "default" && (
                        <div className="text-[9px] text-purple-300/70 text-center">
                          🎭 {voiceMoods[p.id].mood} tone • {voiceMoods[p.id].prosody.rate !== "+0%" ? `${voiceMoods[p.id].prosody.rate} speed` : ""} {voiceMoods[p.id].prosody.pitch !== "+0Hz" ? `${voiceMoods[p.id].prosody.pitch} pitch` : ""}
                        </div>
                      )}
                      <button
                        className="w-full text-[10px] text-cyan-400 bg-cyan-900/20 hover:bg-cyan-900/40 px-2 py-1.5 rounded transition-colors flex items-center justify-center gap-1"
                        disabled={playingPreview === p.id}
                        onClick={async (e) => {
                          e.stopPropagation();
                          setPlayingPreview(p.id);
                          try {
                            const res = await fetch(`${API}/personas/${p.id}/preview-voice`, { method: "POST" });
                            if (res.ok) {
                              const blob = await res.blob();
                              const url = URL.createObjectURL(blob);
                              const audio = new Audio(url);
                              audio.onended = () => { setPlayingPreview(null); URL.revokeObjectURL(url); };
                              audio.play();
                            } else { setPlayingPreview(null); }
                          } catch { setPlayingPreview(null); }
                        }}
                      >
                        {playingPreview === p.id ? "🔊 Playing..." : `▶ Preview ${voiceMoods[p.id]?.mood && voiceMoods[p.id].mood !== "default" ? voiceMoods[p.id].mood + " " : ""}Voice`}
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      {/* ─── Generate Tab ─── */}
      <div className={tab === "generate" ? "" : "hidden"}>
        <div className="mb-6">
          <GenerationPanel personas={personas} onGenerated={refresh} />
        </div>

        {/* Generation Folders by Persona */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold">
              {openFolder !== null
                ? `${personas.find((p) => p.id === openFolder)?.name ?? "Unknown"}'s Generations`
                : "Generation Folders"}
            </h2>
            {openFolder !== null && (
              <button
                onClick={() => setOpenFolder(null)}
                className="text-xs px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 rounded-lg transition-colors"
              >
                ← Back to Folders
              </button>
            )}
          </div>

          {openFolder === null ? (
            (() => {
              const personaIds = Array.from(new Set(generations.map((g) => g.persona_id)));
              return personaIds.length === 0 ? (
                <p className="text-zinc-500 text-sm">No generations yet.</p>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
                  {personaIds.map((pid) => {
                    const persona = personas.find((p) => p.id === pid);
                    const personaGens = generations.filter((g) => g.persona_id === pid);
                    const completed = personaGens.filter((g) => g.status === "completed");
                    const latest = completed.find((g) => g.file_path);
                    const generating = personaGens.some((g) => g.status === "generating");
                    return (
                      <div
                        key={pid}
                        onClick={() => setOpenFolder(pid)}
                        className="bg-zinc-900 rounded-xl border border-zinc-800 overflow-hidden cursor-pointer group hover:border-purple-600/40 hover:scale-[1.02] transition-all"
                      >
                        <div className="aspect-square relative bg-zinc-800">
                          {latest?.file_path ? (
                            <img
                              src={imageUrl(latest.file_path)}
                              alt={persona?.name ?? ""}
                              className="w-full h-full object-cover"
                              loading="lazy"
                            />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center">
                              <span className="text-4xl opacity-30">📁</span>
                            </div>
                          )}
                          <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent" />
                          <div className="absolute bottom-0 left-0 right-0 p-3">
                            <h3 className="font-semibold text-sm truncate">
                              {persona?.name ?? `Persona #${pid}`}
                            </h3>
                            <div className="flex items-center gap-2 mt-1">
                              <span className="text-[10px] text-zinc-400">
                                {completed.length} image{completed.length !== 1 ? "s" : ""}
                              </span>
                              {generating && (
                                <span className="text-[10px] text-yellow-400 flex items-center gap-1">
                                  <span className="w-1.5 h-1.5 rounded-full bg-yellow-400 animate-pulse" />
                                  generating
                                </span>
                              )}
                            </div>
                          </div>
                          {completed.length > 1 && (
                            <div className="absolute top-2 right-2 text-[10px] bg-black/60 backdrop-blur-sm px-2 py-0.5 rounded-full text-zinc-300">
                              +{completed.length - 1}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              );
            })()
          ) : (
            (() => {
              const folderGens = generations.filter((g) => g.persona_id === openFolder);
              return folderGens.length === 0 ? (
                <p className="text-zinc-500 text-sm">No generations for this persona.</p>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
                  {folderGens.map((g) => (
                    <div
                      key={g.id}
                      className="bg-zinc-900 rounded-xl border border-zinc-800 overflow-hidden group hover:border-purple-600/40 transition-colors"
                    >
                      <div className="aspect-square relative bg-zinc-800">
                        {g.status === "completed" && g.file_path ? (
                          <AnimatedPreview
                            src={imageUrl(g.file_path)}
                            alt={g.prompt_used ?? "Generated image"}
                            filePath={g.file_path}
                            className="w-full h-full object-cover cursor-pointer"
                            onClick={() => setLightbox({ src: imageUrl(g.file_path ?? ""), prompt: g.prompt_used ?? "" })}
                          />
                        ) : g.status === "generating" ? (
                          <div className="w-full h-full flex items-center justify-center">
                            <div className="flex flex-col items-center gap-2">
                              <div className="w-6 h-6 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
                              <span className="text-zinc-500 text-xs">Generating...</span>
                            </div>
                          </div>
                        ) : (
                          <div className="w-full h-full flex items-center justify-center">
                            <span className="text-zinc-600 text-xs">Failed</span>
                          </div>
                        )}
                      </div>
                      <div className="p-2.5">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-medium text-zinc-300 truncate">
                            #{g.id}
                          </span>
                          <span
                            className={`text-[10px] px-1.5 py-0.5 rounded ${
                              g.status === "completed"
                                ? "bg-emerald-900/30 text-emerald-400"
                                : g.status === "generating"
                                ? "bg-yellow-900/30 text-yellow-400"
                                : "bg-red-900/30 text-red-400"
                            }`}
                          >
                            {g.status}
                          </span>
                        </div>
                        <p className="text-zinc-500 text-[10px] line-clamp-2">
                          {g.prompt_used ?? "—"}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              );
            })()
          )}
        </section>
      </div>

      {/* ─── Full-size Image Lightbox ─── */}
      {lightbox && (
        <div
          className="fixed inset-0 z-50 bg-black/90 backdrop-blur-sm flex items-center justify-center p-4 cursor-pointer"
          onClick={() => setLightbox(null)}
        >
          <button
            className="absolute top-4 right-4 text-white/70 hover:text-white text-3xl font-light z-50 w-10 h-10 flex items-center justify-center rounded-full bg-black/40 hover:bg-black/60 transition-colors"
            onClick={() => setLightbox(null)}
          >
            ×
          </button>
          <div className="max-w-[90vw] max-h-[90vh] flex flex-col items-center" onClick={(e) => e.stopPropagation()}>
            <img
              src={lightbox.src}
              alt="Full size"
              className="max-w-full max-h-[85vh] object-contain rounded-lg shadow-2xl"
            />
            {lightbox.prompt && (
              <p className="mt-3 text-xs text-zinc-400 max-w-2xl text-center line-clamp-3">
                {lightbox.prompt}
              </p>
            )}
          </div>
        </div>
      )}

      {/* ─── ShadowVid Tab ─── */}
      <div className={tab === "shadowvid" ? "" : "hidden"}>
        <ShadowVidPanel personas={personas} shadowOnline={health?.shadow_wirks ?? false} />
      </div>

      {/* ─── Sets Tab ─── */}
      <div className={tab === "sets" ? "" : "hidden"}>
        <ContentSetPanel personas={personas} />
      </div>

      {/* ─── Review Tab ─── */}
      <div className={tab === "review" ? "" : "hidden"}>
        <ReviewInboxPanel personas={personas} />
      </div>

      {/* ─── Vault Tab ─── */}
      <div className={tab === "vault" ? "" : "hidden"}>
        <VaultPanel personas={personas} />
      </div>

      {/* ─── Calendar Tab ─── */}
      <div className={tab === "schedule" ? "" : "hidden"}>
        <SchedulePanel personas={personas} />
      </div>

      {/* ─── Fan Chat Tab ─── */}
      <div className={tab === "chat" ? "" : "hidden"}>
        <ChatPanel personas={personas} />
      </div>

      {/* ─── Mission Tab ─── */}
      <div className={tab === "mission" ? "" : "hidden"}>
        <MissionControlPanel personas={personas} />
      </div>

      {/* ─── Agents Tab ─── */}
      <div className={tab === "agents" ? "" : "hidden"}>
        <AgentPanel personas={personas} />
      </div>

      {/* ─── Analytics Tab ─── */}
      <div className={tab === "analytics" ? "" : "hidden"}>
        <AnalyticsPanel personas={personas} />
      </div>

      {/* ─── Metrics Tab ─── */}
      <div className={tab === "metrics" ? "" : "hidden"}>
        <MetricsPanel personas={personas} />
      </div>

      {/* ─── Memory Tab ─── */}
      <div className={tab === "memory" ? "" : "hidden"}>
        <PersonaMemoryPanel personas={personas} />
      </div>

      <VoiceCoachPanel
        tab={TABS.find((t) => t.id === tab)?.label ?? tab}
        appGoal="Create, curate, distribute, and scale profitable AI content operations"
        context={{
          tab,
          personas_count: personas.length,
          links_count: links.length,
          generations_active: activeCount,
          generations_completed: completedCount,
          review_pending_hint: generations.filter((g) => g.status === "completed").length,
          shadow_online: !!health?.shadow_wirks,
          comfy_online: !!health?.comfyui,
        }}
      />
    </div>
  );
}

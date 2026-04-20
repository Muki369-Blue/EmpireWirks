"use client";

import { useState, useEffect } from "react";
import {
  triggerGeneration,
  cancelActiveGenerations,
  fetchScenePresets,
  fetchNegativePromptPresets,
  fetchLoras,
  fetchImageModelProfiles,
  refinePrompt,
  type Persona,
  type ScenePreset,
  type NegativePromptPreset,
  type InstalledLora,
  type RecommendedLora,
  type ImageModelProfile,
} from "../lib/api";

interface Props {
  personas: Persona[];
  onGenerated: () => void;
}

export default function GenerationPanel({ personas, onGenerated }: Props) {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [promptExtra, setPromptExtra] = useState("");
  const [batchSize, setBatchSize] = useState(1);
  const [loading, setLoading] = useState(false);
  const [refining, setRefining] = useState(false);
  const [intensity, setIntensity] = useState<"light" | "medium" | "heavy">("medium");
  const [result, setResult] = useState<string | null>(null);
  const [presets, setPresets] = useState<ScenePreset[]>([]);

  // Negative prompt state
  const [negPresets, setNegPresets] = useState<NegativePromptPreset[]>([]);
  const [negativePrompt, setNegativePrompt] = useState("");
  const [negActivePreset, setNegActivePreset] = useState<string>("default");
  const [showNegative, setShowNegative] = useState(true);

  // LoRA state
  const [installedLoras, setInstalledLoras] = useState<InstalledLora[]>([]);
  const [recommendedLoras, setRecommendedLoras] = useState<RecommendedLora[]>([]);
  const [selectedLora, setSelectedLora] = useState<string>("");
  const [imageProfiles, setImageProfiles] = useState<ImageModelProfile[]>([]);
  const [selectedImageProfile, setSelectedImageProfile] = useState<string>("flux_schnell");
  const [showLoras, setShowLoras] = useState(false);
  const [showPresets, setShowPresets] = useState(false);
  const [showRefiner, setShowRefiner] = useState(false);
  const [abRunning, setAbRunning] = useState(false);
  const [stopping, setStopping] = useState(false);

  useEffect(() => {
    fetchScenePresets().then(setPresets);
    fetchNegativePromptPresets().then((np) => {
      setNegPresets(np);
      const def = np.find((p) => p.id === "default");
      if (def) setNegativePrompt(def.prompt);
    });
    fetchLoras().then((data) => {
      setInstalledLoras(data.installed);
      setRecommendedLoras(data.recommended);
    });
    fetchImageModelProfiles().then((profiles) => {
      setImageProfiles(profiles);
      if (profiles.length > 0 && !profiles.some((p) => p.id === selectedImageProfile)) {
        setSelectedImageProfile(profiles[0].id);
      }
    });
  }, []);

  const selected = personas.find((p) => p.id === selectedId);

  const handleRefine = async () => {
    const text = promptExtra.trim() || selected?.prompt_base;
    if (!text) return;
    setRefining(true);
    setResult(null);
    const start = Date.now();
    try {
      const data = await refinePrompt(text, intensity);
      setPromptExtra(data.refined);
      const secs = ((Date.now() - start) / 1000).toFixed(1);
      setResult(`✨ Refined by Celeste in ${secs}s`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      setResult(`Refine failed: ${msg}`);
    } finally {
      setRefining(false);
    }
  };

  const handleGenerate = async () => {
    if (!selectedId || !promptExtra.trim()) return;

    setLoading(true);
    setResult(null);
    try {
      const jobs = await triggerGeneration(
        selectedId,
        promptExtra.trim(),
        batchSize,
        negativePrompt.trim() || undefined,
        selectedLora || undefined,
        selectedImageProfile || undefined,
      );
      const failed = jobs.filter((j) => j.status === "failed").length;
      const queued = jobs.filter((j) => j.status === "generating").length;
      const profileLabel = selectedImageProfile.replace(/_/g, " ");
      setResult(
        `Queued ${queued} job(s) on ${profileLabel}${failed ? `, ${failed} failed (is ComfyUI running?)` : ""}`
      );
      onGenerated();
    } catch {
      setResult("Error: Could not reach backend");
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateAB = async () => {
    if (!selectedId || !promptExtra.trim()) return;

    setAbRunning(true);
    setResult(null);
    try {
      const profileA = "flux_schnell";
      const profileB = "flux2_klein";

      const jobsA = await triggerGeneration(
        selectedId,
        promptExtra.trim(),
        batchSize,
        negativePrompt.trim() || undefined,
        selectedLora || undefined,
        profileA,
      );
      const jobsB = await triggerGeneration(
        selectedId,
        promptExtra.trim(),
        batchSize,
        negativePrompt.trim() || undefined,
        selectedLora || undefined,
        profileB,
      );

      const queuedA = jobsA.filter((j) => j.status === "generating").length;
      const queuedB = jobsB.filter((j) => j.status === "generating").length;
      const failedA = jobsA.filter((j) => j.status === "failed").length;
      const failedB = jobsB.filter((j) => j.status === "failed").length;

      setResult(
        `A/B queued: A(${profileA})=${queuedA}, B(${profileB})=${queuedB}${failedA + failedB > 0 ? `, failed=${failedA + failedB}` : ""}`
      );
      onGenerated();
    } catch {
      setResult("Error: Could not queue A/B test")
    } finally {
      setAbRunning(false);
    }
  };

  const handleStop = async () => {
    setStopping(true);
    setResult(null);
    try {
      const res = await cancelActiveGenerations();
      const n = res.cancelled_content_ids.length;
      setResult(
        n > 0
          ? `Stopped ${n} generation(s) — ComfyUI interrupted`
          : "ComfyUI interrupted — no active DB generations found"
      );
      setLoading(false);
      onGenerated();
    } catch {
      setResult("Error: Could not stop generations");
    } finally {
      setStopping(false);
    }
  };

  return (
    <div className="bg-zinc-900 p-6 rounded-xl border border-zinc-800">
      <h2 className="text-xl font-semibold mb-4">Generate Content</h2>

      {personas.length === 0 ? (
        <p className="text-zinc-500 text-sm">Create a persona first.</p>
      ) : (
        <div className="space-y-3">
          {/* Persona selector */}
          <select
            className="w-full p-2.5 bg-zinc-800 border border-zinc-700 rounded-lg text-sm focus:border-purple-500 focus:outline-none"
            value={selectedId ?? ""}
            onChange={(e) => setSelectedId(Number(e.target.value) || null)}
          >
            <option value="">Select persona...</option>
            {personas.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>

          {selected && (
            <div className="text-xs text-zinc-500 bg-zinc-800/50 p-2 rounded">
              Base prompt: {selected.prompt_base.substring(0, 120)}
              {selected.prompt_base.length > 120 ? "..." : ""}
            </div>
          )}

          {/* Scene / extra prompt */}
          <textarea
            className="w-full p-2.5 bg-zinc-800 border border-zinc-700 rounded-lg text-sm placeholder-zinc-500 focus:border-purple-500 focus:outline-none min-h-[80px]"
            placeholder="Scene description (e.g. 'wearing red dress, luxury bedroom, soft lighting, professional photo')"
            value={promptExtra}
            onChange={(e) => setPromptExtra(e.target.value)}
          />

          {/* ── Quick Presets Section ── */}
          {presets.length > 0 && (
            <div className="border border-zinc-800 rounded-xl overflow-hidden">
              <button
                onClick={() => setShowPresets(!showPresets)}
                className="w-full flex items-center justify-between p-3 bg-zinc-800/40 hover:bg-zinc-800/60 transition-colors text-sm"
              >
                <span className="flex items-center gap-2">
                  <span>🎬</span> Quick Presets
                  {promptExtra && presets.some(p => p.prompt === promptExtra) && (
                    <span className="text-[10px] text-purple-400 bg-purple-900/30 px-1.5 py-0.5 rounded">
                      {presets.find(p => p.prompt === promptExtra)?.label}
                    </span>
                  )}
                </span>
                <span className="text-zinc-500 text-xs">{showPresets ? "▾" : "▸"}</span>
              </button>
              {showPresets && (
                <div className="p-3 border-t border-zinc-800">
                  <div className="flex flex-wrap gap-1.5">
                    {presets.map((preset) => (
                      <button
                        key={preset.id}
                        type="button"
                        onClick={() => setPromptExtra(preset.prompt)}
                        className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors ${
                          promptExtra === preset.prompt
                            ? "border-purple-500 bg-purple-600/20 text-purple-300"
                            : "border-zinc-700 bg-zinc-800 text-zinc-400 hover:border-zinc-600 hover:text-zinc-300"
                        }`}
                      >
                        {preset.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── Prompt Refiner Section ── */}
          <div className="border border-zinc-800 rounded-xl overflow-hidden">
            <button
              onClick={() => setShowRefiner(!showRefiner)}
              className="w-full flex items-center justify-between p-3 bg-zinc-800/40 hover:bg-zinc-800/60 transition-colors text-sm"
            >
              <span className="flex items-center gap-2">
                <span>✨</span> Prompt Refiner
                <span className="text-[10px] text-zinc-500">powered by Celeste</span>
              </span>
              <span className="text-zinc-500 text-xs">{showRefiner ? "▾" : "▸"}</span>
            </button>
            {showRefiner && (
              <div className="p-3 border-t border-zinc-800">
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleRefine}
                    disabled={refining || (!promptExtra.trim() && !selected)}
                    className="flex-1 bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-700 hover:to-orange-700 disabled:opacity-40 px-3 py-2 rounded-lg font-semibold text-sm transition-all flex items-center justify-center gap-1.5"
                  >
                    {refining ? (
                      <>
                        <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        Refining...
                      </>
                    ) : (
                      <>
                        <span className="text-base">✨</span>
                        Refine Prompt
                      </>
                    )}
                  </button>
                  {/* Intensity selector */}
                  <div className="flex bg-zinc-800 rounded-lg border border-zinc-700 overflow-hidden">
                    {(["light", "medium", "heavy"] as const).map((level) => (
                      <button
                        key={level}
                        onClick={() => setIntensity(level)}
                        className={`px-2.5 py-2 text-[11px] font-medium transition-colors ${
                          intensity === level
                            ? "bg-amber-600/30 text-amber-300"
                            : "text-zinc-500 hover:text-zinc-300"
                        }`}
                      >
                        {level === "light" ? "🔥" : level === "medium" ? "🔥🔥" : "🔥🔥🔥"}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Batch size */}

          {/* ── Negative Prompt Section ── */}
          <div className="border border-zinc-800 rounded-xl overflow-hidden">
            <button
              onClick={() => setShowNegative(!showNegative)}
              className="w-full flex items-center justify-between p-3 bg-zinc-800/40 hover:bg-zinc-800/60 transition-colors text-sm"
            >
              <span className="flex items-center gap-2">
                <span>⛔</span> Negative Prompt
                {negativePrompt && <span className="text-[10px] text-red-400 bg-red-900/30 px-1.5 py-0.5 rounded">active</span>}
              </span>
              <span className="text-zinc-500 text-xs">{showNegative ? "▾" : "▸"}</span>
            </button>
            {showNegative && (
              <div className="p-3 space-y-2 border-t border-zinc-800">
                <div className="flex flex-wrap gap-1.5">
                  {negPresets.map((np) => (
                    <button
                      key={np.id}
                      onClick={() => { setNegativePrompt(np.prompt); setNegActivePreset(np.id); }}
                      title={np.description}
                      className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors ${
                        negActivePreset === np.id
                          ? "border-red-500 bg-red-600/20 text-red-300"
                          : "border-zinc-700 bg-zinc-800 text-zinc-400 hover:border-zinc-600"
                      }`}
                    >
                      {np.label}
                    </button>
                  ))}
                  <button
                    onClick={() => { setNegativePrompt(""); setNegActivePreset(""); }}
                    className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors ${
                      !negativePrompt
                        ? "border-zinc-500 bg-zinc-700/50 text-zinc-300"
                        : "border-zinc-700 bg-zinc-800 text-zinc-400 hover:border-zinc-600"
                    }`}
                  >
                    None
                  </button>
                </div>
                <textarea
                  className="w-full p-2 bg-zinc-800 border border-zinc-700 rounded-lg text-xs placeholder-zinc-500 focus:border-red-500 focus:outline-none min-h-[60px] text-red-300/80"
                  placeholder="Things to avoid in generation..."
                  value={negativePrompt}
                  onChange={(e) => { setNegativePrompt(e.target.value); setNegActivePreset(""); }}
                />
              </div>
            )}
          </div>

          {/* ── LoRA Models Section ── */}
          <div className="border border-zinc-800 rounded-xl overflow-hidden">
            <div className="p-3 bg-zinc-800/40 border-b border-zinc-800">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm flex items-center gap-2">
                  <span>🧪</span> Image Model Profile
                </span>
                <span className="text-[10px] text-amber-300 bg-amber-900/30 px-1.5 py-0.5 rounded">
                  A/B Quick Test
                </span>
              </div>
            </div>
            <div className="p-3 space-y-2">
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setSelectedImageProfile("flux_schnell")}
                  className={`px-2.5 py-2 rounded-lg border text-xs font-medium transition-colors ${
                    selectedImageProfile === "flux_schnell"
                      ? "border-amber-500 bg-amber-600/20 text-amber-300"
                      : "border-zinc-700 bg-zinc-800 text-zinc-400 hover:border-zinc-600"
                  }`}
                >
                  A: Flux Schnell
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedImageProfile("flux2_klein")}
                  className={`px-2.5 py-2 rounded-lg border text-xs font-medium transition-colors ${
                    selectedImageProfile === "flux2_klein"
                      ? "border-amber-500 bg-amber-600/20 text-amber-300"
                      : "border-zinc-700 bg-zinc-800 text-zinc-400 hover:border-zinc-600"
                  }`}
                >
                  B: Flux2 Klein
                </button>
              </div>

              <select
                value={selectedImageProfile}
                onChange={(e) => setSelectedImageProfile(e.target.value)}
                className="w-full p-2.5 bg-zinc-800 border border-zinc-700 rounded-lg text-sm focus:border-amber-500 focus:outline-none"
              >
                {(imageProfiles.length > 0
                  ? imageProfiles
                  : [
                      { id: "flux_schnell", unet_name: "flux1-schnell.safetensors", vae_name: "ae.safetensors", default_steps: 4, default_guidance: 3.5 },
                      { id: "flux2_klein", unet_name: "Flux2-Klein-9B-True-v2-bf16.safetensors", vae_name: "ae.safetensors", default_steps: 6, default_guidance: 3.5 },
                    ]
                ).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.id.replace(/_/g, " ")}
                  </option>
                ))}
              </select>

              {imageProfiles.find((p) => p.id === selectedImageProfile) && (
                <p className="text-[11px] text-zinc-500">
                  UNET: {imageProfiles.find((p) => p.id === selectedImageProfile)?.unet_name} | Steps: {imageProfiles.find((p) => p.id === selectedImageProfile)?.default_steps}
                </p>
              )}
            </div>
          </div>

          <div className="border border-zinc-800 rounded-xl overflow-hidden">
            <button
              onClick={() => setShowLoras(!showLoras)}
              className="w-full flex items-center justify-between p-3 bg-zinc-800/40 hover:bg-zinc-800/60 transition-colors text-sm"
            >
              <span className="flex items-center gap-2">
                <span>🧬</span> LoRA Models
                {selectedLora && <span className="text-[10px] text-cyan-400 bg-cyan-900/30 px-1.5 py-0.5 rounded">{selectedLora.replace(/\.safetensors$/, "")}</span>}
              </span>
              <span className="text-zinc-500 text-xs">{showLoras ? "▾" : "▸"}</span>
            </button>
            {showLoras && (
              <div className="p-3 space-y-3 border-t border-zinc-800">
                {/* Installed LoRAs */}
                {installedLoras.length > 0 && (
                  <div>
                    <label className="text-[11px] text-zinc-500 mb-1.5 block font-medium">Installed</label>
                    <div className="space-y-1">
                      {installedLoras.map((lora) => (
                        <label
                          key={lora.filename}
                          className={`flex items-center gap-2 p-2 rounded-lg cursor-pointer transition-colors ${
                            selectedLora === lora.filename
                              ? "bg-cyan-900/20 border border-cyan-700"
                              : "bg-zinc-800/50 border border-transparent hover:bg-zinc-800"
                          }`}
                        >
                          <input
                            type="radio"
                            name="lora"
                            checked={selectedLora === lora.filename}
                            onChange={() => setSelectedLora(selectedLora === lora.filename ? "" : lora.filename)}
                            className="accent-cyan-500"
                          />
                          <div className="flex-1 min-w-0">
                            <span className="text-xs text-zinc-200 truncate block">{lora.name}</span>
                            <span className="text-[10px] text-zinc-500">{lora.size_mb} MB</span>
                          </div>
                          <span className="text-[10px] text-emerald-400 bg-emerald-900/30 px-1.5 py-0.5 rounded">installed</span>
                        </label>
                      ))}
                      {selectedLora && (
                        <button
                          onClick={() => setSelectedLora("")}
                          className="text-[10px] text-zinc-400 hover:text-zinc-300 mt-1"
                        >
                          ✕ Clear LoRA selection
                        </button>
                      )}
                    </div>
                  </div>
                )}

                {/* Recommended LoRAs */}
                <div>
                  <label className="text-[11px] text-zinc-500 mb-1.5 block font-medium">
                    Recommended for Flux {installedLoras.length === 0 && "(none installed)"}
                  </label>
                  <div className="space-y-1 max-h-[200px] overflow-y-auto">
                    {recommendedLoras.map((lora) => (
                      <div
                        key={lora.id}
                        className={`flex items-center gap-2 p-2 rounded-lg transition-colors ${
                          lora.installed
                            ? "bg-zinc-800/50 cursor-pointer hover:bg-zinc-800"
                            : "bg-zinc-800/30 opacity-60"
                        }`}
                        onClick={() => lora.installed && setSelectedLora(selectedLora === lora.filename ? "" : lora.filename)}
                      >
                        <div className="flex-1 min-w-0">
                          <span className="text-xs text-zinc-200 truncate block">{lora.name}</span>
                          <span className="text-[10px] text-zinc-500">{lora.description}</span>
                        </div>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                          lora.installed
                            ? "text-emerald-400 bg-emerald-900/30"
                            : "text-zinc-400 bg-zinc-800"
                        }`}>
                          {lora.installed ? "✓ installed" : lora.category}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Batch size */}
          <div className="flex items-center gap-3">
            <label className="text-sm text-zinc-400">Batch:</label>
            <input
              type="number"
              min={1}
              max={16}
              value={batchSize}
              onChange={(e) =>
                setBatchSize(Math.max(1, Math.min(16, Number(e.target.value))))
              }
              className="w-20 p-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-center focus:border-purple-500 focus:outline-none"
            />
            <span className="text-xs text-zinc-500">images</span>
          </div>

          <div className="flex gap-2">
            <button
              onClick={handleGenerate}
              disabled={loading || abRunning || stopping || !selectedId || !promptExtra.trim()}
              className="flex-1 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 disabled:opacity-40 px-4 py-2.5 rounded-lg font-semibold text-sm transition-all"
            >
              {loading ? `Sending to ${selectedImageProfile.replace(/_/g, " ")}...` : "Generate"}
            </button>
            <button
              onClick={handleGenerateAB}
              disabled={loading || abRunning || stopping || !selectedId || !promptExtra.trim()}
              className="bg-gradient-to-r from-amber-600 to-yellow-600 hover:from-amber-700 hover:to-yellow-700 disabled:opacity-40 px-4 py-2.5 rounded-lg font-semibold text-sm transition-all"
            >
              {abRunning ? "Queueing A/B..." : "Run A/B"}
            </button>
            <button
              onClick={handleStop}
              disabled={stopping || loading || abRunning}
              className="bg-red-600 hover:bg-red-700 disabled:opacity-40 px-4 py-2.5 rounded-lg font-semibold text-sm transition-all flex items-center gap-1.5"
            >
              {stopping ? (
                <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <span>◼</span>
              )}
              Stop
            </button>
          </div>

          {result && (
            <p className="text-sm text-emerald-400 bg-emerald-900/20 p-2 rounded">
              {result}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

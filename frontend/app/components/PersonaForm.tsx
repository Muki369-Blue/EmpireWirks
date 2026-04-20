"use client";

import { useState, useEffect } from "react";
import { createPersona, fetchPersonaPresets, personaCoach, refinePrompt, type PersonaCoachResult, type PersonaPreset } from "../lib/api";

interface Props {
  onCreated: () => void;
}

export default function PersonaForm({ onCreated }: Props) {
  const [name, setName] = useState("");
  const [promptBase, setPromptBase] = useState("");
  const [personality, setPersonality] = useState("");
  const [loraName, setLoraName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [presets, setPresets] = useState<PersonaPreset[]>([]);
  const [showPresets, setShowPresets] = useState(false);
  const [showRefiner, setShowRefiner] = useState(false);
  const [refining, setRefining] = useState(false);
  const [intensity, setIntensity] = useState<"light" | "medium" | "heavy">("medium");
  const [refineResult, setRefineResult] = useState<string | null>(null);
  const [showBrain, setShowBrain] = useState(false);
  const [brainIdea, setBrainIdea] = useState("");
  const [brainVibe, setBrainVibe] = useState("bold, seductive, premium");
  const [brainLoading, setBrainLoading] = useState(false);
  const [brainError, setBrainError] = useState<string | null>(null);
  const [brainResult, setBrainResult] = useState<PersonaCoachResult | null>(null);

  useEffect(() => {
    fetchPersonaPresets().then(setPresets);
  }, []);

  const handleRefine = async () => {
    if (!promptBase.trim()) return;
    setRefining(true);
    setRefineResult(null);
    const start = Date.now();
    try {
      const data = await refinePrompt(promptBase.trim(), intensity);
      setPromptBase(data.refined);
      const secs = ((Date.now() - start) / 1000).toFixed(1);
      setRefineResult(`✨ Refined by ${data.model ?? "MLX"} in ${secs}s`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      setRefineResult(`Refine failed: ${msg}`);
    } finally {
      setRefining(false);
    }
  };

  const handleBrainGenerate = async () => {
    if (!brainIdea.trim()) return;
    setBrainLoading(true);
    setBrainError(null);
    try {
      const res = await personaCoach(brainIdea.trim(), brainVibe.trim());
      setBrainResult(res);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      setBrainError(msg);
    } finally {
      setBrainLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !promptBase.trim()) return;

    setLoading(true);
    setError("");
    try {
      await createPersona({
        name: name.trim(),
        prompt_base: promptBase.trim(),
        personality: personality.trim() || undefined,
        lora_name: loraName.trim() || undefined,
      });
      setName("");
      setPromptBase("");
      setPersonality("");
      setLoraName("");
      setRefineResult(null);
      onCreated();
    } catch (err: any) {
      setError(err.message || "Failed to create persona");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative bg-zinc-900 p-6 pt-10 rounded-xl border border-zinc-800">
      <button
        type="button"
        onClick={() => setShowBrain((v) => !v)}
        className="absolute left-1/2 -translate-x-1/2 -top-4 px-4 py-1.5 text-xs font-semibold rounded-full border border-cyan-400/40 text-cyan-200 bg-cyan-500/20 shadow-[0_0_24px_rgba(34,211,238,0.35)] hover:bg-cyan-500/30 transition-all animate-pulse"
      >
        Persona Brain
      </button>
      <h2 className="text-xl font-semibold mb-4">Create AI Persona</h2>

      {showBrain && (
        <div className="mb-4 border border-cyan-500/30 rounded-xl bg-cyan-950/20 p-3 space-y-2">
          <div className="text-sm font-semibold text-cyan-200">Separate Persona Builder</div>
          <textarea
            className="w-full p-2.5 bg-zinc-800 border border-zinc-700 rounded-lg text-sm placeholder-zinc-500 focus:border-cyan-500 focus:outline-none min-h-[84px]"
            placeholder="Describe the vibe and look you want, e.g. confident alt-girl gamer with neon style and playful teasing tone"
            value={brainIdea}
            onChange={(e) => setBrainIdea(e.target.value)}
          />
          <input
            className="w-full p-2.5 bg-zinc-800 border border-zinc-700 rounded-lg text-sm placeholder-zinc-500 focus:border-cyan-500 focus:outline-none"
            placeholder="Vibe tags"
            value={brainVibe}
            onChange={(e) => setBrainVibe(e.target.value)}
          />
          <button
            type="button"
            onClick={handleBrainGenerate}
            disabled={brainLoading || !brainIdea.trim()}
            className="w-full bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-700 hover:to-blue-700 disabled:opacity-40 px-3 py-2 rounded-lg text-sm font-semibold"
          >
            {brainLoading ? "Thinking..." : "Generate Persona Pack"}
          </button>
          {brainError && <p className="text-xs text-red-400">{brainError}</p>}

          {brainResult && (
            <div className="mt-2 border border-cyan-500/20 rounded-lg p-3 bg-zinc-900/60 space-y-2">
              <div className="text-xs text-zinc-400">Model: {brainResult.model ?? "unknown"}</div>
              <div className="text-xs text-zinc-300"><span className="text-cyan-300">Name:</span> {brainResult.name}</div>
              <div className="text-xs text-zinc-300"><span className="text-cyan-300">Opening:</span> {brainResult.opening_line}</div>
              <div className="text-xs text-zinc-300"><span className="text-cyan-300">Personality:</span> {brainResult.personality}</div>
              <div className="text-xs text-zinc-300"><span className="text-cyan-300">Prompt Base:</span> {brainResult.prompt_base}</div>

              <div className="grid grid-cols-1 sm:grid-cols-4 gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setName(brainResult.name || name)}
                  className="text-xs px-2 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 border border-zinc-700"
                >
                  Apply Name
                </button>
                <button
                  type="button"
                  onClick={() => setPromptBase(brainResult.prompt_base || promptBase)}
                  className="text-xs px-2 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 border border-zinc-700"
                >
                  Apply Prompt
                </button>
                <button
                  type="button"
                  onClick={() => setPersonality(brainResult.personality || personality)}
                  className="text-xs px-2 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 border border-zinc-700"
                >
                  Apply Personality
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setName(brainResult.name || name);
                    setPromptBase(brainResult.prompt_base || promptBase);
                    setPersonality(brainResult.personality || personality);
                  }}
                  className="text-xs px-2 py-1.5 rounded bg-cyan-600/30 hover:bg-cyan-600/40 border border-cyan-500/40 sm:col-span-1"
                >
                  Apply All
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Quick Start presets — collapsible */}
      {presets.length > 0 && (
        <div className="mb-3 border border-zinc-800 rounded-xl overflow-hidden">
          <button
            onClick={() => setShowPresets(!showPresets)}
            className="w-full flex items-center justify-between p-3 bg-zinc-800/40 hover:bg-zinc-800/60 transition-colors text-sm"
          >
            <span className="flex items-center gap-2">
              <span>🚀</span> Quick Start
              {name && presets.some(p => p.name === name) && (
                <span className="text-[10px] text-purple-400 bg-purple-900/30 px-1.5 py-0.5 rounded">
                  {presets.find(p => p.name === name)?.label}
                </span>
              )}
            </span>
            <span className="text-zinc-500 text-xs">{showPresets ? "▾" : "▸"}</span>
          </button>
          {showPresets && (
            <div className="p-3 border-t border-zinc-800">
              <div className="flex flex-wrap gap-1.5">
                {presets.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => {
                      setName(p.name);
                      setPromptBase(p.prompt_base);
                    }}
                    className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors ${
                      name === p.name
                        ? "border-purple-500 bg-purple-600/20 text-purple-300"
                        : "border-zinc-700 bg-zinc-800 text-zinc-400 hover:border-zinc-600 hover:text-zinc-300"
                    }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-3">
        <input
          className="w-full p-2.5 bg-zinc-800 border border-zinc-700 rounded-lg text-sm placeholder-zinc-500 focus:border-purple-500 focus:outline-none"
          placeholder="Persona Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <textarea
          className="w-full p-2.5 bg-zinc-800 border border-zinc-700 rounded-lg text-sm placeholder-zinc-500 focus:border-purple-500 focus:outline-none min-h-[100px]"
          placeholder="Physical description / prompt base (e.g. 'beautiful woman, brown hair, green eyes, slender build, 25yo')"
          value={promptBase}
          onChange={(e) => setPromptBase(e.target.value)}
          required
        />
        <textarea
          className="w-full p-2.5 bg-zinc-800 border border-zinc-700 rounded-lg text-sm placeholder-zinc-500 focus:border-purple-500 focus:outline-none min-h-[84px]"
          placeholder="Personality / chat voice (optional)"
          value={personality}
          onChange={(e) => setPersonality(e.target.value)}
        />

        {/* Prompt Refiner — collapsible */}
        <div className="border border-zinc-800 rounded-xl overflow-hidden">
          <button
            type="button"
            onClick={() => setShowRefiner(!showRefiner)}
            className="w-full flex items-center justify-between p-3 bg-zinc-800/40 hover:bg-zinc-800/60 transition-colors text-sm"
          >
            <span className="flex items-center gap-2">
              <span>✨</span> Refine Prompt
              <span className="text-[10px] text-zinc-500">powered by MLX</span>
            </span>
            <span className="text-zinc-500 text-xs">{showRefiner ? "▾" : "▸"}</span>
          </button>
          {showRefiner && (
            <div className="p-3 border-t border-zinc-800 space-y-2">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleRefine}
                  disabled={refining || !promptBase.trim()}
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
                <div className="flex bg-zinc-800 rounded-lg border border-zinc-700 overflow-hidden">
                  {(["light", "medium", "heavy"] as const).map((level) => (
                    <button
                      key={level}
                      type="button"
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
              {refineResult && (
                <p className="text-xs text-emerald-400 bg-emerald-900/20 p-2 rounded">{refineResult}</p>
              )}
            </div>
          )}
        </div>

        <input
          className="w-full p-2.5 bg-zinc-800 border border-zinc-700 rounded-lg text-sm placeholder-zinc-500 focus:border-purple-500 focus:outline-none"
          placeholder="LoRA filename (optional, e.g. my_model.safetensors)"
          value={loraName}
          onChange={(e) => setLoraName(e.target.value)}
        />
        {error && (
          <p className="text-red-400 text-sm">{error}</p>
        )}
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-purple-600 hover:bg-purple-700 disabled:bg-purple-800 disabled:opacity-50 px-4 py-2.5 rounded-lg font-semibold text-sm transition-colors"
        >
          {loading ? "Deploying..." : "Deploy Persona"}
        </button>
      </form>
    </div>
  );
}

"use client";

import { useEffect, useMemo, useState } from "react";
import { clearPersonaSocialMan, setPersonaSocialMan, type Persona } from "../lib/api";

interface Props {
  personas: Persona[];
  onChanged: () => void;
}

const PLATFORM_OPTIONS = [
  { id: "instagram", label: "Instagram", accent: "bg-pink-600/20 text-pink-300 border-pink-500/30" },
  { id: "facebook", label: "Facebook", accent: "bg-blue-600/20 text-blue-300 border-blue-500/30" },
  { id: "twitter", label: "X / Twitter", accent: "bg-zinc-700/40 text-zinc-200 border-zinc-500/30" },
  { id: "linkedin", label: "LinkedIn", accent: "bg-sky-700/20 text-sky-300 border-sky-500/30" },
  { id: "pinterest", label: "Pinterest", accent: "bg-rose-700/20 text-rose-300 border-rose-500/30" },
  { id: "tiktok", label: "TikTok", accent: "bg-fuchsia-700/20 text-fuchsia-300 border-fuchsia-500/30" },
];

export default function SocialManPanel({ personas, onChanged }: Props) {
  const [personaId, setPersonaId] = useState<number | "">("");
  const [enabled, setEnabled] = useState(false);
  const [token, setToken] = useState("");
  const [platforms, setPlatforms] = useState<string[]>([]);
  const [titleTemplate, setTitleTemplate] = useState("");
  const [descriptionTemplate, setDescriptionTemplate] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!personas.length) {
      setPersonaId("");
      return;
    }
    if (personaId === "" || !personas.some((persona) => persona.id === personaId)) {
      setPersonaId(personas[0].id);
    }
  }, [personaId, personas]);

  const selectedPersona = useMemo(
    () => personas.find((persona) => persona.id === personaId) ?? null,
    [personaId, personas]
  );

  useEffect(() => {
    if (!selectedPersona) {
      setEnabled(false);
      setToken("");
      setPlatforms([]);
      setTitleTemplate("");
      setDescriptionTemplate("");
      return;
    }
    setEnabled(Boolean(selectedPersona.socialman_enabled));
    setToken("");
    setPlatforms(selectedPersona.socialman_platforms ?? []);
    setTitleTemplate(selectedPersona.socialman_title_template ?? "{persona} drop");
    setDescriptionTemplate(selectedPersona.socialman_description_template ?? "Fresh content from {persona}. {prompt}");
    setError(null);
    setNotice(null);
  }, [selectedPersona]);

  const togglePlatform = (platformId: string) => {
    setPlatforms((current) =>
      current.includes(platformId)
        ? current.filter((entry) => entry !== platformId)
        : [...current, platformId]
    );
  };

  const handleSave = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selectedPersona) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      await setPersonaSocialMan(selectedPersona.id, {
        enabled,
        token: token.trim() || undefined,
        platforms,
        title_template: titleTemplate.trim() || undefined,
        description_template: descriptionTemplate.trim() || undefined,
      });
      setToken("");
      setNotice("SocialMan settings saved");
      onChanged();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save SocialMan settings");
    } finally {
      setSaving(false);
    }
  };

  const handleClear = async () => {
    if (!selectedPersona) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      await clearPersonaSocialMan(selectedPersona.id);
      setEnabled(false);
      setToken("");
      setPlatforms([]);
      setTitleTemplate("{persona} drop");
      setDescriptionTemplate("Fresh content from {persona}. {prompt}");
      setNotice("SocialMan settings cleared");
      onChanged();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to clear SocialMan settings");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-zinc-900 p-6 rounded-xl border border-zinc-800">
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <h2 className="text-xl font-semibold">SocialMan Auto-Post</h2>
          <p className="text-xs text-zinc-500 mt-1">
            Initial slice: image generations can publish straight from ComfyUI when the SocialMan nodes are installed.
          </p>
        </div>
        <span className="text-[10px] px-2 py-1 rounded-full border border-cyan-500/30 bg-cyan-500/10 text-cyan-200">
          ComfyUI-linked
        </span>
      </div>

      {personas.length === 0 ? (
        <p className="text-zinc-500 text-sm">Create a persona first, then bind its SocialMan token here.</p>
      ) : (
        <form onSubmit={handleSave} className="space-y-4">
          <div>
            <label className="block text-xs uppercase tracking-[0.18em] text-zinc-500 mb-2">Persona</label>
            <select
              className="w-full p-2.5 bg-zinc-800 border border-zinc-700 rounded-lg text-sm focus:border-cyan-500 focus:outline-none"
              value={personaId}
              onChange={(event) => setPersonaId(Number(event.target.value))}
            >
              {personas.map((persona) => (
                <option key={persona.id} value={persona.id}>
                  {persona.name}
                </option>
              ))}
            </select>
          </div>

          <label className="flex items-center justify-between gap-3 rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2.5">
            <div>
              <div className="text-sm text-zinc-200">Enable auto-post after image generation</div>
              <div className="text-[11px] text-zinc-500 mt-0.5">Disabled personas keep their token but skip the publish nodes.</div>
            </div>
            <input
              type="checkbox"
              checked={enabled}
              onChange={(event) => setEnabled(event.target.checked)}
              className="h-4 w-4 rounded border-zinc-600 bg-zinc-800 text-cyan-500 focus:ring-cyan-500"
            />
          </label>

          <div>
            <label className="block text-xs uppercase tracking-[0.18em] text-zinc-500 mb-2">SocialMan token</label>
            <input
              type="password"
              className="w-full p-2.5 bg-zinc-800 border border-zinc-700 rounded-lg text-sm placeholder-zinc-500 focus:border-cyan-500 focus:outline-none"
              placeholder={selectedPersona?.socialman_configured ? "Leave blank to keep current token" : "Paste SocialMan token"}
              value={token}
              onChange={(event) => setToken(event.target.value)}
            />
            {selectedPersona?.socialman_configured && (
              <p className="mt-1 text-[11px] text-zinc-500">A token is already stored for this persona. Re-enter only if you want to replace it.</p>
            )}
          </div>

          <div>
            <label className="block text-xs uppercase tracking-[0.18em] text-zinc-500 mb-2">Platforms</label>
            <div className="grid grid-cols-2 gap-2">
              {PLATFORM_OPTIONS.map((platform) => {
                const active = platforms.includes(platform.id);
                return (
                  <button
                    key={platform.id}
                    type="button"
                    onClick={() => togglePlatform(platform.id)}
                    className={`rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${
                      active
                        ? platform.accent
                        : "border-zinc-700 bg-zinc-800/70 text-zinc-400 hover:border-zinc-600 hover:text-zinc-200"
                    }`}
                  >
                    {platform.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <label className="block text-xs uppercase tracking-[0.18em] text-zinc-500 mb-2">Title template</label>
            <input
              className="w-full p-2.5 bg-zinc-800 border border-zinc-700 rounded-lg text-sm placeholder-zinc-500 focus:border-cyan-500 focus:outline-none"
              value={titleTemplate}
              onChange={(event) => setTitleTemplate(event.target.value)}
              placeholder="{persona} drop"
            />
          </div>

          <div>
            <label className="block text-xs uppercase tracking-[0.18em] text-zinc-500 mb-2">Description template</label>
            <textarea
              className="w-full p-2.5 bg-zinc-800 border border-zinc-700 rounded-lg text-sm placeholder-zinc-500 focus:border-cyan-500 focus:outline-none min-h-[92px]"
              value={descriptionTemplate}
              onChange={(event) => setDescriptionTemplate(event.target.value)}
              placeholder="Fresh content from {persona}. {prompt}"
            />
            <p className="mt-1 text-[11px] text-zinc-500">Supported placeholders: {"{persona}"}, {"{prompt}"}, and {"{platform}"}.</p>
          </div>

          {error && <p className="text-sm text-red-400">{error}</p>}
          {notice && <p className="text-sm text-emerald-400">{notice}</p>}

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={saving}
              className="flex-1 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-700 hover:to-blue-700 disabled:opacity-40 px-4 py-2.5 rounded-lg font-semibold text-sm transition-colors"
            >
              {saving ? "Saving..." : "Save SocialMan Config"}
            </button>
            <button
              type="button"
              disabled={saving || !selectedPersona?.socialman_configured}
              onClick={handleClear}
              className="px-4 py-2.5 rounded-lg border border-zinc-700 bg-zinc-800 text-sm text-zinc-300 hover:bg-zinc-700 disabled:opacity-40 transition-colors"
            >
              Clear
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
  fetchVault,
  toggleFavorite,
  fetchVaultStats,
  deleteVaultItem,
  generateCaption,
  queuePost,
  imageUrl,
  downloadMp4Url,
  isVideoItem,
  type Persona,
  type VaultItem,
} from "../lib/api";
import AnimatedPreview from "./AnimatedPreview";

const PLATFORMS = ["onlyfans", "fansly", "twitter", "reddit"];

function getModelTag(tags?: string | null): string | null {
  if (!tags) return null;
  const parts = tags.split(",").map((t) => t.trim()).filter(Boolean);
  const model = parts.find((t) => t.startsWith("model:"));
  return model ? model.replace("model:", "") : null;
}

function modelBadge(model?: string | null): string {
  if (!model) return "";
  if (model === "flux_schnell") return "A";
  if (model === "flux2_klein") return "B";
  return model.replace(/_/g, " ");
}

export default function VaultPanel({ personas }: { personas: Persona[] }) {
  const [items, setItems] = useState<VaultItem[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [favOnly, setFavOnly] = useState(false);
  const [modelFilter, setModelFilter] = useState<"all" | "a" | "b">(
    () => (typeof window !== "undefined" ? (localStorage.getItem("vault_modelFilter") as "all" | "a" | "b" | null) ?? "all" : "all")
  );
  const [selected, setSelected] = useState<VaultItem | null>(null);
  const [captioning, setCaptioning] = useState(false);
  const [posting, setPosting] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [openFolder, setOpenFolder] = useState<number | null>(null);
  const [expandedItem, setExpandedItem] = useState<VaultItem | null>(null);
  const suppressOpenUntilRef = useRef(0);

  const refresh = () => {
    fetchVault({ favorites_only: favOnly }).then(setItems).catch(() => {});
    fetchVaultStats().then(setStats).catch(() => {});
  };

  useEffect(() => { refresh(); }, [favOnly]);

  const handleFavorite = async (id: number) => {
    await toggleFavorite(id);
    refresh();
  };

  const handleCaption = async (item: VaultItem, platform: string) => {
    setCaptioning(true);
    try {
      const result = await generateCaption(item.id, platform);
      setSelected({ ...item, caption: result.caption, hashtags: result.hashtags });
      refresh();
    } catch {}
    setCaptioning(false);
  };

  const handlePost = async (item: VaultItem, platform: string) => {
    setPosting(platform);
    try {
      const caption = item.caption || `New content from ${personas.find((p) => p.id === item.persona_id)?.name ?? "your favorite"} 💋`;
      await queuePost({ content_id: item.id, platform, caption });
      refresh();
    } catch {}
    setPosting(null);
  };

  const getPreviewPath = (item: VaultItem) => {
    if (isVideoItem(item)) return item.file_path;
    return item.watermarked_path || item.upscaled_path || item.file_path;
  };

  const handleDelete = async (item: VaultItem) => {
    if (!window.confirm(`Delete item #${item.id}? This cannot be undone.`)) return;

    setDeletingId(item.id);
    try {
      await deleteVaultItem(item.id);
      if (selected?.id === item.id) setSelected(null);
      if (expandedItem?.id === item.id) setExpandedItem(null);
      refresh();
    } catch {
      // Keep UX simple for now; refresh state stays unchanged on failure.
    } finally {
      setDeletingId(null);
    }
  };

  const openExpanded = useCallback((item: VaultItem) => {
    if (Date.now() < suppressOpenUntilRef.current) return;
    setExpandedItem(item);
  }, []);

  const closeExpanded = useCallback(() => {
    suppressOpenUntilRef.current = Date.now() + 250;
    setExpandedItem(null);
  }, []);

  useEffect(() => {
    if (!expandedItem) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeExpanded();
      }
    };

    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKeyDown);

    return () => {
      document.body.style.overflow = prevOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [expandedItem, closeExpanded]);

  // Group items by persona
  const visibleItems = items.filter((item) => {
    if (modelFilter === "all") return true;
    const model = getModelTag(item.tags);
    if (modelFilter === "a") return model === "flux_schnell";
    if (modelFilter === "b") return model === "flux2_klein";
    return true;
  });

  // Group items by persona
  const personaIds = Array.from(new Set(visibleItems.map((i) => i.persona_id)));

  // Items for the currently open folder
  const folderItems = openFolder !== null ? visibleItems.filter((i) => i.persona_id === openFolder) : [];

  useEffect(() => {
    localStorage.setItem("vault_modelFilter", modelFilter);
  }, [modelFilter]);

  useEffect(() => {
    if (selected && !visibleItems.some((i) => i.id === selected.id)) {
      setSelected(null);
    }
    if (expandedItem && !visibleItems.some((i) => i.id === expandedItem.id)) {
      setExpandedItem(null);
    }
  }, [modelFilter, visibleItems, selected, expandedItem]);

  return (
    <div className="bg-zinc-900 p-6 rounded-xl border border-zinc-800">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <span>🔒</span>
          {openFolder !== null
            ? `${personas.find((p) => p.id === openFolder)?.name ?? "Unknown"}'s Vault`
            : "Content Vault"}
        </h2>
        <div className="flex items-center gap-3">
          {stats && (
            <div className="flex gap-3 text-xs text-zinc-400">
              <span>{stats.total} items</span>
              <span>❤️ {stats.favorites}</span>
              <span>📤 {stats.posted}</span>
              <span>⬆️ {stats.upscaled}</span>
            </div>
          )}
          {openFolder !== null && (
            <button
              onClick={() => { setOpenFolder(null); setSelected(null); }}
              className="text-xs px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 rounded-lg transition-colors"
            >
              ← Back to Folders
            </button>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 mb-4">
        <button
          onClick={() => setFavOnly(!favOnly)}
          className={`text-xs px-3 py-2 rounded-lg border transition-colors ${
            favOnly ? "border-red-500 bg-red-600/20 text-red-300" : "border-zinc-700 bg-zinc-800 text-zinc-400"
          }`}
        >
          ❤️ Favorites Only
        </button>
        <div className="flex gap-1.5">
          <button
            onClick={() => setModelFilter("all")}
            className={`text-xs px-3 py-2 rounded-lg border transition-colors ${
              modelFilter === "all"
                ? "border-amber-500 bg-amber-600/20 text-amber-300"
                : "border-zinc-700 bg-zinc-800 text-zinc-400"
            }`}
          >
            All Models
          </button>
          <button
            onClick={() => setModelFilter("a")}
            className={`text-xs px-3 py-2 rounded-lg border transition-colors ${
              modelFilter === "a"
                ? "border-amber-500 bg-amber-600/20 text-amber-300"
                : "border-zinc-700 bg-zinc-800 text-zinc-400"
            }`}
          >
            A Only
          </button>
          <button
            onClick={() => setModelFilter("b")}
            className={`text-xs px-3 py-2 rounded-lg border transition-colors ${
              modelFilter === "b"
                ? "border-amber-500 bg-amber-600/20 text-amber-300"
                : "border-zinc-700 bg-zinc-800 text-zinc-400"
            }`}
          >
            B Only
          </button>
        </div>
      </div>

      {openFolder === null ? (
        /* ── Folder grid: one card per persona ── */
        personaIds.length === 0 ? (
          <p className="text-zinc-500 text-sm text-center py-8">No content in vault yet.</p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
            {personaIds.map((pid) => {
              const persona = personas.find((p) => p.id === pid);
              const personaItems = visibleItems.filter((i) => i.persona_id === pid);
              const withFile = personaItems.filter((i) => i.file_path);
              const latest = withFile[0];
              const favCount = personaItems.filter((i) => i.is_favorite).length;
              const postedCount = personaItems.filter((i) => i.is_posted).length;
              return (
                <div
                  key={pid}
                  onClick={() => setOpenFolder(pid)}
                  className="bg-zinc-800/50 rounded-xl border border-zinc-800 overflow-hidden cursor-pointer group hover:border-purple-600/40 hover:scale-[1.02] transition-all"
                >
                  {/* Cover image */}
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
                    {/* Overlay */}
                    <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent" />
                    <div className="absolute bottom-0 left-0 right-0 p-3">
                      <h3 className="font-semibold text-sm truncate">
                        {persona?.name ?? `Persona #${pid}`}
                      </h3>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-[10px] text-zinc-400">
                          {withFile.length} item{withFile.length !== 1 ? "s" : ""}
                        </span>
                        {favCount > 0 && (
                          <span className="text-[10px] text-red-400">❤️ {favCount}</span>
                        )}
                        {postedCount > 0 && (
                          <span className="text-[10px] text-emerald-400">📤 {postedCount}</span>
                        )}
                      </div>
                    </div>
                    {/* Stack count */}
                    {withFile.length > 1 && (
                      <div className="absolute top-2 right-2 text-[10px] bg-black/60 backdrop-blur-sm px-2 py-0.5 rounded-full text-zinc-300">
                        +{withFile.length - 1}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )
      ) : (
        /* ── Expanded folder: all vault items for the selected persona ── */
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
            {folderItems.map((item) => (
              <div
                key={item.id}
                className={`relative rounded-xl border overflow-hidden cursor-pointer transition-colors group ${
                  selected?.id === item.id ? "border-purple-500" : "border-zinc-800 hover:border-zinc-700"
                }`}
                onClick={() => setSelected(selected?.id === item.id ? null : item)}
              >
                <div className="aspect-square bg-zinc-800">
                  {getPreviewPath(item) && (
                    <AnimatedPreview
                      src={imageUrl(getPreviewPath(item) as string)}
                      alt=""
                      filePath={item.file_path ?? ""}
                      className="w-full h-full object-cover"
                      onClick={(e) => {
                        e.stopPropagation();
                        openExpanded(item);
                      }}
                    />
                  )}
                </div>
                {/* Badges */}
                <div className="absolute top-1 left-1">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(item);
                    }}
                    disabled={deletingId === item.id}
                    className="text-[10px] bg-black/60 hover:bg-red-700/80 px-1.5 py-0.5 rounded-full transition-colors disabled:opacity-50"
                    title="Delete item"
                  >
                    {deletingId === item.id ? "..." : "🗑"}
                  </button>
                </div>
                <div className="absolute top-1 right-1 flex gap-1">
                  {isVideoItem(item) && <span className="text-[10px] bg-purple-600/80 px-1.5 py-0.5 rounded-full">🎬</span>}
                  {getModelTag(item.tags) && (
                    <span className="text-[10px] bg-amber-600/80 px-1.5 py-0.5 rounded-full" title={`Model: ${getModelTag(item.tags)}`}>
                      {modelBadge(getModelTag(item.tags))}
                    </span>
                  )}
                  {item.is_favorite && <span className="text-[10px] bg-red-600/80 px-1.5 py-0.5 rounded-full">❤️</span>}
                  {item.upscaled_path && !isVideoItem(item) && <span className="text-[10px] bg-blue-600/80 px-1.5 py-0.5 rounded-full">4K</span>}
                  {item.is_posted && <span className="text-[10px] bg-emerald-600/80 px-1.5 py-0.5 rounded-full">📤</span>}
                </div>
                {/* Prompt preview on hover */}
                <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  <p className="text-[10px] text-zinc-300 truncate">
                    {item.prompt_used ?? `#${item.id}`}
                  </p>
                </div>
              </div>
            ))}
          </div>

          {folderItems.length === 0 && (
            <p className="text-zinc-500 text-sm text-center py-8">No content for this persona.</p>
          )}

          {/* Selected item detail panel */}
          {selected && (
            <div className="mt-4 p-4 bg-zinc-800/50 rounded-xl border border-zinc-700 space-y-3">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-sm font-medium">
                    Content #{selected.id} — {personas.find((p) => p.id === selected.persona_id)?.name}
                  </h3>
                  {getModelTag(selected.tags) && (
                    <p className="text-[11px] text-amber-300 mt-1">
                      Model: {getModelTag(selected.tags)?.replace(/_/g, " ")}
                    </p>
                  )}
                  <p className="text-xs text-zinc-500 mt-1 line-clamp-2">{selected.prompt_used}</p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleFavorite(selected.id)}
                    className="text-lg hover:scale-125 transition-transform"
                    title="Toggle favorite"
                  >
                    {selected.is_favorite ? "❤️" : "🤍"}
                  </button>
                  <button
                    onClick={() => handleDelete(selected)}
                    disabled={deletingId === selected.id}
                    className="text-xs px-2.5 py-1.5 rounded-lg bg-red-900/50 border border-red-700 hover:bg-red-800/70 transition-colors disabled:opacity-50"
                    title="Delete this item"
                  >
                    {deletingId === selected.id ? "Deleting..." : "Delete"}
                  </button>
                </div>
              </div>

              {getPreviewPath(selected) && (
                <button
                  type="button"
                  onClick={() => openExpanded(selected)}
                  className="w-full rounded-lg overflow-hidden border border-zinc-700 hover:border-zinc-500 transition-colors"
                  title="Open full size"
                >
                  {isVideoItem(selected) ? (
                    <video
                      src={imageUrl(getPreviewPath(selected) as string)}
                      className="w-full max-h-72 object-contain bg-black"
                      controls
                      preload="metadata"
                    />
                  ) : (
                    <img
                      src={imageUrl(getPreviewPath(selected) as string)}
                      alt="Selected vault content"
                      className="w-full max-h-72 object-contain bg-black"
                      loading="lazy"
                    />
                  )}
                </button>
              )}

              {/* Caption */}
              {selected.caption && (
                <div className="p-2 bg-zinc-900 rounded-lg">
                  <p className="text-xs text-zinc-300">{selected.caption}</p>
                  {selected.hashtags && (
                    <p className="text-[10px] text-purple-400 mt-1">
                      {selected.hashtags.split(",").map((h) => `#${h.trim()}`).join(" ")}
                    </p>
                  )}
                </div>
              )}

              {/* Actions */}
              <div className="flex flex-wrap gap-2">
                {PLATFORMS.map((plat) => (
                  <button
                    key={plat}
                    onClick={() => handleCaption(selected, plat)}
                    disabled={captioning}
                    className="text-[11px] px-3 py-1.5 bg-zinc-700 hover:bg-zinc-600 rounded-lg transition-colors disabled:opacity-40"
                  >
                    {captioning ? "..." : `✍️ ${plat} caption`}
                  </button>
                ))}
              </div>

              <div className="flex flex-wrap gap-2">
                {PLATFORMS.map((plat) => (
                  <button
                    key={plat}
                    onClick={() => handlePost(selected, plat)}
                    disabled={posting === plat}
                    className="text-[11px] px-3 py-1.5 bg-gradient-to-r from-emerald-700 to-teal-700 hover:from-emerald-800 hover:to-teal-800 rounded-lg transition-colors disabled:opacity-40"
                  >
                    {posting === plat ? "Posting..." : `📤 Post to ${plat}`}
                  </button>
                ))}
              </div>

              {/* Download MP4 for videos */}
              {isVideoItem(selected) && (
                <div>
                  <a
                    href={downloadMp4Url(selected.id)}
                    download
                    className="inline-block text-[11px] px-3 py-1.5 bg-gradient-to-r from-violet-700 to-purple-700 hover:from-violet-800 hover:to-purple-800 rounded-lg transition-colors"
                  >
                    ⬇️ Download MP4
                  </a>
                </div>
              )}

              {selected.posted_platforms && (
                <p className="text-[10px] text-emerald-400">
                  Posted to: {selected.posted_platforms.split(",").join(", ")}
                </p>
              )}
            </div>
          )}
        </>
      )}

      {expandedItem && (
        <div
          className="fixed inset-0 z-50 bg-black/90 backdrop-blur-sm p-4"
          onMouseDown={closeExpanded}
        >
          <div className="absolute top-4 right-4 z-10 flex gap-2">
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                handleDelete(expandedItem);
              }}
              disabled={deletingId === expandedItem.id}
              className="px-3 py-2 rounded-lg bg-red-900/70 border border-red-700 hover:bg-red-800 transition-colors disabled:opacity-50"
            >
              {deletingId === expandedItem.id ? "Deleting..." : "Delete"}
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                closeExpanded();
              }}
              className="px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 hover:bg-zinc-700 transition-colors"
            >
              Close
            </button>
          </div>
          <div className="w-full h-full overflow-auto" onMouseDown={(e) => e.stopPropagation()}>
            {isVideoItem(expandedItem) ? (
              <div className="min-h-full flex items-center justify-center">
                <video
                  src={imageUrl(getPreviewPath(expandedItem) as string)}
                  controls
                  autoPlay
                  className="max-w-full max-h-full"
                />
              </div>
            ) : (
              <img
                src={imageUrl(getPreviewPath(expandedItem) as string)}
                alt="Full size"
                className="block"
                style={{ maxWidth: "none", width: "auto", height: "auto" }}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

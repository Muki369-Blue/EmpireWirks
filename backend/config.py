"""Empire role-aware configuration.

Single env var controls Mac-vs-Shadow behaviour:
    EMPIRE_ROLE=hub      (default) — Mac hub: shadow proxy + ping, ComfyUI :8000
    EMPIRE_ROLE=shadow   — Windows shadow PC: no shadow proxy, ComfyUI :8188
"""
import os


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}

EMPIRE_ROLE: str = os.environ.get("EMPIRE_ROLE", "hub").lower()
if not os.environ.get("EMPIRE_ROLE"):
    # On Windows shadow workers default to shadow when role is not explicitly set.
    EMPIRE_ROLE = "shadow" if os.name == "nt" else "hub"
if EMPIRE_ROLE not in {"hub", "shadow"}:
    EMPIRE_ROLE = "hub"
IS_HUB: bool = EMPIRE_ROLE == "hub"
IS_SHADOW: bool = EMPIRE_ROLE == "shadow"

# ComfyUI port: both Mac and Windows desktops default to 8000
COMFY_PORT: int = int(os.environ.get("COMFY_PORT", "8000"))

# Shadow-Wirk remote URL (only meaningful on the hub)
SHADOW_URL: str = os.environ.get("SHADOW_WIRKS_URL", "http://100.126.90.91:8800") if IS_HUB else ""

# Label stamped on generation jobs so we know which machine produced them
MACHINE_LABEL: str = "mac" if IS_HUB else "shadow"

# Auto memory/model unload after T2I completion.
# Default: disabled on Mac hub to avoid cold-start reload penalties;
# enabled on shadow worker where memory pressure is usually higher.
AUTO_UNLOAD_AFTER_T2I: bool = _env_bool("AUTO_UNLOAD_AFTER_T2I", default=not IS_HUB)

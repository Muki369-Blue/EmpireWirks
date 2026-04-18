"""Empire role-aware configuration.

Single env var controls Mac-vs-Shadow behaviour:
    EMPIRE_ROLE=hub      (default) — Mac hub: shadow proxy + ping, ComfyUI :8000
    EMPIRE_ROLE=shadow   — Windows shadow PC: no shadow proxy, ComfyUI :8188
"""
import os

EMPIRE_ROLE: str = os.environ.get("EMPIRE_ROLE", "hub").lower()
IS_HUB: bool = EMPIRE_ROLE == "hub"
IS_SHADOW: bool = EMPIRE_ROLE == "shadow"

# ComfyUI port: Mac desktop uses 8000, Windows desktop uses 8188
COMFY_PORT: int = int(os.environ.get("COMFY_PORT", "8000" if IS_HUB else "8188"))

# Shadow-Wirk remote URL (only meaningful on the hub)
SHADOW_URL: str = os.environ.get("SHADOW_WIRKS_URL", "http://100.119.54.18:8800") if IS_HUB else ""

# Label stamped on generation jobs so we know which machine produced them
MACHINE_LABEL: str = "mac" if IS_HUB else "shadow"

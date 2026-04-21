"""
ComfyUI API wrapper.

ComfyUI exposes:
  POST http://127.0.0.1:8188/prompt          — queue a workflow
  GET  http://127.0.0.1:8188/history/{id}     — check job status
  GET  http://127.0.0.1:8188/view?filename=x  — download output image

This module wraps those endpoints so the rest of the backend
never talks to ComfyUI directly.

It can also auto-start ComfyUI using the Desktop app's bundled code
with the local data directory at ~/Documents/ComfyUI.
"""

import uuid
import random
import logging
import socket
import subprocess
import atexit
import time
import os
import json
import threading
from pathlib import Path
from typing import Optional

import requests

try:
    from .config import COMFY_PORT
except ImportError:
    from config import COMFY_PORT

logger = logging.getLogger(__name__)

COMFY_BASE = f"http://127.0.0.1:{COMFY_PORT}"
CLIENT_ID = str(uuid.uuid4())

IMAGE_MODEL_PROFILES = {
    "flux_schnell": {
        "clip_name1": "t5xxl_fp16.safetensors",
        "clip_name2": "clip_l.safetensors",
        "unet_name": "flux1-schnell.safetensors",
        "vae_name": "ae.safetensors",
        "steps": 4,
        "guidance": 3.5,
    },
    "flux2_klein": {
        "clip_name1": "t5xxl_fp16.safetensors",
        "clip_name2": "clip_l.safetensors",
        "unet_name": "Flux2-Klein-9B-True-v2-bf16.safetensors",
        "vae_name": "ae.safetensors",
        "steps": 6,
        "guidance": 3.5,
    },
}

SOCIALMAN_PLATFORM_NODE_MAP = {
    "facebook": "FacebookPosterData",
    "instagram": "InstagramPosterData",
    "linkedin": "LinkedinPosterData",
    "pinterest": "PinterestPosterData",
    "tiktok": "TiktokPosterData",
    "twitter": "TwitterPosterData",
}

# Managed ComfyUI subprocess (if we started it)
_comfyui_process: Optional[subprocess.Popen] = None
_socialman_object_info_cache: set[str] = set()
_socialman_object_info_checked_at = 0.0

# ─── Progress Tracking ───────────────────────────────────────────────

# Stores progress per prompt_id: {"value": current_step, "max": total_steps}
_progress: dict[str, dict] = {}
_progress_lock = threading.Lock()
_ws_thread: Optional[threading.Thread] = None


def get_progress(prompt_id: str) -> dict:
    """Get progress for a prompt_id. Returns {"value": N, "max": M} or empty dict."""
    with _progress_lock:
        return _progress.get(prompt_id, {}).copy()


def _normalize_socialman_platforms(platforms: Optional[list[str]]) -> list[str]:
    normalized: list[str] = []
    for platform in platforms or []:
        value = (platform or "").strip().lower()
        if value in SOCIALMAN_PLATFORM_NODE_MAP and value not in normalized:
            normalized.append(value)
    return normalized


def _render_socialman_template(
    template: Optional[str],
    *,
    default: str,
    persona_name: str,
    prompt_text: str,
    platform: str,
) -> str:
    if not template:
        return default
    try:
        rendered = template.format(persona=persona_name, prompt=prompt_text, platform=platform)
        return rendered.strip() or default
    except Exception:
        logger.warning("Invalid SocialMan template for persona=%s platform=%s", persona_name, platform)
        return template.strip() or default


def _get_object_info_names() -> set[str]:
    global _socialman_object_info_cache, _socialman_object_info_checked_at
    now = time.time()
    if _socialman_object_info_cache and now - _socialman_object_info_checked_at < 30:
        return _socialman_object_info_cache
    try:
        resp = requests.get(f"{COMFY_BASE}/object_info", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            _socialman_object_info_cache = set(data.keys())
            _socialman_object_info_checked_at = now
            return _socialman_object_info_cache
    except Exception as exc:
        logger.warning("Failed to query ComfyUI object_info: %s", exc)
    return set()


def _socialman_nodes_available(platforms: list[str]) -> bool:
    available = _get_object_info_names()
    if not available:
        return False
    required = {
        "SocialManPoster",
        "SocialManMediaToPoster",
        "SocialManPostData",
        *(SOCIALMAN_PLATFORM_NODE_MAP[p] for p in platforms if p in SOCIALMAN_PLATFORM_NODE_MAP),
    }
    missing = sorted(required - available)
    if missing:
        logger.warning("SocialMan nodes missing in ComfyUI: %s", ", ".join(missing))
        return False
    return True


def _inject_socialman_nodes(workflow: dict, publish: Optional[dict], image_node_id: str = "8") -> tuple[dict, bool]:
    if not publish:
        return workflow, False

    token = (publish.get("token") or "").strip()
    platforms = _normalize_socialman_platforms(publish.get("platforms"))
    if not token or not platforms:
        return workflow, False
    if not _socialman_nodes_available(platforms):
        logger.info("Skipping SocialMan publish because required ComfyUI nodes are unavailable")
        return workflow, False

    persona_name = (publish.get("persona_name") or "Empire").strip() or "Empire"
    prompt_text = (publish.get("prompt") or "").strip()
    default_title = f"{persona_name} drop"
    default_description = prompt_text or f"Fresh content from {persona_name}."
    title_text = _render_socialman_template(
        publish.get("title_template"),
        default=default_title,
        persona_name=persona_name,
        prompt_text=prompt_text,
        platform="all",
    )
    description_text = _render_socialman_template(
        publish.get("description_template"),
        default=default_description,
        persona_name=persona_name,
        prompt_text=prompt_text,
        platform="all",
    )
    media_file = (publish.get("media_file") or f"{persona_name.lower().replace(' ', '_')}_{int(time.time())}.png").strip()

    workflow["60"] = {
        "class_type": "SocialManPostData",
        "inputs": {
            "title": title_text,
            "description": description_text,
        },
    }
    workflow["61"] = {
        "class_type": "SocialManMediaToPoster",
        "inputs": {
            "media_file": media_file,
            "images": [image_node_id, 0],
        },
    }
    workflow["62"] = {
        "class_type": "SocialManPoster",
        "inputs": {
            "token": token,
            "show_status_banner": None,
            "prepare_only": None,
            "media_file_path": ["61", 0],
            "post_data": ["60", 0],
        },
    }

    if "twitter" in platforms:
        workflow["70"] = {
            "class_type": "TwitterPosterData",
            "inputs": {
                "caption": _render_socialman_template(
                    publish.get("description_template"),
                    default=description_text,
                    persona_name=persona_name,
                    prompt_text=prompt_text,
                    platform="twitter",
                ),
            },
        }
        workflow["62"]["inputs"]["twitter_data"] = ["70", 0]

    if "linkedin" in platforms:
        workflow["71"] = {
            "class_type": "LinkedinPosterData",
            "inputs": {
                "caption": _render_socialman_template(
                    publish.get("description_template"),
                    default=description_text,
                    persona_name=persona_name,
                    prompt_text=prompt_text,
                    platform="linkedin",
                ),
            },
        }
        workflow["62"]["inputs"]["linkedin_data"] = ["71", 0]

    if "facebook" in platforms:
        workflow["72"] = {
            "class_type": "FacebookPosterData",
            "inputs": {
                "target_account": None,
                "caption": _render_socialman_template(
                    publish.get("description_template"),
                    default=description_text,
                    persona_name=persona_name,
                    prompt_text=prompt_text,
                    platform="facebook",
                ),
                "post_to_story": False,
                "fb_thumbnail": None,
            },
        }
        workflow["62"]["inputs"]["facebook_data"] = ["72", 0]

    if "instagram" in platforms:
        workflow["73"] = {
            "class_type": "InstagramPosterData",
            "inputs": {
                "target_account": None,
                "caption": _render_socialman_template(
                    publish.get("description_template"),
                    default=description_text,
                    persona_name=persona_name,
                    prompt_text=prompt_text,
                    platform="instagram",
                ),
                "post_to_story": False,
                "insta_thumbnail": None,
            },
        }
        workflow["62"]["inputs"]["instagram_data"] = ["73", 0]

    if "pinterest" in platforms:
        workflow["74"] = {
            "class_type": "PinterestPosterData",
            "inputs": {
                "target_board": None,
                "title": _render_socialman_template(
                    publish.get("title_template"),
                    default=title_text,
                    persona_name=persona_name,
                    prompt_text=prompt_text,
                    platform="pinterest",
                ),
                "description": _render_socialman_template(
                    publish.get("description_template"),
                    default=description_text,
                    persona_name=persona_name,
                    prompt_text=prompt_text,
                    platform="pinterest",
                ),
                "link": "",
                "pin_thumbnail": None,
            },
        }
        workflow["62"]["inputs"]["pinterest_data"] = ["74", 0]

    if "tiktok" in platforms:
        workflow["75"] = {
            "class_type": "TiktokPosterData",
            "inputs": {
                "caption": _render_socialman_template(
                    publish.get("description_template"),
                    default=description_text,
                    persona_name=persona_name,
                    prompt_text=prompt_text,
                    platform="tiktok",
                ),
                "photo_title": _render_socialman_template(
                    publish.get("title_template"),
                    default=title_text,
                    persona_name=persona_name,
                    prompt_text=prompt_text,
                    platform="tiktok",
                ),
                "video_cover_timestamp_percent_from_0_to_1": 0.5,
                "privacy": "PUBLIC_TO_EVERYONE",
                "users_can_comment": True,
                "users_can_duet": True,
                "users_can_stitch": True,
                "content_disclosure_enabled": False,
                "content_disclosure_branded_content": False,
                "content_disclosure_your_brand": False,
            },
        }
        workflow["62"]["inputs"]["tiktok_data"] = ["75", 0]

    return workflow, True


def _history_execution_error(job: dict) -> Optional[str]:
    status = job.get("status") or {}
    status_str = str(status.get("status_str") or "").lower()
    messages = status.get("messages") or []
    for message in messages:
        if not isinstance(message, (list, tuple)) or not message:
            continue
        event_type = str(message[0]).lower()
        payload = message[-1]
        if event_type == "execution_error":
            if isinstance(payload, dict):
                return payload.get("exception_message") or payload.get("error") or json.dumps(payload)
            return str(payload)
    if status_str == "error":
        return "ComfyUI execution error"
    return None


def _ws_listener():
    """Background thread: listen to ComfyUI WebSocket for progress events."""
    try:
        import websocket
    except ImportError:
        logger.warning("websocket-client not installed, progress tracking disabled")
        return

    ws_url = f"ws://127.0.0.1:{COMFY_PORT}/ws?clientId={CLIENT_ID}"
    _first_connect = True
    while True:
        try:
            ws = websocket.WebSocket()
            ws.connect(ws_url, timeout=10)
            if _first_connect:
                logger.info("ComfyUI WebSocket connected for progress tracking")
                _first_connect = False
            else:
                logger.debug("ComfyUI WebSocket reconnected")
            while True:
                msg = ws.recv()
                if not msg or not isinstance(msg, str):
                    continue
                try:
                    data = json.loads(msg)
                except (json.JSONDecodeError, TypeError):
                    continue
                msg_type = data.get("type")
                msg_data = data.get("data", {})
                if msg_type == "progress":
                    pid = msg_data.get("prompt_id", "")
                    if pid:
                        with _progress_lock:
                            _progress[pid] = {
                                "value": msg_data.get("value", 0),
                                "max": msg_data.get("max", 1),
                            }
                elif msg_type == "executed":
                    # Node finished — keep progress at 100%
                    pid = msg_data.get("prompt_id", "")
                    if pid:
                        with _progress_lock:
                            if pid in _progress:
                                _progress[pid]["value"] = _progress[pid]["max"]
                elif msg_type == "execution_cached":
                    pass
                elif msg_type == "executing" and msg_data.get("node") is None:
                    # Execution complete for this prompt
                    pid = msg_data.get("prompt_id", "")
                    if pid:
                        with _progress_lock:
                            _progress.pop(pid, None)
        except Exception as e:
            logger.debug("ComfyUI WebSocket disconnected: %s — reconnecting in 5s", e)
            time.sleep(5)
        finally:
            try:
                ws.close()
            except Exception:
                pass


def start_progress_listener():
    """Start the background WebSocket listener (call once at startup)."""
    global _ws_thread
    if _ws_thread and _ws_thread.is_alive():
        return
    _ws_thread = threading.Thread(target=_ws_listener, daemon=True, name="comfy-progress")
    _ws_thread.start()


# ─── ComfyUI Launcher ────────────────────────────────────────────────


def _detect_comfyui_listener(port: int = COMFY_PORT, timeout: float = 0.2) -> bool:
    """Check if something is listening on the given port."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except (ConnectionRefusedError, socket.timeout, OSError):
        return False


def ensure_comfyui() -> bool:
    """Start ComfyUI if it's not already running. Returns True if healthy."""
    global _comfyui_process

    # Already running?
    if _detect_comfyui_listener():
        logger.info("ComfyUI already listening on port %d", COMFY_PORT)
        return True

    # Already started by us but not responding?
    if _comfyui_process is not None and _comfyui_process.poll() is None:
        logger.info("ComfyUI process exists but not responding yet, waiting...")
        return _wait_for_comfyui(timeout=30)

    comfy_data = Path.home() / "Documents" / "ComfyUI"

    # Strategy 1: Try local ComfyUI checkout in ~/Documents/ComfyUI
    main_candidates = [
        comfy_data / "main.py",
        comfy_data / "ComfyUI" / "main.py",
    ]
    py_candidates = [
        comfy_data / ".venv" / "bin" / "python",
        comfy_data / ".venv" / "Scripts" / "python.exe",
        Path(os.environ.get("PYTHON", "")) if os.environ.get("PYTHON") else None,
    ]
    comfy_main = next((p for p in main_candidates if p.exists()), None)
    comfy_python = next((p for p in py_candidates if p and p.exists()), None)

    if comfy_main and comfy_python:
        cmd = [
            str(comfy_python),
            str(comfy_main),
            "--port", str(COMFY_PORT),
            "--base-directory", str(comfy_data),
        ]
        logger.info("Starting ComfyUI: %s", " ".join(cmd))
        try:
            _comfyui_process = subprocess.Popen(
                cmd,
                cwd=str(comfy_data),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            atexit.register(_shutdown_comfyui)
            return _wait_for_comfyui(timeout=60)
        except Exception as exc:
            logger.error("Failed to start ComfyUI from local checkout: %s", exc)

    # Strategy 1b (macOS): Use Desktop app bundle with local venv + data dir
    comfy_venv_python = comfy_data / ".venv" / "bin" / "python"
    comfy_app_main = Path("/Applications/ComfyUI.app/Contents/Resources/ComfyUI/main.py")
    extra_config = Path.home() / "Library" / "Application Support" / "ComfyUI" / "extra_models_config.yaml"
    if comfy_venv_python.exists() and comfy_app_main.exists():
        cmd = [
            str(comfy_venv_python),
            str(comfy_app_main),
            "--port", str(COMFY_PORT),
            "--base-directory", str(comfy_data),
        ]
        if extra_config.exists():
            cmd += ["--extra-model-paths-config", str(extra_config)]

        logger.info("Starting ComfyUI Desktop bundle: %s", " ".join(cmd))
        try:
            _comfyui_process = subprocess.Popen(
                cmd,
                cwd=str(comfy_data),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            atexit.register(_shutdown_comfyui)
            return _wait_for_comfyui(timeout=60)
        except Exception as exc:
            logger.error("Failed to start ComfyUI Desktop bundle: %s", exc)

    # Strategy 2: Try `open -a ComfyUI` (Desktop app)
    app_path = Path("/Applications/ComfyUI.app")
    if app_path.exists():
        try:
            subprocess.Popen(
                ["open", "-a", "ComfyUI"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("Launched ComfyUI Desktop app, waiting for server...")
            return _wait_for_comfyui(timeout=60)
        except Exception as exc:
            logger.error("Failed to launch ComfyUI Desktop: %s", exc)
            return False

    logger.warning("No ComfyUI installation found (checked ~/Documents/ComfyUI and /Applications/ComfyUI.app)")
    return False


def _wait_for_comfyui(timeout: int = 60) -> bool:
    """Poll until ComfyUI responds on the expected port."""
    for i in range(timeout):
        time.sleep(1)
        if _detect_comfyui_listener():
            # Verify /system_stats actually responds (not just TCP)
            try:
                resp = requests.get(f"{COMFY_BASE}/system_stats", timeout=2)
                if resp.status_code == 200:
                    logger.info("ComfyUI ready on port %d (waited %ds)", COMFY_PORT, i + 1)
                    return True
            except Exception:
                pass
    logger.warning("ComfyUI did not become ready within %ds", timeout)
    return False


def _shutdown_comfyui() -> None:
    """Terminate managed ComfyUI process on exit."""
    global _comfyui_process
    if _comfyui_process is not None and _comfyui_process.poll() is None:
        try:
            _comfyui_process.terminate()
            _comfyui_process.wait(timeout=10)
            logger.info("Stopped managed ComfyUI process")
        except Exception:
            try:
                _comfyui_process.kill()
            except Exception:
                pass
    _comfyui_process = None


def _flux_workflow(
    positive_prompt: str,
    lora_name: Optional[str] = None,
    negative_prompt: Optional[str] = None,
    width: int = 1024,
    height: int = 1024,
    batch_size: int = 1,
    steps: int = 4,
    guidance: float = 3.5,
    seed: Optional[int] = None,
    model_profile: Optional[str] = None,
    lora_strength_model: float = 0.85,
    lora_strength_clip: float = 0.85,
) -> dict:
    """
    Flux Schnell text-to-image workflow from AI-ArtWirks.

    Pipeline:
      Node 11 — DualCLIPLoader (t5xxl + clip_l for Flux)
      Node 12 — UNETLoader   (flux1-schnell)
      Node 10 — VAELoader    (ae.safetensors)
      Node 6  — CLIPTextEncode (positive prompt)  ← injected
      Node 26 — FluxGuidance
      Node 25 — RandomNoise   ← seed injected
      Node 16 — KSamplerSelect (euler)
      Node 17 — BasicScheduler
      Node 22 — BasicGuider
      Node 27 — EmptySD3LatentImage ← width/height/batch injected
      Node 13 — SamplerCustomAdvanced
      Node 8  — VAEDecode
      Node 9  — SaveImage
    """
    if seed is None:
        seed = random.randint(0, 2**53)

    profile_name = (model_profile or "flux_schnell").lower()
    profile = IMAGE_MODEL_PROFILES.get(profile_name, IMAGE_MODEL_PROFILES["flux_schnell"])

    # Flux doesn't support a separate negative conditioning node.
    # Append negative terms as "Avoid:" suffix — established Flux community pattern.
    final_prompt = positive_prompt
    if negative_prompt:
        final_prompt = f"{positive_prompt}\n\nAvoid: {negative_prompt}"

    workflow = {
        "11": {
            "class_type": "DualCLIPLoader",
            "inputs": {
                "clip_name1": profile["clip_name1"],
                "clip_name2": profile["clip_name2"],
                "type": "flux",
            },
        },
        "12": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": profile["unet_name"],
                "weight_dtype": "default",
            },
        },
        "10": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": profile["vae_name"],
            },
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": final_prompt,
                "clip": ["11", 0],
            },
        },
        "26": {
            "class_type": "FluxGuidance",
            "inputs": {
                "guidance": guidance,
                "conditioning": ["6", 0],
            },
        },
        "25": {
            "class_type": "RandomNoise",
            "inputs": {
                "noise_seed": seed,
            },
        },
        "16": {
            "class_type": "KSamplerSelect",
            "inputs": {
                "sampler_name": "euler",
            },
        },
        "17": {
            "class_type": "BasicScheduler",
            "inputs": {
                "scheduler": "simple",
                "steps": steps,
                "denoise": 1,
                "model": ["12", 0],
            },
        },
        "22": {
            "class_type": "BasicGuider",
            "inputs": {
                "model": ["12", 0],
                "conditioning": ["26", 0],
            },
        },
        "27": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": batch_size,
            },
        },
        "13": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["25", 0],
                "guider": ["22", 0],
                "sampler": ["16", 0],
                "sigmas": ["17", 0],
                "latent_image": ["27", 0],
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["13", 0],
                "vae": ["10", 0],
            },
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "Empire/gen",
                "images": ["8", 0],
            },
        },
    }

    # Inject LoRA if the persona has one — wire between UNET and the guider/scheduler
    if lora_name:
        workflow["30"] = {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": lora_name,
                "strength_model": lora_strength_model,
                "strength_clip": lora_strength_clip,
                "model": ["12", 0],
                "clip": ["11", 0],
            },
        }
        # Re-wire downstream nodes to use LoRA outputs
        workflow["17"]["inputs"]["model"] = ["30", 0]
        workflow["22"]["inputs"]["model"] = ["30", 0]
        workflow["6"]["inputs"]["clip"] = ["30", 1]

    return workflow


def upload_image_to_comfyui(image_path: str) -> Optional[str]:
    """Upload a local image to ComfyUI's input directory. Returns the filename ComfyUI uses."""
    path = Path(image_path)
    if not path.exists():
        logger.error("Reference image not found: %s", image_path)
        return None
    try:
        with open(path, "rb") as f:
            resp = requests.post(
                f"{COMFY_BASE}/upload/image",
                files={"image": (path.name, f, "image/png")},
                data={"overwrite": "true"},
                timeout=30,
            )
        resp.raise_for_status()
        data = resp.json()
        name = data.get("name", path.name)
        logger.info("Uploaded reference image to ComfyUI: %s", name)
        return name
    except Exception as exc:
        logger.error("Failed to upload image to ComfyUI: %s", exc)
        return None


def _flux_redux_workflow(
    positive_prompt: str,
    reference_image_name: str,
    lora_name: Optional[str] = None,
    negative_prompt: Optional[str] = None,
    width: int = 1024,
    height: int = 1024,
    batch_size: int = 1,
    steps: int = 4,
    guidance: float = 3.5,
    redux_strength: float = 0.85,
    seed: Optional[int] = None,
    model_profile: Optional[str] = None,
    lora_strength_model: float = 0.85,
    lora_strength_clip: float = 0.85,
) -> dict:
    """
    Flux Schnell + Redux face/style consistency workflow.

    Proven from Ai-ArtWirks flux_redux_identity_v1.json.
    Adds SigCLIP vision encoding + StyleModelApply (Redux) to the base Flux pipeline.

    Extra nodes vs base workflow:
      Node 38 — CLIPVisionLoader (sigclip_vision_patch14_384)
      Node 39 — CLIPVisionEncode (encodes reference image)
      Node 40 — LoadImage        (the reference face image)
      Node 41 — StyleModelApply  (applies Redux conditioning)
      Node 42 — StyleModelLoader (flux1-redux-dev)
    """
    if seed is None:
        seed = random.randint(0, 2**53)

    profile_name = (model_profile or "flux_schnell").lower()
    profile = IMAGE_MODEL_PROFILES.get(profile_name, IMAGE_MODEL_PROFILES["flux_schnell"])
    steps = profile.get("steps", steps)
    guidance = profile.get("guidance", guidance)

    # Start with the base Flux workflow
    workflow = _flux_workflow(
        positive_prompt,
        lora_name,
        negative_prompt,
        width,
        height,
        batch_size,
        steps,
        guidance,
        seed,
        model_profile,
        lora_strength_model,
        lora_strength_clip,
    )

    # Add Redux nodes
    workflow["38"] = {
        "class_type": "CLIPVisionLoader",
        "inputs": {
            "clip_name": "sigclip_vision_patch14_384.safetensors",
        },
    }
    workflow["40"] = {
        "class_type": "LoadImage",
        "inputs": {
            "image": reference_image_name,
            "upload": "image",
        },
    }
    workflow["39"] = {
        "class_type": "CLIPVisionEncode",
        "inputs": {
            "crop": "center",
            "clip_vision": ["38", 0],
            "image": ["40", 0],
        },
    }
    workflow["42"] = {
        "class_type": "StyleModelLoader",
        "inputs": {
            "style_model_name": "flux1-redux-dev.safetensors",
        },
    }
    workflow["41"] = {
        "class_type": "StyleModelApply",
        "inputs": {
            "strength": redux_strength,
            "strength_type": "multiply",
            "conditioning": ["26", 0],
            "style_model": ["42", 0],
            "clip_vision_output": ["39", 0],
        },
    }

    # Re-wire: the guider now uses Redux-conditioned output instead of raw FluxGuidance
    workflow["22"]["inputs"]["conditioning"] = ["41", 0]

    return workflow


# ─── Wan 2.1 Video Workflows ─────────────────────────────────────────


def _wan_t2v_workflow(
    positive_prompt: str,
    negative_prompt: Optional[str] = None,
    width: int = 832,
    height: int = 480,
    length: int = 81,
    steps: int = 30,
    cfg: float = 4.5,
    seed: Optional[int] = None,
    lora_name: Optional[str] = None,
    scheduler: str = "normal",
) -> dict:
    """
    Wan 2.1 Text-to-Video workflow (1.3B).

    Pipeline:
      Node 1  — UNETLoader   (wan2.1_t2v_1.3B_bf16)
      Node 2  — CLIPLoader   (umt5_xxl_fp8_e4m3fn_scaled, type=wan)
      Node 3  — VAELoader    (wan_2.1_vae)
      Node 4  — CLIPTextEncode (positive prompt)
      Node 5  — CLIPTextEncode (negative prompt)
      Node 6  — WanImageToVideo (creates empty video latent)
      Node 7  — KSampler
      Node 8  — VAEDecode
      Node 9  — SaveAnimatedWEBP
    """
    if seed is None:
        seed = random.randint(0, 2**53)

    workflow = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "wan2.1_t2v_1.3B_bf16.safetensors",
                "weight_dtype": "default",
            },
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                "type": "wan",
            },
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "wan_2.1_vae.safetensors",
            },
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": positive_prompt,
                "clip": ["2", 0],
            },
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative_prompt or "",
                "clip": ["2", 0],
            },
        },
        "6": {
            "class_type": "WanImageToVideo",
            "inputs": {
                "positive": ["4", 0],
                "negative": ["5", 0],
                "vae": ["3", 0],
                "width": width,
                "height": height,
                "length": length,
                "batch_size": 1,
            },
        },
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["6", 0],
                "negative": ["6", 1],
                "latent_image": ["6", 2],
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler",
                "scheduler": scheduler,
                "denoise": 1.0,
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["7", 0],
                "vae": ["3", 0],
            },
        },
        "9": {
            "class_type": "SaveAnimatedWEBP",
            "inputs": {
                "filename_prefix": "Empire/video",
                "fps": 16.0,
                "lossless": False,
                "quality": 95,
                "method": "default",
                "images": ["8", 0],
            },
        },
    }

    # Inject LoRA loader if specified
    if lora_name:
        workflow["13"] = {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": lora_name,
                "strength_model": 1.0,
                "strength_clip": 1.0,
                "model": ["1", 0],
                "clip": ["2", 0],
            },
        }
        # Re-wire: KSampler uses LoRA-modified model, CLIP encodes use LoRA-modified clip
        workflow["7"]["inputs"]["model"] = ["13", 0]
        workflow["4"]["inputs"]["clip"] = ["13", 1]
        workflow["5"]["inputs"]["clip"] = ["13", 1]

    return workflow


def _wan_i2v_workflow(
    positive_prompt: str,
    start_image_name: str,
    negative_prompt: Optional[str] = None,
    width: int = 832,
    height: int = 480,
    length: int = 81,
    steps: int = 30,
    cfg: float = 4.5,
    seed: Optional[int] = None,
    lora_name: Optional[str] = None,
    scheduler: str = "normal",
) -> dict:
    """
    Wan 2.1 Image-to-Video workflow (14B fp8).

    Same pipeline as T2V but uses the I2V model, adds CLIPVisionLoader +
    CLIPVisionEncode + LoadImage, and feeds start_image + clip_vision_output
    into WanImageToVideo.

    Extra nodes vs T2V:
      Node 10 — CLIPVisionLoader (clip_vision_h)
      Node 11 — LoadImage        (the start image)
      Node 12 — CLIPVisionEncode (encodes start image for conditioning)
    """
    if seed is None:
        seed = random.randint(0, 2**53)

    workflow = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "wan2.1_i2v_480p_14B_fp8_scaled.safetensors",
                "weight_dtype": "fp8_e4m3fn",
            },
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                "type": "wan",
            },
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "wan_2.1_vae.safetensors",
            },
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": positive_prompt,
                "clip": ["2", 0],
            },
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative_prompt or "",
                "clip": ["2", 0],
            },
        },
        "10": {
            "class_type": "CLIPVisionLoader",
            "inputs": {
                "clip_name": "clip_vision_h.safetensors",
            },
        },
        "11": {
            "class_type": "LoadImage",
            "inputs": {
                "image": start_image_name,
                "upload": "image",
            },
        },
        "12": {
            "class_type": "CLIPVisionEncode",
            "inputs": {
                "crop": "center",
                "clip_vision": ["10", 0],
                "image": ["11", 0],
            },
        },
        "6": {
            "class_type": "WanImageToVideo",
            "inputs": {
                "positive": ["4", 0],
                "negative": ["5", 0],
                "vae": ["3", 0],
                "width": width,
                "height": height,
                "length": length,
                "batch_size": 1,
                "clip_vision_output": ["12", 0],
                "start_image": ["11", 0],
            },
        },
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["6", 0],
                "negative": ["6", 1],
                "latent_image": ["6", 2],
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler",
                "scheduler": scheduler,
                "denoise": 1.0,
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["7", 0],
                "vae": ["3", 0],
            },
        },
        "9": {
            "class_type": "SaveAnimatedWEBP",
            "inputs": {
                "filename_prefix": "Empire/video",
                "fps": 16.0,
                "lossless": False,
                "quality": 95,
                "method": "default",
                "images": ["8", 0],
            },
        },
    }

    # Inject LoRA loader if specified
    if lora_name:
        workflow["13"] = {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": lora_name,
                "strength_model": 1.0,
                "strength_clip": 1.0,
                "model": ["1", 0],
                "clip": ["2", 0],
            },
        }
        workflow["7"]["inputs"]["model"] = ["13", 0]
        workflow["4"]["inputs"]["clip"] = ["13", 1]
        workflow["5"]["inputs"]["clip"] = ["13", 1]

    return workflow


def queue_video(
    positive_prompt: str,
    start_image: Optional[str] = None,
    negative_prompt: Optional[str] = None,
    width: int = 832,
    height: int = 480,
    length: int = 81,
    steps: int = 30,
    cfg: float = 4.5,
    seed: Optional[int] = None,
    lora_name: Optional[str] = None,
) -> dict:
    """Queue a Wan 2.1 video generation job. Uses I2V workflow if start_image is provided."""
    # LoRA presets: speed/distillation LoRAs need low steps + cfg to work properly
    _LORA_PRESETS = {
        "Lightning": {"steps": 4, "cfg": 1.0, "scheduler": "sgm_uniform"},
        "rCM": {"steps": 6, "cfg": 1.0},
        "self_forcing_dmd": {"steps": 4, "cfg": 1.0},
        "self_forcing_sid": {"steps": 6, "cfg": 1.0},
    }
    scheduler = "normal"
    if lora_name:
        for key, preset in _LORA_PRESETS.items():
            if key in lora_name:
                logger.info("Applying LoRA preset '%s': %s", key, preset)
                steps = preset.get("steps", steps)
                cfg = preset.get("cfg", cfg)
                scheduler = preset.get("scheduler", scheduler)
                break

    _DEFAULT_VIDEO_NEG = "blurry face, distorted face, deformed features, extra fingers, bad anatomy, disfigured, low quality, blurry"
    if not negative_prompt:
        negative_prompt = _DEFAULT_VIDEO_NEG
    if start_image:
        workflow = _wan_i2v_workflow(
            positive_prompt, start_image, negative_prompt,
            width, height, length, steps, cfg, seed, lora_name,
            scheduler,
        )
    else:
        workflow = _wan_t2v_workflow(
            positive_prompt, negative_prompt,
            width, height, length, steps, cfg, seed, lora_name,
            scheduler,
        )
    payload = {
        "prompt": workflow,
        "client_id": CLIENT_ID,
    }
    try:
        resp = requests.post(f"{COMFY_BASE}/prompt", json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data or data.get("node_errors"):
            logger.error(
                "ComfyUI workflow error (i2v=%s): %s | node_errors: %s",
                bool(start_image),
                data.get("error"),
                data.get("node_errors"),
            )
        else:
            logger.info("Queued video (i2v=%s): %s", bool(start_image), data.get("prompt_id"))
        return data
    except requests.ConnectionError:
        logger.error("Cannot reach ComfyUI at %s", COMFY_BASE)
        return {"error": "ComfyUI is not running. Start it first."}
    except Exception as exc:
        logger.error("ComfyUI error: %s", exc)
        return {"error": str(exc)}


def get_video_job_status(prompt_id: str) -> dict:
    """Check video job status — looks for animated images (webp/gif) in outputs."""
    try:
        resp = requests.get(f"{COMFY_BASE}/history/{prompt_id}", timeout=10)
        resp.raise_for_status()
        history = resp.json()

        if prompt_id not in history:
            # Check if it's actively running or still queued
            try:
                qr = requests.get(f"{COMFY_BASE}/queue", timeout=5)
                qdata = qr.json()
                running_ids = [item[1] for item in qdata.get("queue_running", [])]
                pending_ids = [item[1] for item in qdata.get("queue_pending", [])]
                if prompt_id in running_ids:
                    return {"status": "processing", "outputs": []}
                if prompt_id in pending_ids:
                    return {"status": "pending", "outputs": []}
            except Exception:
                pass
            return {"status": "pending", "outputs": []}

        job = history[prompt_id]
        execution_error = _history_execution_error(job)
        if execution_error:
            return {"status": "error", "detail": execution_error}
        outputs = []
        for node_id, node_out in job.get("outputs", {}).items():
            for img in node_out.get("images", []):
                outputs.append({
                    "filename": img["filename"],
                    "subfolder": img.get("subfolder", ""),
                    "type": img.get("type", "output"),
                })
            for vid in node_out.get("gifs", []):
                outputs.append({
                    "filename": vid["filename"],
                    "subfolder": vid.get("subfolder", ""),
                    "type": vid.get("type", "output"),
                })

        return {"status": "completed" if outputs else "processing", "outputs": outputs}
    except requests.ConnectionError:
        return {"status": "error", "detail": "ComfyUI unreachable"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def list_loras() -> list[str]:
    """Get list of available LoRA filenames from ComfyUI."""
    try:
        resp = requests.get(f"{COMFY_BASE}/object_info/LoraLoader", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        lora_list = data.get("LoraLoader", {}).get("input", {}).get("required", {}).get("lora_name", [[]])[0]
        return sorted(lora_list) if isinstance(lora_list, list) else []
    except Exception:
        return []


def queue_prompt(
    positive_prompt: str,
    lora_name: Optional[str] = None,
    reference_image: Optional[str] = None,
    negative_prompt: Optional[str] = None,
    seed: Optional[int] = None,
    model_profile: Optional[str] = None,
    lora_strength_model: float = 0.85,
    lora_strength_clip: float = 0.85,
    socialman_publish: Optional[dict] = None,
) -> dict:
    """Queue a generation job on ComfyUI. Uses Redux workflow if reference_image is provided."""
    profile_name = (model_profile or "flux_schnell").lower()
    profile = IMAGE_MODEL_PROFILES.get(profile_name, IMAGE_MODEL_PROFILES["flux_schnell"])
    steps = profile.get("steps", 4)
    guidance = profile.get("guidance", 3.5)

    if reference_image:
        workflow = _flux_redux_workflow(
            positive_prompt,
            reference_image,
            lora_name,
            negative_prompt,
            steps=steps,
            guidance=guidance,
            seed=seed,
            model_profile=profile_name,
            lora_strength_model=lora_strength_model,
            lora_strength_clip=lora_strength_clip,
        )
    else:
        workflow = _flux_workflow(
            positive_prompt,
            lora_name,
            negative_prompt,
            steps=steps,
            guidance=guidance,
            seed=seed,
            model_profile=profile_name,
            lora_strength_model=lora_strength_model,
            lora_strength_clip=lora_strength_clip,
        )
    workflow, socialman_applied = _inject_socialman_nodes(workflow, socialman_publish, image_node_id="8")
    payload = {
        "prompt": workflow,
        "client_id": CLIENT_ID,
    }
    try:
        resp = requests.post(f"{COMFY_BASE}/prompt", json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data or data.get("node_errors"):
            logger.error(
                "ComfyUI workflow error (redux=%s): %s | node_errors: %s",
                bool(reference_image),
                data.get("error"),
                data.get("node_errors"),
            )
        else:
            logger.info("Queued prompt (redux=%s): %s", bool(reference_image), data.get("prompt_id"))
        data["socialman_applied"] = socialman_applied
        return data
    except requests.ConnectionError:
        logger.error("Cannot reach ComfyUI at %s", COMFY_BASE)
        return {"error": "ComfyUI is not running. Start it first."}
    except Exception as exc:
        logger.error("ComfyUI error: %s", exc)
        return {"error": str(exc)}


def get_job_status(prompt_id: str) -> dict:
    """Check the status / outputs of a queued job."""
    try:
        resp = requests.get(f"{COMFY_BASE}/history/{prompt_id}", timeout=10)
        resp.raise_for_status()
        history = resp.json()

        if prompt_id not in history:
            return {"status": "pending", "outputs": []}

        job = history[prompt_id]
        execution_error = _history_execution_error(job)
        if execution_error:
            return {"status": "error", "detail": execution_error}
        outputs = []
        for node_id, node_out in job.get("outputs", {}).items():
            for img in node_out.get("images", []):
                outputs.append({
                    "filename": img["filename"],
                    "subfolder": img.get("subfolder", ""),
                    "type": img.get("type", "output"),
                })

        return {"status": "completed" if outputs else "processing", "outputs": outputs}
    except requests.ConnectionError:
        return {"status": "error", "detail": "ComfyUI unreachable"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def is_comfy_running() -> bool:
    """Quick health-check."""
    try:
        resp = requests.get(f"{COMFY_BASE}/system_stats", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def free_memory(unload_models: bool = True) -> bool:
    """Unload models and free VRAM/RAM via ComfyUI's /free endpoint."""
    try:
        resp = requests.post(
            f"{COMFY_BASE}/free",
            json={"unload_models": unload_models, "free_memory": True},
            timeout=10,
        )
        if resp.status_code == 200:
            logger.info("ComfyUI memory freed (unload_models=%s)", unload_models)
            return True
        logger.warning("ComfyUI /free returned %s", resp.status_code)
        return False
    except Exception as exc:
        logger.error("Failed to free ComfyUI memory: %s", exc)
        return False


def get_system_stats() -> Optional[dict]:
    """Get ComfyUI system stats including VRAM usage."""
    try:
        resp = requests.get(f"{COMFY_BASE}/system_stats", timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def interrupt():
    """Interrupt the currently running ComfyUI generation."""
    try:
        resp = requests.post(f"{COMFY_BASE}/interrupt", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def clear_queue():
    """Clear all pending items from the ComfyUI queue."""
    try:
        resp = requests.post(f"{COMFY_BASE}/queue", json={"clear": True}, timeout=5)
        return resp.status_code == 200
    except Exception:
        return False

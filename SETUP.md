# AI Content Empire - Setup Guide (Current)

## Repository

Canonical repo:

```bash
git clone https://github.com/Muki369-Blue/EmpireWirks.git Empire
```

## Deployment Modes

Empire is role-aware via `EMPIRE_ROLE`:

- `hub` (default): main machine (commonly Mac) that runs frontend/backend and can proxy video work to a shadow machine.
- `shadow`: GPU worker machine (commonly Windows PC) that runs backend + ComfyUI for heavy generation.

## Network and Ports

| Service | Port | Notes |
|---------|------|-------|
| Frontend (Next.js) | `3000` | Local dev UI |
| Backend (FastAPI) | `8800` | Bind to `0.0.0.0` for LAN/Tailscale access |
| ComfyUI | `8000` | Backend expects ComfyUI on localhost:`COMFY_PORT` |

Example machine mapping used in this project:

| Machine | Role | LAN IP | Tailscale IP |
|---------|------|--------|--------------|
| Windows PC | shadow (GPU worker) | `10.0.1.10` | `100.119.54.18` |
| Mac | hub/dev | - | - |

## Prerequisites

- Python 3.13 and virtualenv
- Node.js 18+
- ComfyUI Desktop installed
- NVIDIA GPU on shadow machine for Wan 2.1 video generation
- Optional Ollama for prompt refine/chat/caption features

## Required Models (ComfyUI)

Flux (image):

- `unet/flux1-schnell.safetensors`
- `clip/t5xxl_fp16.safetensors`
- `clip/clip_l.safetensors`
- `vae/ae.safetensors`

Wan 2.1 (video):

- `diffusion_models/wan2.1_t2v_1.3B_bf16.safetensors`
- `diffusion_models/wan2.1_i2v_480p_14B_fp8_scaled.safetensors`
- `text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors`
- `vae/wan_2.1_vae.safetensors`
- `clip_vision/clip_vision_h.safetensors`

## Start Commands

### Fast local start on Mac

Use the launcher script:

```bash
./Launch\ Empire.command
```

This clears ports, clears Next cache, starts backend on `:8800`, starts frontend on `:3000`, and opens the app.

### Manual backend start (Mac/Linux)

```bash
cd ~/dev/apps/Empire
backend/.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8800 --reload
```

### Manual frontend start

```bash
cd ~/dev/apps/Empire/frontend
NEXT_PUBLIC_API_URL=http://localhost:8800 npm run dev
```

### Windows shadow start

Use:

```bat
WinEmpire.bat
```

Or manual backend:

```powershell
cd C:\Users\Shadow\Desktop\Empire
.\.venv\Scripts\Activate.ps1
$env:EMPIRE_ROLE="shadow"
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8800 --reload
```

## Frontend Modes

Default:

```bash
npm run dev
```

Also available:

- `npm run dev:local`
- `npm run dev:split`

These mode scripts expect env templates at `frontend/env/local.env` and `frontend/env/split.env` and generate `frontend/.env.local`.

## Environment Variables

### Backend

| Variable | Default | Purpose |
|----------|---------|---------|
| `EMPIRE_ROLE` | `hub` | `hub` or `shadow` behavior |
| `COMFY_PORT` | `8000` | ComfyUI local API port |
| `SHADOW_WIRKS_URL` | `http://100.119.54.18:8800` (hub only) | Shadow backend base URL |
| `AUTO_UNLOAD_AFTER_T2I` | `false` on hub, `true` on shadow | Auto unload models after image completion |
| `FRONTEND_ORIGINS` | empty | Extra CORS origins, comma-separated |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama service URL |
| `OLLAMA_MODEL` | `empire-qwen2.5-14b` | LLM model for refine/chat/caption |

### Frontend

| Variable | Default | Purpose |
|----------|---------|---------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8800` | Primary backend URL |
| `NEXT_PUBLIC_VIDEO_API_URL` | same as API URL | Optional dedicated video endpoint |

## Architecture

Common split setup:

```text
Mac browser -> Next.js (:3000) -> FastAPI (:8800)
								  -> ComfyUI (:8000, local to machine running backend)
```

Hub + shadow setup:

```text
Hub backend (EMPIRE_ROLE=hub) -> shadow backend via SHADOW_WIRKS_URL for delegated video workflows
```

## API Surface

Core endpoints still include:

- `/health`
- `/personas/*`
- `/generate/{persona_id}`
- `/generations/*`
- `/generate-video` and `/generate-video/{persona_id}`
- `/video-status/{content_id}`
- `/upload-video-start-image`
- `/presets/*`
- `/links/*`

Additional modules now available:

- `/jobs/*`
- `/campaigns/*`
- `/agents/*`
- `/review/*`
- `/metrics/*`
- `/persona-memory/*`
- `/shadow/*` (hub proxy routes)
- vault/content/schedule/chat/analytics endpoints

Use live OpenAPI docs for exact request/response schemas:

- `http://localhost:8800/docs`
- `http://localhost:8800/openapi.json`

## Troubleshooting

- Frontend cannot reach backend: verify backend is listening on `0.0.0.0:8800` and `NEXT_PUBLIC_API_URL` matches LAN/Tailscale address.
- CORS issues: set `FRONTEND_ORIGINS` (comma-separated), for example `http://localhost:3000,http://127.0.0.1:3000`.
- Video stuck in processing: ensure ComfyUI is running on the same machine as backend, and Wan 2.1 models are installed.
- ComfyUI not detected: start ComfyUI Desktop manually, then restart backend.
- Prompt refine errors: run `ollama serve` and verify `OLLAMA_URL`.

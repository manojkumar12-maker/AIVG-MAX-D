# AIVG-MAX-D

**A self-hosted AI image and video studio powered by open-weight models and a free Google Colab GPU.**

AIVG-MAX-D is a browser studio for text-to-image, image-to-image, text-to-video and image-to-video
generation. There is no paid generation API: every request is rendered by ComfyUI on a GPU you
control, using open-weight models such as SD 1.5, SDXL, FLUX.1 schnell, Wan 2.1, LTX-Video and
AnimateDiff.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/manojkumar12-maker/AIVG-MAX-D/blob/main/notebooks/OpenGenerativeAI_Colab.ipynb)

- **Studio (live):** https://manojkumar12-maker.github.io/AIVG-MAX-D/
- **GPU backend:** [`notebooks/OpenGenerativeAI_Colab.ipynb`](notebooks/OpenGenerativeAI_Colab.ipynb)
- **Docs index:** [`docs/README.md`](docs/README.md)

> **Works out of the box:** SDXL text-to-image and image-to-image on a free Colab T4.
> Video, FLUX and SD 1.5 are shipped but need extra ComfyUI nodes and/or filename alignment.
> See [Model presets](#model-presets) and [Known limitations](#known-limitations) before you start.

---

## Contents

- [How it works](#how-it-works)
- [Features](#features)
- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Model presets](#model-presets)
- [Configuration](#configuration)
- [Run locally](#run-locally)
- [Repository layout](#repository-layout)
- [Deploy your own copy](#deploy-your-own-copy)
- [Troubleshooting](#troubleshooting)
- [Known limitations](#known-limitations)
- [Documentation](#documentation)
- [Model licences](#model-licences)
- [Tech stack](#tech-stack)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgements](#acknowledgements)

## How it works

```
Browser studio (React + Vite, hosted on GitHub Pages)
   │  session token over HTTPS
   ▼
FastAPI adapter (backend/adapter) — auth, job queue, uploads, gallery, settings
   │  ComfyUI JSON API on localhost
   ▼
ComfyUI on a Colab GPU — SD 1.5 / SDXL / FLUX schnell / Wan 2.1 / LTX / AnimateDiff
```

- **Frontend** (`frontend/`): static React SPA deployed to GitHub Pages; no server of its own.
- **Backend** (`backend/adapter/`): turns studio requests into ComfyUI workflows, runs one GPU job
  at a time, and stores results.
- **Workflows** (`backend/workflows/`): ComfyUI graph templates, one per model and mode.
- **Notebook** (`notebooks/`): installs everything on Colab, downloads models, and prints the URL
  and token the studio connects with.

## Features

- **Image Studio** — text-to-image with SD 1.5, SDXL or FLUX.1 schnell.
- **Image to Image** — upload a reference picture and restyle it (SDXL).
- **Video Studio** — text-to-video and image-to-video with Wan 2.1, LTX-Video or AnimateDiff.
- **Queue and progress** — live job updates over WebSocket, with polling as a fallback.
- **Gallery and history** — every result saved and browsable; videos preview in the browser.
- **Models page** — each model's VRAM need, disk size and licence shown in the app.
- **VRAM checks** — jobs that won't fit your GPU fail fast with a clear message instead of
  crashing ComfyUI mid-run.
- **Low-VRAM mode** — halves latent resolution and forces batch size 1.
- **Drive persistence** — optional model cache and output mirroring to Google Drive.

## Requirements

- A **Google account** for Colab (the free T4 tier is enough for SDXL images).
- **Node.js 20.19+ (or 22.12+)** for the frontend (Vite 7; the Pages workflow pins Node 22).
- **Python 3.10+** for the adapter (it uses `X | None` type syntax).
- No API keys and no paid generation service.

Video workflows are experimental: plan on installing ComfyUI custom nodes and using a
24 GB-class GPU for the larger models.

## Quick start

### 1. Start the GPU backend on Colab

1. Click **Open in Colab** above.
2. **Runtime → Change runtime type → T4 GPU** (the free tier works).
3. Run cells **A → E** in order:
   - **A** — checks the GPU, optionally mounts Google Drive to cache models and outputs.
   - **B** — installs ComfyUI and this repository.
   - **C** — pick a model preset (see the table below).
   - **D** — downloads the models (resumable, Drive-cached when mounted).
   - **E** — starts ComfyUI and the adapter, opens a `trycloudflare.com` tunnel, and prints a
     **Frontend URL** and a **Session token**.

Cell E must stay running while you generate. A runtime restart gives you a new tunnel URL and a
new token.

### 2. Optional: install custom nodes for video and FLUX

The notebook installs stock ComfyUI only. Video and FLUX workflows need extra node packs. Add this
as a new cell after cell **B** and run it before cell **E**:

```python
!git clone --depth 1 https://github.com/city96/ComfyUI-GGUF {COMFYUI_DIR}/custom_nodes/ComfyUI-GGUF
!git clone --depth 1 https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite {COMFYUI_DIR}/custom_nodes/ComfyUI-VideoHelperSuite
!git clone --depth 1 https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved {COMFYUI_DIR}/custom_nodes/ComfyUI-AnimateDiff-Evolved
!for d in {COMFYUI_DIR}/custom_nodes/*/; do [ -f "$d/requirements.txt" ] && pip -q install -r "$d/requirements.txt"; done
```

- **ComfyUI-GGUF** — FLUX schnell Q4.
- **VideoHelperSuite** — mp4 output for every video workflow.
- **AnimateDiff-Evolved** — AnimateDiff text-to-video.

LTX-Video and Wan use nodes that ship with a recent ComfyUI build. See
[Workflows and models](docs/WORKFLOWS.md) for the exact node classes each template needs.

### 3. Connect the studio

Open https://manojkumar12-maker.github.io/AIVG-MAX-D/, paste the **Frontend URL** and **Session
token** from cell E into the **Connection** panel, and wait for the status dot to turn green. The
token is stored in `sessionStorage` and is cleared when the tab closes.

## Model presets

These are the presets in notebook cell C. They control what cell D downloads.

| Preset (cell C) | Main downloads | Suggested GPU | Status |
|---|---|---|---|
| SD 1.5 (fastest, any GPU) | SD 1.5 checkpoint, ~2 GB | Any | Notebook saves a differently named file than the registry expects; see below |
| SDXL (high quality, ~12GB) | SDXL base 1.0, ~6.9 GB | ~12 GB VRAM | **Works out of the box** (recommended on T4) |
| SDXL + FLUX schnell Q4 (~16GB) | SDXL + FLUX Q4 GGUF + T5 + VAE | ~16 GB | Experimental; needs ComfyUI-GGUF and filename alignment |
| Everything incl. Wan 2.1 video (~24GB) | SDXL + Wan 2.1 T2V 1.3B + UMT5 + VAE | ~24 GB recommended | Experimental; needs VideoHelperSuite |

The notebook does **not** have presets for every registered model. Wan 2.1 I2V 14B, LTX-Video 2B
and AnimateDiff are registered in `backend/adapter/models_registry.py` and have workflow templates,
but you must download the weights manually and install the matching nodes.

On a free T4 (about 15 GB), use **SDXL** for images. Video generation is possible but slow and
usually needs `--lowvram`/`--novram`; the 14B I2V model needs a 24 GB-class GPU.

**Filename caveat:** in the current revision the SD 1.5 notebook preset saves
`sd_v1-5_pruned_emaonly_fp16.safetensors`, while the registry and workflow expect
`v1-5-pruned-emaonly-fp16.safetensors`. The FLUX preset also downloads Q4_K_S/FP8 files into
`unet/`/`clip/`, while the workflow expects `flux1-schnell-Q4_0.gguf`,
`t5-v1_1-xxl-encoder-Q5_1.gguf` and `ae.safetensors`. Until those are aligned, prefer SDXL. The
exact expected names are listed in [docs/WORKFLOWS.md](docs/WORKFLOWS.md#known-filename-mismatches).

## Configuration

Everything is environment-driven. The Colab notebook sets these automatically; use them when
running the adapter locally.

| Variable | Default | Purpose |
|---|---|---|
| `OGAI_SESSION_TOKEN` | generated on first boot | Token required by `/api/*` and `/ws/jobs`. If unset, a random token is generated and persisted to `OGAI_STATE_DIR/runtime.json`. |
| `OGAI_COMFY_URL` | `http://127.0.0.1:8188` | Local ComfyUI base URL. |
| `OGAI_OUTPUT_DIR` | `backend/outputs` | Where generated files are saved and served from. |
| `OGAI_UPLOAD_DIR` | `backend/uploads` | Where reference images are stored. |
| `OGAI_STATE_DIR` | `backend/state` | Job history, settings and the generated token. |
| `OGAI_WORKFLOW_DIR` | `backend/workflows` | ComfyUI graph templates. |
| `OGAI_DRIVE_DIR` | unset | Enables the optional Google Drive output mirror. |
| `OGAI_CORS_ORIGINS` | `*` | Comma-separated allowed browser origins. Restrict this for a long-lived install. |
| `OGAI_MAX_UPLOAD_BYTES` | `26214400` (25 MB) | Upload size cap. |
| `OGAI_MAX_CONCURRENT_JOBS` | `1` | Maximum simultaneous GPU jobs. |
| `OGAI_GPU_NAME` / `OGAI_GPU_VRAM_GB` | unset | Fallback GPU details when ComfyUI is offline. |

The adapter rate-limits each token to **30 authenticated requests per 60 seconds**. The budget is
shared by every authenticated endpoint, not just generation.

See [Security notes](docs/SECURITY.md) for the threat model and [API](docs/API.md) for endpoints.

## Run locally

### Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

The dev server has no proxy: open the Connection panel and point it at a running adapter (local or
a Colab tunnel). To produce a Pages-style build:

```bash
# macOS, Linux, PowerShell
npm run build -- --base=/AIVG-MAX-D/          # output in frontend/dist

# Git Bash for Windows (MSYS rewrites leading-slash arguments)
MSYS_NO_PATHCONV=1 npm run build -- --base=/AIVG-MAX-D/
```

The Pages workflow instead sets the `BASE_PATH` environment variable, which
`frontend/vite.config.js` reads.

### Adapter

The adapter can run without a GPU for API development. Without a reachable ComfyUI it still serves
health, models, workflows, settings and the job list; generation jobs fail with a clear connection
error.

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt

# bash
export OGAI_SESSION_TOKEN=devtoken
export OGAI_COMFY_URL=http://127.0.0.1:8188
python -m uvicorn backend.adapter.main:app --host 127.0.0.1 --port 8189
```

```powershell
# PowerShell
$env:OGAI_SESSION_TOKEN = "devtoken"
$env:OGAI_COMFY_URL = "http://127.0.0.1:8188"
python -m uvicorn backend.adapter.main:app --host 127.0.0.1 --port 8189
```

If you leave `OGAI_SESSION_TOKEN` unset, read the generated token with:

```bash
python -c "import json; print(json.load(open('backend/state/runtime.json'))['session_token'])"
```

### Tests

The backend suite uses a mock ComfyUI server, so no GPU or model downloads are required.

```bash
pip install -r backend/requirements.txt pytest-asyncio
python -m pytest backend/tests -q
```

`pytest-asyncio` is imported by the tests but is not yet listed in `backend/requirements.txt`.
There is no frontend test suite; run `npm run build` in `frontend/` to verify the UI compiles.

## Repository layout

```
frontend/              React + Vite studio (the GitHub Pages app)
backend/adapter/       FastAPI adapter: auth, queue, uploads, gallery, settings
backend/workflows/     ComfyUI API-format graph templates and metadata
backend/tests/         Mock-ComfyUI pytest suite
notebooks/             Colab GPU backend (cells A-E)
docs/                  Installation, Colab, API, security, workflows, troubleshooting
.github/workflows/     pages.yml - build frontend/ and deploy to GitHub Pages
```

The root-level `app/`, `components/`, `src/`, `electron/`, `packages/`, `Dockerfile`,
`next.config.mjs` and root `package.json` belong to the **upstream Open-Generative-AI web/desktop
app** and are kept separate from this studio. They are **not** used by the self-hosted
frontend/backend described here (and `Dockerfile` builds that older app, not the studio).

## Deploy your own copy

The workflow `.github/workflows/pages.yml` builds `frontend/` and publishes it to GitHub Pages on
every push to `main`.

1. Fork or push this repository to GitHub.
2. Go to **Settings → Pages → Source: GitHub Actions**.
3. Push to `main`. The site appears at `https://<user>.github.io/<repo-name>/`.

The workflow builds with `BASE_PATH=/<repo-name>/`; if you build by hand, pass
`--base=/<repo-name>/` (see [Run locally](#run-locally)).

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Connection dot stays red | Cell E is not running, or the tunnel URL/token is stale. Re-run E and paste the new pair. |
| `401` in the UI | Token mismatch. Every runtime restart creates a new token. |
| `429` | The 30-request/60-second token budget was exceeded. Wait a minute and retry. |
| `502` / "ComfyUI unreachable" | ComfyUI crashed or is still starting. Check `/content/comfyui.log` and restart cell E. |
| "Missing custom node classes" | Install the node pack listed in the error (see [Workflows](docs/WORKFLOWS.md)). |
| `CUDA out of memory` | Lower the resolution/frames, use SDXL instead of video, or unload models in Settings. |
| Model shows "not installed" | Check the filename/folder against [Workflows](docs/WORKFLOWS.md); SD 1.5 and FLUX presets currently mismatch. |
| Blank page on Pages | Build with the correct `BASE_PATH` (the included workflow does this). |

Full list: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Known limitations

- **Ephemeral backend.** Colab runtimes and `trycloudflare.com` tunnels are temporary; URL and
  token change every session. This is a personal tool, not a multi-user service.
- **One GPU job at a time.** VRAM contention is avoided by serialising jobs. Submitting while a job
  is already active is rejected rather than queued indefinitely.
- **All video workflows are experimental.** They need custom nodes, and the larger models need far
  more VRAM than a free T4 provides.
- **SD 1.5 and FLUX preset filenames are not aligned** with the registry/workflows in this
  revision. SDXL is the reliable image path.
- **The frontend has no automated tests.** The backend suite is the primary regression check.
- **The upstream Next.js/Electron app is not wired to this backend.** Its features are separate
  from the studio.

## Documentation

| Doc | What's in it |
|---|---|
| [Docs index](docs/README.md) | Map of all documentation and where to start |
| [Installation](docs/INSTALLATION.md) | Frontend, local adapter, Colab backend and connecting them |
| [Colab setup](docs/COLAB_SETUP.md) | What each notebook cell does |
| [Workflows and models](docs/WORKFLOWS.md) | Templates, VRAM needs, node packs and model licences |
| [API](docs/API.md) | Every backend endpoint, payload and error code |
| [Security](docs/SECURITY.md) | Session token, CORS, uploads and exposure |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Common errors and fixes |

## Model licences

Models carry their own licences, separate from this code:

- **FLUX.1 schnell** — non-commercial licence; do not use outputs commercially.
- **SD 1.5** — CreativeML Open RAIL-M; use restrictions apply.
- **SDXL** — CreativeML Open RAIL++-M; commercial use allowed with use restrictions.
- **Wan 2.1** — Apache-2.0.
- **LTX-Video** — Lightricks open-weights licence; check before commercial use.
- **AnimateDiff** — Apache-2.0 module; the SD 1.5 checkpoint licence also applies to outputs.

Check [docs/WORKFLOWS.md](docs/WORKFLOWS.md) before using outputs commercially.

## Tech stack

React 19, Vite, Tailwind CSS · FastAPI, Python · ComfyUI · Google Colab · GitHub Pages ·
cloudflared.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: keep pull requests to one concern, run
`python -m pytest backend/tests -q`, build the frontend, and never commit tokens, model weights or
generated outputs.

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgements

Started from the open-source [Open-Generative-AI](https://github.com/Anil-matcha/Open-Generative-AI)
project (MIT) and rebuilt around self-hosted ComfyUI models. Model generation is powered by
[ComfyUI](https://github.com/comfyanonymous/ComfyUI).

# AIVG-MAX-D

**A self-hosted AI image and video studio that runs on open-source models and a free Google Colab GPU.**

AIVG-MAX-D gives you a browser studio for text-to-image, image-to-image, text-to-video and
image-to-video generation. Instead of a paid cloud API, every generation runs on open-weight models
(SD 1.5, SDXL, FLUX schnell, Wan 2.1) inside ComfyUI on a GPU you control.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/manojkumar12-maker/AIVG-MAX-D/blob/main/notebooks/OpenGenerativeAI_Colab.ipynb)

- **Studio (live):** https://manojkumar12-maker.github.io/AIVG-MAX-D/
- **GPU backend:** [`notebooks/OpenGenerativeAI_Colab.ipynb`](notebooks/OpenGenerativeAI_Colab.ipynb)

---

## How it works

```
Browser studio (React + Vite, hosted on GitHub Pages)
   │  session token over HTTPS
   ▼
FastAPI adapter (backend/adapter) — auth, job queue, uploads, gallery
   │  ComfyUI JSON API on localhost
   ▼
ComfyUI on a Colab GPU — SD 1.5 / SDXL / FLUX schnell / Wan 2.1
```

- **Frontend** (`frontend/`): static React app, deployed to GitHub Pages; no server of its own.
- **Backend** (`backend/adapter/`): turns studio requests into ComfyUI workflows, runs one GPU job
  at a time, and stores results.
- **Workflows** (`backend/workflows/`): ComfyUI graph templates, one per model and mode.
- **Notebook** (`notebooks/`): installs everything on Colab, downloads models, and prints the URL and
  token the studio connects with.

## Features

- **Image Studio** — text-to-image with SD 1.5, SDXL or FLUX schnell.
- **Image to Image** — upload a reference picture and restyle it (SDXL).
- **Video Studio** — text-to-video and image-to-video with Wan 2.1.
- **Queue and progress** — live job status streamed from the backend.
- **Gallery and history** — every result saved and browsable.
- **Models page** — each model's VRAM need and licence shown in the app.
- **VRAM checks** — jobs that won't fit your GPU fail fast with a clear message instead of crashing.

## Quick start

### 1. Start the GPU backend on Colab

1. Click **Open in Colab** above.
2. **Runtime → Change runtime type → T4 GPU** (free tier works).
3. Run cells **A → E** in order:
   - **A** — checks the GPU, optionally mounts Google Drive to cache models.
   - **B** — installs ComfyUI and this repository.
   - **C** — pick a model preset (see the table below).
   - **D** — downloads the models (resumable).
   - **E** — starts the services and prints a **Frontend URL** and a **Session token**.

### 2. Connect the studio

Open https://manojkumar12-maker.github.io/AIVG-MAX-D/, paste the URL and token from cell E into the
**Connection** panel, and wait for the status dot to turn green. Then start generating.

### Model presets

| Preset | GPU needed | Includes |
|---|---|---|
| SD 1.5 | any GPU (T4 is fine) | SD 1.5 checkpoint, ~2 GB |
| SDXL | ~12 GB VRAM | SDXL base, ~6.9 GB |
| SDXL + FLUX schnell Q4 | ~16 GB | SDXL + FLUX Q4 + T5 + VAE |
| Everything incl. Wan 2.1 video | ~24 GB | SDXL + Wan 2.1 text-to-video stack |

On a free T4 (about 15 GB), use **SD 1.5** or **SDXL**.

## Run locally

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Backend tests (from the repository root):

```bash
pip install -r backend/requirements.txt
python -m pytest backend/tests -q
```

## Deploy your own copy

The workflow `.github/workflows/pages.yml` builds `frontend/` and publishes it to GitHub Pages on
every push to `main`. In your fork, set **Settings → Pages → Source: GitHub Actions**.

## Documentation

| Doc | What's in it |
|---|---|
| [Installation](docs/INSTALLATION.md) | Frontend, Colab backend and connecting them |
| [Colab setup](docs/COLAB_SETUP.md) | What each notebook cell does |
| [Workflows and models](docs/WORKFLOWS.md) | Templates, VRAM needs and model licences |
| [API](docs/API.md) | Backend endpoints |
| [Security](docs/SECURITY.md) | Session token and exposure |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Common errors and fixes |

## Model licences

Models carry their own licences, separate from this code. FLUX.1 schnell is **non-commercial**, and
SD 1.5 and SDXL come with use restrictions; check [docs/WORKFLOWS.md](docs/WORKFLOWS.md) before using
outputs commercially.

## Tech stack

React, Vite, Tailwind CSS · FastAPI, Python · ComfyUI · Google Colab · GitHub Pages

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgements

Started from the open-source [Open-Generative-AI](https://github.com/Anil-matcha/Open-Generative-AI)
project (MIT) and rebuilt around self-hosted ComfyUI models. Model generation is powered by
[ComfyUI](https://github.com/comfyanonymous/ComfyUI).

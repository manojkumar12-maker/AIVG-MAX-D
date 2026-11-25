# PLAN — Open Generative AI: Self-Hosted AI Creative Studio

## Goal and users
Self-hosted AI creative studio based on Anil-matcha's Open-Generative-AI. Creators generate
images and videos from a browser dashboard (GitHub Pages static frontend) using their own free
Google Colab GPU running ComfyUI with open-weight models — no paid generation API. The original
project's dark, glowing, panel-based design language is preserved.

Working means: start the Colab notebook, copy the tunnel URL + session token into the frontend
connection panel, generate images (text-to-image, image-to-image) and videos (text-to-video,
image-to-video) through ComfyUI, see real progress, and download results.

## Repo layout (what goes where)
- Original Next.js app at repo root is **kept unmodified** (cloud/Muapi version, still builds).
- `frontend/` — new React 19 + Vite static SPA for GitHub Pages (self-hosted backend).
- `backend/` — FastAPI adapter + ComfyUI client + workflow/model registries.
- `backend/workflows/` — ComfyUI API-format workflow templates with metadata.
- `notebooks/OpenGenerativeAI_Colab.ipynb` — one-click Colab runtime.
- `docs/` — INSTALLATION, COLAB_SETUP, API, SECURITY, WORKFLOWS, TROUBLESHOOTING.
- `.github/workflows/pages.yml` — GitHub Pages deployment.

## Architecture
- **Frontend**: React 19 + Vite, static build with configurable base path (`/open-generative-ai/`),
  no secrets; backend URL + session token entered by user in Connection panel (token optionally
  kept in sessionStorage only).
- **Adapter (FastAPI)**: abstracts ComfyUI node graph API behind stable REST endpoints; owns the
  job queue, auth, uploads, outputs, settings; talks to ComfyUI over 127.0.0.1 HTTP + WebSocket
  progress; single active GPU job by default.
- **ComfyUI**: stock install + workflow templates; models downloaded on demand by notebook helper.
- **Colab notebook**: sections A–E (env check / install / model selection / download manager /
  start services), cloudflared tunnel, random session token, optional Drive mount.
- **Data model** (adapter, persisted to JSON on disk / Drive): `jobs` (id, type, status, params,
  workflow, outputs, timestamps), `settings`, `outputs` metadata. Frontend keeps history locally
  (localStorage) and mirrors job state from the API.

## API contract (full detail in docs/API.md)
`GET /health`, `GET /api/status`, `GET /api/capabilities`, `GET /api/models`, `GET /api/workflows`,
`POST /api/generate/image|image-to-image|video|image-to-video`, `GET /api/jobs`, `GET /api/jobs/{id}`,
`POST /api/jobs/{id}/cancel`, `DELETE /api/jobs/{id}`, `GET /api/output/{filename}`,
`POST /api/upload`, `GET|POST /api/settings`. All auth via `X-Session-Token` (or `?token=` for
media tags). `/health` is the only unauthenticated endpoint.

## Scope
In scope (phases below): image t2i/i2i, video t2v/i2v, queue, gallery, connection panel, presets,
GPU compatibility layer, Drive storage, docs, GitHub Pages CI.
Out of scope for now: lip sync, audio, agents, LoRA training UI, MCP, Electron packaging,
local-AI binary staging — these remain in the original Next app and are labeled unavailable in
the new frontend.

## Risks and assumptions
- No GPU in this workspace: adapter is tested against a mock ComfyUI; real generation must be
  verified by the user in Colab. Not claimed as verified here.
- Colab tunnels (cloudflared) are temporary and rate-limited; documented as non-production.
- Video models are large; workflows ship but are gated by VRAM checks with honest errors.

## Phase 1: Thin vertical slice (self-hosted core)
Goal: connect frontend → adapter → ComfyUI and generate one image end to end.
- [x] FastAPI adapter with token auth, health, capabilities, models, workflows, generate/image,
      jobs queue, upload, output serving, settings + pytest suite (mock ComfyUI)
- [x] Workflow registry + ComfyUI API templates: SD1.5 t2i, SDXL t2i, SDXL i2i (+ metadata,
      validation with missing-dependency errors)
- [x] Model registry with VRAM classes, disk sizes, licenses
- [x] React frontend: layout, connection panel, Image Studio, Gallery, queue sidebar
- [x] Colab notebook sections A–E with tunnel + token
- [x] GitHub Pages workflow + Vite base path config
- [x] Docs: README, INSTALLATION, COLAB_SETUP, API, SECURITY, WORKFLOWS, TROUBLESHOOTING
- [x] Verified: pytest suite green, frontend production build green, adapter boots and serves
      health/auth/queue endpoints end to end
      (2026-11-25: pytest 15/15; `npm run build` green in root and frontend; BASE_PATH build
      emits `/open-generative-ai/` asset URLs; adapter exercised live on :8189 — 401 without
      token, health/capabilities/models/workflows OK, generate reports missing_model honestly;
      browser checks of the built SPA pass at 1280px and 390px incl. drawer navigation and
      Gallery. No real generation: no GPU here — user verifies in Colab.)

Acceptance: user starts notebook, pastes URL+token, generates an image, sees it in the gallery.

## Phase 2: Video and image-to-video
Goal: real video generation through ComfyUI.
- [x] Video Studio UI (prompt, duration, fps, motion, presets, Shorts 9:16 presets)
- [x] Image-to-Video UI (start image, camera movement presets, end frame where supported)
- [x] Wan / LTX / AnimateDiff workflow templates with VRAM gating and install hints
      (2026-11-25: added video_ltx_t2v + video_animdiff_t2v templates and their model-registry
      entries; `min_vram_gb` is now enforced in the adapter — honest `insufficient_vram` 400 with
      install hint, tested against the mock GPU)
- [x] Video outputs in gallery with preview, duration, size, download
Acceptance: generate a short video from the dashboard on a >=24GB GPU.
(Verified as far as this no-GPU machine allows: pytest 18/18 incl. VRAM-gate and template
registration tests; browser checks of Video Studio and Image-to-Video pass at 1280px with no
errors. Real generation still needs the Colab GPU from Phase 1's notebook.)

## Phase 3: Google Drive storage and persistence
- [x] Drive mount in notebook (explicit consent), OpenGenerativeAI/ folder structure
      (cell A already had MOUNT_DRIVE; cell E now passes OGAI_DRIVE_DIR=/content/drive/MyDrive/OpenGenerativeAI)
- [x] Optional save-to-Drive of outputs + metadata JSON + workflow JSON
      (adapter `_mirror_to_drive`: outputs/<job>_<file> + <jobid>.json sidecar with params and
      output list; gated by the existing save_to_drive setting, failures recorded as error_hint
      without failing the job; /health and /api/settings expose drive_available)
- [x] Model storage on Drive to survive runtime resets
      (section D already cached model downloads to Drive when mounted)
Acceptance: outputs survive a runtime reset when Drive storage is enabled.
(2026-11-25: pytest 20/20 incl. mirror-on and mirror-off tests; notebook JSON valid; frontend
build green; Settings page renders clean at 1280px. Actual Drive round-trip needs the Colab
runtime — verify there by generating with save_to_drive on, resetting the runtime, and
reopening the Drive folder.)

## Phase 4: Robustness and reach
- [x] WebSocket live progress in frontend (polling fallback already in Phase 1)
      (2026-11-25: /ws/jobs endpoint broadcasts job_update on every job change; frontend
      subscribes when connected, merges updates into the polled list, reconnects with backoff;
      polling stays as safety net. pytest 23/23 incl. hub broadcast test.)
- [x] FLUX quantized workflows, LoRA slots, low-VRAM/auto-offload presets
      (FLUX schnell Q4 shipped in Phase 1; low_vram setting now rewrites rendered graphs —
      batch_size 1, latent width/height halved with a 320px floor — and the notebook passes
      --lowvram/--novram to ComfyUI based on detected VRAM)
- [x] Retry/unload controls, model cache warm-up, idle polling backoff
      (retry existed end-to-end; unload_after_job now calls ComfyUI /free after each job;
      idle polling backoff existed in useJobPolling)
- [x] Mobile polish pass (settings drawer, camera upload)
      (capture="environment" on the image uploader; 390px browser check clean: 0 clipped,
      0 overlaps, 0 low contrast, no overflow)
Acceptance: a T4 can complete a low-VRAM image job with auto fallbacks.
(2026-11-25: pytest 22/22 incl. low_vram graph rewrite and unload-after-job tests; frontend
build green; 1280px and 390px browser checks pass with 0 page/console errors. The T4 acceptance
run itself needs the Colab GPU.)

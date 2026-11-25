# AIVG-MAX-D documentation

AIVG-MAX-D is a self-hosted AI image and video studio. The browser UI is a static React app; the
GPU work runs in ComfyUI on a Google Colab runtime you control; a FastAPI adapter connects them.

```
Browser (GitHub Pages, static React)
   │  session token + HTTPS
   ▼
FastAPI adapter (backend/adapter) — auth, queue, uploads, gallery, settings
   │  ComfyUI JSON API, localhost
   ▼
ComfyUI on Colab GPU — SDXL / SD 1.5 / FLUX schnell / Wan 2.1 / LTX / AnimateDiff
```

## Start here

1. [Installation](INSTALLATION.md) — publish the frontend, run the adapter locally if you want,
   and start the Colab backend.
2. [Colab setup](COLAB_SETUP.md) — exactly what cells A-E do, including custom-node installation.
3. [Workflows and models](WORKFLOWS.md) — templates, VRAM floors, model licences and current
   filename caveats.

## Reference

| Document | Audience | Contents |
|---|---|---|
| [Installation](INSTALLATION.md) | New users | Frontend, local adapter, Colab, connection, tests |
| [Colab setup](COLAB_SETUP.md) | New users | Cell-by-cell walkthrough, logs, Drive cache |
| [Workflows and models](WORKFLOWS.md) | Users, contributors | Workflow selection, all 8 templates, 7 models, node packs, licences |
| [API](API.md) | Integrators, frontend work | Every endpoint, payload, job lifecycle, WebSocket, errors |
| [Security](SECURITY.md) | Operators | Token handling, CORS, uploads, exposure limits |
| [Troubleshooting](TROUBLESHOOTING.md) | Everyone | Connection, auth, rate limits, VRAM, missing nodes, known mismatches |

The project overview, quick start and configuration table live in the
[root README](../README.md).

## Source map

| Path | What it is |
|---|---|
| `frontend/` | React 19 + Vite + Tailwind studio, deployed to GitHub Pages |
| `backend/adapter/main.py` | FastAPI routes, auth, uploads, settings, WebSocket |
| `backend/adapter/jobs.py` | Persistent, single-active-job queue |
| `backend/adapter/workflows.py` | Template loading, validation, graph rendering |
| `backend/adapter/models_registry.py` | Model ids, VRAM, disk, licences |
| `backend/workflows/` | ComfyUI API-format templates |
| `backend/tests/` | Mock-ComfyUI pytest suite |
| `notebooks/` | Colab GPU backend |
| `.github/workflows/pages.yml` | Frontend build and Pages deployment |

The root-level Next.js/Electron app (`app/`, `components/`, `src/`, `electron/`, `packages/`,
`Dockerfile`, root `package.json`) is the upstream Open-Generative-AI app, kept separate from this
studio.

## Keeping docs accurate

When you change behaviour, update the matching document:

- **Ports** — frontend dev server is **3000**; adapter is **8189**; ComfyUI is **8188**.
- **Environment variables** — all adapter settings are `OGAI_*`; the table is in the
  [root README](../README.md#configuration).
- **Workflow or model names** — update [WORKFLOWS.md](WORKFLOWS.md) and
  `backend/adapter/models_registry.py` together.
- **Endpoints** — update [API.md](API.md) and the tests in `backend/tests/test_adapter.py`.
- **Token/CORS behaviour** — update [SECURITY.md](SECURITY.md).

If a command in these docs does not work on a clean checkout, treat that as a documentation bug.

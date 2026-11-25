# Installation

You need two halves: the static frontend (yours, on GitHub Pages) and the GPU backend (one Colab
runtime at a time). The adapter and tests can also run locally without a GPU.

## Prerequisites

| Piece | Requirement |
|---|---|
| Frontend | Node.js 20.19+ or 22+ |
| Adapter | Python 3.10+ |
| GPU backend | A Google account with Colab (free T4 is fine for SDXL images) |
| Models | Downloaded by the notebook; no API key is required |

For video and FLUX you also need ComfyUI custom nodes; see
[Workflows and models](WORKFLOWS.md).

## 1. Publish the frontend

1. Fork or push this repository to GitHub.
2. In the repository: **Settings → Pages → Source: GitHub Actions**.
3. The included workflow `.github/workflows/pages.yml` builds `frontend/` with
   `BASE_PATH=/<repo-name>/` and deploys `frontend/dist` to Pages on every push to `main`.
4. Your studio will be at `https://<user>.github.io/<repo-name>/`.

Local frontend development instead:

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

The dev server has no API proxy. Enter the backend URL and token in the studio's **Connection**
panel. The URL is remembered in `localStorage`; the token is kept in `sessionStorage` only.

Build a Pages-style bundle by hand with:

```bash
# macOS, Linux, PowerShell
npm run build -- --base=/<repo-name>/          # writes frontend/dist

# Git Bash for Windows
MSYS_NO_PATHCONV=1 npm run build -- --base=/<repo-name>/
```

The CI workflow uses the `BASE_PATH` environment variable instead; both feed the same Vite `base`
option.

## 2. Run the GPU backend on Colab

Open `notebooks/OpenGenerativeAI_Colab.ipynb` in Google Colab, choose **Runtime → Change runtime
type → T4 GPU**, and run sections A → E. Full walkthrough: [COLAB_SETUP.md](COLAB_SETUP.md).

## 3. Connect

Section E prints a **Frontend URL** (a `trycloudflare.com` tunnel) and a **Session token**. Paste
both into the studio's Connection panel; the status dot turns green when `/health` answers.

The token is regenerated every time you run section E. After a runtime reset, re-run A → E and use
the new URL and token.

## 4. Optional: run the adapter locally (no GPU needed for API dev)

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt

export OGAI_SESSION_TOKEN=devtoken
export OGAI_COMFY_URL=http://127.0.0.1:8188
export OGAI_STATE_DIR=backend/state
python -m uvicorn backend.adapter.main:app --host 127.0.0.1 --port 8189
```

PowerShell equivalent:

```powershell
$env:OGAI_SESSION_TOKEN = "devtoken"
$env:OGAI_COMFY_URL = "http://127.0.0.1:8188"
python -m uvicorn backend.adapter.main:app --host 127.0.0.1 --port 8189
```

Without a reachable ComfyUI the adapter still serves health, models, workflows, settings and the
queue; generation jobs fail with a clear connection error.

If you omit `OGAI_SESSION_TOKEN`, the adapter generates a random token on first boot and writes it
to `backend/state/runtime.json`:

```bash
python -c "import json; print(json.load(open('backend/state/runtime.json'))['session_token'])"
```

### Environment variables

The adapter is configured entirely through `OGAI_*` variables. The full table lives in the
[README](../README.md#configuration). The values used by the notebook are:

| Variable | Value in Colab |
|---|---|
| `OGAI_SESSION_TOKEN` | random 24-byte URL-safe token |
| `OGAI_COMFY_URL` | `http://127.0.0.1:8188` |
| `OGAI_OUTPUT_DIR` | Drive `outputs/` or `/content/outputs` |
| `OGAI_DRIVE_DIR` | `/content/drive/MyDrive/OpenGenerativeAI` when Drive is mounted |
| `OGAI_STATE_DIR` | `/content/state` |

### CORS

The adapter accepts any origin by default (`OGAI_CORS_ORIGINS=*`). For a long-lived install set it
to your Pages origin:

```bash
export OGAI_CORS_ORIGINS=https://<user>.github.io
```

Use the scheme and host only; a Pages project path such as `/AIVG-MAX-D/` is not part of the
origin. Multiple origins can be comma-separated.

## 5. Tests

```bash
pip install -r backend/requirements.txt pytest-asyncio
python -m pytest backend/tests -q
```

The suite uses a mock ComfyUI server, so no GPU or models are needed. `pytest-asyncio` is imported
by the tests but is not yet listed in `backend/requirements.txt`.

## Save results to Google Drive

In the Colab notebook keep `MOUNT_DRIVE = True` (section A): models and outputs are then cached
under `MyDrive/OpenGenerativeAI/` and survive runtime resets. Output mirroring is controlled by the
**Save to Drive** setting in the studio; the model cache is automatic when Drive is mounted.

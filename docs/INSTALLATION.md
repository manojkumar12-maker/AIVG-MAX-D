# Installation

You need two halves: the static frontend (yours, on GitHub Pages) and the GPU backend (one Colab
runtime at a time).

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
npm run dev        # http://localhost:5199
```

## 2. Run the GPU backend on Colab

Open `notebooks/OpenGenerativeAI_Colab.ipynb` in Google Colab, choose **Runtime → Change runtime
type → T4 GPU**, and run sections A → E. Full walkthrough: `docs/COLAB_SETUP.md`.

## 3. Connect

Section E prints a **Frontend URL** (trycloudflare tunnel) and a **Session token**. Paste both into
the studio's Connection panel; the status dot turns green when `/api/health` answers.

## 4. Optional: run the adapter locally (no GPU needed for API dev)

```bash
pip install -r backend/requirements.txt
SESSION_TOKEN=devtoken COMFYUI_URL=http://127.0.0.1:8188 \
  python -m uvicorn backend.adapter.main:app --port 8189
```

Without a reachable ComfyUI the adapter still serves health, models, workflows and the queue;
generation jobs fail with a clear connection error.

## Save results to Google Drive

In the Colab notebook keep `MOUNT_DRIVE = True` (section A): models and outputs are then cached
under `MyDrive/OpenGenerativeAI/` and survive runtime resets.

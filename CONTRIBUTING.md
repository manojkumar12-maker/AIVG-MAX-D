# Contributing to AIVG-MAX-D

Thanks for contributing. This project is MIT licensed; by opening a pull request you agree your
contribution can be distributed under the same licence.

Keep each pull request to **one concern** (one bug, one docs fix, one workflow). Do not bundle
unrelated changes.

## What this repository actually is

Two applications live in this repository:

- **The self-hosted studio** — `frontend/` (React + Vite), `backend/` (FastAPI adapter, workflows,
  tests), `notebooks/` (Colab GPU backend) and `docs/`. This is what the README describes.
- **The upstream Open-Generative-AI app** — the root `app/`, `components/`, `src/`, `electron/`,
  `packages/`, `Dockerfile`, `next.config.mjs` and root `package.json`. It is kept for reference
  and as the original web/desktop app; it is **not wired to the self-hosted adapter**.

Do not change the upstream app to fix a studio issue. Unless your change is explicitly about that
app, work in `frontend/`, `backend/`, `notebooks/` or `docs/`.

## Setup

Prerequisites: Node.js 20.19+ or 22+, and Python 3.10+.

```bash
git clone https://github.com/manojkumar12-maker/AIVG-MAX-D.git
cd AIVG-MAX-D
```

### Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000
```

### Backend

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt pytest-asyncio
```

Run the adapter without a GPU:

```bash
export OGAI_SESSION_TOKEN=devtoken   # PowerShell: $env:OGAI_SESSION_TOKEN = "devtoken"
python -m uvicorn backend.adapter.main:app --host 127.0.0.1 --port 8189
```

## Tests and checks

```bash
# Backend: mock ComfyUI, no GPU required
python -m pytest backend/tests -q

# Frontend: production build
cd frontend && npm run build
```

- The only GitHub Action is the Pages deployment; there is **no automated test CI**. Run the
  checks yourself and say in the pull request which commands you ran and what they reported.
- `pytest-asyncio` is imported by the test suite but is not yet in `backend/requirements.txt`.
- There is no frontend test suite and no lint script in `frontend/package.json`. At minimum, make
  sure `npm run build` passes and check the affected screens in a browser.
- For notebook changes, verify the JSON is valid (open it in Colab or run
  `python -m json.tool notebooks/OpenGenerativeAI_Colab.ipynb > /dev/null`). Real generation
  requires a GPU and cannot be verified in CI.

## Changing workflows or models

Workflow templates and the model registry must agree. If you change one, update the other:

- `backend/workflows/*.json` — graph plus `_meta` (`id`, `type`, `mode`, `requires_model`,
  `min_vram_gb`, `features`, `needs_upload`, `param_map`, optional limits and `experimental`).
- `backend/adapter/models_registry.py` — id, file path, URL, VRAM, disk, licence and extra nodes.
- `notebooks/OpenGenerativeAI_Colab.ipynb` — the preset that downloads the file.
- `docs/WORKFLOWS.md` — the tables and any filename caveats.

The current SD 1.5 and FLUX presets do not match the registry/template filenames. Aligning them is
a welcome focused pull request; if you change the names, update all four places and the tests that
assert template/model ids.

## Changing the API

- Add or update the route in `backend/adapter/main.py`.
- Add a test in `backend/tests/test_adapter.py`.
- Update `docs/API.md`.
- If the frontend calls it, update `frontend/src/services/backendClient.js` and the relevant hook
  or page.

## Changing configuration

Adapter configuration is environment-driven and prefixed `OGAI_`. Add new variables in
`backend/adapter/config.py`, document them in the root README's configuration table, and pass them
from the notebook if Colab needs them.

## Documentation changes

Docs live in `README.md`, `CONTRIBUTING.md` and `docs/`. The useful invariants are:

- Frontend dev port **3000**, adapter port **8189**, ComfyUI port **8188**.
- All adapter environment variables use the `OGAI_` prefix.
- The token is sent as `X-Session-Token` (or `?token=` for media).
- CORS defaults to `*`, not to a GitHub Pages origin.
- Rate limit is 30 authenticated requests per 60 seconds per token.

If you find a command in the docs that does not work on a clean checkout, a docs PR that fixes it
is valuable. Include the command you ran and its output in the PR description.

## What to avoid

- Do not commit tokens, tunnel URLs, `.env` files, model weights, generated outputs, Drive dumps or
  `backend/state/` contents.
- Do not loosen authentication, CORS, upload validation or output path checks to make something
  work locally.
- Do not add a paid API dependency; the point of this project is self-hosted open-weight models.
- Do not edit both the upstream app and the self-hosted studio in one pull request.
- Do not add large binary files (images, videos, models) to git.
- Do not "fix" unrelated lint/formatting noise in a focused PR.

## Pull request checklist

- [ ] One concern, with a clear title and description
- [ ] `python -m pytest backend/tests -q` passes (or the PR explains why it does not)
- [ ] `npm run build` passes in `frontend/` for UI changes
- [ ] Docs updated when behaviour, setup, a command or a filename changed
- [ ] No secrets, tokens, model weights or generated media added
- [ ] The PR description says which commands you ran and their results

## Reporting issues

Include the relevant log (`/content/adapter.log`, `/content/comfyui.log`), the job error text, the
model and workflow id, the GPU/VRAM, and whether you installed custom nodes. Do not paste live
tunnel URLs or session tokens.

For security issues, use a private GitHub security advisory instead of a public issue; see
[docs/SECURITY.md](docs/SECURITY.md).

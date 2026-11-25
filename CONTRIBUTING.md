# Contributing to AIVG-MAX-D

Thanks for helping improve AIVG-MAX-D — a self-hosted AI image and video studio running open
models on ComfyUI.

## Code of conduct

Be respectful. Keep discussions on-topic and assume good faith.

## Getting started

```bash
git clone https://github.com/manojkumar12-maker/AIVG-MAX-D.git
cd AIVG-MAX-D

# Frontend (Vite + React)
cd frontend && npm install && npm run dev

# Backend tests (from the repository root)
pip install -r backend/requirements.txt
python -m pytest backend/tests -q
```

## How the code is organised

- `frontend/` — static React + Vite studio, published to GitHub Pages.
- `backend/adapter/` — FastAPI service: auth, job queue, uploads, gallery.
- `backend/workflows/` — ComfyUI graph templates, one per model and mode.
- `notebooks/` — the Colab notebook that installs and runs everything.

## Pull requests

1. Create a feature branch from `main`.
2. Keep changes focused; one topic per PR.
3. Run the backend tests and make sure they pass.
4. Describe what changed and why in the PR description.

## Guidelines

- Never commit API keys, tokens, or any secret. The session token is generated automatically at
  runtime and stored outside git.
- Adding a model: add an entry in `backend/adapter/models_registry.py` (with its licence), a
  workflow JSON in `backend/workflows/`, and a download preset in notebook cell C if it should be
  downloadable from Colab. Run the tests — they verify every workflow resolves its model.
- Documentation lives in `docs/`; update the relevant page when behaviour changes.

## Licence

By contributing, you agree that your contributions are licensed under the MIT Licence that covers
this repository.

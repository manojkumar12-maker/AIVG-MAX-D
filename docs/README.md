# AIVG-MAX-D — Self-Hosted AI Creative Studio

AIVG-MAX-D runs **open-source models (SD 1.5, Pony Diffusion V6 XL, SDXL, FLUX schnell, Wan 2.1)
on ComfyUI**, which you can drive from a free Google Colab GPU. No paid generation API.

```
Browser (GitHub Pages, static React)
   │  session token + HTTPS
   ▼
FastAPI adapter  (backend/adapter) — auth, queue, uploads, gallery
   │  ComfyUI JSON API, localhost
   ▼
ComfyUI on Colab GPU — SD 1.5 / Pony V6 XL / SDXL / FLUX schnell / Wan 2.1
```

- **Frontend**: static React + Vite (`frontend/`), deployed to GitHub Pages, no server needed.
- **Backend**: FastAPI adapter translates the studio's requests into ComfyUI workflows, keeps a
  one-job-at-a-time GPU queue, and stores results.
- **Models**: open weights; licences are listed in `docs/WORKFLOWS.md`. No paid generation API is
  required by default.
- **Videos**: Wan 2.1 (Apache-2.0) workflows ship, gated by VRAM checks.

Start here: `docs/INSTALLATION.md`, then `docs/COLAB_SETUP.md`.
Operate and debug: `docs/API.md`, `docs/SECURITY.md`, `docs/WORKFLOWS.md`, `docs/TROUBLESHOOTING.md`.

Run the tests locally: `python -m pytest backend/tests -q` (from the repository root).

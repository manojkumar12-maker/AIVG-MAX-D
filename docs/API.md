# Adapter API

All `/api/*` routes require the session token via an `X-Session-Token` header (or `?token=` query
parameter). `/health` is public. Base URL is your tunnel URL
(`https://<name>.trycloudflare.com`).

## Health and status

- `GET /health` — liveness. `{"status": "ok"}`.
- `GET /api/status` — adapter + ComfyUI connectivity, GPU queue state.
- `GET /api/capabilities` — which features this backend supports (text-to-image,
  image-to-image, video, …).

## Models and workflows

- `GET /api/models` — registry entries with name, type, licence, VRAM class, disk size.
- `GET /api/workflows` — available workflow templates with metadata. Experimental workflows are
  never auto-selected.

## Uploads

- `POST /api/upload` — multipart image upload (reference image for i2i / i2v). 25 MB cap, content
  sniffed by MIME. Returns the server-side filename used by generation requests.

## Generation

- `POST /api/generate/image` — text-to-image.
- `POST /api/generate/image-to-image` — text-to-image with an uploaded reference.
- `POST /api/generate/video` — text-to-video.
- `POST /api/generate/image-to-video` — animate an uploaded reference.

All accept JSON body `{model, prompt, negative_prompt?, width?, height?, steps?, seed?, image?}`.
`model` is a registry id (e.g. `sd15`, `sdxl`); invalid models get a friendly error listing what is
available. Returns `{"job_id": ...}`.

## Queue

The GPU queue runs **one job at a time**; everything else waits.

- `GET /api/jobs` — all jobs with status.
- `GET /api/jobs/{job_id}` — one job (status, progress, result filename).
- `POST /api/jobs/{job_id}/cancel` — cancel a queued/running job.
- `DELETE /api/jobs/{job_id}` — remove a finished job from the list.

## Results

- `GET /api/output/{filename}` — download a generated file (path-traversal safe).
- `POST /api/unload` — free VRAM by unloading models in ComfyUI.

## Errors

`401` missing/bad token · `404` unknown job or output · `413` upload too large ·
`502` ComfyUI unreachable · `409` job-level errors (missing model or node are surfaced verbatim so
you know what to download/install).

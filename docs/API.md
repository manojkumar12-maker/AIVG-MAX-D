# Adapter API

The adapter is the only public surface in front of ComfyUI. Base URL is your tunnel URL
(`https://<name>.trycloudflare.com`) or `http://127.0.0.1:8189` locally.

## Authentication

- Every `/api/*` route and `/ws/jobs` requires the session token.
- `/health` is public.
- Send the token as `X-Session-Token: <token>` or as a `?token=<token>` query parameter. The query
  form exists so `<img>` and `<video>` tags can load outputs; prefer the header everywhere else.
- A missing or wrong token returns `401` with `{"error": {"code": "invalid_token", ...}}`.
- Every authenticated request consumes the token's rate-limit budget (30 requests per 60 seconds).
  The budget is shared across all authenticated endpoints, including polling.

## Common response shapes

Errors raised by the adapter use:

```json
{
  "error": {
    "code": "insufficient_vram",
    "message": "Workflow 'video_wan_i2v' needs about 22GB of VRAM; this GPU reports 15.0GB.",
    "hint": "Pick a smaller workflow or reduce resolution and frame count."
  }
}
```

Generation jobs report their own errors on the job object (`status: "failed"`, `error`,
`error_hint`).

## Health and status

### `GET /health` (public)

Liveness and capability summary. Also reports whether ComfyUI and Drive are available.

```json
{
  "backend_online": true,
  "comfyui_online": true,
  "drive_available": false,
  "gpu_name": "Tesla T4",
  "gpu_vram_gb": 15.0,
  "loaded_models": [],
  "queue_size": 0,
  "active_jobs": 0,
  "capabilities": {
    "image": true,
    "video": true,
    "image_to_image": true,
    "image_to_video": true,
    "max_concurrent_jobs": 1,
    "vram_class": "MEDIUM_VRAM"
  },
  "backend_version": "1.0.0"
}
```

`queue_size` is the number of jobs currently in the internal queue; `active_jobs` counts jobs in
`loading_model`, `generating`, `processing` or `saving`.

### `GET /api/status`

Authenticated variant with queue counts, persisted settings and uptime:

```json
{
  "backend_online": true,
  "comfyui_online": true,
  "drive_available": false,
  "gpu_name": "Tesla T4",
  "gpu_vram_gb": 15.0,
  "queue": {"queued": 0, "generating": 0, "completed": 4, "failed": 0},
  "settings": {"save_to_drive": false, "low_vram": false, "unload_after_job": false},
  "uptime_seconds": 123.4
}
```

### `GET /api/capabilities`

Returns the `capabilities` object from `/health`.

## Models and workflows

### `GET /api/models`

Returns registry entries with install status:

```json
{
  "models": [
    {
      "id": "sdxl",
      "name": "Stable Diffusion XL 1.0 base",
      "type": "image",
      "file": "checkpoints/sd_xl_base_1.0.safetensors",
      "url": "https://huggingface.co/...",
      "vram_gb": 12,
      "disk_gb": 7,
      "license": "CreativeML Open RAIL++-M ...",
      "license_url": "https://huggingface.co/...",
      "recommended_for": ["MEDIUM_VRAM", "HIGH_VRAM"],
      "installed": true
    }
  ]
}
```

### `GET /api/workflows`

Returns every template's public metadata (the internal `param_map` is omitted). `experimental`
marks templates that need extra nodes or are not production-ready.

## Uploads

### `POST /api/upload`

Multipart form upload with a single `file` field.

- 25 MB cap (`OGAI_MAX_UPLOAD_BYTES`).
- Content is sniffed by magic bytes, not the declared MIME type.
- Accepted: PNG, JPEG, WebP, GIF.
- Filenames are sanitised and prefixed with a timestamp.

```json
{"url": "1700000000_reference.png", "filename": "1700000000_reference.png", "size_bytes": 12345, "mime": "image/png"}
```

Pass the returned filename as `image` in an image-to-image or image-to-video request.

## Generation

All generation endpoints accept JSON and return `{"job_id": "...", "status": "queued"}`. The job
then runs asynchronously; poll `GET /api/jobs/{job_id}` or subscribe to `/ws/jobs`.

| Endpoint | Kind | Workflow type + mode |
|---|---|---|
| `POST /api/generate/image` | text-to-image | `image` + `text-to-image` |
| `POST /api/generate/image-to-image` | image-to-image | `image` + `image-to-image` |
| `POST /api/generate/video` | text-to-video | `video` + `text-to-video` |
| `POST /api/generate/image-to-video` | image-to-video | `video` + `image-to-video` |

### Request body

| Field | Type | Notes |
|---|---|---|
| `prompt` | string | Required. |
| `negative_prompt` | string | Used by templates that map it (SD 1.5, SDXL, video). |
| `model` | string | Registry id (`sd15`, `sdxl`, `flux_schnell_q4`, `wan21_t2v_480p`, `wan21_i2v_480p`, `ltxvideo_2b`, `animatediff_motion_v15`). Must be installed; must match the workflow's `requires_model`. |
| `workflow_id` | string | Explicit template id. Must match the endpoint's type and mode. `model` alone does not select a template; the studio picks one by model id and sends this. Without it the adapter falls back to the first non-experimental template for the mode. |
| `width`, `height` | integer | Multiples of 8, at least 64, within the template's maximum. Defaults come from the template. |
| `steps`, `cfg`, `seed`, `sampler`, `scheduler` | number/string | Mapped where the template supports them. |
| `batch_size` | integer | 1-4, image workflows only. |
| `frames`, `fps` | integer | Video workflows. `frames` must be 8 to the template's `max_frames` (default max 121). |
| `strength` | number | Image-to-image denoise strength. |
| `image` | string | Uploaded filename for image-to-image or image-to-video. Required by those modes. |

The UI may send additional fields (for example `motion_strength`); they are ignored unless the
workflow's `param_map` maps them.

### Validation before the GPU runs

- `prompt` is required (and `image` for upload-based modes).
- Dimensions must be multiples of 8 and within the template's limits.
- `frames` and `batch_size` must be in range.
- The model must be installed and must be the one the template requires.
- The detected GPU VRAM must meet the template's `min_vram_gb`.
- Every node class referenced by the template must exist in ComfyUI.

Failures return `400` (`missing_model`, `missing_dependency`, `insufficient_vram`) or `422`
(validation), before a job is created.

### Example

```bash
curl -X POST "$BASE/api/generate/image" \
  -H "X-Session-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"a red fox in snow","model":"sdxl","workflow_id":"image_sdxl_t2i","width":1024,"height":1024,"steps":30}'
```

Send `workflow_id` whenever you request a non-default model: the fallback picks the first
non-experimental template for the mode (for text-to-image that is SD 1.5), and a model that does
not match the template's `requires_model` is rejected with `422`. The studio always sends it.

## Jobs

The adapter runs one GPU job at a time by default (`OGAI_MAX_CONCURRENT_JOBS=1`). Job state is
persisted to `OGAI_STATE_DIR/jobs.json`; in-flight jobs are marked failed if the adapter restarts.

Job statuses: `queued`, `loading_model`, `generating`, `processing`, `saving`, `completed`,
`failed`, `cancelled`.

### `GET /api/jobs`

Returns `{"jobs": [...]}` sorted by creation time. Optional `?since=<unix timestamp>` returns only
jobs created after that time.

### `GET /api/jobs/{job_id}`

Returns one job:

```json
{
  "job_id": "a1b2c3d4e5f6",
  "type": "image",
  "status": "completed",
  "stage": "completed",
  "progress": null,
  "outputs": [{"filename": "a1b2c3d4e5f6_img_00001_.png", "type": "image", "size_bytes": 123456}],
  "error": null,
  "error_hint": null,
  "params": {"prompt": "...", "model": "sdxl"},
  "created_at": 1700000000.0,
  "started_at": 1700000000.1,
  "finished_at": 1700000012.0
}
```

### `POST /api/jobs/{job_id}/cancel`

Cancels a queued job immediately. For an active job it sets a cancellation flag; the adapter stops
waiting, marks the job `cancelled`, and returns immediately. The ComfyUI prompt may keep running on
the GPU until it finishes; use `POST /api/unload` or restart cell E if you need the GPU back.

### `DELETE /api/jobs/{job_id}`

Cancels (if needed) and removes the job from history. Returns `{"deleted": "<job_id>"}`.

## Results

### `GET /api/output/{filename}`

Downloads a generated file. Requires the token (header or `?token=`). The filename is sanitised and
resolved inside `OGAI_OUTPUT_DIR`; path traversal is rejected.

### `POST /api/unload`

Asks ComfyUI to unload models and free VRAM. Returns `{"unloaded": true}`, or `502` if ComfyUI is
unreachable.

## Settings

### `GET /api/settings`

```json
{"save_to_drive": false, "low_vram": false, "unload_after_job": false, "drive_available": false}
```

### `POST /api/settings`

Accepts any subset of the three booleans and returns the stored settings:

```json
{"save_to_drive": true, "low_vram": false, "unload_after_job": false}
```

| Setting | Effect |
|---|---|
| `save_to_drive` | Mirrors outputs and a metadata sidecar to `OGAI_DRIVE_DIR` when configured. |
| `low_vram` | Rewrites the rendered graph: batch size 1 and latent width/height halved (minimum 320). |
| `unload_after_job` | Calls ComfyUI `/free` after each successful job. |

## WebSocket progress

### `GET /ws/jobs` (WebSocket)

Connect with `wss://<host>/ws/jobs?token=<token>` (or an `x-session-token` header). The server
accepts the socket and pushes:

```json
{"event": "job_update", "job": {"job_id": "...", "status": "generating", "...": "..."}}
```

Clients only need to keep the socket open; inbound messages are ignored. An invalid token closes
the socket with code `4401`. The frontend uses this stream for live updates and still polls
`GET /api/jobs` as a fallback.

## Error status codes

| Status | Meaning |
|---|---|
| `400` | `missing_model`, `missing_dependency` or `insufficient_vram`; the workflow cannot run as requested. |
| `401` | Missing or invalid session token. |
| `404` | Unknown job, output, workflow or mode. |
| `413` | Upload exceeds the size cap. |
| `422` | Validation failure, bad filename, unsupported upload type, or workflow/mode mismatch. |
| `429` | Token rate limit exceeded (30 authenticated requests per 60 seconds). |
| `502` | ComfyUI is unreachable (for example `POST /api/unload`). |
| `500` | Unexpected adapter error. Generation failures are normally reported on the job instead. |

## Quick curl checks

```bash
curl "$BASE/health"
curl -H "X-Session-Token: $TOKEN" "$BASE/api/models"
curl -H "X-Session-Token: $TOKEN" "$BASE/api/jobs"
```

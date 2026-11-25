# Troubleshooting

## Connection panel stays red

- Tunnel URLs are valid **only while Colab cell E is running**. Re-run A → E and use the fresh URL
  and token it printed — every restart creates a new URL and a new token.
- Confirm `/health` on the tunnel URL answers in a browser tab. It should return JSON with
  `"backend_online": true`.
- GitHub Pages serves over HTTPS and so does the tunnel. An `http://` backend URL causes
  mixed-content errors. Use the full `https://...trycloudflare.com` URL.
- If the tunnel was not ready when E finished, wait a few seconds and re-run only cell E.

## `401` in the UI

Token mismatch. Paste the token printed by section E of the **current** session; old tokens die
with the old runtime. If you run the adapter locally without `OGAI_SESSION_TOKEN`, read the
generated token from `backend/state/runtime.json`.

## `429` / "rate limit exceeded"

Each token gets 30 authenticated requests per 60 seconds across all `/api/*` endpoints, including
job polling. Wait a minute and retry. If this happens constantly, check for multiple open studio
tabs polling the same backend, or increase the interval in `frontend/src/hooks/useJobPolling.js`.

## "ComfyUI unreachable" / `502`

ComfyUI crashed or is still starting. Check `/content/comfyui.log` and restart cell E (it starts
both services). `POST /api/unload` also returns `502` when ComfyUI is down.

## Missing model or node

The job error names what is missing.

- **Missing model.** Check `GET /api/models`; `installed` must be `true`. The file must be in the
  folder ComfyUI scans and the filename must match the registry/template. See
  [WORKFLOWS.md](WORKFLOWS.md#known-filename-mismatches).
- **Missing node class.** Install the pack named in the hint (ComfyUI-GGUF, VideoHelperSuite,
  AnimateDiff-Evolved), then restart ComfyUI by re-running cell E.

## SD 1.5 downloads but shows "not installed"

Known mismatch: the notebook saves `sd_v1-5_pruned_emaonly_fp16.safetensors`; the registry and
workflow expect `v1-5-pruned-emaonly-fp16.safetensors`. Rename the file in
`ComfyUI/models/checkpoints/` (and the Drive cache) or use SDXL.

## FLUX fails after downloading

The notebook's FLUX files do not currently match the template's expected names/folders (Q4_K_S vs
Q4_0, fp8 T5 vs GGUF text encoder, `ae_schnell` vs `ae`). See
[WORKFLOWS.md](WORKFLOWS.md#known-filename-mismatches). Use SDXL until they are aligned.

## Video generation fails immediately

- All video workflows are **experimental** and need `ComfyUI-VideoHelperSuite` for mp4 output
  (`VHS_VideoCombine`). Add the custom-node cell described in [COLAB_SETUP.md](COLAB_SETUP.md) and
  restart cell E.
- The model must be installed. No notebook preset downloads Wan I2V 14B, LTX-Video or AnimateDiff.
- Check the VRAM floor: Wan I2V needs about 22 GB, so it cannot run on a free T4.
- `animatediff_motion_v15` also needs `ComfyUI-AnimateDiff-Evolved`.

## `CUDA out of memory`

Your GPU is smaller than the model's needs. Try, in order:

1. Enable **Low VRAM** in Settings (halves latent resolution and forces batch size 1).
2. Enable **Unload after job** or press **Unload** to free VRAM.
3. Lower width/height or frames, or use a smaller model: SD 1.5 → SDXL → FLUX Q4 → video.

On a free T4, SDXL images are the realistic target. The I2V 14B model needs a 24 GB-class GPU.

## Queue appears stuck

The adapter runs one GPU job at a time and does not queue an unbounded backlog. Cancel the active
job from the queue sidebar (`POST /api/jobs/{id}/cancel`); if ComfyUI itself is wedged, re-run cell
E. Jobs that were running when the adapter restarted are marked `failed`.

## Download is slow after a runtime reset

Section D resumes partial downloads (`wget -c`) and reuses the Drive cache when
`MOUNT_DRIVE=True`. Mount Drive in section A to avoid re-downloading.

## Results do not appear in the gallery

Outputs live in `OGAI_OUTPUT_DIR` (`MyDrive/OpenGenerativeAI/outputs` when Drive is mounted and
`save_to_drive` is enabled). Check `/content/adapter.log` for write errors; Drive quota exhaustion
shows up there. The gallery reads `GET /api/jobs`, so a 401/429 can also empty it temporarily.

## Frontend shows a blank page on GitHub Pages

The build must know its base path. The Pages workflow sets `BASE_PATH=/<repo-name>/`
automatically. If you built and uploaded `dist/` by hand, rebuild with the correct base:

```bash
# macOS, Linux, PowerShell
npm run build -- --base=/<repo-name>/

# Git Bash for Windows
MSYS_NO_PATHCONV=1 npm run build -- --base=/<repo-name>/
```

MSYS (Git Bash) rewrites leading-slash arguments and environment values into filesystem paths; on
Windows use PowerShell or disable the conversion as shown.

## `npm run dev` uses the wrong port

The studio's Vite config uses port **3000** with `strictPort`. If 3000 is taken, stop the other
process or change `frontend/vite.config.js`. The old docs mentioned 5199; that is not this app.

## CORS error in the browser

The adapter defaults to `OGAI_CORS_ORIGINS=*`, so CORS should not block you. If you set that
variable, include your Pages origin (scheme + host only), for example
`https://<user>.github.io`, and restart the adapter.

## Backend tests fail during collection

Install the test dependencies, including `pytest-asyncio` (imported by the tests but not listed in
`backend/requirements.txt`), and `python-multipart` (in requirements) so FastAPI can parse uploads:

```bash
pip install -r backend/requirements.txt pytest-asyncio
python -m pytest backend/tests -q
```

## Notebook cell A stops with "No GPU"

Choose **Runtime → Change runtime type → T4 GPU**, then reconnect and re-run A → E.

## Drive runs out of space

Models are large and copied to `MyDrive/OpenGenerativeAI/models`. Delete old model folders in
Drive, or set `MOUNT_DRIVE = False` in cell A to keep everything in the ephemeral runtime.

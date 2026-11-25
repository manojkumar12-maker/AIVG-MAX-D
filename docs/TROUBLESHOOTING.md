# Troubleshooting

## Connection panel stays red
- Tunnel URLs are valid **only while Colab cell E is running**. Re-run A → E and use the fresh URL
  and token it printed — every restart creates a new URL and a new token.
- Confirm `/health` on the tunnel URL answers in a browser tab.
- GitHub Pages serves over HTTPS; the tunnel does too. A mixed-content error means you typed an
  `http://` frontend URL.

## `401` in the UI
Token mismatch. Paste the token printed by section E of the current session — old tokens die with
the old runtime.

## "ComfyUI unreachable" / `502`
ComfyUI crashed or is still starting. Check `/content/comfyui.log`. Restart cell E (it starts both
services).

## Job fails with a missing model or node
The error names what to download or install. See `docs/WORKFLOWS.md` for the file list per workflow
and the `git clone` lines for ComfyUI-GGUF, KJNodes and VideoHelperSuite. After installing nodes,
restart ComfyUI (re-run cell E).

## `CUDA out of memory`
Your GPU is smaller than the model's VRAM class. Use `POST /api/unload` (or the Unload button) to
free VRAM, or drop to a smaller model: SD 1.5 → SDXL → FLUX Q4 → Wan. The I2V 14B model needs a
24 GB class GPU; on T4 use the 1.3B T2V model instead.

## Queue stuck
The GPU queue runs one job at a time. Cancel a hung job from the queue sidebar
(`POST /api/jobs/{id}/cancel`); if ComfyUI itself is wedged, re-run cell E.

## Download too slow after a runtime reset
Section D resumes partial downloads (`wget -c`) and reuses the Drive cache when `MOUNT_DRIVE=True`.
Mount Drive in section A to avoid re-downloading.

## Results do not appear in the gallery
Outputs live in `OUTPUT_DIR` (Drive `MyDrive/OpenGenerativeAI/outputs` when mounted). Check
`/content/adapter.log` for write errors; Drive quota exhaustion shows up there.

## Frontend shows a blank page on GitHub Pages
The build must know its base path — the Pages workflow sets `BASE_PATH=/<repo-name>/` automatically.
If you built and uploaded `dist/` by hand, rebuild with that variable set.

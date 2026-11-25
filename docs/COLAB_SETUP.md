# Colab setup walkthrough

`notebooks/OpenGenerativeAI_Colab.ipynb` runs the whole GPU backend in one session. Sections run in
order A → E; each is a single cell.

## A — Environment check and options
Confirms a CUDA GPU is attached (stops early with a clear message if not) and reports the GPU name
and VRAM. `MOUNT_DRIVE = True` mounts Google Drive and creates `MyDrive/OpenGenerativeAI/` for
model and output caching. On GPUs under 20 GB the notebook warns that video models will not fit.

## B — Install
Clones ComfyUI (shallow) and this repository into the runtime, then installs both requirement sets.

## C — Choose models
Pick one preset from a dropdown. The cell lists every file it will download, its size and its
licence before anything downloads:

| Preset | Fits | Content |
|---|---|---|
| SD 1.5 | any GPU | SD 1.5 checkpoint, ~2 GB |
| SDXL | ~12 GB VRAM | SDXL base checkpoint, ~6.9 GB |
| SDXL + FLUX schnell Q4 | ~16 GB | SDXL + FLUX Q4 gguf + T5 fp8 + VAE |
| Everything incl. Wan 2.1 | ~24 GB | SDXL + Wan 2.1 T2V 1.3B stack |

## D — Download (resumable)
Downloads each file with `wget -c` (resumable), skipping anything already present. With Drive
mounted, finished files are copied to Drive and symlinked back on later runs, so a runtime reset
does not re-download gigabytes.

## E — Start services and print connection details
1. Starts ComfyUI bound to `127.0.0.1:8188` (never exposed directly).
2. Generates a random 24-byte session token and starts the adapter on `127.0.0.1:8189` with
   `SESSION_TOKEN`, `COMFYUI_URL`, `OUTPUT_DIR` and `STATE_DIR` set.
3. Installs cloudflared and opens a free `trycloudflare.com` tunnel to the adapter only.
4. Prints the **Frontend URL** and **Session token** to paste into the studio Connection panel.

Keep cell E running while you generate. Logs are at `/content/comfyui.log`, `/content/adapter.log`,
`/content/tunnel.log`. When the runtime resets, re-run A → E (Drive caching makes D fast).

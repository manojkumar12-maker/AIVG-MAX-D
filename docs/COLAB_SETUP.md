# Colab setup walkthrough

`notebooks/OpenGenerativeAI_Colab.ipynb` runs the whole GPU backend in one session. Sections run in
order A → E; each is a single cell. Cells B, D and E are self-sufficient, so they still work if you
skipped A or the runtime restarted.

## A — Environment check and options

Confirms a CUDA GPU is attached (stops early with a clear message if not) and reports the GPU name
and VRAM. `MOUNT_DRIVE = True` mounts Google Drive and creates
`MyDrive/OpenGenerativeAI/{models,outputs}` for model and output caching.

On GPUs under 20 GB the notebook prints a warning that video models will likely not fit. This is
advice, not a hard block; the adapter still enforces each workflow's minimum VRAM.

Variables set here that later cells reuse:

| Variable | Value |
|---|---|
| `COMFYUI_DIR` | `/content/ComfyUI` |
| `REPO_DIR` | `/content/Open-Generative-AI` |
| `REPO_URL` | this repository |
| `MOUNT_DRIVE` | `True` by default |

## B — Install

Clones ComfyUI (shallow) and this repository into the runtime, then installs both requirement sets.
It also self-heals a wrong or partial clone of the repository by deleting and re-cloning it.

**It does not install custom ComfyUI nodes.** Stock ComfyUI covers SDXL image generation. Video and
FLUX workflows need extra packs. Add a new cell after B and run it before E:

```python
!git clone --depth 1 https://github.com/city96/ComfyUI-GGUF {COMFYUI_DIR}/custom_nodes/ComfyUI-GGUF
!git clone --depth 1 https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite {COMFYUI_DIR}/custom_nodes/ComfyUI-VideoHelperSuite
!git clone --depth 1 https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved {COMFYUI_DIR}/custom_nodes/ComfyUI-AnimateDiff-Evolved
!for d in {COMFYUI_DIR}/custom_nodes/*/; do [ -f "$d/requirements.txt" ] && pip -q install -r "$d/requirements.txt"; done
```

- **ComfyUI-GGUF** — FLUX schnell Q4 nodes.
- **VideoHelperSuite** — `VHS_VideoCombine` mp4 output for every video workflow.
- **AnimateDiff-Evolved** — `ADE_*` nodes for AnimateDiff.

LTX-Video and Wan workflows use nodes that ship with a recent ComfyUI build.

## C — Choose models

Pick one preset from the dropdown. The cell lists every file it will download, its size and its
licence before anything downloads.

| Preset | Content | Notes |
|---|---|---|
| **SD 1.5 (fastest, any GPU)** | SD 1.5 checkpoint, ~2 GB | Notebook filename does not match the registry in this revision |
| **SDXL (high quality, ~12GB)** | SDXL base 1.0, ~6.9 GB | Recommended default; works on a T4 |
| **SDXL + FLUX schnell Q4 (~16GB)** | SDXL + FLUX Q4 GGUF + T5 fp8 + VAE | Experimental; needs ComfyUI-GGUF and filename alignment |
| **Everything incl. Wan 2.1 video (~24GB)** | SDXL base + Wan 2.1 T2V 1.3B + UMT5 encoder + Wan VAE | Experimental; needs VideoHelperSuite; 24 GB recommended |

The presets do **not** include Wan 2.1 I2V 14B, LTX-Video 2B or AnimateDiff, even though those
models are registered in the adapter. Download them manually and install the matching nodes; see
[WORKFLOWS.md](WORKFLOWS.md).

## D — Download (resumable)

Downloads each file with `wget -c` (resumable), skipping anything already present. With Drive
mounted, finished files are copied to Drive and symlinked back on later runs, so a runtime reset
does not re-download gigabytes.

Files are placed in ComfyUI's model folders (`checkpoints/`, `diffusion_models/`, `text_encoders/`,
`vae/`, and for the FLUX preset `unet/`, `clip/`, `vae/`).

## E — Start services and print connection details

1. Starts ComfyUI bound to `127.0.0.1:8188` (never exposed directly). It adds `--lowvram` below
   20 GB VRAM and `--novram` below 12 GB.
2. Generates a random 24-byte session token and starts the adapter on `127.0.0.1:8189` with
   `OGAI_SESSION_TOKEN`, `OGAI_COMFY_URL`, `OGAI_OUTPUT_DIR`, `OGAI_DRIVE_DIR` (when mounted) and
   `OGAI_STATE_DIR` set.
3. Installs `cloudflared` and opens a free `trycloudflare.com` tunnel to the adapter only.
4. Prints the **Frontend URL** and **Session token** to paste into the studio Connection panel.

Keep cell E running while you generate. Logs:

| Log | Path |
|---|---|
| ComfyUI | `/content/comfyui.log` |
| Adapter | `/content/adapter.log` |
| Tunnel | `/content/tunnel.log` |

When the runtime resets, re-run A → E. Drive caching makes D fast, but the tunnel URL and token are
new every time E runs.

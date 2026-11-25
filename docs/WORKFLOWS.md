# Workflows and models

ComfyUI workflow templates live in `backend/workflows/`. Each template is a full ComfyUI
API-format graph plus a `_meta` block (id, mode, model, VRAM floor, features, parameter map,
experimental flag and install hint).

## How a workflow is selected

When the studio posts to `/api/generate/*`:

1. If the body contains `workflow_id`, that workflow is used (it must match the requested mode).
2. Otherwise, the adapter looks at every workflow with the same type and mode, **prefers a
   non-experimental one**, and falls back to the first candidate if all are experimental.
3. The selected workflow is validated against the live ComfyUI install: model file present,
   dimensions valid, required node classes present, and detected GPU VRAM above the workflow's
   floor.

The SD 1.5 and SDXL image workflows are non-experimental. FLUX and **all video workflows are
experimental**, so a video request falls back to the first matching template unless the UI sends
`workflow_id`. `model` on its own does not pick a template; the studio chooses one by model id and
sends `workflow_id`.

## Workflow templates

| File | Mode | Registry model | Min VRAM | Experimental | Custom node classes |
|---|---|---|---|---|---|
| `image_sd15_t2i.json` | text-to-image | `sd15` | 4 GB | No | none |
| `image_sdxl_t2i.json` | text-to-image | `sdxl` | 10 GB | No | none |
| `image_sdxl_i2i.json` | image-to-image | `sdxl` | 10 GB | No | none |
| `image_flux_schnell_q4.json` | text-to-image | `flux_schnell_q4` | 12 GB | Yes | `UnetLoaderGGUF`, `CLIPLoaderGGUF` (ComfyUI-GGUF) |
| `video_wan_t2v.json` | text-to-video | `wan21_t2v_480p` | 10 GB | Yes | `VHS_VideoCombine` (VideoHelperSuite) |
| `video_wan_i2v.json` | image-to-video | `wan21_i2v_480p` | 22 GB | Yes | `VHS_VideoCombine` (VideoHelperSuite) |
| `video_ltx_t2v.json` | text-to-video | `ltxvideo_2b` | 8 GB | Yes | `VHS_VideoCombine`; LTXV nodes from a recent ComfyUI |
| `video_animdiff_t2v.json` | text-to-video | `animatediff_motion_v15` | 6 GB | Yes | `ADE_*` (AnimateDiff-Evolved) + `VHS_VideoCombine` |

Widths and heights must be multiples of 8 and within each template's `max_width`/`max_height`.
Frame counts must be between 8 and the template's `max_frames`. The adapter rejects invalid values
before submitting to ComfyUI.

## Model registry

Source of truth: `backend/adapter/models_registry.py`. The live list is served on
`GET /api/models`, including an `installed` flag from ComfyUI's model folder listings.

| Model id | Name | VRAM | Disk | Licence | Recommended class |
|---|---|---|---|---|---|
| `sd15` | Stable Diffusion 1.5 | 4 GB | 2.2 GB | CreativeML Open RAIL-M — **check before commercial use** | `LOW_VRAM` |
| `sdxl` | Stable Diffusion XL 1.0 base | 12 GB | 7 GB | CreativeML Open RAIL++-M — commercial use allowed, use restrictions apply | `MEDIUM_VRAM`, `HIGH_VRAM` |
| `flux_schnell_q4` | FLUX.1 schnell Q4 | 12 GB | 7 GB | FLUX.1 [schnell] **non-commercial** | `MEDIUM_VRAM`, `HIGH_VRAM` |
| `wan21_t2v_480p` | Wan 2.1 T2V 1.3B | 12 GB | 3 GB | Apache-2.0 | `MEDIUM_VRAM`, `HIGH_VRAM` |
| `wan21_i2v_480p` | Wan 2.1 I2V 14B | 24 GB | 29 GB | Apache-2.0 | `HIGH_VRAM`, `VERY_HIGH_VRAM` |
| `ltxvideo_2b` | LTX-Video 2B 0.9 | 8 GB | 10 GB | LTX-Video Open Weights Licence — check before commercial use | `MEDIUM_VRAM`, `HIGH_VRAM` |
| `animatediff_motion_v15` | AnimateDiff motion module v2 | 6 GB | 2 GB | Apache-2.0 module; SD 1.5 licence applies to outputs | `LOW_VRAM`, `MEDIUM_VRAM` |

The registry's `vram_gb` is the model's own recommendation; a workflow's `min_vram_gb` can be
slightly lower or higher. The **workflow floor** is what the adapter enforces.

## Notebook presets vs registry

The notebook has four presets; the registry has seven models. Only a subset is downloaded
automatically.

| Notebook preset | Downloads | Registry models covered |
|---|---|---|
| SD 1.5 | SD 1.5 checkpoint | `sd15` |
| SDXL | SDXL base 1.0 | `sdxl` |
| SDXL + FLUX schnell Q4 | SDXL, FLUX Q4 GGUF, T5 fp8, VAE | `sdxl`, `flux_schnell_q4` (with caveats below) |
| Everything incl. Wan 2.1 video | SDXL, Wan 2.1 T2V 1.3B, UMT5 encoder, Wan VAE | `sdxl`, `wan21_t2v_480p` |

No preset installs `wan21_i2v_480p`, `ltxvideo_2b` or `animatediff_motion_v15`. To use them,
download the weights into the folders ComfyUI expects, install the node packs, and restart cell E.

## Known filename mismatches

These are current inconsistencies between the notebook, the registry and the workflow templates.
They cause "model not installed" or ComfyUI execution errors even after a successful download.

| Model | Notebook saves | Registry / workflow expects |
|---|---|---|
| SD 1.5 | `checkpoints/sd_v1-5_pruned_emaonly_fp16.safetensors` | `checkpoints/v1-5-pruned-emaonly-fp16.safetensors` |
| FLUX checkpoint | `unet/flux1-schnell-Q4_K_S.gguf` | `diffusion_models/flux1-schnell-Q4_0.gguf` (registry) / `flux1-schnell-Q4_0.gguf` (`UnetLoaderGGUF`) |
| FLUX text encoder | `clip/t5xxl_fp8_e4m3fn.safetensors` | `t5-v1_1-xxl-encoder-Q5_1.gguf` (`CLIPLoaderGGUF`) |
| FLUX VAE | `vae/ae_schnell.safetensors` | `ae.safetensors` (`VAELoader`) |

Until the notebook and registry are aligned, **SDXL is the reliable image path**. To make FLUX
work manually, download or rename files to the exact names and folders the template lists, then
restart ComfyUI so its folder listings refresh. To make SD 1.5 work, rename the downloaded
checkpoint to `v1-5-pruned-emaonly-fp16.safetensors` or update the registry + workflow `param_map`
to the new name.

The registry also lists extra node packs that may exceed what the shipped template needs (for
example KJNodes for Wan). The **Custom node classes** column above comes from the actual template.

## Installing extra custom nodes

In Colab, add a cell after section B and run it before section E:

```python
!git clone --depth 1 https://github.com/city96/ComfyUI-GGUF {COMFYUI_DIR}/custom_nodes/ComfyUI-GGUF
!git clone --depth 1 https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite {COMFYUI_DIR}/custom_nodes/ComfyUI-VideoHelperSuite
!git clone --depth 1 https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved {COMFYUI_DIR}/custom_nodes/ComfyUI-AnimateDiff-Evolved
!for d in {COMFYUI_DIR}/custom_nodes/*/; do [ -f "$d/requirements.txt" ] && pip -q install -r "$d/requirements.txt"; done
```

| Pack | Provides | Used by |
|---|---|---|
| [ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF) | `UnetLoaderGGUF`, `CLIPLoaderGGUF` | FLUX schnell Q4 |
| [ComfyUI-VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite) | `VHS_VideoCombine` | every video workflow |
| [ComfyUI-AnimateDiff-Evolved](https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved) | `ADE_*` nodes | AnimateDiff video |

If a workflow references a node class that is not installed, the job fails with the missing class
names in the error hint, so you know exactly what to add.

## GPU classes

`backend/adapter/models_registry.py` maps detected VRAM to a class:

| VRAM | Class |
|---|---|
| `< 8 GB` | `LOW_VRAM` |
| `< 24 GB` | `MEDIUM_VRAM` |
| `< 48 GB` | `HIGH_VRAM` |
| `>= 48 GB` | `VERY_HIGH_VRAM` |
| unknown | `UNKNOWN` |

Each model lists the classes it recommends. Independently, every workflow has a hard `min_vram_gb`
floor; requests below it fail synchronously with `insufficient_vram` instead of crashing ComfyUI
mid-run. On a free T4 (about 15 GB) use SDXL for images; video is experimental and slow.

## Model licences

Models carry their own licences, separate from this MIT-licensed code.

- **SD 1.5** — CreativeML Open RAIL-M; use restrictions apply. Check before commercial use.
- **SDXL** — CreativeML Open RAIL++-M; commercial use allowed with use restrictions.
- **FLUX.1 schnell** — non-commercial licence. Do not use outputs commercially.
- **Wan 2.1** — Apache-2.0.
- **LTX-Video** — Lightricks open-weights licence; check before commercial use.
- **AnimateDiff** — Apache-2.0 module; the SD 1.5 checkpoint licence also applies to outputs.

## Adding a workflow template

Drop a ComfyUI API-format graph in `backend/workflows/` with a `_meta` block containing at minimum:

```json
{
  "_meta": {
    "id": "image_example",
    "name": "Example workflow",
    "type": "image",
    "mode": "text-to-image",
    "requires_model": "sdxl",
    "min_vram_gb": 10,
    "features": ["prompt", "seed"],
    "needs_upload": false,
    "experimental": false,
    "param_map": {
      "prompt": {"node": "1", "field": "text"},
      "model": {"node": "0", "field": "ckpt_name"}
    }
  }
}
```

`type` is `image` or `video`; `mode` is one of `text-to-image`, `image-to-image`,
`text-to-video`, `image-to-video`. `param_map` maps API fields onto graph nodes. The registry
reloads templates on startup; restart the adapter after editing.

# Workflows and models

ComfyUI workflow templates live in `backend/workflows/`. Each template is a full ComfyUI API-format
graph plus metadata (model id, experimental flag). The adapter picks the template that matches your
requested model and mode; experimental workflows are never auto-selected.

## Workflow templates

| File | Mode | Model | Notes |
|---|---|---|---|
| `image_sd15_t2i.json` | text-to-image | sd15 | Fastest; runs on any GPU |
| `image_sdxl_t2i.json` | text-to-image | sdxl | Higher quality, slower |
| `image_sdxl_i2i.json` | image-to-image | sdxl | Uses uploaded reference + denoise |
| `image_flux_schnell_q4.json` | text-to-image | flux_schnell_q4 | Needs ComfyUI-GGUF nodes |
| `video_wan_t2v.json` | text-to-video | wan21_t2v_480p | Apache-2.0; needs KJNodes + VideoHelperSuite |
| `video_wan_i2v.json` | image-to-video | wan21_i2v_480p | 24 GB VRAM class |

## Model registry and licences

From `backend/adapter/models_registry.py`; served live on `GET /api/models`.

| Model | VRAM | Disk | Licence | Extra nodes |
|---|---|---|---|---|
| SD 1.5 (`sd15`) | 4 GB | 2.2 GB | CreativeML Open RAIL-M — **check before commercial use** | — |
| SDXL base 1.0 (`sdxl`) | 12 GB | 7 GB | CreativeML Open RAIL++-M — commercial use allowed, use restrictions apply | — |
| FLUX.1 schnell Q4 (`flux_schnell_q4`) | 12 GB | 7 GB | FLUX.1 [schnell] non-commercial — **not for commercial output** | ComfyUI-GGUF |
| Wan 2.1 T2V 1.3B (`wan21_t2v_480p`) | 12 GB | 3 GB | Apache-2.0 | KJNodes, VideoHelperSuite |
| Wan 2.1 I2V 14B (`wan21_i2v_480p`) | 24 GB | 29 GB | Apache-2.0 | KJNodes, VideoHelperSuite |

The studio reports each model's licence in the model list, so licence questions are answered inside
the UI, not buried in this doc.

## GPU compatibility

VRAM classes: `<8 GB LOW_VRAM`, `<24 GB MEDIUM_VRAM`, `<48 GB HIGH_VRAM`, above VERY_HIGH_VRAM
(`UNKNOWN` when the backend cannot see the GPU). Each model lists the classes it is recommended
for; jobs requesting a model above the detected class fail fast with a clear message instead of
crashing ComfyUI mid-run.

## Installing extra custom nodes

FLUX Q4 and the Wan workflows need ComfyUI custom nodes. In Colab, add to section B:

```python
!git clone --depth 1 https://github.com/comfyanonymous/ComfyUI-GGUF {COMFYUI_DIR}/custom_nodes/ComfyUI-GGUF
!git clone --depth 1 https://github.com/kijai/ComfyUI-KJNodes {COMFYUI_DIR}/custom_nodes/ComfyUI-KJNodes
!git clone --depth 1 https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite {COMFYUI_DIR}/custom_nodes/ComfyUI-VideoHelperSuite
```

If a workflow references a node type that is not installed, the job fails with the missing node
pack named, so you know exactly what to add.

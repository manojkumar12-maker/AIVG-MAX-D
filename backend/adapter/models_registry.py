"""Model registry with GPU compatibility data.

Every entry documents license and hardware requirements. Models are listed
as usable only when a workflow that supports them exists in workflows/.
"""
from __future__ import annotations

VRAM_CLASSES = [
    (8, "LOW_VRAM"),
    (24, "MEDIUM_VRAM"),
    (48, "HIGH_VRAM"),
    (float("inf"), "VERY_HIGH_VRAM"),
]


def vram_class(vram_gb: float | None) -> str:
    if vram_gb is None:
        return "UNKNOWN"
    for threshold, name in VRAM_CLASSES:
        if vram_gb < threshold:
            return name
    return "VERY_HIGH_VRAM"


MODELS = [
    {
        "id": "sd15",
        "name": "Stable Diffusion 1.5",
        "type": "image",
        "file": "checkpoints/v1-5-pruned-emaonly-fp16.safetensors",
        "url": "https://huggingface.co/Comfy-Org/stable-diffusion-v1-5-archive/resolve/main/v1-5-pruned-emaonly-fp16.safetensors",
        "vram_gb": 4,
        "disk_gb": 2.2,
        "license": "CreativeML Open RAIL-M",
        "license_url": "https://huggingface.co/Comfy-Org/stable-diffusion-v1-5-archive/blob/main/LICENSE",
        "recommended_for": ["LOW_VRAM"],
        "installed": False,
    },
    {
        "id": "sdxl",
        "name": "Stable Diffusion XL 1.0 base",
        "type": "image",
        "file": "checkpoints/sd_xl_base_1.0.safetensors",
        "url": "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors",
        "vram_gb": 12,
        "disk_gb": 7,
        "license": "CreativeML Open RAIL++-M (commercial use allowed, use restrictions apply)",
        "license_url": "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/main/LICENSE.md",
        "recommended_for": ["MEDIUM_VRAM", "HIGH_VRAM"],
        "installed": False,
    },
    {
        "id": "pony_v6_xl",
        "name": "Pony Diffusion V6 XL",
        "type": "image",
        "file": "checkpoints/ponyDiffusionV6XL_v6StartWithThisOne.safetensors",
        "url": "https://huggingface.co/LyliaEngine/Pony_Diffusion_V6_XL/resolve/main/ponyDiffusionV6XL_v6StartWithThisOne.safetensors",
        "vram_gb": 12,
        "disk_gb": 7,
        "license": "CreativeML Open RAIL++-M (SDXL-based; use restrictions apply)",
        "license_url": "https://huggingface.co/LyliaEngine/Pony_Diffusion_V6_XL",
        "recommended_for": ["MEDIUM_VRAM", "HIGH_VRAM"],
        "installed": False,
    },
    {
        "id": "flux_schnell_q4",
        "name": "FLUX.1 schnell (FP8/quantized)",
        "type": "image",
        "file": "diffusion_models/flux1-schnell-q4_0.gguf",
        "url": "https://huggingface.co/city96/FLUX.1-schnell-gguf/resolve/main/flux1-schnell-Q4_0.gguf",
        "vram_gb": 12,
        "disk_gb": 7,
        "license": "FLUX.1 [schnell] Non-Commercial License (Apache-2.0 weights, artifacts restricted; check before commercial use)",
        "license_url": "https://huggingface.co/black-forest-labs/FLUX.1-schnell/blob/main/LICENSE.md",
        "recommended_for": ["MEDIUM_VRAM", "HIGH_VRAM"],
        "installed": False,
        "extra_nodes": ["ComfyUI-GGUF"],
    },
    {
        "id": "wan21_t2v_480p",
        "name": "Wan 2.1 T2V 1.3B (480p video)",
        "type": "video",
        "file": "diffusion_models/wan2.1_t2v_1.3B_fp16.safetensors",
        "url": "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/diffusion_models/wan2.1_t2v_1.3B_fp16.safetensors",
        "vram_gb": 12,
        "disk_gb": 3,
        "license": "Apache-2.0",
        "license_url": "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged",
        "recommended_for": ["MEDIUM_VRAM", "HIGH_VRAM"],
        "installed": False,
        "extra_nodes": ["KJNodes", "VideoHelperSuite"],
    },
    {
        "id": "wan21_i2v_480p",
        "name": "Wan 2.1 I2V 14B 480p (image to video)",
        "type": "video",
        "file": "diffusion_models/wan2.1_i2v_480p_14B_fp16.safetensors",
        "url": "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/diffusion_models/wan2.1_i2v_480p_14B_fp16.safetensors",
        "vram_gb": 24,
        "disk_gb": 29,
        "license": "Apache-2.0",
        "license_url": "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged",
        "recommended_for": ["HIGH_VRAM", "VERY_HIGH_VRAM"],
        "installed": False,
        "extra_nodes": ["KJNodes", "VideoHelperSuite"],
    },
    {
        "id": "ltxvideo_2b",
        "name": "LTX-Video 2B 0.9 (fast distilled video)",
        "type": "video",
        "file": "diffusion_models/ltx-video-2b-v0.9.safetensors",
        "url": "https://huggingface.co/Lightricks/LTX-Video/resolve/main/ltx-video-2b-v0.9.safetensors",
        "vram_gb": 8,
        "disk_gb": 10,
        "license": "LTX-Video Open Weights License (Lightricks; non-commercial research, check before commercial use)",
        "license_url": "https://huggingface.co/Lightricks/LTX-Video/blob/main/LICENSE",
        "recommended_for": ["MEDIUM_VRAM", "HIGH_VRAM"],
        "installed": False,
        "extra_nodes": ["LTXVideo", "VideoHelperSuite"],
    },
    {
        "id": "animatediff_motion_v15",
        "name": "AnimateDiff motion module v2 (SD1.5)",
        "type": "video",
        "file": "animatediff_models/mm_sd_v15_v2.ckpt",
        "url": "https://huggingface.co/guoyww/animatediff/resolve/main/mm_sd_v15_v2.ckpt",
        "vram_gb": 6,
        "disk_gb": 2,
        "license": "Apache-2.0 (module; SD1.5 checkpoint license applies to outputs)",
        "license_url": "https://huggingface.co/guoyww/animatediff",
        "recommended_for": ["LOW_VRAM", "MEDIUM_VRAM"],
        "installed": False,
        "extra_nodes": ["AnimateDiff-Evolved", "VideoHelperSuite"],
    },
]

MODEL_BY_ID = {m["id"]: m for m in MODELS}


def installed_ids(comfy_models: list[str]) -> None:
    """Mark registry entries installed when ComfyUI reports their file."""
    for m in MODELS:
        m["installed"] = any(m["file"] in c or c.endswith(m["file"].split("/")[-1]) for c in comfy_models)

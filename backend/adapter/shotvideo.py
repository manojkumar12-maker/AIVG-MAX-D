"""Shot-video prompt building (Phase 3B).

Deterministically assembles an image-to-video prompt for one storyboard shot
from context already stored in the FilmStore: the Phase 3A image prompt
(bible style guide, matched characters, scene context) plus the shot's own
motion/camera directions. Nothing is invented: absent fields are reported in
``missing`` and left out. User-supplied prompts always win over the assembled
context, mirroring :mod:`adapter.shotgen`.
"""
from __future__ import annotations

from typing import Any

from .shotgen import ShotLookupError, TOTAL_LIMIT, build_shot_prompt

MOTION_LIMIT = 400


def build_shot_video_prompt(store, project_id: str, scene_id: str, shot_id: str) -> dict[str, Any]:
    """Return {prompt, base_prompt, negative_prompt, motion, context_used,
    missing, source_image}.

    ``source_image`` is the shot's selected generated image (``None`` when the
    shot has none — image-to-video requires one). Raises
    :class:`ShotLookupError` when the project, scene or shot is unknown.
    """
    image_ctx = build_shot_prompt(store, project_id, scene_id, shot_id)

    project = store.get(project_id)
    if project is None:
        raise ShotLookupError("project_not_found")
    scene = next((s for s in project.get("scenes", []) if s.get("id") == scene_id), None)
    if scene is None:
        raise ShotLookupError("scene_not_found")
    shot = next((s for s in scene.get("shots", []) if s.get("id") == shot_id), None)
    if shot is None:
        raise ShotLookupError("shot_not_found")

    params = shot.get("params") or {}
    missing = list(image_ctx["missing"])
    context_used = list(image_ctx["context_used"])
    prompt = image_ctx["prompt"]

    motion_parts: list[str] = []
    for key in ("camera_movement", "motion", "action"):
        value = " ".join(str(params.get(key) or "").split())
        if value:
            motion_parts.append(value[:MOTION_LIMIT].rstrip(", ;"))
            context_used.append(f"shot.params.{key}")
    motion = ", ".join(motion_parts)
    if motion:
        candidate = f"{prompt}, {motion}" if prompt else motion
        if len(candidate) <= TOTAL_LIMIT:
            prompt = candidate
        else:
            motion = ""
    else:
        missing.append("shot.params.motion")

    selected = next((img for img in shot.get("images", []) if img.get("selected")), None)
    source_image = None
    if selected:
        source_image = {
            "id": selected.get("id"),
            "job_id": selected.get("job_id"),
            "filename": selected.get("filename"),
        }
    else:
        missing.append("shot.selected_image")

    return {
        "prompt": prompt,
        "base_prompt": image_ctx["base_prompt"],
        "negative_prompt": image_ctx["negative_prompt"],
        "motion": motion,
        "context_used": context_used,
        "missing": missing,
        "source_image": source_image,
    }

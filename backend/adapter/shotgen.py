"""Shot-image prompt building (Phase 3A).

Deterministically assembles a text-to-image prompt for one storyboard shot
from Film Project context already stored in the FilmStore: Film Bible style
guide, character sheets whose names actually appear in the shot/scene text,
and scene title/bible refs. Nothing is invented: absent fields are reported
in ``missing`` and simply left out. Each source is clipped so a large bible
cannot flood the prompt, and the final prompt is capped.

The output of :func:`build_shot_prompt` is what the shot-generation endpoint
uses when the user has not supplied their own prompt, so user edits always
win over the assembled context.
"""
from __future__ import annotations

from typing import Any

from . import continuity

BASE_LIMIT = 1200
PART_LIMIT = 400
CHARACTER_LIMIT = 300
TOTAL_LIMIT = 4000


class ShotLookupError(LookupError):
    """Project, scene or shot id does not exist."""


def _clip(text: Any, limit: int) -> str:
    collapsed = " ".join(str(text or "").split())
    return collapsed[:limit].rstrip(", ;")


def build_shot_prompt(store, project_id: str, scene_id: str, shot_id: str) -> dict[str, Any]:
    """Return {prompt, base_prompt, negative_prompt, context_used, missing}.

    Raises :class:`ShotLookupError` when the project, scene or shot is unknown.
    """
    project = store.get(project_id)
    if project is None:
        raise ShotLookupError("project_not_found")
    scene = next((s for s in project.get("scenes", []) if s.get("id") == scene_id), None)
    if scene is None:
        raise ShotLookupError("scene_not_found")
    shot = next((s for s in scene.get("shots", []) if s.get("id") == shot_id), None)
    if shot is None:
        raise ShotLookupError("shot_not_found")

    bible = project.get("bible") or {}
    params = shot.get("params") or {}
    parts: list[str] = []
    context_used: list[str] = []
    missing: list[str] = []

    base = _clip(shot.get("prompt"), BASE_LIMIT)
    if not base:
        missing.append("shot.prompt")

    style = bible.get("style_guide") or bible.get("visual_style") or ""
    if style:
        parts.append(_clip(style, PART_LIMIT))
        context_used.append("bible.style_guide")
    else:
        missing.append("bible.style_guide")

    haystack = f"{base} {scene.get('bible_refs', '')}".lower()
    matched = []
    characters = bible.get("characters") or []
    for char in characters:
        if not isinstance(char, dict):
            continue
        name = str(char.get("name") or "").strip()
        if not name or name.lower() not in haystack:
            continue
        desc = ", ".join(
            filter(None, [str(char.get(k) or "").strip() for k in ("appearance", "description", "wardrobe")])
        )
        if desc:
            matched.append(f"{name}: {_clip(desc, CHARACTER_LIMIT)}")
    if matched:
        parts.extend(matched)
        context_used.append("bible.characters")
    elif not characters:
        missing.append("bible.characters")

    scene_title = _clip(scene.get("title"), PART_LIMIT)
    if scene_title:
        parts.append(f"Scene: {scene_title}")
        context_used.append("scene.title")
    scene_refs = _clip(scene.get("bible_refs"), PART_LIMIT)
    if scene_refs:
        parts.append(scene_refs)
        context_used.append("scene.bible_refs")
    else:
        missing.append("scene.bible_refs")

    # Phase 4: resolved continuity (film canon -> scene -> shot). Canon-backed
    # text only; the shot's own prompt stays first and is never overwritten.
    resolved = continuity.resolve_continuity(project, scene, shot)
    continuity_frags = continuity.continuity_parts(resolved)
    if continuity_frags:
        parts.extend(continuity_frags)
        context_used.append("continuity")
    for warning in resolved.get("warnings", []):
        missing.append(f"warning: {warning}")
    for entry in resolved.get("missing", []):
        if entry not in missing:
            missing.append(entry)

    prompt = base
    for part in parts:
        candidate = f"{prompt}, {part}" if prompt else part
        if len(candidate) > TOTAL_LIMIT:
            break
        prompt = candidate

    return {
        "prompt": prompt,
        "base_prompt": base,
        "negative_prompt": str(params.get("negative_prompt") or ""),
        "context_used": context_used,
        "missing": missing,
    }

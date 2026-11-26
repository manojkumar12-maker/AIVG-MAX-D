"""Audio Bible, voice identity and audio cues (Phase 5.2).

Data-model only: pure validation and normalisation for the audio fields stored
in the existing FilmStore project JSON. Nothing here talks to the GPU, calls a
provider or invents facts — malformed patches return ``None`` and the store
leaves the project untouched. No TTS, upload, playback or scheduling exists in
this phase.
"""
from __future__ import annotations

from typing import Any

from .continuity import FIELD_LIMIT, _sid

BIBLE_FIELDS = (
    "style_guide",
    "music_direction",
    "ambience_direction",
    "foley_direction",
    "mixing_notes",
)

VOICE_FIELDS = (
    "description",
    "language",
    "accent",
    "pitch_range",
    "texture",
    "pace",
    "consistency_notes",
)

CUE_CATEGORIES = ("dialogue", "ambience", "foley", "sfx", "music")
CUE_STATUSES = ("planned", "approved")
MAX_CUES = 200


# ---- empty shapes -----------------------------------------------------------

def empty_audio_bible() -> dict[str, Any]:
    """Default audio bible for projects created before this phase."""
    return {field: "" for field in BIBLE_FIELDS}


def empty_voice() -> dict[str, Any]:
    """Voice identity for one canon character; ``voice_id`` is optional and
    free-form — no provider or model is bound in this phase."""
    data = {field: "" for field in VOICE_FIELDS}
    data["voice_id"] = ""
    return data


def empty_cue() -> dict[str, Any]:
    return {
        "category": "",
        "description": "",
        "scene_id": "",
        "shot_id": "",
        "character_id": "",
        "notes": "",
        "status": "planned",
    }


# ---- validation / normalisation (edit path) ---------------------------------

def normalize_audio_bible(patch: Any) -> dict[str, Any] | None:
    """Validate an audio-bible patch; ``None`` when malformed."""
    if not isinstance(patch, dict):
        return None
    return {field: str(patch.get(field) or "").strip()[:FIELD_LIMIT]
            for field in BIBLE_FIELDS}


def normalize_voice(patch: Any) -> dict[str, Any] | None:
    """Validate a character voice-identity patch; ``None`` when malformed."""
    if not isinstance(patch, dict):
        return None
    data = empty_voice()
    data["voice_id"] = _sid(patch.get("voice_id"))
    for field in VOICE_FIELDS:
        data[field] = str(patch.get(field) or "").strip()[:FIELD_LIMIT]
    return data


def normalize_cue(patch: Any, *, partial: bool = False) -> dict[str, Any] | None:
    """Validate a cue create (full) or update (partial) patch.

    ``partial=True`` only normalises the fields present in the patch, so an
    update can never blank out fields the caller did not send.
    """
    if not isinstance(patch, dict):
        return None
    data: dict[str, Any] = {}
    if "category" in patch or not partial:
        category = _sid(patch.get("category"))
        if category not in CUE_CATEGORIES:
            return None
        data["category"] = category
    if "status" in patch or not partial:
        status = _sid(patch.get("status")) or "planned"
        if status not in CUE_STATUSES:
            return None
        data["status"] = status
    for field in ("description", "scene_id", "shot_id", "character_id", "notes"):
        if field in patch or not partial:
            data[field] = _sid(patch.get(field))
    return data

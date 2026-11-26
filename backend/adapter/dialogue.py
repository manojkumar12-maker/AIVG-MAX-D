"""Dialogue pipeline (Phase 5.3): extraction, validation, metadata.

Structured dialogue records sourced from the project's existing screenplay
artifact. Extraction is LLM-assisted (the screenplay schema carries no dialogue
fields) but strictly extraction-only: every extracted line is verified against
the source text and unverifiable lines are reported, never kept. No TTS, no
generation jobs, no paraphrasing — wording comes verbatim from the source.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any

EXTRACTION_STAGE = "dialogue_extract"

LINE_TYPES = ("dialogue", "voiceover")
EMOTIONS = ("", "neutral", "happy", "sad", "angry", "fearful", "surprised",
            "disgusted")
MAX_LINES = 300
MAX_TEXT = 2000

EXTRACTION_PROMPT = """STAGE: dialogue_extract
You are a Script Supervisor. Extract spoken dialogue from the screenplay below.

STRICT RULES:
- Extraction only. Copy spoken text VERBATIM from the screenplay scene text
  (summary, purpose or continuity notes). Never write, complete, correct or
  invent dialogue.
- Each line must quote text that literally appears in that scene's text.
- speaker_name must be the character name as written in the screenplay.
- line_type is "dialogue", or "voiceover" only when the text explicitly marks
  narration/voiceover.
- Leave delivery_note and emotion empty unless the text explicitly states them.
- If a scene has no spoken lines, extract nothing for it.

Return JSON exactly like:
{{"lines": [{{"scene_number": 1, "speaker_name": "MARA", "text": "We leave at dawn.", "line_type": "dialogue", "delivery_note": "", "emotion": ""}}]}}

Screenplay: {screenplay}"""


# ---- normalization helpers ---------------------------------------------------

def _norm(text: str) -> str:
    """Normalize for verbatim matching: unicode, case, whitespace, quotes."""
    text = unicodedata.normalize("NFKC", str(text)).lower()
    text = (text.replace("\u2018", "'").replace("\u2019", "'")
                .replace("\u201c", '"').replace("\u201d", '"'))
    return re.sub(r"\s+", " ", text).strip()


def stable_line_id(source_version: int, scene_number: Any, order: int,
                   text: str) -> str:
    """Deterministic id: same source, same line -> same id (idempotency)."""
    raw = f"{source_version}|{scene_number}|{order}|{_norm(text)}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


def emotion_ok(emotion: str) -> bool:
    if emotion in EMOTIONS:
        return True
    # "custom, if supported safely": a single short word, letters only.
    return bool(re.fullmatch(r"[a-zA-Z]{1,24}", emotion))


# ---- LLM output validation ---------------------------------------------------

def validate_extraction(data: Any) -> list[dict] | None:
    """Strict schema check of the extractor's JSON. None on any mismatch."""
    if not isinstance(data, dict) or not isinstance(data.get("lines"), list):
        return None
    out = []
    for i, line in enumerate(data["lines"]):
        if not isinstance(line, dict):
            return None
        scene_number = line.get("scene_number")
        speaker = str(line.get("speaker_name") or "").strip()
        text = str(line.get("text") or "").strip()
        line_type = str(line.get("line_type") or "dialogue").strip().lower()
        if not isinstance(scene_number, int) or not speaker or not text \
                or line_type not in LINE_TYPES or len(text) > MAX_TEXT:
            return None
        emotion = str(line.get("emotion") or "").strip().lower()
        if not emotion_ok(emotion):
            return None
        out.append({
            "scene_number": scene_number,
            "speaker_name": speaker,
            "text": text,
            "line_type": line_type,
            "delivery_note": str(line.get("delivery_note") or "").strip()[:200],
            "emotion": emotion,
        })
    if len(out) > MAX_LINES:
        return None
    return out


def scene_source_text(screenplay_scene: dict) -> str:
    """All free text of one screenplay scene, for verbatim verification."""
    return " ".join(str(screenplay_scene.get(k) or "")
                    for k in ("summary", "purpose", "continuity_notes"))


def verify_and_resolve(raw_lines: list[dict], screenplay: dict,
                       characters: list[dict]) -> tuple[list[dict], list[str]]:
    """Verify each line against the source and resolve speakers.

    Returns (verified_lines, reports). A line is kept only when its text
    appears verbatim in its own scene's source text; the speaker is resolved
    to a canon character id by exact (case-insensitive) name, else it stays
    unresolved and is reported. Nothing is ever invented here.
    """
    scenes = {sc.get("number"): sc
              for sc in (screenplay.get("scenes") or []) if isinstance(sc, dict)}
    canon = {str(c.get("name") or "").strip().lower(): c.get("id")
             for c in characters if isinstance(c, dict)}
    kept, reports = [], []
    for line in raw_lines:
        scene = scenes.get(line["scene_number"])
        if scene is None:
            reports.append(f"dropped: scene {line['scene_number']} not in screenplay")
            continue
        if _norm(line["text"]) not in _norm(scene_source_text(scene)):
            reports.append(f"dropped: '{line['text'][:60]}' not verbatim in scene "
                           f"{line['scene_number']}")
            continue
        character_id = canon.get(line["speaker_name"].lower())
        if character_id is None:
            reports.append(f"unresolved speaker: {line['speaker_name']}")
        kept.append({**line,
                     "character_id": character_id or "",
                     "speaker_resolved": character_id is not None})
    return kept, reports


def validate_for_approval(lines: list[dict]) -> list[str]:
    """Approval gate problems: unresolved scene or speaker references."""
    problems = []
    for line in lines:
        if not line.get("scene_id"):
            problems.append(f"line {line.get('id')}: scene reference unresolved")
        if not line.get("speaker_resolved"):
            problems.append(f"line {line.get('id')}: speaker "
                            f"'{line.get('speaker_name')}' unresolved")
        if not str(line.get("text") or "").strip():
            problems.append(f"line {line.get('id')}: empty dialogue text")
    return problems


def normalize_line_patch(patch: Any) -> dict[str, Any] | None:
    """Partial edit patch: text, delivery, emotion, notes only. None if bad."""
    if not isinstance(patch, dict):
        return None
    data: dict[str, Any] = {}
    for field in ("text", "delivery_note", "emotion", "notes"):
        if field in patch:
            value = str(patch[field] or "").strip()
            if field == "text" and (not value or len(value) > MAX_TEXT):
                return None
            if field == "emotion" and value and not emotion_ok(value):
                return None
            data[field] = value[:MAX_TEXT if field == "text" else 200]
    return data or None

"""Creative pipeline stages: concept, treatment, screenplay, scene breakdown,
storyboard.

Each stage is a pure function of the Film Project state: it builds a prompt
from the Film Bible and upstream artifacts, calls the configured LLM provider
for structured JSON, validates the shape, and returns data for FilmStore to
save as a new artifact version. No GPU and no image generation here — this is
creative planning only.
"""
from __future__ import annotations

import json
from typing import Any

from .films import FilmStore
from .llm import LLMError, LLMProvider

STAGES = ("concept", "treatment", "screenplay", "scene_breakdown", "storyboard")

# Upstream artifact each stage consumes, so prompts chain context.
_STAGE_INPUTS = {
    "concept": [],
    "treatment": ["concept"],
    "screenplay": ["treatment"],
    "scene_breakdown": ["screenplay"],
    "storyboard": ["screenplay", "scene_breakdown"],
}


class StageValidationError(LLMError):
    def __init__(self, problems: list[str]):
        super().__init__("llm_schema_mismatch",
                         "The generated " + " / ".join(problems[:3]) + ("..." if len(problems) > 3 else ""),
                         hint="The provider output did not match the stage schema. Retry or adjust the model.")


def _bible_context(bible: dict) -> str:
    return json.dumps(bible or {}, ensure_ascii=False)


def _upstream_context(store: FilmStore, project_id: str, kinds: list[str]) -> str:
    parts = []
    for kind in kinds:
        art = store.get_artifact(project_id, kind)
        if art and art.get("status") == "approved":
            parts.append(f"### {kind}\n{json.dumps(art['data'], ensure_ascii=False)}")
    return "\n\n".join(parts)


# ---- prompts ----------------------------------------------------------------
def _concept_prompt(bible: dict, brief: str) -> str:
    return f"""STAGE: concept
You are the Director of a film. Turn the Film Bible and brief into ONE creative concept.

Return JSON exactly like:
{{"title": "...", "logline": "...", "genre": "...", "tone": "...", "premise": "...", "visual_style": "...", "differentiators": ["..."], "risks": ["..."]}}

Film Bible: {_bible_context(bible)}
Brief: {brief or '(none given — invent from the Bible)'}"""


def _treatment_prompt(bible: dict, concept: dict, brief: str) -> str:
    return f"""STAGE: treatment
You are the Screenwriter. Expand the approved concept into a narrative treatment.

Return JSON exactly like:
{{"title": "...", "synopsis": "...", "themes": ["..."], "characters": [{{"name": "...", "description": "...", "arc": "..."}}], "acts": [{{"number": 1, "summary": "..."}}], "world_notes": "..."}}

Film Bible: {_bible_context(bible)}
Concept: {json.dumps(concept, ensure_ascii=False)}
Brief: {brief or '(none)'}"""


def _screenplay_prompt(bible: dict, treatment: dict, brief: str) -> str:
    return f"""STAGE: screenplay
You are the Screenwriter. Write a SHORT screenplay from the treatment.

Rules: preserve scene order; number scenes; use standard sluglines
("INT./EXT. LOCATION - TIME"); every scene must have action lines; keep the
characters' names and descriptions exactly as given in the treatment.

Return JSON exactly like:
{{"title": "...", "logline": "...", "scenes": [{{"number": 1, "slugline": "EXT. CITY STREET - NIGHT", "location": "City Street", "interior_exterior": "EXT", "time_of_day": "NIGHT", "summary": "...", "purpose": "...", "characters": ["..."], "mood": "...", "estimated_duration_seconds": 60, "story_beat": "...", "continuity_notes": []}}]}}

Film Bible: {_bible_context(bible)}
Treatment: {json.dumps(treatment, ensure_ascii=False)}
Brief: {brief or '(none)'}"""


def _breakdown_prompt(screenplay: dict) -> str:
    return f"""STAGE: scene_breakdown
You are the Script Supervisor. Break the screenplay into production scenes.

Rules: keep every screenplay scene (do not omit or merge silently); keep the
numbering; flag problems instead of inventing fixes; reference characters by
name as they appear in the screenplay.

Return JSON exactly like:
{{"scenes": [{{"number": 1, "slugline": "...", "location": "...", "characters": ["..."], "summary": "...", "props": ["..."], "wardrobe": ["..."], "shooting_notes": "...", "warnings": ["..."]}}]}}

Screenplay: {json.dumps(screenplay, ensure_ascii=False)}"""


def _storyboard_prompt(bible: dict, scene: dict, panel_count: int) -> str:
    return f"""STAGE: storyboard
You are the Cinematographer. Storyboard ONE scene into {panel_count} ordered panels.

Rules: use cinematic vocabulary with visual variety (do not repeat the same
framing); camera choices must serve the story; keep characters consistent
with the Film Bible descriptions; visual_prompt must be a self-contained
image-generation prompt including character appearance.

Return JSON exactly like:
{{"panels": [{{"shot_number": 1, "shot_size": "WIDE", "camera_angle": "EYE_LEVEL", "camera_movement": "STATIC", "subject": "...", "action": "...", "environment": "...", "composition": "...", "lighting": "...", "mood": "...", "visual_prompt": "...", "negative_prompt": "", "character_refs": ["..."], "continuity_notes": [], "duration_seconds": 4}}]}}

Film Bible: {_bible_context(bible)}
Scene: {json.dumps(scene, ensure_ascii=False)}"""


# ---- validators ---------------------------------------------------------------
def _require(cond: bool, problems: list[str], msg: str) -> None:
    if not cond:
        problems.append(msg)


def validate_concept(data: Any) -> dict:
    problems = []
    _require(isinstance(data, dict), problems, "concept must be a JSON object")
    if isinstance(data, dict):
        for key in ("title", "logline", "premise"):
            _require(isinstance(data.get(key), str) and data[key].strip(), problems, f"concept.{key} must be non-empty text")
    if problems:
        raise StageValidationError(problems)
    return data


def validate_treatment(data: Any) -> dict:
    problems = []
    _require(isinstance(data, dict), problems, "treatment must be a JSON object")
    if isinstance(data, dict):
        _require(isinstance(data.get("synopsis"), str) and data["synopsis"].strip(), problems, "treatment.synopsis must be non-empty text")
        _require(isinstance(data.get("characters"), list) and data["characters"], problems, "treatment.characters must be a non-empty list")
        _require(isinstance(data.get("acts"), list) and data["acts"], problems, "treatment.acts must be a non-empty list")
    if problems:
        raise StageValidationError(problems)
    return data


def validate_screenplay(data: Any) -> dict:
    problems = []
    _require(isinstance(data, dict), problems, "screenplay must be a JSON object")
    if isinstance(data, dict):
        scenes = data.get("scenes")
        _require(isinstance(scenes, list) and scenes, problems, "screenplay.scenes must be a non-empty list")
        if isinstance(scenes, list):
            numbers = []
            for i, sc in enumerate(scenes):
                if not isinstance(sc, dict):
                    problems.append(f"screenplay.scenes[{i}] must be an object")
                    continue
                slug = sc.get("slugline", "")
                _require(isinstance(slug, str) and slug.strip(), problems, f"screenplay.scenes[{i}].slugline missing")
                heading = slug.upper().replace("INT./EXT.", "").replace("INT./ EXT.", "")
                if isinstance(slug, str) and slug.strip() and (
                    not any(tag in heading.upper() for tag in ("INT", "EXT"))
                    or " - " not in slug.upper()
                ):
                    problems.append(f"screenplay.scenes[{i}].slugline is not a standard heading (INT/EXT - LOCATION - TIME)")
                _require(isinstance(sc.get("summary"), str) and sc["summary"].strip(), problems, f"screenplay.scenes[{i}].summary must be non-empty")
                numbers.append(sc.get("number"))
            clean = [n for n in numbers if isinstance(n, int)]
            _require(len(clean) == len(numbers) and clean == sorted(clean) and clean == list(range(1, len(clean) + 1)),
                     problems, "screenplay scene numbers must be 1..N in order")
    if problems:
        raise StageValidationError(problems)
    return data


def validate_breakdown(data: Any) -> dict:
    problems = []
    _require(isinstance(data, dict), problems, "scene_breakdown must be a JSON object")
    if isinstance(data, dict):
        scenes = data.get("scenes")
        _require(isinstance(scenes, list) and scenes, problems, "scene_breakdown.scenes must be a non-empty list")
        if isinstance(scenes, list):
            for i, sc in enumerate(scenes):
                if not isinstance(sc, dict):
                    problems.append(f"scene_breakdown.scenes[{i}] must be an object")
                    continue
                _require(isinstance(sc.get("summary"), str) and sc["summary"].strip(), problems, f"scene_breakdown.scenes[{i}].summary must be non-empty")
    if problems:
        raise StageValidationError(problems)
    return data


def validate_storyboard(data: Any) -> dict:
    problems = []
    _require(isinstance(data, dict), problems, "storyboard must be a JSON object")
    if isinstance(data, dict):
        panels = data.get("panels")
        _require(isinstance(panels, list) and panels, problems, "storyboard.panels must be a non-empty list")
        if isinstance(panels, list):
            numbers = []
            for i, p in enumerate(panels):
                if not isinstance(p, dict):
                    problems.append(f"storyboard.panels[{i}] must be an object")
                    continue
                _require(isinstance(p.get("visual_prompt"), str) and p["visual_prompt"].strip(), problems, f"storyboard.panels[{i}].visual_prompt must be non-empty")
                _require(isinstance(p.get("shot_size"), str) and p["shot_size"].strip(), problems, f"storyboard.panels[{i}].shot_size missing")
                numbers.append(p.get("shot_number"))
            clean = [n for n in numbers if isinstance(n, int)]
            _require(len(clean) == len(numbers) and clean == sorted(clean),
                     problems, "storyboard panel shot_numbers must be present and ordered")
    if problems:
        raise StageValidationError(problems)
    return data


_VALIDATORS = {
    "concept": validate_concept,
    "treatment": validate_treatment,
    "screenplay": validate_screenplay,
    "scene_breakdown": validate_breakdown,
    "storyboard": validate_storyboard,
}


# ---- runner -------------------------------------------------------------------
async def run_stage(store: FilmStore, provider: LLMProvider, project_id: str,
                    stage: str, *, brief: str = "", scene: dict | None = None,
                    panel_count: int = 6) -> dict:
    """Generate the next version of a stage artifact. Returns the saved entry."""
    if stage not in STAGES:
        raise LLMError("stage_unknown", f"Unknown stage '{stage}'.", hint=f"Use one of {', '.join(STAGES)}.")
    project = store.get(project_id)
    if project is None:
        raise LLMError("project_missing", "Film project not found.")
    if stage == "storyboard":
        if not scene:
            raise LLMError("scene_missing", "The storyboard stage needs a scene (scene id or dict).")

    if stage == "concept":
        prompt = _concept_prompt(project.get("bible", {}), brief)
    else:
        upstream: dict[str, Any] = {}
        for kind in _STAGE_INPUTS[stage]:
            art = store.get_artifact(project_id, kind)
            if art is None:
                raise LLMError("stage_dependency_missing",
                               f"The {stage} stage needs the {kind} artifact first.",
                               hint=f"Generate and approve {kind} before {stage}.")
            if art.get("status") != "approved":
                raise LLMError("stage_dependency_not_approved",
                               f"The {kind} artifact must be approved before {stage} can run.",
                               hint=f"Approve the {kind} artifact, then retry.")
            upstream[kind] = art["data"]
        if stage == "treatment":
            prompt = _treatment_prompt(project.get("bible", {}), upstream["concept"], brief)
        elif stage == "screenplay":
            prompt = _screenplay_prompt(project.get("bible", {}), upstream["treatment"], brief)
        elif stage == "scene_breakdown":
            prompt = _breakdown_prompt(upstream["screenplay"])
        else:
            prompt = _storyboard_prompt(project.get("bible", {}), scene, panel_count)

    result = await provider.complete_json(
        "You are part of a film pre-production pipeline. Output strict JSON only.",
        prompt,
    )
    data = _VALIDATORS[stage](result["json"])
    entry = store.add_version(project_id, stage, data, source="agent", usage=result.get("usage"))
    if entry is None:
        raise LLMError("artifact_locked",
                       f"The {stage} artifact is approved; unapprove it before regenerating.",
                       hint="Unapprove the artifact to allow a new version.")
    return entry

"""Visual continuity resolution (Phase 4).

Pure, deterministic resolver for film-level canon, scene overrides and shot
overrides. Nothing here talks to the GPU, mutates stored project data or
invents facts: absent fields are reported in ``missing``, contradictory or
unknown references in ``warnings``. All text is clipped so a large canon
cannot flood a prompt.

Precedence is explicit: Film canon → Scene override → Shot override. A more
specific level wins only where it is explicitly populated; empty overrides
inherit.
"""
from __future__ import annotations

from typing import Any

from .shotgen import CHARACTER_LIMIT, PART_LIMIT, _clip

FIELD_LIMIT = 200
MAX_LIST = 12


# ---- empty shapes -----------------------------------------------------------

def empty_continuity() -> dict[str, Any]:
    """Default, valid continuity for projects created before Phase 4."""
    return {
        "style": "",
        "characters": [],   # [{id, name, appearance, wardrobe_id}]
        "wardrobe": [],     # [{id, label, description}]
        "props": [],        # [{id, label, description}]
        "locations": [],    # [{id, label, description}]
    }


def empty_override() -> dict[str, Any]:
    return {
        "character_ids": [],
        "wardrobe": {},     # {character_id: wardrobe_id}
        "prop_ids": [],
        "location_id": "",
        "conditions": "",   # lighting / time / weather / atmosphere
        "blocking": "",
        "camera_direction": "",
        "action_state": "",
        "notes": "",
    }


# ---- validation / normalisation (edit path) ---------------------------------

def _sid(value: Any) -> str:
    return _clip(value, 64)


def normalize_film_continuity(patch: Any) -> dict[str, Any] | None:
    """Validate a film-level continuity patch; ``None`` when malformed."""
    if not isinstance(patch, dict):
        return None
    data = empty_continuity()
    data["style"] = _clip(patch.get("style"), PART_LIMIT)
    for key, fields in (
        ("characters", ("name", "appearance")),
        ("wardrobe", ("label", "description")),
        ("props", ("label", "description")),
        ("locations", ("label", "description")),
    ):
        items = patch.get(key)
        if items is None:
            continue
        if not isinstance(items, list) or len(items) > MAX_LIST:
            return None
        out = []
        for item in items:
            if not isinstance(item, dict):
                return None
            entry: dict[str, Any] = {"id": _sid(item.get("id")) or None}
            for field in fields:
                entry[field] = _clip(item.get(field), FIELD_LIMIT)
            if key == "characters":
                if not entry["name"]:
                    return None  # canonical characters need a stable name
                entry["wardrobe_id"] = _sid(item.get("wardrobe_id")) or ""
            elif not entry["label"]:
                return None
            out.append(entry)
        data[key] = out
    return data


def normalize_override(patch: Any) -> dict[str, Any] | None:
    """Validate a scene- or shot-level continuity override; ``None`` when malformed."""
    if not isinstance(patch, dict):
        return None
    data = empty_override()
    for key in ("character_ids", "prop_ids"):
        items = patch.get(key)
        if items is None:
            continue
        if not isinstance(items, list) or len(items) > MAX_LIST:
            return None
        data[key] = [_sid(v) for v in items if _sid(v)]
    ward = patch.get("wardrobe")
    if ward is not None:
        if not isinstance(ward, dict) or len(ward) > MAX_LIST:
            return None
        data["wardrobe"] = {_sid(k): _sid(v) for k, v in ward.items() if _sid(k) and _sid(v)}
    data["location_id"] = _sid(patch.get("location_id"))
    for key in ("conditions", "blocking", "camera_direction", "action_state", "notes"):
        data[key] = _clip(patch.get(key), FIELD_LIMIT)
    return data


# ---- resolution (read path) --------------------------------------------------

def _by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item.get("id")): item for item in items if item.get("id")}


def _relevant(item: dict[str, Any], haystack: str) -> bool:
    label = str(item.get("name") or item.get("label") or "").strip().lower()
    return bool(label) and label in haystack


def resolve_continuity(project: dict[str, Any], scene: dict[str, Any],
                       shot: dict[str, Any]) -> dict[str, Any]:
    """Return the structured continuity context for one shot.

    Shape: {style, characters, props, location, conditions, constraints,
    context_used, missing, warnings}. ``characters`` entries carry
    {name, appearance, wardrobe, source}; ``constraints`` merges shot blocking,
    camera direction, action state and notes.
    """
    bible = project.get("bible") or {}
    film_c = project.get("continuity") or empty_continuity()
    scene_o = {**empty_override(), **(scene.get("continuity") or {})}
    shot_o = {**empty_override(), **(shot.get("continuity") or {})}

    context_used: list[str] = []
    missing: list[str] = []
    warnings: list[str] = []

    # --- film style (bible stays canonical; continuity.style supplements) ----
    style = _clip(bible.get("style_guide") or bible.get("visual_style"), PART_LIMIT)
    if style:
        context_used.append("bible.style_guide")
    extra_style = _clip(film_c.get("style"), PART_LIMIT)
    if extra_style and extra_style.lower() != style.lower():
        style = f"{style}, {extra_style}" if style else extra_style
        context_used.append("continuity.style")
    # (no style at all is already reported above as bible.style_guide missing)

    # --- canon maps -----------------------------------------------------------
    ward_by_id = _by_id(film_c.get("wardrobe") or [])
    prop_by_id = _by_id(film_c.get("props") or [])
    loc_by_id = _by_id(film_c.get("locations") or [])
    char_by_id = _by_id(film_c.get("characters") or [])

    base = _clip(shot.get("prompt"), 1200)
    haystack = f"{base} {scene.get('bible_refs', '')} {scene.get('title', '')}".lower()

    # --- which characters are in this shot ------------------------------------
    override_char_ids = shot_o["character_ids"] or scene_o["character_ids"]
    if shot_o["character_ids"] and scene_o["character_ids"]:
        warnings.append("scene.character_ids overridden by shot")
    if shot_o["character_ids"]:
        level = "continuity.shot.characters"
    elif scene_o["character_ids"]:
        level = "continuity.scene.characters"
    else:
        level = "continuity.characters"
    unknown_chars = [cid for cid in override_char_ids if cid not in char_by_id]
    if unknown_chars:
        warnings.append(f"unknown character_ids: {', '.join(sorted(unknown_chars))}")
    selected_ids = [cid for cid in override_char_ids if cid in char_by_id]
    if not override_char_ids:
        # no override: canon characters whose name appears in the shot text
        selected_ids = [cid for cid, c in char_by_id.items() if _relevant(c, haystack)]

    characters = []
    for cid in selected_ids:
        canon = char_by_id[cid]
        name = str(canon.get("name") or "").strip()
        wid = shot_o["wardrobe"].get(cid) or scene_o["wardrobe"].get(cid) \
            or canon.get("wardrobe_id") or ""
        if shot_o["wardrobe"].get(cid) and scene_o["wardrobe"].get(cid) \
                and shot_o["wardrobe"][cid] != scene_o["wardrobe"][cid]:
            warnings.append(f"wardrobe conflict for {name}: scene overridden by shot")
        wardrobe_desc = ""
        if wid:
            if wid in ward_by_id:
                wardrobe_desc = _clip(ward_by_id[wid].get("description")
                                      or ward_by_id[wid].get("label"), CHARACTER_LIMIT)
            else:
                warnings.append(f"unknown wardrobe_id {wid} for {name}")
        desc = _clip(f"{canon.get('appearance') or ''} {wardrobe_desc}", CHARACTER_LIMIT)
        if desc:
            characters.append({"name": name, "appearance": desc,
                               "wardrobe": wardrobe_desc, "source": "continuity"})
    if characters:
        context_used.append(level)
    elif not (film_c.get("characters") or bible.get("characters")):
        pass  # no canon characters defined: optional, bible.characters handles this

    # --- props ----------------------------------------------------------------
    override_prop_ids = shot_o["prop_ids"] or scene_o["prop_ids"]
    if shot_o["prop_ids"] and scene_o["prop_ids"]:
        warnings.append("scene.prop_ids overridden by shot")

    def _prop_text(p: dict[str, Any]) -> str:
        return f"{_clip(p.get('label'), FIELD_LIMIT)}: " \
               f"{_clip(p.get('description'), CHARACTER_LIMIT)}".rstrip(": ")

    props: list[str] = []
    if override_prop_ids:
        for pid in override_prop_ids:
            if pid not in prop_by_id:
                warnings.append(f"unknown prop_ids: {pid}")
                continue
            props.append(_prop_text(prop_by_id[pid]))
    else:
        props = [_prop_text(p) for p in (film_c.get("props") or []) if _relevant(p, haystack)]
    if props:
        context_used.append("continuity.props")

    # --- location -------------------------------------------------------------
    loc_id = shot_o["location_id"] or scene_o["location_id"]
    if shot_o["location_id"] and scene_o["location_id"] \
            and shot_o["location_id"] != scene_o["location_id"]:
        warnings.append("scene.location_id overridden by shot")
    location = ""
    if loc_id:
        if loc_id in loc_by_id:
            loc = loc_by_id[loc_id]
            location = _prop_text(loc)
            context_used.append("continuity.location")
        else:
            warnings.append(f"unknown location_id: {loc_id}")
    elif not loc_by_id:
        pass  # no locations defined at all: optional, nothing to report

    # --- scene conditions and shot constraints --------------------------------
    conditions = _clip(scene_o["conditions"], PART_LIMIT)
    if conditions:
        context_used.append("continuity.scene.conditions")

    constraint_parts = []
    for key in ("blocking", "camera_direction", "action_state"):
        value = _clip(shot_o[key], FIELD_LIMIT)
        if value:
            constraint_parts.append(value)
            context_used.append(f"continuity.shot.{key}")
    notes = _clip(shot_o["notes"], FIELD_LIMIT)
    if notes:
        constraint_parts.append(notes)
        context_used.append("continuity.shot.notes")
    constraints = ", ".join(constraint_parts)

    return {
        "style": style,
        "characters": characters,
        "props": props,
        "location": location,
        "conditions": conditions,
        "constraints": constraints,
        "context_used": context_used,
        "missing": missing,
        "warnings": warnings,
    }


def continuity_parts(resolved: dict[str, Any]) -> list[str]:
    """Ordered prompt fragments from a resolved continuity context.

    Stable order: characters, props, location, conditions, constraints. Only
    non-empty, canon-backed text is returned — nothing is invented.
    """
    parts: list[str] = []
    for char in resolved.get("characters", []):
        parts.append(f"{char['name']}: {_clip(char['appearance'], CHARACTER_LIMIT)}")
    parts.extend(resolved.get("props", []))
    if resolved.get("location"):
        parts.append(f"Location: {resolved['location']}")
    if resolved.get("conditions"):
        parts.append(_clip(resolved["conditions"], PART_LIMIT))
    if resolved.get("constraints"):
        parts.append(_clip(resolved["constraints"], PART_LIMIT))
    return parts

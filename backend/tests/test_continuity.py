"""Phase 4: continuity resolver unit tests (pure module, no GPU, no HTTP)."""
from backend.adapter import continuity


def _project():
    return {
        "id": "p1",
        "bible": {
            "style_guide": "grainy 16mm film",
            "characters": [{"name": "Mara", "appearance": "tall, grey coat"}],
        },
        "continuity": {
            "style": "cold palette",
            "characters": [
                {"id": "c1", "name": "Mara", "appearance": "tall, red scarf", "wardrobe_id": "w1"},
                {"id": "c2", "name": "Ivo", "appearance": "short, beard"},
            ],
            "wardrobe": [{"id": "w1", "label": "rain coat", "description": "wet blue raincoat"}],
            "props": [{"id": "pr1", "label": "lantern", "description": "brass lantern"}],
            "locations": [{"id": "l1", "label": "pier", "description": "storm-lashed pier"}],
        },
    }


def _scene():
    return {"id": "s1", "title": "The Pier", "bible_refs": "Mara waits on the pier", "shots": []}


def _shot():
    return {"id": "sh1", "prompt": "Mara with a lantern"}


def test_shot_text_relevance_selects_characters_and_props():
    r = continuity.resolve_continuity(_project(), _scene(), _shot())
    names = [c["name"] for c in r["characters"]]
    assert names == ["Mara"]
    assert any(c["wardrobe"] == "wet blue raincoat" for c in r["characters"])
    assert any(p.startswith("lantern") for p in r["props"])
    assert "continuity.location" not in r["context_used"]


def test_shot_override_wins_over_scene_wins_over_film():
    project = _project()
    scene = _scene()
    scene["continuity"] = {"character_ids": ["c1", "c2"], "location_id": "l1",
                           "conditions": "dusk, heavy rain"}
    shot = _shot()
    shot["continuity"] = {"character_ids": ["c2"], "wardrobe": {"c2": "w1"}}
    r = continuity.resolve_continuity(project, scene, shot)
    assert [c["name"] for c in r["characters"]] == ["Ivo"]
    assert any(c["wardrobe"] == "wet blue raincoat" for c in r["characters"])
    assert r["location"].startswith("pier")
    assert r["conditions"] == "dusk, heavy rain"
    assert "continuity.shot.characters" in r["context_used"]


def test_unknown_ids_reported_never_invented():
    scene = _scene()
    scene["continuity"] = {"character_ids": ["cX"], "prop_ids": ["pX"], "location_id": "lX"}
    r = continuity.resolve_continuity(_project(), scene, _shot())
    assert r["characters"] == []
    assert any("unknown character_ids" in w for w in r["warnings"])
    assert any("unknown prop_ids" in w for w in r["warnings"])
    assert any("unknown location_id" in w for w in r["warnings"])


def test_conflicts_reported_shot_beats_scene():
    scene = _scene()
    scene["continuity"] = {"character_ids": ["c1"], "location_id": "l1",
                           "wardrobe": {"c1": "w1"}}
    shot = _shot()
    shot["continuity"] = {"character_ids": ["c2"], "location_id": "l1",
                          "wardrobe": {"c1": "w1"}}
    r = continuity.resolve_continuity(_project(), scene, shot)
    assert any("overridden by shot" in w for w in r["warnings"])


def test_empty_overrides_inherit_no_warnings():
    r = continuity.resolve_continuity(_project(), _scene(), _shot())
    # optional fields never populated are simply absent, not "missing" noise
    assert "warnings" in r and not r["warnings"]
    assert "continuity.scene.conditions" not in r["context_used"]
    assert not r["warnings"]


def test_bible_canon_not_duplicated_style_merged():
    r = continuity.resolve_continuity(_project(), _scene(), _shot())
    assert r["style"].startswith("grainy 16mm film")
    assert "cold palette" in r["style"]


def test_deterministic_and_stable_ordering():
    scene = _scene()
    scene["continuity"] = {"character_ids": ["c1", "c2"], "prop_ids": ["pr1"],
                           "location_id": "l1", "conditions": "dusk",
                           "blocking": "close on hands"}
    a = continuity.resolve_continuity(_project(), scene, _shot())
    b = continuity.resolve_continuity(_project(), scene, _shot())
    assert a == b
    order = continuity.continuity_parts(a)
    assert order[0].startswith("Mara") and order[1].startswith("Ivo")
    assert any(p.startswith("Location:") for p in order)


def test_no_source_mutation():
    project, scene, shot = _project(), _scene(), _shot()
    scene["continuity"] = {"character_ids": ["c1"], "wardrobe": {"c1": "wX"}}
    snapshot = json_roundtrip(project)
    continuity.resolve_continuity(project, scene, shot)
    assert json_roundtrip(project) == snapshot


def test_normalization_bounds_and_rejects():
    ok = continuity.normalize_film_continuity({"characters": [{"name": "A"}]})
    assert ok["characters"][0]["name"] == "A"
    assert continuity.normalize_film_continuity({"characters": [{"name": ""}]}) is None
    assert continuity.normalize_film_continuity({"props": "nope"}) is None
    assert continuity.normalize_film_continuity({"style": "x" * 5000})["style"] \
        == "x" * continuity.PART_LIMIT
    assert continuity.normalize_override({"character_ids": ["a", ""]})["character_ids"] == ["a"]
    assert continuity.normalize_override({"conditions": "y" * 5000})["conditions"] \
        == "y" * continuity.FIELD_LIMIT


def json_roundtrip(obj):
    import json
    return json.loads(json.dumps(obj, sort_keys=True))

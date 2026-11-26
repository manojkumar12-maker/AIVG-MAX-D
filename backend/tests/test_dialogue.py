"""Phase 5.3 tests: dialogue pipeline (extraction, verification, versioning)."""
import importlib
import json

import pytest
from fastapi.testclient import TestClient

from backend.adapter import dialogue as dialogue_mod
from backend.adapter import films as films_mod


@pytest.fixture()
def store(tmp_path):
    return films_mod.FilmStore(root=tmp_path / "films")


def make_screenplay(store, pid):
    """Approved screenplay artifact whose summaries contain verbatim quotes."""
    data = {
        "title": "T", "logline": "L",
        "scenes": [
            {"number": 1, "slugline": "INT. HUT - NIGHT", "location": "Hut",
             "interior_exterior": "INT", "time_of_day": "NIGHT",
             "summary": 'Mara says: "We leave at dawn." Ben looks away.',
             "purpose": "setup", "characters": ["Mara", "Ben"], "mood": "tense",
             "estimated_duration_seconds": 30, "story_beat": "a",
             "continuity_notes": ""},
            {"number": 2, "slugline": "EXT. DOCK - DAY", "location": "Dock",
             "interior_exterior": "EXT", "time_of_day": "DAY",
             "summary": "They walk. Nobody speaks.",
             "purpose": "bridge", "characters": ["Mara"], "mood": "calm",
             "estimated_duration_seconds": 20, "story_beat": "b",
             "continuity_notes": "V.O.: 'Rain again.'"},
        ],
    }
    store.add_version(pid, "screenplay", data)
    store.set_artifact_status(pid, "screenplay", "approved")
    return data


def make_breakdown(store, pid):
    """Approved scene_breakdown + applied scenes, so scene numbers link."""
    store.add_version(pid, "scene_breakdown", {
        "scenes": [{"number": 1, "slugline": "INT. HUT - NIGHT", "location": "Hut",
                    "characters": ["Mara", "Ben"], "summary": "setup",
                    "props": [], "wardrobe": [], "shooting_notes": "",
                    "warnings": []},
                   {"number": 2, "slugline": "EXT. DOCK - DAY", "location": "Dock",
                    "characters": ["Mara"], "summary": "bridge",
                    "props": [], "wardrobe": [], "shooting_notes": "",
                    "warnings": []}]})
    store.set_artifact_status(pid, "scene_breakdown", "approved")
    assert store.apply_breakdown(pid) is not None


def make_canon(store, pid):
    store.update_film_continuity(pid, {
        "characters": [
            {"id": "mara", "name": "Mara", "appearance": "grey coat"},
            {"id": "ben", "name": "Ben", "appearance": "young"},
        ]})


@pytest.fixture()
def project(store):
    p = store.create("Dialogue film")
    make_screenplay(store, p["id"])
    make_breakdown(store, p["id"])
    make_canon(store, p["id"])
    return p["id"]


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("OGAI_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("OGAI_SESSION_TOKEN", "testtoken")
    monkeypatch.setenv("OGAI_RATE_LIMIT", "1000/60")
    monkeypatch.setenv("OGAI_LLM_PROVIDER", "mock")
    from backend.adapter import config, llm, main
    importlib.reload(config)
    importlib.reload(main)
    llm.reset_provider()
    yield TestClient(main.app)
    llm.reset_provider()


def H():
    return {"X-Session-Token": "testtoken"}


# ---- pure functions ------------------------------------------------------------

def test_stable_line_id_is_deterministic_and_case_insensitive():
    a = dialogue_mod.stable_line_id(2, 1, 0, "We  LEAVE at dawn.")
    b = dialogue_mod.stable_line_id(2, 1, 0, "we leave at dawn.")
    c = dialogue_mod.stable_line_id(3, 1, 0, "we leave at dawn.")
    assert a == b and a != c


def test_validate_extraction_rejects_malformed():
    good = {"lines": [{"scene_number": 1, "speaker_name": "MARA",
                       "text": "hi", "line_type": "dialogue",
                       "delivery_note": "", "emotion": ""}]}
    assert dialogue_mod.validate_extraction(good) is not None
    assert dialogue_mod.validate_extraction({"lines": "nope"}) is None
    assert dialogue_mod.validate_extraction("x") is None
    assert dialogue_mod.validate_extraction({"lines": [{"scene_number": "1",
                                                        "speaker_name": "A",
                                                        "text": "t"}]}) is None
    assert dialogue_mod.validate_extraction({"lines": [{"scene_number": 1,
                                                        "speaker_name": "A",
                                                        "text": "t",
                                                        "line_type": "song"}]}) is None
    assert dialogue_mod.validate_extraction({"lines": [{"scene_number": 1,
                                                        "speaker_name": "A",
                                                        "text": "t",
                                                        "emotion": "not a word 42"}]}) is None


def test_verify_drops_unverifiable_and_resolves_speakers():
    screenplay = {"scenes": [{"number": 1, "summary": 'Mara: "We leave at dawn."',
                              "purpose": "", "continuity_notes": ""}]}
    raw = [
        {"scene_number": 1, "speaker_name": "mara", "text": "We leave at dawn.",
         "line_type": "dialogue", "delivery_note": "", "emotion": ""},
        {"scene_number": 1, "speaker_name": "Mara", "text": "Invented line",
         "line_type": "dialogue", "delivery_note": "", "emotion": ""},
        {"scene_number": 9, "speaker_name": "Mara", "text": "We leave at dawn.",
         "line_type": "dialogue", "delivery_note": "", "emotion": ""},
    ]
    kept, reports = dialogue_mod.verify_and_resolve(raw, screenplay,
                                                    [{"id": "mara", "name": "Mara"}])
    assert len(kept) == 1 and kept[0]["character_id"] == "mara"
    assert kept[0]["speaker_resolved"] is True
    assert len(reports) == 2
    assert any("not verbatim" in r for r in reports)
    assert any("scene 9" in r for r in reports)


def test_approval_gate_and_patch_rules():
    lines = [{"id": "a", "scene_id": "", "speaker_resolved": True, "text": "x",
              "speaker_name": "Mara"}]
    problems = dialogue_mod.validate_for_approval(lines)
    assert any("scene reference" in p for p in problems)
    assert dialogue_mod.normalize_line_patch({"text": "  reworded  "}) == {
        "text": "reworded"}
    assert dialogue_mod.normalize_line_patch({"emotion": "grim"}) == {"emotion": "grim"}
    assert dialogue_mod.normalize_line_patch({"emotion": "grim, loud"}) is None
    assert dialogue_mod.normalize_line_patch({"text": ""}) is None
    assert dialogue_mod.normalize_line_patch({"nope": 1}) is None


# ---- store -----------------------------------------------------------------------

def test_replace_dialogue_maps_scene_and_is_idempotent(store, project):
    sp = films_mod.FilmStore.get_artifact(store, project, "screenplay")
    raw = [{"scene_number": 1, "speaker_name": "Mara", "text": "We leave at dawn.",
            "line_type": "dialogue", "delivery_note": "", "emotion": ""}]
    verified, _ = dialogue_mod.verify_and_resolve(raw, sp["data"],
                                                  [{"id": "mara", "name": "Mara"}])
    entry = store.replace_dialogue(project, sp["version"], verified)

    again = store.replace_dialogue(project, sp["version"], verified)
    assert again["version"] == entry["version"], "idempotent re-run: no new version"
    project_data = store.get(project)
    assert len(project_data["artifacts"]["dialogue"]["versions"]) == 1


def test_replace_dialogue_never_touches_approved(store, project):
    sp = films_mod.FilmStore.get_artifact(store, project, "screenplay")
    verified, _ = dialogue_mod.verify_and_resolve(
        [{"scene_number": 1, "speaker_name": "Mara", "text": "We leave at dawn.",
          "line_type": "dialogue", "delivery_note": "", "emotion": ""}],
        sp["data"], [{"id": "mara", "name": "Mara"}])
    store.replace_dialogue(project, sp["version"], verified)
    store.set_artifact_status(project, "dialogue", "approved")
    more = verified + [dict(verified[0], text="We leave at dawn.",
                            speaker_name="Ben")]
    assert store.replace_dialogue(project, sp["version"], more) is None


def test_update_dialogue_line_partial(store, project):
    sp = films_mod.FilmStore.get_artifact(store, project, "screenplay")
    entry = store.replace_dialogue(project, sp["version"], [])
    line_id = entry["data"]["lines"][0]["id"] if entry["data"]["lines"] else None
    # seed one line directly for the edit test
    entry = store.replace_dialogue(project, sp["version"], [
        {"scene_number": 1, "speaker_name": "Mara", "text": "We leave at dawn.",
         "line_type": "dialogue", "delivery_note": "", "emotion": "neutral"}])
    line_id = entry["data"]["lines"][0]["id"]
    updated = store.update_dialogue_line(project, line_id, {"emotion": "grim"})
    assert updated["emotion"] == "grim"
    assert updated["text"] == "We leave at dawn."  # partial: text preserved
    assert updated["id"] == line_id
    assert store.update_dialogue_line(project, "zzz", {"emotion": "sad"}) is None


def test_voiceover_allowed_from_continuity_notes(store, project):
    sp = films_mod.FilmStore.get_artifact(store, project, "screenplay")
    verified, _ = dialogue_mod.verify_and_resolve(
        [{"scene_number": 2, "speaker_name": "Mara", "text": "Rain again.",
          "line_type": "voiceover", "delivery_note": "", "emotion": ""}],
        sp["data"], [{"id": "mara", "name": "Mara"}])
    assert len(verified) == 1 and verified[0]["line_type"] == "voiceover"


# ---- API ------------------------------------------------------------------------

def test_dialogue_api_requires_approved_screenplay(client):
    pid = client.post("/api/films", json={"title": "No sp"}, headers=H()).json()["id"]
    r = client.post(f"/api/films/{pid}/dialogue/extract", headers=H())
    detail = str(r.json()["detail"])
    assert r.status_code == 409 and "approved screenplay" in detail


def test_dialogue_api_extract_get_edit_approve(client, monkeypatch):
    from backend.adapter import llm, main
    pid = client.post("/api/films", json={"title": "Api"}, headers=H()).json()["id"]
    store = main.films
    make_screenplay(store, pid)
    make_breakdown(store, pid)
    make_canon(store, pid)

    class FakeProvider:
        name = "fake"

        async def complete(self, system, prompt, **kw):
            text = 'Mara says: "We leave at dawn." Ben looks away.'
            payload = {"lines": [
                {"scene_number": 1, "speaker_name": "Mara",
                 "text": "We leave at dawn.", "line_type": "dialogue",
                 "delivery_note": "", "emotion": ""},
                {"scene_number": 1, "speaker_name": "Mara",
                 "text": "Totally invented", "line_type": "dialogue",
                 "delivery_note": "", "emotion": ""}]}
            return {"text": json.dumps(payload), "usage": {}}

    from backend.adapter import llm
    monkeypatch.setattr(main, "get_provider", lambda: FakeProvider())

    r = client.post(f"/api/films/{pid}/dialogue/extract", headers=H())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["extracted"] == 1 and body["submitted"] == 2
    assert any("not verbatim" in rep for rep in body["reports"])
    line = body["lines"][0]
    assert line["speaker_resolved"] is True and line["character_id"] == "mara"

    assert client.get(f"/api/films/{pid}/dialogue", headers=H()).json()["lines"][0]["id"] == line["id"]
    assert client.get(f"/api/films/{pid}/dialogue").status_code == 401

    # repeated extraction is idempotent: same source + same lines -> no new version
    r = client.post(f"/api/films/{pid}/dialogue/extract", headers=H())
    assert r.status_code == 200
    versions_after_repeat = len(main.films.get(pid)["artifacts"]["dialogue"]["versions"])
    assert versions_after_repeat == 1

    r = client.put(f"/api/films/{pid}/dialogue/lines/{line['id']}",
                   headers=H(), json={"emotion": "grim"})
    assert r.status_code == 200 and r.json()["line"]["emotion"] == "grim"

    # approval gate passes now (scene + speaker resolved)
    r = client.post(f"/api/films/{pid}/artifacts/dialogue/approve", headers=H())
    assert r.status_code == 200, r.text
    # approved -> line edits locked, re-extract refused
    assert client.put(f"/api/films/{pid}/dialogue/lines/{line['id']}",
                      headers=H(), json={"emotion": "sad"}).status_code == 409
    assert client.post(f"/api/films/{pid}/dialogue/extract",
                       headers=H()).status_code == 409


def test_dialogue_approve_blocked_on_unresolved_references(client, monkeypatch):
    from backend.adapter import llm, main
    pid = client.post("/api/films", json={"title": "Gate"}, headers=H()).json()["id"]
    store = main.films
    make_screenplay(store, pid)  # no continuity canon -> speaker unresolved
    make_breakdown(store, pid)

    class FakeProvider:
        name = "fake"

        async def complete(self, system, prompt, **kw):
            payload = {"lines": [{"scene_number": 1, "speaker_name": "Ghost",
                                  "text": "We leave at dawn.",
                                  "line_type": "dialogue", "delivery_note": "",
                                  "emotion": ""}]}
            return {"text": json.dumps(payload), "usage": {}}

    from backend.adapter import llm
    monkeypatch.setattr(main, "get_provider", lambda: FakeProvider())
    r = client.post(f"/api/films/{pid}/dialogue/extract", headers=H())
    assert r.status_code == 200
    r = client.post(f"/api/films/{pid}/artifacts/dialogue/approve", headers=H())
    assert r.status_code == 422
    body = r.json()
    problems = body.get("problems") or [str(body.get("detail") or body)]
    assert any("unresolved" in str(p) for p in problems)


def test_dialogue_api_malformed_llm_output_rejected(client, monkeypatch):
    from backend.adapter import llm, main
    pid = client.post("/api/films", json={"title": "Bad"}, headers=H()).json()["id"]
    store = main.films
    make_screenplay(store, pid)
    make_breakdown(store, pid)

    class BadProvider:
        name = "bad"

        async def complete(self, system, prompt, **kw):
            return {"text": "not json at all", "usage": {}}

    from backend.adapter import llm
    monkeypatch.setattr(llm, "get_provider", lambda: BadProvider())
    r = client.post(f"/api/films/{pid}/dialogue/extract", headers=H())
    assert r.status_code == 502
    assert "nothing was stored" in str(r.json()["detail"])
    assert client.get(f"/api/films/{pid}/dialogue", headers=H()).json()["lines"] == []

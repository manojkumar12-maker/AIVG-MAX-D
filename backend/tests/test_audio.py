"""Phase 5.2 tests: audio bible, voice identity and audio cues (data model only)."""
import pytest
from fastapi.testclient import TestClient

from backend.adapter import films as films_mod


@pytest.fixture()
def store(tmp_path):
    return films_mod.FilmStore(root=tmp_path / "films")


@pytest.fixture()
def project_with_canon(store):
    """Project with one scene, one shot and one canon character with a stable id."""
    p = store.create("Audio film")
    scene = store.add_scene(p["id"], "One")
    shot = store.add_shot(p["id"], scene["id"], "Wide establishing shot")
    r = store.update_film_continuity(p["id"], {
        "characters": [{"id": "mara", "name": "Mara", "appearance": "tall, grey coat"}],
    })
    assert r is not None
    return p["id"], scene["id"], shot["id"]


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("OGAI_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("OGAI_SESSION_TOKEN", "testtoken")
    monkeypatch.setenv("OGAI_RATE_LIMIT", "1000/60")
    monkeypatch.setenv("OGAI_LLM_PROVIDER", "mock")
    from backend.adapter import config, llm, main
    import importlib
    importlib.reload(config)
    importlib.reload(main)
    llm.reset_provider()
    yield TestClient(main.app)
    llm.reset_provider()


def H():
    return {"X-Session-Token": "testtoken"}


# ---- audio bible -------------------------------------------------------------

def test_audio_bible_roundtrip(store):
    p = store.create("Bible film")
    bible = store.get_audio(p["id"])["bible"]
    assert set(bible) == {"style_guide", "music_direction", "ambience_direction",
                          "foley_direction", "mixing_notes"}
    updated = store.update_audio_bible(p["id"], {"style_guide": "Warm analog score"})
    assert updated["style_guide"] == "Warm analog score"
    assert store.get_audio(p["id"])["bible"]["style_guide"] == "Warm analog score"


def test_audio_bible_edit_only(store):
    """Updating the bible never touches scenes, generations or other data."""
    p = store.create("Safe film")
    scene = store.add_scene(p["id"], "One")
    store.update_audio_bible(p["id"], {"style_guide": "x"})
    project = store.get(p["id"])
    assert [s["id"] for s in project["scenes"]] == [scene["id"]]
    assert project["audio"]["bible"]["music_direction"] == ""


def test_audio_bible_rejects_malformed(store):
    p = store.create("Bad film")
    assert store.update_audio_bible(p["id"], "not a dict") is None
    before = store.get_audio(p["id"])
    after = store.get_audio(p["id"])
    assert before == after
    assert store.update_audio_bible("missing", {}) is None


# ---- voice identity ----------------------------------------------------------

def test_voice_identity_on_canon_character(store, project_with_canon):
    pid, scene_id, shot_id = project_with_canon
    assert store.get_character_voice(pid, "mara") == {
        "voice_id": "", "description": "", "language": "", "accent": "",
        "pitch_range": "", "texture": "", "pace": "", "consistency_notes": "",
    }
    updated = store.update_character_voice(pid, "mara", {
        "voice_id": "vp-77", "description": "low, gravelly", "pace": "slow",
    })
    assert updated["voice_id"] == "vp-77"
    assert store.get_character_voice(pid, "mara")["pace"] == "slow"


def test_voice_update_preserves_visual_fields(store, project_with_canon):
    pid, _, _ = project_with_canon
    assert store.update_character_voice(pid, "mara", {"texture": "smoky"}) is not None
    character = next(c for c in store.get_continuity(pid)["characters"] if c["id"] == "mara")
    assert character["appearance"] == "tall, grey coat"
    assert character["voice"]["texture"] == "smoky"


def test_voice_unknown_character_rejected(store, project_with_canon):
    pid, _, _ = project_with_canon
    assert store.get_character_voice(pid, "ghost") is None
    assert store.update_character_voice(pid, "ghost", {"texture": "x"}) is None
    assert store.update_character_voice(pid, "mara", 42) is None


# ---- cues ---------------------------------------------------------------------

def test_cue_add_update_flow(store, project_with_canon):
    pid, scene_id, shot_id = project_with_canon
    cue = store.add_cue(pid, {
        "category": "dialogue", "description": "Mara: 'We leave at dawn.'",
        "scene_id": scene_id, "shot_id": shot_id, "character_id": "mara",
    })
    assert cue["id"] and cue["status"] == "planned"
    cues = store.get_audio(pid)["cues"]
    assert len(cues) == 1 and cues[0]["id"] == cue["id"]

    updated = store.update_cue(pid, cue["id"], {"status": "approved"})
    assert updated["status"] == "approved"
    # partial update: unsent fields keep their values
    assert updated["description"] == cue["description"]
    assert updated["id"] == cue["id"]


def test_cue_unknown_references_rejected(store, project_with_canon):
    pid, scene_id, _ = project_with_canon
    assert store.add_cue(pid, {"category": "sfx", "description": "x",
                               "scene_id": "nope"}) is None
    assert store.add_cue(pid, {"category": "sfx", "description": "x",
                               "character_id": "ghost"}) is None
    cue = store.add_cue(pid, {"category": "sfx", "description": "rain"})
    assert cue is not None
    assert store.update_cue(pid, cue["id"], {"shot_id": "nope"}) is None
    assert store.update_cue(pid, "missing", {"status": "approved"}) is None


def test_cue_invalid_category_and_status(store, project_with_canon):
    pid, _, _ = project_with_canon
    assert store.add_cue(pid, {"category": "explosion", "description": "x"}) is None
    cue = store.add_cue(pid, {"category": "music", "description": "theme"})
    assert store.update_cue(pid, cue["id"], {"status": "mastered"}) is None
    # partial update never blanks unsent fields even after a rejected patch
    assert store.get_audio(pid)["cues"][0]["description"] == "theme"


# ---- API ----------------------------------------------------------------------

def test_audio_api_roundtrip(client):
    pid = client.post("/api/films", json={"title": "Api film"}, headers=H()).json()["id"]
    assert client.get(f"/api/films/{pid}/audio", headers=H()).status_code == 200
    assert client.get(f"/api/films/{pid}/audio").status_code == 401

    r = client.put(f"/api/films/{pid}/audio/bible", headers=H(),
                   json={"style_guide": "No music before act two"})
    assert r.status_code == 200 and r.json()["bible"]["style_guide"].startswith("No music")

    assert client.get(f"/api/films/{pid}/audio/cues", headers=H()).json()["cues"] == []
    r = client.post(f"/api/films/{pid}/audio/cues", headers=H(),
                    json={"category": "ambience", "description": "harbour gulls"})
    assert r.status_code == 200 and r.json()["cue"]["id"]
    cue_id = r.json()["cue"]["id"]

    r = client.put(f"/api/films/{pid}/audio/cues/{cue_id}", headers=H(),
                   json={"status": "approved"})
    assert r.status_code == 200 and r.json()["cue"]["status"] == "approved"

    assert client.put(f"/api/films/{pid}/audio/bible", headers=H(),
                      json=["bad"]).status_code == 422
    assert client.post(f"/api/films/{pid}/audio/cues", headers=H(),
                       json={"category": "nope"}).status_code == 422
    assert client.put(f"/api/films/{pid}/audio/cues/zzz", headers=H(),
                      json={"status": "approved"}).status_code == 422
    assert client.get("/api/films/missing/audio", headers=H()).status_code == 404


def test_voice_api_roundtrip(client):
    pid = client.post("/api/films", json={"title": "Voice film"}, headers=H()).json()["id"]
    r = client.put(f"/api/films/{pid}/continuity", headers=H(),
                   json={"characters": [{"id": "mara", "name": "Mara", "appearance": "tall"}]})
    assert r.status_code == 200, r.text

    r = client.put(f"/api/films/{pid}/characters/mara/voice", headers=H(),
                   json={"description": "low and steady", "voice_id": "vp-1"})
    assert r.status_code == 200 and r.json()["voice"]["voice_id"] == "vp-1"
    assert client.get(f"/api/films/{pid}/characters/mara/voice",
                      headers=H()).json()["voice"]["description"] == "low and steady"

    # character's visual canon untouched
    chars = client.get(f"/api/films/{pid}/continuity", headers=H()).json()["continuity"]["characters"]
    assert chars[0]["appearance"] == "tall"

    assert client.get(f"/api/films/{pid}/characters/ghost/voice",
                      headers=H()).status_code == 404
    assert client.put(f"/api/films/{pid}/characters/ghost/voice", headers=H(),
                      json={"texture": "x"}).status_code == 404
    assert client.get("/api/films/missing/characters/mara/voice",
                      headers=H()).status_code == 404

"""Phase 1 tests: Film Project data model and project API."""
import json
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from backend.adapter import films as films_mod


@pytest.fixture()
def store(tmp_path):
    return films_mod.FilmStore(root=tmp_path / "films")


def test_create_get_update_delete(store):
    p = store.create("  My Film  ")
    assert p["title"] == "My Film" and p["id"]
    assert store.get(p["id"])["title"] == "My Film"
    assert store.list()[0]["id"] == p["id"]

    updated = store.update(p["id"], {"title": "Renamed", "bible": {"logline": "A story"}})
    assert updated["title"] == "Renamed"
    assert updated["bible"]["logline"] == "A story"
    assert updated["bible"]["style_guide"] == ""  # existing bible keys preserved

    assert store.delete(p["id"]) is True
    assert store.get(p["id"]) is None
    assert store.list() == []
    assert store.delete(p["id"]) is False


def test_scenes_reorder_on_delete(store):
    p = store.create("Scenes film")
    s1 = store.add_scene(p["id"], "One")
    s2 = store.add_scene(p["id"], "Two")
    s3 = store.add_scene(p["id"], "Three")
    assert [s["order"] for s in store.get(p["id"])["scenes"]] == [0, 1, 2]
    assert store.delete_scene(p["id"], s2["id"]) is True
    scenes = store.get(p["id"])["scenes"]
    assert [s["id"] for s in scenes] == [s1["id"], s3["id"]]
    assert [s["order"] for s in scenes] == [0, 1]
    assert store.delete_scene(p["id"], "missing") is False


def test_shot_status_gate(store):
    p = store.create("Shots film")
    scene = store.add_scene(p["id"], "Scene")
    shot = store.add_shot(p["id"], scene["id"], "a wide shot", model="pony")
    assert shot["status"] == "draft"

    got = store.set_shot_status(p["id"], scene["id"], shot["id"], "approved", approved_by="human")
    assert got["status"] == "approved" and got["approved_by"] == "human"

    # invalid status is rejected, not stored
    assert store.set_shot_status(p["id"], scene["id"], shot["id"], "bogus") is None
    assert store.get(p["id"])["scenes"][0]["shots"][0]["status"] == "approved"

    # unknown scene/shot/project return None
    assert store.add_shot(p["id"], "nope", "x") is None
    assert store.set_shot_status(p["id"], scene["id"], "nope", "approved") is None
    assert store.set_shot_status("nope", scene["id"], shot["id"], "approved") is None


def test_summary_counts(store):
    p = store.create("Summary film")
    scene = store.add_scene(p["id"], "S")
    store.add_shot(p["id"], scene["id"], "one")
    shot2 = store.add_shot(p["id"], scene["id"], "two")
    store.set_shot_status(p["id"], scene["id"], shot2["id"], "approved", approved_by="me")
    summary = store.list()[0]
    assert summary["scene_count"] == 1 and summary["shot_count"] == 2
    assert summary["approved_shots"] == 1


# ---- API -------------------------------------------------------------------
@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("OGAI_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("OGAI_SESSION_TOKEN", "testtoken")
    monkeypatch.setenv("OGAI_RATE_LIMIT", "1000/60")
    from backend.adapter import config, main
    import importlib
    importlib.reload(config)
    importlib.reload(main)
    return TestClient(main.app)


def test_film_api_end_to_end(client):
    r = client.get("/api/films", headers={"X-Session-Token": "testtoken"})
    assert r.status_code == 200 and r.json() == {"projects": []}

    r = client.post("/api/films", json={"title": "Test Film"}, headers={"X-Session-Token": "testtoken"})
    assert r.status_code == 200
    pid = r.json()["id"]
    assert r.json()["title"] == "Test Film"

    # auth required
    assert client.get("/api/films").status_code == 401

    # scenes and shots
    r = client.post(f"/api/films/{pid}/scenes", json={"title": "Scene 1"}, headers={"X-Session-Token": "testtoken"})
    sid = r.json()["id"]
    r = client.post(f"/api/films/{pid}/scenes/{sid}/shots", json={"prompt": "shot prompt"},
                    headers={"X-Session-Token": "testtoken"})
    shid = r.json()["id"]
    r = client.post(f"/api/films/{pid}/scenes/{sid}/shots/{shid}/status",
                    json={"status": "approved", "approved_by": "user"}, headers={"X-Session-Token": "testtoken"})
    assert r.status_code == 200 and r.json()["status"] == "approved"

    # full project readback
    r = client.get(f"/api/films/{pid}", headers={"X-Session-Token": "testtoken"})
    assert r.status_code == 200
    body = r.json()
    assert body["scenes"][0]["shots"][0]["prompt"] == "shot prompt"

    # validation errors
    assert client.post("/api/films", json={"title": ""}, headers={"X-Session-Token": "testtoken"}).status_code == 422
    assert client.post(f"/api/films/{pid}/scenes/{sid}/shots", json={"prompt": ""},
                       headers={"X-Session-Token": "testtoken"}).status_code == 422
    assert client.get("/api/films/nope", headers={"X-Session-Token": "testtoken"}).status_code == 404

    # update + delete
    r = client.patch(f"/api/films/{pid}", json={"bible": {"logline": "LL"}}, headers={"X-Session-Token": "testtoken"})
    assert r.status_code == 200 and r.json()["bible"]["logline"] == "LL"
    assert client.delete(f"/api/films/{pid}", headers={"X-Session-Token": "testtoken"}).status_code == 200
    assert client.get(f"/api/films/{pid}", headers={"X-Session-Token": "testtoken"}).status_code == 404

"""Phase 2 API tests: creative pipeline endpoints (mock provider, no network)."""
import pytest
from fastapi.testclient import TestClient


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


def test_provider_status(client):
    r = client.get("/api/llm/provider", headers=H())
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "mock" and "concept" in body["stages"]
    assert client.get("/api/llm/provider").status_code == 401


def test_creative_pipeline_end_to_end(client):
    pid = client.post("/api/films", json={"title": "Pipeline Film"}, headers=H()).json()["id"]

    # dependency order enforced via HTTP
    r = client.post(f"/api/films/{pid}/generate/treatment", json={}, headers=H())
    assert r.status_code == 409 and r.json()["error"]["code"] == "stage_dependency_missing"

    chain = ["concept", "treatment", "screenplay", "scene_breakdown"]
    for stage in chain:
        r = client.post(f"/api/films/{pid}/generate/{stage}", json={"brief": "noir"}, headers=H())
        assert r.status_code == 200, r.text
        assert r.json()["kind"] == stage
        r = client.post(f"/api/films/{pid}/artifacts/{stage}/approve", headers=H())
        assert r.status_code == 200

    # regeneration of approved artifact is blocked (409 artifact_locked)
    r = client.post(f"/api/films/{pid}/generate/concept", json={}, headers=H())
    assert r.status_code == 409 and r.json()["error"]["code"] == "artifact_locked"

    # apply approved breakdown -> scenes created
    r = client.post(f"/api/films/{pid}/apply-breakdown", headers=H())
    assert r.status_code == 200 and r.json()["scenes_added"] >= 1

    # storyboard for a scene
    scene = client.get(f"/api/films/{pid}", headers=H()).json()["scenes"][0]
    r = client.post(f"/api/films/{pid}/generate/storyboard",
                    json={"scene": scene.get("breakdown", scene), "panel_count": 4}, headers=H())
    assert r.status_code == 200

    # artifacts listing shows all five kinds
    kinds = [a["kind"] for a in client.get(f"/api/films/{pid}/artifacts", headers=H()).json()["artifacts"]]
    assert kinds == ["concept", "treatment", "screenplay", "scene_breakdown", "storyboard"]

    # version list + edit + activate
    art = client.get(f"/api/films/{pid}/artifacts/storyboard", headers=H()).json()
    assert art["status"] == "draft"
    r = client.patch(f"/api/films/{pid}/artifacts/storyboard",
                     json={"data": art["data"]}, headers=H())
    assert r.status_code == 200 and r.json()["source"] == "user_edit"
    r = client.post(f"/api/films/{pid}/artifacts/storyboard/versions/1/activate", headers=H())
    assert r.status_code == 200 and r.json()["active_version"] == 1
    assert client.get(f"/api/films/{pid}/artifacts/storyboard?version=2", headers=H()).status_code == 200

    # apply already done above; unknown kind/project -> 404
    assert client.get(f"/api/films/{pid}/artifacts/nope", headers=H()).status_code == 404
    assert client.get("/api/films/nope/artifacts", headers=H()).status_code == 404

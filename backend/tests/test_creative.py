"""Phase 2 tests: LLM provider layer, creative stages, artifact versioning."""
import asyncio
import json

import pytest

from backend.adapter import creative, llm
from backend.adapter.films import FilmStore
from backend.adapter.llm import LLMError, MockProvider
from backend.adapter.llm import OpenAICompatibleProvider


@pytest.fixture()
def store(tmp_path):
    return FilmStore(root=tmp_path / "films")


@pytest.fixture()
def mock():
    return MockProvider()


def run(coro):
    return asyncio.run(coro)


def test_mock_provider_deterministic(mock):
    r1 = run(mock.complete_json("s", "STAGE: concept\nmake a film"))
    assert r1["json"]["mock"] is True and r1["json"]["stage"] == "concept"
    assert r1["json"]["title"]  # mock data is schema-valid, not empty
    assert len(mock.calls) == 1


def test_extract_json_tolerates_fences():
    text = 'Sure!\n```json\n{"a": 1}\n```\nhope that helps'
    assert llm._extract_json(text) == {"a": 1}
    assert llm._extract_json('{"b": [2]}') == {"b": [2]}
    with pytest.raises(ValueError):
        llm._extract_json("no json here")
    with pytest.raises(ValueError):
        llm._extract_json("")


def test_openai_compatible_rejects_missing_key():
    p = OpenAICompatibleProvider(api_key="", base_url="http://x/v1", model="m")
    with pytest.raises(LLMError) as e:
        run(p.complete("s", "p"))
    assert e.value.code == "llm_missing_key"


def test_concept_stage_roundtrip(store, mock):
    p = store.create("Test film")
    entry = run(creative.run_stage(store, mock, p["id"], "concept", brief="make it noir"))
    assert entry["version"] == 1 and entry["source"] == "agent"
    art = store.get_artifact(p["id"], "concept")
    assert art["data"]["stage"] == "concept"
    assert any("STAGE: concept" in c["prompt"] for c in mock.calls)


def test_stage_dependency_chain(store, mock):
    p = store.create("Chain film")
    # treatment before concept must fail with a clear code
    with pytest.raises(LLMError) as e:
        run(creative.run_stage(store, mock, p["id"], "treatment"))
    assert e.value.code == "stage_dependency_missing"

    run(creative.run_stage(store, mock, p["id"], "concept"))
    # concept exists but is not approved yet
    with pytest.raises(LLMError) as e:
        run(creative.run_stage(store, mock, p["id"], "treatment"))
    assert e.value.code == "stage_dependency_not_approved"

    store.set_artifact_status(p["id"], "concept", "approved")
    entry = run(creative.run_stage(store, mock, p["id"], "treatment"))
    assert entry["version"] == 1


def test_approval_lock_and_versions(store, mock):
    p = store.create("Versions film")
    run(creative.run_stage(store, mock, p["id"], "concept"))
    store.set_artifact_status(p["id"], "concept", "approved")
    # regeneration while approved is refused and raises artifact_locked
    with pytest.raises(LLMError) as e:
        run(creative.run_stage(store, mock, p["id"], "concept"))
    assert e.value.code == "artifact_locked"
    # user edit of approved artifact is refused too
    assert store.edit_artifact(p["id"], "concept", {"x": 1}) is None
    # unapprove -> regenerate -> two versions, history kept, active = 2
    store.set_artifact_status(p["id"], "concept", None)
    store.edit_artifact(p["id"], "concept", {"manual": True})
    run(creative.run_stage(store, mock, p["id"], "concept"))
    art = store.get_artifact(p["id"], "concept")
    assert art["active_version"] == 3 and len(art["versions"]) == 3
    assert art["versions"][0]["source"] == "agent"
    assert art["versions"][1]["source"] == "user_edit"
    # revert to version 1
    store.activate_version(p["id"], "concept", 1)
    assert store.get_artifact(p["id"], "concept")["active_version"] == 1


def test_invalid_json_from_provider(store):
    class BadProvider(MockProvider):
        async def complete(self, system, prompt, **kw):
            return {"text": "not json at all", "usage": {}}

    p = store.create("Bad json film")
    with pytest.raises(LLMError) as e:
        run(creative.run_stage(store, BadProvider(), p["id"], "concept"))
    assert e.value.code == "llm_invalid_json"
    assert store.get_artifact(p["id"], "concept") is None


def test_schema_validation_rejects_bad_concept(store):
    class SloppyProvider(MockProvider):
        async def complete(self, system, prompt, **kw):
            return {"text": json.dumps({"title": ""}), "usage": {}}

    p = store.create("Sloppy film")
    with pytest.raises(LLMError) as e:
        run(creative.run_stage(store, SloppyProvider(), p["id"], "concept"))
    assert e.value.code == "llm_schema_mismatch"


def test_screenplay_slugline_and_ordering_rules():
    good = {"scenes": [{"number": 1, "slugline": "EXT. STREET - NIGHT", "summary": "s"}]}
    creative.validate_screenplay(good)
    bad_order = {"scenes": [{"number": 2, "slugline": "EXT. A - NIGHT", "summary": "s"},
                            {"number": 1, "slugline": "INT. B - DAY", "summary": "s"}]}
    with pytest.raises(LLMError):
        creative.validate_screenplay(bad_order)
    bad_slug = {"scenes": [{"number": 1, "slugline": "The street at night", "summary": "s"}]}
    with pytest.raises(LLMError):
        creative.validate_screenplay(bad_slug)


def test_storyboard_validation():
    good = {"panels": [{"shot_number": 1, "shot_size": "WIDE", "visual_prompt": "a wide shot"}]}
    creative.validate_storyboard(good)
    bad = {"panels": [{"shot_number": 1, "shot_size": "WIDE"}]}
    with pytest.raises(LLMError):
        creative.validate_storyboard(bad)


def test_apply_breakdown_requires_approved_artifact(store, mock):
    p = store.create("Breakdown film")
    assert store.apply_breakdown(p["id"]) is None  # no artifact at all
    run(creative.run_stage(store, mock, p["id"], "concept"))
    store.set_artifact_status(p["id"], "concept", "approved")
    run(creative.run_stage(store, mock, p["id"], "treatment"))
    store.set_artifact_status(p["id"], "treatment", "approved")
    run(creative.run_stage(store, mock, p["id"], "screenplay"))
    store.set_artifact_status(p["id"], "screenplay", "approved")
    run(creative.run_stage(store, mock, p["id"], "scene_breakdown"))
    # not approved yet
    assert store.apply_breakdown(p["id"]) is None
    store.set_artifact_status(p["id"], "scene_breakdown", "approved")
    result = store.apply_breakdown(p["id"])
    assert result and result["scene_count"] >= 1
    # applying again never duplicates existing scenes destructively: it appends
    before = store.get(p["id"])["scenes"]
    result2 = store.apply_breakdown(p["id"])
    after = store.get(p["id"])["scenes"]
    assert len(after) == len(before) + result2["scenes_added"]


def test_unknown_stage_rejected(store, mock):
    p = store.create("Unknown stage film")
    with pytest.raises(LLMError) as e:
        run(creative.run_stage(store, mock, p["id"], "montage"))
    assert e.value.code == "stage_unknown"

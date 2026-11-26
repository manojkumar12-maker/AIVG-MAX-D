"""Tests run against a mock ComfyUI app so no GPU is required."""
from __future__ import annotations

import io
import asyncio
import json


def _async_none():
    async def _f():
        return None
    return _f()
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.adapter import config
from backend.adapter.comfyui import ComfyUIClient
from backend.adapter.jobs import JobManager
from backend.adapter.main import app
from backend.adapter.workflows import WorkflowRegistry

PNG = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 32, "image/png")


class MockComfy(BaseHTTPRequestHandler):
    uploaded: dict[str, bytes] = {}
    fail_prompt = False
    outputs = [{"filename": "img_00001_.png", "subfolder": "OpenGenerativeAI", "type": "output"}]

    def log_message(self, *a):  # silence
        pass

    def _json(self, body, status=200):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/system_stats"):
            self._json({"devices": [{"name": "Mock T4", "vram_total": 15 * 1024 ** 3}]})
        elif self.path.startswith("/object_info"):
            self._json({
                "CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [["v1-5-pruned-emaonly-fp16.safetensors", "sd_xl_base_1.0.safetensors"], {}]}}},
                "KSampler": {"input": {"required": {}}},
                "CLIPTextEncode": {"input": {"required": {}}},
                "EmptyLatentImage": {"input": {"required": {}}},
                "VAEDecode": {"input": {"required": {}}},
                "SaveImage": {"input": {"required": {}}},
                "LoadImage": {"input": {"required": {}}},
                "ImageScale": {"input": {"required": {}}},
                "VAEEncode": {"input": {"required": {}}},
                "CheckpointLoaderSimple#2": {"input": {"required": {}}},
                # Wan 2.1 I2V loader choices so the Phase 3B end-to-end tests can
                # exercise the image-to-video path against the mock (model files
                # are not really present; the workflow itself never runs).
                "UNETLoader": {"input": {"required": {"unet_name": [["wan2.1_i2v_480p_14B_fp16.safetensors"], {}]}}},
                "CLIPLoader": {"input": {"required": {"clip_name": [["wan_umtv5_v2_fp8_e4m3fn.safetensors"], {}]}}},
                "VAELoader": {"input": {"required": {"vae_name": [["wan_2.1_vae.safetensors"], {}]}}},
                # Custom node classes the Wan I2V graph needs (names only; the
                # workflow never actually executes against the mock).
                "CLIPVisionEncode": {"input": {"required": {}}},
                "CLIPVisionLoader": {"input": {"required": {}}},
                "VHS_VideoCombine": {"input": {"required": {}}},
                "WanImageToVideo": {"input": {"required": {}}},
            })
        elif self.path.startswith("/history/prompt-ok"):
            self._json({"prompt-ok": {"status": {"status_str": "success", "completed": True},
                                      "outputs": {"6": {"images": self.outputs}}}})
        elif self.path.startswith("/history/"):
            self._json({})
        elif self.path.startswith("/queue"):
            self._json({"queue": {"running": [], "pending": []}})
        elif self.path.startswith("/view"):
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(PNG[0])))
            self.end_headers()
            self.wfile.write(PNG[0])
        else:
            self._json({}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        if self.path.startswith("/upload/image"):
            # multipart: crude parse - grab last part's content
            content = body.split(b"\r\n\r\n", 1)[1].rsplit(b"\r\n--", 1)[0]
            MockComfy.uploaded["input.png"] = content
            self._json({"name": "input.png", "subfolder": ""})
        elif self.path.startswith("/prompt"):
            if MockComfy.fail_prompt:
                self._json({"error": {"message": "prompt failed"}}, 400)
            else:
                self._json({"prompt_id": "prompt-ok", "number": 1})
        elif self.path.startswith("/interrupt") or self.path.startswith("/free"):
            self._json({})
        else:
            self._json({}, 404)


@pytest.fixture(scope="session")
def comfy_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), MockComfy)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    yield url
    server.shutdown()


@pytest_asyncio.fixture
async def client(comfy_server, tmp_path, monkeypatch):
    config.OUTPUT_DIR = tmp_path / "outputs"
    config.UPLOAD_DIR = tmp_path / "uploads"
    config.STATE_DIR = tmp_path / "state"
    config.OUTPUT_DIR.mkdir()
    config.UPLOAD_DIR.mkdir()
    monkeypatch.setattr(config, "SESSION_TOKEN", "test-token")
    monkeypatch.setattr(config, "RATE_LIMIT", (10_000, 60))
    from backend.adapter import main as main_mod
    main_mod.comfy = ComfyUIClient(base_url=comfy_server)
    main_mod.registry = WorkflowRegistry()
    main_mod.jobs = JobManager(main_mod.comfy, persist_path=tmp_path / "state" / "jobs.json")
    main_mod._settings_path = tmp_path / "state" / "settings.json"
    transport = ASGITransport(app=main_mod.app)
    yield AsyncClient(transport=transport, base_url="http://adapter")
    main_mod.jobs.shutdown()


def run(coro):
    import asyncio
    return asyncio.get_event_loop().run_until_complete(coro) if False else coro


H = {"X-Session-Token": "test-token"}


@pytest.mark.anyio
class TestAuth:
    async def test_health_no_auth(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["backend_online"] is True
        assert body["comfyui_online"] is True
        assert body["gpu_name"] == "Mock T4"
        assert body["capabilities"]["vram_class"] == "MEDIUM_VRAM"

    async def test_missing_token_rejected(self, client):
        resp = await client.get("/api/jobs")
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "invalid_token"

    async def test_bad_token_rejected(self, client):
        resp = await client.get("/api/jobs", headers={"X-Session-Token": "wrong"})
        assert resp.status_code == 401

    async def test_query_param_token_accepted(self, client):
        resp = await client.get("/api/settings", params={"token": "test-token"})
        assert resp.status_code == 200


@pytest.mark.anyio
class TestInfo:
    async def test_models_list(self, client):
        body = (await client.get("/api/models", headers=H)).json()
        ids = [m["id"] for m in body["models"]]
        assert {"sd15", "sdxl", "wan21_t2v_480p"} <= set(ids)
        sd15 = next(m for m in body["models"] if m["id"] == "sd15")
        assert sd15["installed"] is True
        assert sd15["license"]

    async def test_workflows_list(self, client):
        body = (await client.get("/api/workflows", headers=H)).json()
        assert len(body["workflows"]) >= 6
        for wf in body["workflows"]:
            assert {"id", "name", "type", "min_vram_gb", "features"} <= set(wf)

    async def test_settings_roundtrip(self, client):
        resp = await client.post("/api/settings", headers=H, json={"low_vram": True})
        assert resp.json() == {"save_to_drive": False, "low_vram": True, "unload_after_job": False}


@pytest.mark.anyio
class TestGeneration:
    async def test_text_to_image_end_to_end(self, client):
        resp = await client.post("/api/generate/image", headers=H, json={
            "prompt": "a red fox in snow", "negative_prompt": "blurry",
            "width": 512, "height": 512, "steps": 20, "cfg": 7, "seed": 1,
            "sampler": "euler", "scheduler": "normal", "batch_size": 1, "model": "sd15",
        })
        assert resp.status_code == 200, resp.text
        job_id = resp.json()["job_id"]
        for _ in range(100):
            job = (await client.get(f"/api/jobs/{job_id}", headers=H)).json()
            if job["status"] in ("completed", "failed"):
                break
            time.sleep(0.1)
        assert job["status"] == "completed", job.get("error")
        assert job["outputs"] and job["outputs"][0]["type"] == "image"
        filename = job["outputs"][0]["filename"]
        # output retrievable and path traversal impossible
        out = await client.get(f"/api/output/{filename}", headers=H)
        assert out.status_code == 200 and out.content.startswith(b"\x89PNG")
        assert (await client.get("/api/output/..%2Fstate%2Fjobs.json", headers=H)).status_code in (404, 422)

    async def test_validation_rejects_bad_dimensions(self, client):
        resp = await client.post("/api/generate/image", headers=H, json={
            "prompt": "x", "width": 511, "height": 512, "model": "sd15"})
        assert resp.status_code == 422

    async def test_missing_model(self, client):
        resp = await client.post("/api/generate/video", headers=H, json={
            "prompt": "cat", "width": 512, "height": 512, "frames": 16, "fps": 8})
        assert resp.status_code == 400
        body = resp.json()["error"]
        assert body["code"] == "missing_model"
        assert "not installed" in body["message"]

    async def test_vram_gate_refuses_small_gpu(self, client):
        # Mock T4 reports 15GB; Wan I2V needs 22GB per its template.
        resp = await client.post("/api/generate/image-to-video", headers=H, json={
            "prompt": "ocean waves", "model": "wan21_i2v_480p",
            "width": 832, "height": 480, "frames": 33, "fps": 16})
        assert resp.status_code == 400
        body = resp.json()["error"]
        assert body["code"] == "insufficient_vram"
        assert "22GB" in body["message"]

    async def test_vram_gate_allows_big_enough_gpu(self, client):
        # LTX needs 8GB; the mock GPU has 15GB — must get past the VRAM gate
        # (it then fails on the missing model file, which is the honest error).
        resp = await client.post("/api/generate/video", headers=H, json={
            "prompt": "city timelapse", "model": "ltxvideo_2b",
            "width": 768, "height": 512, "frames": 97, "fps": 24})
        assert resp.status_code == 400
        body = resp.json()["error"]
        assert body["code"] == "missing_model"

    async def test_drive_mirror(self, client, tmp_path, monkeypatch):
        from backend.adapter import config as config_mod
        drive = tmp_path / "drive"
        monkeypatch.setattr(config_mod, "DRIVE_DIR", drive)
        resp = await client.post("/api/settings", headers=H, json={"save_to_drive": True})
        assert resp.status_code == 200
        resp = await client.post("/api/generate/image", headers=H, json={"prompt": "a red cube"})
        assert resp.status_code == 200, resp.text
        job_id = resp.json()["job_id"]
        for _ in range(100):
            job = (await client.get(f"/api/jobs/{job_id}", headers=H)).json()
            if job["status"] in ("completed", "failed"):
                break
            await asyncio.sleep(0.05)
        assert job["status"] == "completed", job.get("error")
        out = drive / "outputs"
        files = list(out.glob("*.png"))
        assert files, "no PNG mirrored to Drive"
        meta = json.loads((out / f"{job_id}.json").read_text())
        assert meta["job_id"] == job_id
        assert meta["params"]["save_to_drive"] is True
        assert any(o["filename"] == files[0].name for o in meta["outputs"])

    async def test_drive_mirror_off_by_default(self, client, tmp_path, monkeypatch):
        from backend.adapter import config as config_mod
        drive = tmp_path / "drive"
        monkeypatch.setattr(config_mod, "DRIVE_DIR", drive)
        resp = await client.post("/api/generate/image", headers=H, json={"prompt": "a red cube"})
        job_id = resp.json()["job_id"]
        for _ in range(100):
            job = (await client.get(f"/api/jobs/{job_id}", headers=H)).json()
            if job["status"] in ("completed", "failed"):
                break
            await asyncio.sleep(0.05)
        assert job["status"] == "completed"
        assert not (drive / "outputs").exists(), "Drive must stay untouched when save_to_drive is off"

    async def test_low_vram_rewrites_graph(self, client, tmp_path, monkeypatch):
        from backend.adapter import main as main_mod
        captured = {}
        real_submit = main_mod.jobs.submit

        def spy(job_type, params):
            captured["graph"] = params["_graph"]
            return real_submit(job_type, params)

        monkeypatch.setattr(main_mod.jobs, "submit", spy)
        resp = await client.post("/api/settings", headers=H, json={"low_vram": True})
        assert resp.status_code == 200
        resp = await client.post("/api/generate/image", headers=H, json={"prompt": "cube"})
        assert resp.status_code == 200
        latents = [n for n in captured["graph"].values()
                   if "EmptyLatent" in n.get("class_type", "") or n.get("class_type") == "ADE_EmptyLatentImage"]
        assert latents, "graph has no latent node"
        assert all(n["inputs"]["batch_size"] == 1 for n in captured["graph"].values()
                   if "batch_size" in n.get("inputs", {}))
        assert all(n["inputs"]["width"] <= 512 and n["inputs"]["height"] <= 512 for n in latents)

    async def test_unload_after_job_calls_free(self, client, tmp_path, monkeypatch):
        from backend.adapter import main as main_mod
        calls = []
        monkeypatch.setattr(main_mod.comfy, "free_memory", lambda: calls.append(1) or _async_none())
        resp = await client.post("/api/settings", headers=H, json={"unload_after_job": True})
        assert resp.status_code == 200
        resp = await client.post("/api/generate/image", headers=H, json={"prompt": "cube"})
        job_id = resp.json()["job_id"]
        for _ in range(100):
            job = (await client.get(f"/api/jobs/{job_id}", headers=H)).json()
            if job["status"] in ("completed", "failed"):
                break
            await asyncio.sleep(0.05)
        assert job["status"] == "completed", job.get("error")
        assert calls, "free_memory was not called after the job"

    def test_ws_jobs_hub_broadcast(self):
        """Sync test: hub fan-out works and never blocks the caller (regression:
        run_coroutine_threadsafe from the loop's own thread deadlocked)."""
        import threading
        from backend.adapter import main as main_mod
        from backend.adapter.jobs import Job

        sent = []

        class FakeWS:
            async def send_text(self, text):
                sent.append(json.loads(text))

        ready = threading.Event()
        stop = threading.Event()
        loop_holder = {}

        def run_loop():
            loop_holder["loop"] = asyncio.new_event_loop()
            ready.set()
            loop_holder["loop"].run_until_complete(_pump(stop))

        async def _pump(stop):
            while not stop.is_set():
                await asyncio.sleep(0.01)

        t = threading.Thread(target=run_loop, daemon=True)
        t.start()
        ready.wait()
        saved = main_mod.loop
        main_mod.loop = loop_holder["loop"]
        try:
            ws = FakeWS()
            main_mod.hub.connect(ws)
            job = Job("image", {"prompt": "x"})
            job.status = "completed"
            main_mod.hub.broadcast(job)  # worker-thread path: run_coroutine_threadsafe
            deadline = time.time() + 2
            while not sent and time.time() < deadline:
                time.sleep(0.01)
            main_mod.hub.disconnect(ws)
        finally:
            main_mod.loop = saved
            stop.set()
            t.join(timeout=2)
        assert sent and sent[0]["event"] == "job_update" and sent[0]["job"]["status"] == "completed"

    async def test_video_templates_registered(self, client):
        resp = await client.get("/api/workflows", headers=H)
        ids = {w["id"] for w in resp.json()["workflows"]}
        assert {"video_wan_t2v", "video_wan_i2v", "video_ltx_t2v", "video_animdiff_t2v"} <= ids
        # experimental templates are flagged so the UI can warn
        meta = {w["id"]: w for w in resp.json()["workflows"]}
        assert meta["video_ltx_t2v"]["experimental"] is True

    async def test_i2i_requires_image(self, client):
        resp = await client.post("/api/generate/image-to-image", headers=H, json={
            "prompt": "x", "model": "sdxl", "strength": 0.6})
        assert resp.status_code == 422

    async def test_upload_rejects_non_image(self, client):
        resp = await client.post("/api/upload", headers=H, files={"file": ("evil.png", b"#!/bin/sh", "image/png")})
        assert resp.status_code == 422

    async def test_upload_accepts_png(self, client):
        data, mime = PNG
        resp = await client.post("/api/upload", headers=H, files={"file": ("pic.png", data, mime)})
        assert resp.status_code == 200
        assert resp.json()["mime"] == "image/png"

    async def test_oversize_upload_rejected(self, client):
        big = PNG[0] + b"\x00" * (25 * 1024 * 1024)
        resp = await client.post("/api/upload", headers=H, files={"file": ("big.png", big, "image/png")})
        assert resp.status_code in (413, 422)

    async def test_cancel_and_delete(self, client):
        MockComfy.fail_prompt = False
        resp = await client.post("/api/generate/image", headers=H, json={"prompt": "x", "width": 512, "height": 512, "model": "sd15"})
        job_id = resp.json()["job_id"]
        for _ in range(100):
            job = (await client.get(f"/api/jobs/{job_id}", headers=H)).json()
            if job["status"] == "completed":
                break
            time.sleep(0.1)
        resp = await client.delete(f"/api/jobs/{job_id}", headers=H)
        assert resp.json()["deleted"] == job_id
        assert (await client.get(f"/api/jobs/{job_id}", headers=H)).status_code == 404


@pytest.mark.anyio
class TestShotGeneration:
    """Phase 3A: storyboard shot -> image generation through the existing pipeline."""

    def _make_project(self, tmp_path, monkeypatch):
        from backend.adapter import main as main_mod
        from backend.adapter.films import FilmStore
        store = FilmStore(root=tmp_path / "films")
        monkeypatch.setattr(main_mod, "films", store)
        proj = store.create("Noir Sky", bible={
            "style_guide": "cinematic noir, rain-soaked neon, high contrast",
            "characters": [{"name": "Nova", "appearance": "silver jacket, cropped hair",
                            "wardrobe": "steel-toed boots"}],
        })
        scene = store.add_scene(proj["id"], "Rooftop chase", bible_refs="Nova sprints past antennas")
        shot = store.add_shot(proj["id"], scene["id"], "Nova runs across the rooftop", model="sd15")
        return store, proj, scene, shot

    async def test_shot_prompt_assembles_bible_context(self, client, tmp_path, monkeypatch):
        store, proj, scene, shot = self._make_project(tmp_path, monkeypatch)
        url = f"/api/films/{proj['id']}/scenes/{scene['id']}/shots/{shot['id']}/prompt"
        assert (await client.get(url)).status_code == 401
        body = (await client.get(url, headers=H)).json()
        assert "cinematic noir" in body["prompt"]
        assert "Nova: silver jacket" in body["prompt"]
        assert "Rooftop chase" in body["prompt"]
        assert "bible.characters" in body["context_used"] and "bible.style_guide" in body["context_used"]
        assert body["missing"] == []

    async def test_shot_prompt_reports_missing_context(self, client, tmp_path, monkeypatch):
        from backend.adapter import main as main_mod
        from backend.adapter.films import FilmStore
        store = FilmStore(root=tmp_path / "films2")
        monkeypatch.setattr(main_mod, "films", store)
        proj = store.create("Bare Bones")
        scene = store.add_scene(proj["id"], "Empty scene")
        empty_shot = store.add_shot(proj["id"], scene["id"], "A lamp flickers")
        body = (await client.get(
            f"/api/films/{proj['id']}/scenes/{scene['id']}/shots/{empty_shot['id']}/prompt",
            headers=H)).json()
        assert "bible.style_guide" in body["missing"]
        assert "bible.characters" in body["missing"]
        assert body["prompt"]  # base shot prompt still present

    async def test_shot_generate_uses_jobmanager_and_associates_records(self, client, tmp_path, monkeypatch):
        store, proj, scene, shot = self._make_project(tmp_path, monkeypatch)
        url = f"/api/films/{proj['id']}/scenes/{scene['id']}/shots/{shot['id']}/generate"
        assert (await client.post(url, json={"prompt": "x"})).status_code == 401
        r = await client.post(url, headers=H, json={
            "prompt": "Nova runs, user edited", "width": 512, "height": 512, "model": "sd15"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["workflow_id"].startswith("image_")
        gen = body["generation"]
        assert gen["job_id"] == body["job_id"] and gen["status"] == "submitted"
        assert gen["prompt"] == "Nova runs, user edited"  # user edit wins
        # the job really went through the existing JobManager
        job = (await client.get(f"/api/jobs/{body['job_id']}", headers=H)).json()
        assert job["type"] == "image"
        for _ in range(100):
            job = (await client.get(f"/api/jobs/{body['job_id']}", headers=H)).json()
            if job["status"] == "completed":
                break
            time.sleep(0.1)
        assert job["status"] == "completed"
        # attach the outcome onto the shot (idempotent recovery path)
        attach_url = url.rsplit("/generate", 1)[0] + f"/jobs/{body['job_id']}/attach"
        assert (await client.post(attach_url)).status_code == 401
        att = (await client.post(attach_url, headers=H)).json()["generation"]
        assert att["status"] == "completed" and att["output"]["filename"].endswith(".png")
        again = (await client.post(attach_url, headers=H)).json()["generation"]
        assert again["status"] == "completed"  # idempotent, no duplicate image
        project = store.get(proj["id"])
        shot_doc = project["scenes"][0]["shots"][0]
        assert len(shot_doc["images"]) == 1 and shot_doc["images"][0]["selected"] is True
        assert shot_doc["images"][0]["job_id"] == body["job_id"]

    async def test_generation_history_preserved_and_select(self, client, tmp_path, monkeypatch):
        store, proj, scene, shot = self._make_project(tmp_path, monkeypatch)
        base = f"/api/films/{proj['id']}/scenes/{scene['id']}/shots/{shot['id']}"
        ids = []
        for prompt in ("first take", "second take"):
            r = await client.post(f"{base}/generate", headers=H,
                                  json={"prompt": prompt, "width": 512, "height": 512, "model": "sd15"})
            job_id = r.json()["job_id"]
            for _ in range(100):
                job = (await client.get(f"/api/jobs/{job_id}", headers=H)).json()
                if job["status"] == "completed":
                    break
                time.sleep(0.1)
            await client.post(f"{base}/jobs/{job_id}/attach", headers=H)
            ids.append(job_id)
        shot_doc = store.get(proj["id"])["scenes"][0]["shots"][0]
        assert len(shot_doc["images"]) == 2  # history preserved, nothing overwritten
        # a regeneration never silently replaces the currently selected visual
        assert shot_doc["images"][0]["selected"] is True
        assert shot_doc["images"][1]["selected"] is False
        newer = shot_doc["images"][1]
        r = await client.post(f"{base}/images/{newer['id']}/select", headers=H)
        selected = [i for i in r.json()["images"] if i["selected"]]
        assert len(selected) == 1 and selected[0]["id"] == newer["id"]
        assert len(r.json()["images"]) == 2  # still nothing deleted

    async def test_failed_generation_recorded_without_output(self, client, tmp_path, monkeypatch):
        store, proj, scene, shot = self._make_project(tmp_path, monkeypatch)
        MockComfy.fail_prompt = True
        try:
            r = await client.post(
                f"/api/films/{proj['id']}/scenes/{scene['id']}/shots/{shot['id']}/generate",
                headers=H, json={"prompt": "retry me", "width": 512, "height": 512, "model": "sd15"})
            job_id = r.json()["job_id"]
            for _ in range(100):
                job = (await client.get(f"/api/jobs/{job_id}", headers=H)).json()
                if job["status"] in ("failed", "completed"):
                    break
                time.sleep(0.1)
            att = (await client.post(
                f"/api/films/{proj['id']}/scenes/{scene['id']}/shots/{shot['id']}/jobs/{job_id}/attach",
                headers=H)).json()["generation"]
            assert att["status"] == "failed" and att["error"]
            shot_doc = store.get(proj["id"])["scenes"][0]["shots"][0]
            assert shot_doc.get("images", []) == []  # no output attached on failure
        finally:
            MockComfy.fail_prompt = False
        # retry: a new submission succeeds and the failed record stays in history
        r = await client.post(
            f"/api/films/{proj['id']}/scenes/{scene['id']}/shots/{shot['id']}/generate",
            headers=H, json={"prompt": "retry me", "width": 512, "height": 512, "model": "sd15"})
        job_id = r.json()["job_id"]
        for _ in range(100):
            job = (await client.get(f"/api/jobs/{job_id}", headers=H)).json()
            if job["status"] == "completed":
                break
            time.sleep(0.1)
        await client.post(
            f"/api/films/{proj['id']}/scenes/{scene['id']}/shots/{shot['id']}/jobs/{job_id}/attach",
            headers=H)
        shot_doc = store.get(proj["id"])["scenes"][0]["shots"][0]
        assert [g["status"] for g in shot_doc["generations"]] == ["failed", "completed"]
        assert len(shot_doc["images"]) == 1

    async def test_backend_unavailable_fails_gracefully(self, client, tmp_path, monkeypatch):
        from backend.adapter import main as main_mod
        from backend.adapter.comfyui import ComfyUIClient
        store, proj, scene, shot = self._make_project(tmp_path, monkeypatch)
        monkeypatch.setattr(main_mod, "comfy", ComfyUIClient(base_url="http://127.0.0.1:1"))
        r = await client.post(
            f"/api/films/{proj['id']}/scenes/{scene['id']}/shots/{shot['id']}/generate",
            headers=H, json={"prompt": "x", "width": 512, "height": 512, "model": "sd15"})
        assert r.status_code >= 400
        assert r.json()["error"]["code"]  # clear error body, not a hang
        shot_doc = store.get(proj["id"])["scenes"][0]["shots"][0]
        assert shot_doc.get("generations", []) == []  # project data preserved, no record
        assert shot_doc["prompt"] == "Nova runs across the rooftop"

    async def test_workflow_and_shot_validation(self, client, tmp_path, monkeypatch):
        store, proj, scene, shot = self._make_project(tmp_path, monkeypatch)
        base = f"/api/films/{proj['id']}/scenes/{scene['id']}/shots/{shot['id']}"
        assert (await client.get(f"/api/films/nope/scenes/x/shots/y/prompt", headers=H)).status_code == 404
        assert (await client.get(f"{base.replace(shot['id'], 'nope')}/prompt", headers=H)).status_code == 404
        bare = store.create("No Context", bible={"style_guide": "", "characters": []})
        bare_scene = store.add_scene(bare["id"], "")
        bare_shot = store.add_shot(bare["id"], bare_scene["id"], "")
        # add_scene auto-titles ("Scene 1"), so a scene always contributes;
        # with no shot prompt and no other context, that title is the whole prompt
        body = (await client.post(
            f"/api/films/{bare['id']}/scenes/{bare_scene['id']}/shots/{bare_shot['id']}/generate",
            headers=H, json={})).json()
        assert body["generation"]["prompt"]  # falls back to assembled context
        r = await client.post(f"{base}/generate", headers=H, json={
            "prompt": "x", "workflow_id": "../../etc/passwd", "width": 512, "height": 512, "model": "sd15"})
        assert r.status_code in (404, 422)
        shot_doc = store.get(proj["id"])["scenes"][0]["shots"][0]
        assert shot_doc.get("generations", []) == []


@pytest.mark.anyio
class TestShotVideoGeneration:
    """Phase 3B: storyboard shot -> video generation through the existing pipeline."""

    def _make_project(self, tmp_path, monkeypatch):
        from backend.adapter import main as main_mod
        from backend.adapter.films import FilmStore
        store = FilmStore(root=tmp_path / "films3b")
        monkeypatch.setattr(main_mod, "films", store)
        proj = store.create("Noir Sky", bible={
            "style_guide": "cinematic noir, rain-soaked neon, high contrast",
            "characters": [{"name": "Nova", "appearance": "silver jacket, cropped hair",
                            "wardrobe": "steel-toed boots"}],
        })
        scene = store.add_scene(proj["id"], "Rooftop chase", bible_refs="Nova sprints past antennas")
        shot = store.add_shot(proj["id"], scene["id"], "Nova runs across the rooftop", model="sd15",
                              params={"camera_movement": "slow dolly forward"})
        return store, proj, scene, shot

    async def _completed_image(self, client, store, proj, scene, shot):
        r = await client.post(
            f"/api/films/{proj['id']}/scenes/{scene['id']}/shots/{shot['id']}/generate",
            headers=H, json={"prompt": "key frame", "width": 512, "height": 512, "model": "sd15"})
        job_id = r.json()["job_id"]
        for _ in range(100):
            job = (await client.get(f"/api/jobs/{job_id}", headers=H)).json()
            if job["status"] == "completed":
                break
            time.sleep(0.1)
        await client.post(
            f"/api/films/{proj['id']}/scenes/{scene['id']}/shots/{shot['id']}/jobs/{job_id}/attach",
            headers=H)
        shot_doc = store.get(proj["id"])["scenes"][0]["shots"][0]
        return shot_doc["images"][0]

    @pytest.fixture
    def big_gpu(self, monkeypatch):
        # Wan I2V needs 22GB; the mock T4 reports 15GB. Report a big enough GPU
        # so the end-to-end tests exercise the happy path (the VRAM gate
        # itself is covered by the existing test_vram_gate_refuses_small_gpu).
        from backend.adapter import main as main_mod
        async def _big():
            return {"gpu_name": "Mock A100", "gpu_vram_gb": 24.0}
        monkeypatch.setattr(main_mod, "_gpu_info", _big)

    async def test_video_prompt_assembles_motion_and_source(self, client, tmp_path, monkeypatch):
        store, proj, scene, shot = self._make_project(tmp_path, monkeypatch)
        url = f"/api/films/{proj['id']}/scenes/{scene['id']}/shots/{shot['id']}/video/prompt"
        assert (await client.get(url)).status_code == 401
        body = (await client.get(url, headers=H)).json()
        assert "cinematic noir" in body["prompt"] and "slow dolly forward" in body["prompt"]
        assert "shot.params.camera_movement" in body["context_used"]
        assert body["missing"] == ["shot.selected_image"]  # no image yet
        assert body["source_image"] is None

    async def test_video_generate_requires_selected_image(self, client, tmp_path, monkeypatch):
        store, proj, scene, shot = self._make_project(tmp_path, monkeypatch)
        r = await client.post(
            f"/api/films/{proj['id']}/scenes/{scene['id']}/shots/{shot['id']}/video/generate",
            headers=H, json={})
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "no_source_image"
        shot_doc = store.get(proj["id"])["scenes"][0]["shots"][0]
        assert shot_doc.get("video_generations", []) == []

    async def test_video_generate_end_to_end_via_existing_pipeline(self, client, tmp_path, monkeypatch, big_gpu):
        store, proj, scene, shot = self._make_project(tmp_path, monkeypatch)
        image = await self._completed_image(client, store, proj, scene, shot)
        url = f"/api/films/{proj['id']}/scenes/{scene['id']}/shots/{shot['id']}/video/generate"
        assert (await client.post(url, json={})).status_code == 401
        r = await client.post(url, headers=H, json={"prompt": "user edited motion", "frames": 33})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["workflow_id"] == "video_wan_i2v"
        gen = body["generation"]
        assert gen["status"] == "submitted" and gen["source_image_id"] == image["id"]
        assert gen["prompt"] == "user edited motion"  # user edit wins, nothing overwritten
        assert gen["params"]["image"] == "input.png"  # uploaded start frame reached ComfyUI
        job = (await client.get(f"/api/jobs/{body['job_id']}", headers=H)).json()
        assert job["type"] in ("video", "image-to-video")
        for _ in range(100):
            job = (await client.get(f"/api/jobs/{body['job_id']}", headers=H)).json()
            if job["status"] in ("completed", "failed"):
                break
            time.sleep(0.1)
        assert job["status"] == "completed", job.get("error")

    async def test_video_attach_idempotent_and_history_preserved(self, client, tmp_path, monkeypatch, big_gpu):
        store, proj, scene, shot = self._make_project(tmp_path, monkeypatch)
        base = f"/api/films/{proj['id']}/scenes/{scene['id']}/shots/{shot['id']}"
        await self._completed_image(client, store, proj, scene, shot)
        r = await client.post(f"{base}/video/generate", headers=H, json={})
        job_id = r.json()["job_id"]
        for _ in range(100):
            job = (await client.get(f"/api/jobs/{job_id}", headers=H)).json()
            if job["status"] == "completed":
                break
            time.sleep(0.1)
        att = (await client.post(f"{base}/video/jobs/{job_id}/attach", headers=H)).json()["generation"]
        assert att["status"] == "completed" and att["output"]["filename"]
        again = (await client.post(f"{base}/video/jobs/{job_id}/attach", headers=H)).json()["generation"]
        assert again["status"] == "completed"  # idempotent, no duplicate video record
        shot_doc = store.get(proj["id"])["scenes"][0]["shots"][0]
        assert len(shot_doc["videos"]) == 1
        assert shot_doc["videos"][0]["selected"] is True  # first completed video auto-selected

    async def test_video_select_and_regeneration_keeps_history(self, client, tmp_path, monkeypatch, big_gpu):
        store, proj, scene, shot = self._make_project(tmp_path, monkeypatch)
        base = f"/api/films/{proj['id']}/scenes/{scene['id']}/shots/{shot['id']}"
        await self._completed_image(client, store, proj, scene, shot)
        video_ids = []
        for _ in range(2):
            r = await client.post(f"{base}/video/generate", headers=H, json={})
            job_id = r.json()["job_id"]
            for _ in range(100):
                job = (await client.get(f"/api/jobs/{job_id}", headers=H)).json()
                if job["status"] == "completed":
                    break
                time.sleep(0.1)
            await client.post(f"{base}/video/jobs/{job_id}/attach", headers=H)
            shot_doc = store.get(proj["id"])["scenes"][0]["shots"][0]
            video_ids.append(shot_doc["videos"][-1]["id"])
        shot_doc = store.get(proj["id"])["scenes"][0]["shots"][0]
        assert len(shot_doc["videos"]) == 2  # history preserved
        assert shot_doc["videos"][0]["selected"] is True
        r = await client.post(f"{base}/videos/{video_ids[1]}/select", headers=H)
        assert r.status_code == 200
        selected = [v for v in r.json()["videos"] if v["selected"]]
        assert len(selected) == 1 and selected[0]["id"] == video_ids[1]
        assert len(r.json()["videos"]) == 2  # nothing deleted

    async def test_video_attach_rejects_foreign_jobs(self, client, tmp_path, monkeypatch):
        store, proj, scene, shot = self._make_project(tmp_path, monkeypatch)
        base = f"/api/films/{proj['id']}/scenes/{scene['id']}/shots/{shot['id']}"
        # an image job cannot be attached as a video generation
        r = await client.post(f"{base}/generate", headers=H,
                              json={"prompt": "x", "width": 512, "height": 512, "model": "sd15"})
        image_job = r.json()["job_id"]
        resp = await client.post(f"{base}/video/jobs/{image_job}/attach", headers=H)
        assert resp.status_code == 422
        assert resp.json()["error"]["message"] == "Only video jobs can be attached to a shot video."
        assert (await client.post(f"{base}/video/jobs/nope/attach", headers=H)).status_code == 404

    async def test_video_workflow_id_cannot_traverse(self, client, tmp_path, monkeypatch):
        store, proj, scene, shot = self._make_project(tmp_path, monkeypatch)
        await self._completed_image(client, store, proj, scene, shot)
        r = await client.post(
            f"/api/films/{proj['id']}/scenes/{scene['id']}/shots/{shot['id']}/video/generate",
            headers=H, json={"workflow_id": "../../etc/passwd"})
        assert r.status_code in (404, 422)
        shot_doc = store.get(proj["id"])["scenes"][0]["shots"][0]
        assert shot_doc.get("video_generations", []) == []

    async def test_video_backend_unavailable_fails_cleanly(self, client, tmp_path, monkeypatch):
        from backend.adapter import main as main_mod
        from backend.adapter.comfyui import ComfyUIClient
        store, proj, scene, shot = self._make_project(tmp_path, monkeypatch)
        await self._completed_image(client, store, proj, scene, shot)
        monkeypatch.setattr(main_mod, "comfy", ComfyUIClient(base_url="http://127.0.0.1:1"))
        r = await client.post(
            f"/api/films/{proj['id']}/scenes/{scene['id']}/shots/{shot['id']}/video/generate",
            headers=H, json={})
        assert r.status_code >= 400
        assert r.json()["error"]["code"]  # clear error body, not a hang
        shot_doc = store.get(proj["id"])["scenes"][0]["shots"][0]
        assert shot_doc.get("video_generations", []) == []  # project data preserved



class TestContinuity:
    """Phase 4: continuity edit endpoints and prompt-context preview."""

    def _make_project(self, tmp_path, monkeypatch):
        from backend.adapter import main as main_mod
        from backend.adapter.films import FilmStore
        store = FilmStore(root=tmp_path / "films4")
        monkeypatch.setattr(main_mod, "films", store)
        proj = store.create("Continuity Film", bible={
            "style_guide": "cinematic noir",
            "characters": [{"name": "Nova", "appearance": "silver jacket"}],
        })
        scene = store.add_scene(proj["id"], "Rooftop", bible_refs="Nova sprints")
        shot = store.add_shot(proj["id"], scene["id"], "Nova runs", model="sd15")
        return store, proj, scene, shot

    @pytest.mark.anyio
    async def test_film_continuity_roundtrip_and_validation(self, client, tmp_path, monkeypatch):
        store, proj, scene, shot = self._make_project(tmp_path, monkeypatch)
        url = f"/api/films/{proj['id']}/continuity"
        assert (await client.get(url)).status_code == 401  # auth required

        r = await client.put(url, headers=H, json={
            "style": "cold palette",
            "characters": [{"id": "c1", "name": "Nova", "appearance": "tall, red scarf"}],
            "wardrobe": [{"id": "w1", "label": "raincoat", "description": "wet blue raincoat"}],
        })
        assert r.status_code == 200
        assert r.json()["continuity"]["characters"][0]["wardrobe_id"] == ""

        r2 = await client.put(url, headers=H, json={"characters": [{"name": ""}]})
        assert r2.status_code == 422
        assert (await client.get(f"/api/films/nonexistent/continuity", headers=H)).status_code == 404

    @pytest.mark.anyio
    async def test_override_endpoints_and_unknown_refs_404(self, client, tmp_path, monkeypatch):
        store, proj, scene, shot = self._make_project(tmp_path, monkeypatch)
        surl = f"/api/films/{proj['id']}/scenes/{scene['id']}/continuity"
        r = await client.put(surl, headers=H, json={"conditions": "dusk, heavy rain", "location_id": "lX"})
        assert r.status_code == 200
        shurl = f"/api/films/{proj['id']}/scenes/{scene['id']}/shots/{shot['id']}/continuity"
        r2 = await client.put(shurl, headers=H, json={"character_ids": ["cX"]})
        assert r2.status_code == 200

        ctx = await client.get(shurl, headers=H)
        body = ctx.json()
        assert ctx.status_code == 200
        assert body["context"]["conditions"] == "dusk, heavy rain"
        assert any("unknown character_ids" in w for w in body["context"]["warnings"])
        assert body["parts"] == ["dusk, heavy rain"]  # unknown canon ids never leak in

        assert (await client.put(f"/api/films/{proj['id']}/scenes/other/continuity",
                                 headers=H, json={})).status_code == 404
        assert (await client.put(f"/api/films/{proj['id']}/scenes/{scene['id']}/shots/other/continuity",
                                 headers=H, json={})).status_code == 404

    @pytest.mark.anyio
    async def test_continuity_reaches_shot_prompts_and_video(self, client, tmp_path, monkeypatch):
        store, proj, scene, shot = self._make_project(tmp_path, monkeypatch)
        await client.put(f"/api/films/{proj['id']}/continuity", headers=H, json={
            "characters": [{"id": "c1", "name": "Nova", "appearance": "red scarf"}],
            "wardrobe": [{"id": "w1", "label": "raincoat", "description": "wet blue raincoat"}],
        })
        await client.put(
            f"/api/films/{proj['id']}/scenes/{scene['id']}/shots/{shot['id']}/continuity",
            headers=H, json={"character_ids": ["c1"], "wardrobe": {"c1": "w1"}})
        body = (await client.get(
            f"/api/films/{proj['id']}/scenes/{scene['id']}/shots/{shot['id']}/prompt",
            headers=H)).json()
        assert "Nova: red scarf wet blue raincoat" in body["prompt"]
        assert "continuity" in body["context_used"]

        vbody = (await client.get(
            f"/api/films/{proj['id']}/scenes/{scene['id']}/shots/{shot['id']}/video/prompt",
            headers=H)).json()
        assert "Nova: red scarf wet blue raincoat" in vbody["prompt"]

    @pytest.mark.anyio
    async def test_continuity_edit_never_triggers_generation_or_touches_history(self, client, tmp_path, monkeypatch):
        store, proj, scene, shot = self._make_project(tmp_path, monkeypatch)
        before = store.get(proj["id"])
        await client.put(f"/api/films/{proj['id']}/continuity", headers=H, json={"style": "x"})
        await client.put(f"/api/films/{proj['id']}/scenes/{scene['id']}/continuity", headers=H, json={})
        await client.put(
            f"/api/films/{proj['id']}/scenes/{scene['id']}/shots/{shot['id']}/continuity",
            headers=H, json={"conditions": "fog"})
        after = store.get(proj["id"])
        assert before["scenes"][0]["shots"][0].get("images", []) == after["scenes"][0]["shots"][0].get("images", [])
        assert after["continuity"]["style"] == "x"
        assert after["scenes"][0]["continuity"]["location_id"] == ""
        assert after["scenes"][0]["shots"][0]["continuity"]["conditions"] == "fog"

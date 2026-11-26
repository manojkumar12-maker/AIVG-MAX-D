"""FastAPI adapter: the only public surface between the frontend and ComfyUI."""
from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import re
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from . import config, models_registry
from .comfyui import ComfyUIClient, ComfyUIError
from .films import FilmStore
from .creative import STAGES, run_stage
from . import continuity
from .jobs import JobManager
from .llm import LLMError, get_provider
from .shotgen import ShotLookupError, build_shot_prompt
from .shotvideo import build_shot_video_prompt
from .workflows import WorkflowRegistry, WorkflowValidationError

app = FastAPI(title="Open Generative AI backend", version=config.BACKEND_VERSION, docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["X-Session-Token", "Content-Type"],
)

comfy = ComfyUIClient()
registry = WorkflowRegistry()
films = FilmStore()
def _broadcast_change(job) -> None:
    if loop is not None:
        hub.broadcast(job)


jobs = JobManager(comfy, on_change=_broadcast_change)
_settings_path = config.STATE_DIR / "settings.json"
_settings_lock = threading.Lock()

DEFAULT_SETTINGS = {"save_to_drive": False, "low_vram": False, "unload_after_job": False}


def _load_settings() -> dict[str, Any]:
    try:
        return {**DEFAULT_SETTINGS, **json.loads(_settings_path.read_text())}
    except (OSError, ValueError):
        return dict(DEFAULT_SETTINGS)


def _save_settings(data: dict[str, Any]) -> None:
    with _settings_lock:
        config.STATE_DIR.mkdir(parents=True, exist_ok=True)
        _settings_path.write_text(json.dumps(data))


def error_response(status: int, code: str, message: str, hint: str | None = None):
    return JSONResponse({"error": {"code": code, "message": message, "hint": hint}}, status_code=status)


# ---- auth & rate limiting ----------------------------------------------------
_rate_lock = threading.Lock()
_rate_hits: dict[str, deque] = {}


def _rate_limited(key: str) -> bool:
    limit, window = config.RATE_LIMIT
    now = time.time()
    with _rate_lock:
        hits = _rate_hits.setdefault(key, deque())
        while hits and hits[0] <= now - window:
            hits.popleft()
        if len(hits) >= limit:
            return True
        hits.append(now)
        return False


async def require_auth(request: Request) -> str:
    token = request.headers.get("X-Session-Token") or request.query_params.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="Missing session token.")
    if not config.SESSION_TOKEN or token != config.SESSION_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid session token.")
    if _rate_limited(token):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Wait a moment and retry.")
    return token


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    code_map = {401: "invalid_token", 403: "forbidden", 404: "not_found", 409: "queue_full",
                422: "validation", 429: "rate_limited", 502: "comfyui_error", 503: "backend_unavailable"}
    if isinstance(exc.detail, dict) and "error" not in exc.detail:
        return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    code = code_map.get(exc.status_code, "error")
    if "token" in str(exc.detail).lower():
        code = "invalid_token"
    return error_response(exc.status_code, code, str(exc.detail))


@app.exception_handler(WorkflowValidationError)
async def workflow_error_handler(request: Request, exc: WorkflowValidationError):
    status = {"missing_model": 400, "missing_dependency": 400, "validation": 422, "missing_workflow": 404}.get(exc.code, 400)
    return error_response(status, exc.code, exc.message, exc.hint)


# ---- health & info -----------------------------------------------------------
async def _gpu_info() -> dict[str, Any]:
    name, vram = None, None
    try:
        stats = await comfy.system_stats()
        device = stats.get("devices", [{}])[0]
        name = device.get("name")
        vram_bytes = device.get("vram_total")
        if vram_bytes:
            vram = round(vram_bytes / (1024 ** 3), 1)
    except ComfyUIError:
        pass
    if name is None:
        name = os.environ.get("OGAI_GPU_NAME")
        if vram is None and os.environ.get("OGAI_GPU_VRAM_GB"):
            vram = float(os.environ["OGAI_GPU_VRAM_GB"])
    return {"gpu_name": name, "gpu_vram_gb": vram}


@app.get("/health")
async def health():
    comfyui_online = await comfy.is_online()
    gpu = await _gpu_info() if comfyui_online else {"gpu_name": None, "gpu_vram_gb": None}
    return {
        "backend_online": True,
        "comfyui_online": comfyui_online,
        "drive_available": config.DRIVE_DIR is not None,
        "gpu_name": gpu["gpu_name"],
        "gpu_vram_gb": gpu["gpu_vram_gb"],
        "loaded_models": [],
        "queue_size": len(jobs.queue),
        "active_jobs": jobs.counts().get("generating", 0),
        "capabilities": {
            "image": True,
            "video": len(registry.for_type("video")) > 0,
            "image_to_image": len(registry.for_type("image")) > 0,
            "image_to_video": any(w.meta["mode"] == "image-to-video" for w in registry.all()),
            "max_concurrent_jobs": jobs.max_concurrent,
            "vram_class": models_registry.vram_class(gpu["gpu_vram_gb"]),
        },
        "backend_version": config.BACKEND_VERSION,
    }


@app.get("/api/status")
async def status(request: Request):
    await require_auth(request)
    comfyui_online = await comfy.is_online()
    gpu = await _gpu_info() if comfyui_online else {"gpu_name": None, "gpu_vram_gb": None}
    return {
        "backend_online": True,
        "comfyui_online": comfyui_online,
        "drive_available": config.DRIVE_DIR is not None,
        "gpu_name": gpu["gpu_name"],
        "gpu_vram_gb": gpu["gpu_vram_gb"],
        "queue": jobs.counts(),
        "settings": _load_settings(),
        "uptime_seconds": time.time() - _START_TIME,
    }


_START_TIME = time.time()


@app.get("/api/capabilities")
async def capabilities(request: Request):
    await require_auth(request)
    h = await health()
    return h["capabilities"]


async def _models_payload() -> dict[str, Any]:
    comfy_models = await comfy.list_models()
    available_files = [f for files in comfy_models.values() for f in files]
    for model in models_registry.MODELS:
        filename = model["file"].split("/")[-1]
        model["installed"] = any(filename in f for f in available_files)
    return {"models": models_registry.MODELS}


@app.get("/api/models")
async def models(request: Request):
    await require_auth(request)
    return await _models_payload()


@app.get("/api/workflows")
async def workflows(request: Request):
    await require_auth(request)
    return {"workflows": [wf.public() for wf in registry.all()]}


# ---- generation ---------------------------------------------------------------
GENERATE_ROUTES = {
    "image": ("image", "text-to-image"),
    "image-to-image": ("image", "image-to-image"),
    "video": ("video", "text-to-video"),
    "image-to-video": ("video", "image-to-video"),
}


async def _handle_generate(request: Request, kind: str, payload: dict[str, Any]):
    await require_auth(request)
    gen_type, mode = GENERATE_ROUTES[kind]
    candidates = [w for w in registry.all() if w.meta["type"] == gen_type and w.meta["mode"] == mode]
    if not candidates:
        raise HTTPException(status_code=404, detail=f"No workflow registered for {kind}.")
    models_resp = await _models_payload()
    model_file_map = {m["id"]: m["file"] for m in models_resp["models"] if m["installed"]}
    workflow_id = payload.get("workflow_id")
    if workflow_id:
        wf = registry.get(workflow_id)
    else:
        model_id = payload.get("model")
        model_match = [w for w in candidates if model_id and w.meta.get("requires_model") == model_id]
        installed = [w for w in candidates if w.meta.get("requires_model", "sd15") in model_file_map]
        pool = model_match or installed or candidates
        non_experimental = [w for w in pool if not w.meta.get("experimental")]
        wf = non_experimental[0] if non_experimental else pool[0]
    if wf.meta["type"] != gen_type or wf.meta["mode"] != mode:
        raise HTTPException(status_code=422, detail=f"Workflow '{wf.meta['id']}' does not match {kind}.")

    min_vram = wf.meta.get("min_vram_gb")
    if min_vram:
        gpu = await _gpu_info() if await comfy.is_online() else {"gpu_vram_gb": None}
        vram = gpu.get("gpu_vram_gb")
        if vram is not None and vram < min_vram:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "insufficient_vram",
                        "message": f"Workflow '{wf.meta['id']}' needs about {min_vram}GB of VRAM; this GPU reports {vram}GB.",
                        "hint": wf.meta.get("install_hint")
                        or "Pick a smaller workflow or reduce resolution and frame count.",
                    }
                },
            )

    registry.validate(wf, payload, model_file_map)
    graph = wf.render(payload, model_file_map)
    if _load_settings().get("low_vram"):
        _apply_low_vram(graph, wf)
    object_info = await comfy.object_info()
    comfy_models = await comfy.list_models()
    registry.validate_nodes(wf, object_info, comfy_models)

    params = {k: v for k, v in payload.items() if k != "workflow_id"}
    params["save_to_drive"] = bool(_load_settings().get("save_to_drive"))
    job = jobs.submit(kind, {**params, "_graph": graph})
    return {"job_id": job.id, "status": job.status, "workflow_id": wf.meta["id"]}


def _apply_low_vram(graph: dict, wf) -> None:
    """Tame a rendered graph for small GPUs: batch 1, and halve width/height
    (min 320) on every latent/empty-image node. Purely local, no ComfyUI call."""
    for node in graph.values():
        ctype = node.get("class_type", "")
        inputs = node.setdefault("inputs", {})
        if "batch_size" in inputs:
            inputs["batch_size"] = 1
        if "EmptyLatent" in ctype or "EmptyLTXV" in ctype or ctype == "ADE_EmptyLatentImage":
            for field in ("width", "height"):
                if isinstance(inputs.get(field), (int, float)):
                    inputs[field] = max(320, int(inputs[field]) // 2)


# ---- websocket live progress -----------------------------------------------------
class JobEventHub:
    """Fans out job updates to connected /ws/jobs clients."""

    def __init__(self) -> None:
        self._clients: set = set()
        self._lock = threading.Lock()

    def connect(self, ws) -> None:
        with self._lock:
            self._clients.add(ws)

    def disconnect(self, ws) -> None:
        with self._lock:
            self._clients.discard(ws)

    def broadcast(self, job) -> None:
        payload = json.dumps({
            "event": "job_update",
            "job": job.public(),
        })
        if loop is None or not loop.is_running():
            return
        with self._lock:
            for ws in list(self._clients):
                try:
                    coro = ws.send_text(payload)
                    try:
                        running = asyncio.get_running_loop()
                    except RuntimeError:
                        running = None
                    if running is loop:
                        asyncio.ensure_future(coro)  # same loop: schedule directly
                    else:
                        asyncio.run_coroutine_threadsafe(coro, loop)
                except Exception:
                    self._clients.discard(ws)


hub = JobEventHub()
loop: asyncio.AbstractEventLoop | None = None


@app.on_event("startup")
async def _capture_loop():
    global loop
    loop = asyncio.get_running_loop()


@app.websocket("/ws/jobs")
async def ws_jobs(websocket: WebSocket):
    token = websocket.query_params.get("token") or websocket.headers.get("x-session-token")
    if not config.SESSION_TOKEN or token != config.SESSION_TOKEN:
        await websocket.accept()
        await websocket.close(code=4401)
        return
    await websocket.accept()
    hub.connect(websocket)
    try:
        while True:
            # Clients keep the socket open; any inbound message is ignored.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        hub.disconnect(websocket)


@app.post("/api/generate/image")
async def generate_image(request: Request):
    return await _handle_generate(request, "image", await request.json())


@app.post("/api/generate/image-to-image")
async def generate_image_to_image(request: Request):
    return await _handle_generate(request, "image-to-image", await request.json())


@app.post("/api/generate/video")
async def generate_video(request: Request):
    return await _handle_generate(request, "video", await request.json())


@app.post("/api/generate/image-to-video")
async def generate_image_to_video(request: Request):
    return await _handle_generate(request, "image-to-video", await request.json())


@app.get("/api/jobs")
async def list_jobs(request: Request, since: float | None = None):
    await require_auth(request)
    return {"jobs": [j.public() for j in jobs.list(since)]}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str, request: Request):
    await require_auth(request)
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job.public()


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, request: Request):
    await require_auth(request)
    job = jobs.cancel(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job.public()


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str, request: Request):
    await require_auth(request)
    if not jobs.delete(job_id):
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"deleted": job_id}


# ---- uploads & outputs ---------------------------------------------------------
_MAGIC = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF8", "image/gif"),
    (b"\x1aE\xdf\xa3", "video/webm"),
]


def _sniff_mime(data: bytes) -> str | None:
    for magic, mime in _MAGIC:
        if data.startswith(magic):
            return mime
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[4:8] == b"ftyp":
        return "video/mp4"
    return None


def _safe_filename(name: str) -> str:
    base = os.path.basename(name.replace("\\", "/"))
    base = re.sub(r"[^A-Za-z0-9_.-]", "_", base)
    if not base or base in (".", ".."):
        raise HTTPException(status_code=422, detail="Invalid filename.")
    return base


@app.post("/api/upload")
async def upload(request: Request, file: UploadFile = File(...)):
    await require_auth(request)
    data = await file.read()
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"Upload exceeds {config.MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit.")
    if not data:
        raise HTTPException(status_code=422, detail="Empty file.")
    mime = _sniff_mime(data)
    if mime not in config.UPLOAD_IMAGE_MIMES:
        raise HTTPException(status_code=422, detail="Only PNG, JPEG, WebP or GIF images are accepted.")
    safe = _safe_filename(file.filename or "upload")
    stamp = int(time.time() * 1000) % 10**9
    stored = f"{stamp}_{safe}"
    (config.UPLOAD_DIR / stored).write_bytes(data)
    return {"url": stored, "filename": stored, "size_bytes": len(data), "mime": mime}


@app.get("/api/output/{filename}")
async def output(filename: str, request: Request):
    await require_auth(request)
    safe = _safe_filename(filename)
    path = (config.OUTPUT_DIR / safe).resolve()
    if config.OUTPUT_DIR.resolve() not in path.parents:
        raise HTTPException(status_code=422, detail="Invalid filename.")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Output not found.")
    mime, _ = mimetypes.guess_type(safe)
    return FileResponse(path, media_type=mime or "application/octet-stream", filename=safe)


# ---- settings -------------------------------------------------------------------
@app.get("/api/settings")
async def get_settings(request: Request):
    await require_auth(request)
    settings = _load_settings()
    settings["drive_available"] = config.DRIVE_DIR is not None
    return settings


@app.post("/api/settings")
async def post_settings(request: Request):
    await require_auth(request)
    data = await request.json()
    current = _load_settings()
    for key in DEFAULT_SETTINGS:
        if key in data:
            current[key] = bool(data[key])
    _save_settings(current)
    return current


@app.post("/api/unload")
async def unload_models(request: Request):
    await require_auth(request)
    try:
        await comfy.free_memory()
    except ComfyUIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# ---- creative pipeline (LLM stages, no GPU) ---------------------------------------
@app.get("/api/llm/provider")
async def llm_provider_status(request: Request):
    await require_auth(request)
    provider = get_provider()
    # Never expose the API key or base URL credentials here.
    return {"provider": provider.name, "stages": list(STAGES)}


@app.post("/api/films/{project_id}/generate/{stage}")
async def generate_stage(project_id: str, stage: str, request: Request):
    await require_auth(request)
    data = await request.json() if await request.body() else {}
    try:
        entry = await run_stage(films, get_provider(), project_id, stage,
                                brief=str(data.get("brief", "")),
                                scene=data.get("scene"),
                                panel_count=int(data.get("panel_count", 6)))
    except LLMError as exc:
        status = 404 if exc.code in ("project_missing", "scene_missing") else (
            409 if exc.code in ("artifact_locked", "stage_dependency_not_approved", "stage_dependency_missing") else 502)
        raise HTTPException(status_code=status, detail=exc.to_dict())
    return {"kind": stage, **entry}


@app.get("/api/films/{project_id}/artifacts")
async def list_artifacts(project_id: str, request: Request):
    await require_auth(request)
    out = films.list_artifacts(project_id)
    if out is None:
        raise HTTPException(status_code=404, detail="Film project not found.")
    return {"artifacts": out}


@app.get("/api/films/{project_id}/artifacts/{kind}")
async def get_artifact(project_id: str, kind: str, request: Request, version: int | None = None):
    await require_auth(request)
    art = films.get_artifact(project_id, kind, version)
    if art is None:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return art


@app.patch("/api/films/{project_id}/artifacts/{kind}")
async def edit_artifact(project_id: str, kind: str, request: Request):
    await require_auth(request)
    data = await request.json()
    entry = films.edit_artifact(project_id, kind, data.get("data"))
    if entry is None:
        raise HTTPException(status_code=404, detail="Artifact not found or locked (approved).")
    return {"kind": kind, **entry}


@app.post("/api/films/{project_id}/artifacts/{kind}/approve")
async def approve_artifact(project_id: str, kind: str, request: Request):
    await require_auth(request)
    entry = films.set_artifact_status(project_id, kind, "approved")
    if entry is None:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return {"kind": kind, "status": "approved", "version": entry["version"]}


@app.post("/api/films/{project_id}/artifacts/{kind}/unapprove")
async def unapprove_artifact(project_id: str, kind: str, request: Request):
    await require_auth(request)
    entry = films.set_artifact_status(project_id, kind, None)
    if entry is None:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return {"kind": kind, "status": "draft", "version": entry["version"]}


@app.post("/api/films/{project_id}/artifacts/{kind}/versions/{version}/activate")
async def activate_artifact_version(project_id: str, kind: str, version: int, request: Request):
    await require_auth(request)
    entry = films.activate_version(project_id, kind, version)
    if entry is None:
        raise HTTPException(status_code=404, detail="Artifact version not found.")
    return {"kind": kind, "active_version": version}


@app.post("/api/films/{project_id}/apply-breakdown")
async def apply_breakdown(project_id: str, request: Request):
    await require_auth(request)
    result = films.apply_breakdown(project_id)
    if result is None:
        raise HTTPException(status_code=409, detail={
            "code": "breakdown_not_approved",
            "message": "An approved scene_breakdown artifact is required.",
            "hint": "Generate the scene breakdown and approve it, then apply."})
    return result


# ---- shot image generation (Phase 3A) ----------------------------------------------
def _shot_or_404(project_id: str, scene_id: str, shot_id: str) -> dict[str, Any]:
    project = films.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Film project not found.")
    scene = next((s for s in project.get("scenes", []) if s.get("id") == scene_id), None)
    if scene is None:
        raise HTTPException(status_code=404, detail="Scene not found.")
    shot = next((s for s in scene.get("shots", []) if s.get("id") == shot_id), None)
    if shot is None:
        raise HTTPException(status_code=404, detail="Shot not found.")
    return shot


# ---- continuity (Phase 4) -----------------------------------------------------------
@app.get("/api/films/{project_id}/continuity")
async def get_film_continuity(project_id: str, request: Request):
    await require_auth(request)
    data = films.get_continuity(project_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Film project not found.")
    return {"continuity": data}


@app.put("/api/films/{project_id}/continuity")
async def put_film_continuity(project_id: str, request: Request):
    """Edit-only film canon. Never triggers generation work."""
    await require_auth(request)
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=422, detail="Request body must be a JSON object.")
    result = films.update_film_continuity(project_id, data)
    if result is None:
        project = films.get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Film project not found.")
        raise HTTPException(status_code=422, detail="Invalid continuity data.")
    return {"continuity": result}


def _scene_or_404(project_id: str, scene_id: str) -> dict[str, Any]:
    project = films.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Film project not found.")
    scene = next((s for s in project.get("scenes", []) if s.get("id") == scene_id), None)
    if scene is None:
        raise HTTPException(status_code=404, detail="Scene not found.")
    return scene


@app.put("/api/films/{project_id}/scenes/{scene_id}/continuity")
async def put_scene_continuity(project_id: str, scene_id: str, request: Request):
    await require_auth(request)
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=422, detail="Request body must be a JSON object.")
    result = films.update_scene_continuity(project_id, scene_id, data)
    if result is None:
        _scene_or_404(project_id, scene_id)
        raise HTTPException(status_code=422, detail="Invalid continuity override data.")
    return {"continuity": result}


@app.put("/api/films/{project_id}/scenes/{scene_id}/shots/{shot_id}/continuity")
async def put_shot_continuity(project_id: str, scene_id: str, shot_id: str, request: Request):
    await require_auth(request)
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=422, detail="Request body must be a JSON object.")
    result = films.update_shot_continuity(project_id, scene_id, shot_id, data)
    if result is None:
        _shot_or_404(project_id, scene_id, shot_id)
        raise HTTPException(status_code=422, detail="Invalid continuity override data.")
    return {"continuity": result}


@app.get("/api/films/{project_id}/scenes/{scene_id}/shots/{shot_id}/continuity")
async def shot_continuity_context(project_id: str, scene_id: str, shot_id: str, request: Request):
    """Preview the resolved continuity context and the exact prompt fragments
    a generation would receive. Read-only: no generation is triggered."""
    await require_auth(request)
    _shot_or_404(project_id, scene_id, shot_id)
    project = films.get(project_id)
    scene = next((s for s in project.get("scenes", []) if s.get("id") == scene_id), None)
    shot = next((s for s in scene.get("shots", []) if s.get("id") == shot_id), None)
    resolved = continuity.resolve_continuity(project, scene, shot)
    return {"context": resolved, "parts": continuity.continuity_parts(resolved)}


@app.get("/api/films/{project_id}/scenes/{scene_id}/shots/{shot_id}/prompt")
async def shot_prompt(project_id: str, scene_id: str, shot_id: str, request: Request):
    """Preview the assembled image prompt for a shot; missing context is listed."""
    await require_auth(request)
    _shot_or_404(project_id, scene_id, shot_id)
    try:
        return build_shot_prompt(films, project_id, scene_id, shot_id)
    except ShotLookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/films/{project_id}/scenes/{scene_id}/shots/{shot_id}/generate")
async def generate_shot_image(project_id: str, scene_id: str, shot_id: str, request: Request):
    """Submit a text-to-image job for one storyboard shot through the existing
    JobManager/_handle_generate pipeline. An explicit user prompt always wins
    over the assembled context prompt."""
    await require_auth(request)
    _shot_or_404(project_id, scene_id, shot_id)
    data = await request.json() if await request.body() else {}
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object.")

    assembled = build_shot_prompt(films, project_id, scene_id, shot_id)
    user_prompt = str(data.get("prompt") or "").strip()
    prompt = user_prompt or assembled["prompt"]
    if not prompt:
        raise HTTPException(status_code=422, detail={
            "error": {
                "code": "empty_prompt",
                "message": "The shot has no prompt and no Film Project context to build one from.",
                "hint": "Write a prompt for the shot or fill in its Film Bible context.",
            }})

    negative = str(data.get("negative_prompt") if data.get("negative_prompt") is not None
                   else assembled["negative_prompt"] or "").strip()
    payload = {"prompt": prompt, "negative_prompt": negative}
    for key in ("workflow_id", "model", "seed", "steps", "cfg", "width", "height"):
        if data.get(key) is not None:
            payload[key] = data[key]

    result = await _handle_generate(request, "image", payload)
    generation = films.add_shot_generation(
        project_id, scene_id, shot_id,
        job_id=result["job_id"], workflow_id=result["workflow_id"],
        prompt=prompt, negative_prompt=negative,
        model=str(payload.get("model") or ""), params=payload)
    return {"job_id": result["job_id"], "status": result["status"],
            "workflow_id": result["workflow_id"], "generation": generation}


@app.post("/api/films/{project_id}/scenes/{scene_id}/shots/{shot_id}/jobs/{job_id}/attach")
async def attach_shot_job(project_id: str, scene_id: str, shot_id: str, job_id: str, request: Request):
    """Sync a finished job's outcome onto the shot's generation record.

    Safe to call repeatedly (idempotent); the UI calls it when the job poller
    reports completion, and it doubles as status recovery after a page reload.
    """
    await require_auth(request)
    _shot_or_404(project_id, scene_id, shot_id)
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.type != "image":
        raise HTTPException(status_code=422, detail="Only image jobs can be attached to a shot.")
    output = None
    if job.status == "completed" and job.outputs:
        first = job.outputs[0] if isinstance(job.outputs[0], dict) else {"filename": str(job.outputs[0])}
        output = {"filename": first.get("filename"), "url": first.get("url")}
    entry = films.attach_shot_output(project_id, scene_id, shot_id, job_id,
                                     status=job.status, output=output, error=job.error)
    if entry is None:
        raise HTTPException(status_code=404, detail="Generation record not found for this shot.")
    return {"generation": entry}


@app.post("/api/films/{project_id}/scenes/{scene_id}/shots/{shot_id}/images/{image_id}/select")
async def select_shot_image(project_id: str, scene_id: str, shot_id: str, image_id: str, request: Request):
    """Pick which generated image is the shot's current visual; nothing deleted."""
    await require_auth(request)
    shot = films.select_shot_image(project_id, scene_id, shot_id, image_id)
    if shot is None:
        raise HTTPException(status_code=404, detail="Shot or image not found.")
    return {"images": shot.get("images", [])}


# ---- shot video generation (Phase 3B) ----------------------------------------------
@app.get("/api/films/{project_id}/scenes/{scene_id}/shots/{shot_id}/video/prompt")
async def shot_video_prompt(project_id: str, scene_id: str, shot_id: str, request: Request):
    await require_auth(request)
    _shot_or_404(project_id, scene_id, shot_id)
    try:
        return build_shot_video_prompt(films, project_id, scene_id, shot_id)
    except ShotLookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/films/{project_id}/scenes/{scene_id}/shots/{shot_id}/video/generate")
async def generate_shot_video(project_id: str, scene_id: str, shot_id: str, request: Request):
    """Submit an image-to-video job for one storyboard shot.

    The start frame is the shot's selected generated image: its bytes are
    pushed to ComfyUI's input via the existing client upload, then the job is
    submitted through the shared _handle_generate/JobManager pipeline. No
    second queue, no workflow changes.
    """
    await require_auth(request)
    _shot_or_404(project_id, scene_id, shot_id)
    data = await request.json() if await request.body() else {}
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object.")

    assembled = build_shot_video_prompt(films, project_id, scene_id, shot_id)
    source = assembled.get("source_image")
    if not source or not source.get("filename"):
        raise HTTPException(status_code=422, detail={
            "error": {
                "code": "no_source_image",
                "message": "This shot has no selected generated image to animate.",
                "hint": "Generate an image for the shot and select it first.",
            }})

    user_prompt = str(data.get("prompt") or "").strip()
    prompt = user_prompt or assembled["prompt"]
    if not prompt:
        raise HTTPException(status_code=422, detail={
            "error": {
                "code": "empty_prompt",
                "message": "The shot has no prompt and no Film Project context to build one from.",
                "hint": "Write a prompt for the shot or fill in its Film Bible context.",
            }})
    negative = str(data.get("negative_prompt") if data.get("negative_prompt") is not None
                   else assembled["negative_prompt"] or "").strip()

    image_path = (config.OUTPUT_DIR / _safe_filename(str(source["filename"]))).resolve()
    if config.OUTPUT_DIR.resolve() not in image_path.parents or not image_path.is_file():
        raise HTTPException(status_code=404, detail="Selected image output not found.")
    image_bytes = image_path.read_bytes()
    try:
        comfy_image = await comfy.upload(image_path.name, image_bytes, "image/png")
    except ComfyUIError as exc:
        raise HTTPException(status_code=502, detail={"error": {"code": "comfyui_error", "message": str(exc)}})

    payload = {"prompt": prompt, "negative_prompt": negative, "image": comfy_image}
    for key in ("workflow_id", "seed", "frames", "fps", "width", "height"):
        if data.get(key) is not None:
            payload[key] = data[key]

    result = await _handle_generate(request, "image-to-video", payload)
    generation = films.add_shot_video_generation(
        project_id, scene_id, shot_id,
        job_id=result["job_id"], workflow_id=result["workflow_id"],
        prompt=prompt, negative_prompt=negative,
        source_image_id=str(source.get("id") or ""), params=payload)
    return {"job_id": result["job_id"], "status": result["status"],
            "workflow_id": result["workflow_id"], "generation": generation}


@app.post("/api/films/{project_id}/scenes/{scene_id}/shots/{shot_id}/video/jobs/{job_id}/attach")
async def attach_shot_video_job(project_id: str, scene_id: str, shot_id: str, job_id: str, request: Request):
    """Sync a finished video job's outcome onto the shot's generation record.

    Safe to call repeatedly (idempotent); only jobs recorded on this exact
    shot can be attached, so cross-project or cross-shot attachment is
    impossible.
    """
    await require_auth(request)
    _shot_or_404(project_id, scene_id, shot_id)
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.type not in ("video", "image-to-video"):
        raise HTTPException(status_code=422, detail="Only video jobs can be attached to a shot video.")
    output = None
    if job.status == "completed" and job.outputs:
        first = job.outputs[0] if isinstance(job.outputs[0], dict) else {"filename": str(job.outputs[0])}
        output = {"filename": first.get("filename"), "url": first.get("url")}
    entry = films.attach_shot_video_output(project_id, scene_id, shot_id, job_id,
                                           status=job.status, output=output, error=job.error)
    if entry is None:
        raise HTTPException(status_code=404, detail="Video generation record not found for this shot.")
    return {"generation": entry}


@app.post("/api/films/{project_id}/scenes/{scene_id}/shots/{shot_id}/videos/{video_id}/select")
async def select_shot_video(project_id: str, scene_id: str, shot_id: str, video_id: str, request: Request):
    """Pick which generated video is the shot's preferred output; nothing deleted."""
    await require_auth(request)
    shot = films.select_shot_video(project_id, scene_id, shot_id, video_id)
    if shot is None:
        raise HTTPException(status_code=404, detail="Shot or video not found.")
    return {"videos": shot.get("videos", [])}


# ---- film projects ---------------------------------------------------------------
@app.get("/api/films")
async def list_films(request: Request):
    await require_auth(request)
    return {"projects": films.list()}


@app.post("/api/films")
async def create_film(request: Request):
    await require_auth(request)
    data = await request.json()
    title = str(data.get("title", "")).strip()
    if not title:
        raise HTTPException(status_code=422, detail="A project title is required.")
    if len(title) > 120:
        raise HTTPException(status_code=422, detail="Project title too long (max 120 characters).")
    bible = data.get("bible") if isinstance(data.get("bible"), dict) else None
    return films.create(title, bible)


@app.get("/api/films/{project_id}")
async def get_film(project_id: str, request: Request):
    await require_auth(request)
    project = films.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Film project not found.")
    return project


@app.patch("/api/films/{project_id}")
async def update_film(project_id: str, request: Request):
    await require_auth(request)
    if films.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Film project not found.")
    data = await request.json()
    project = films.update(project_id, data)
    if project is None:
        raise HTTPException(status_code=404, detail="Film project not found.")
    return project


@app.delete("/api/films/{project_id}")
async def delete_film(project_id: str, request: Request):
    await require_auth(request)
    if not films.delete(project_id):
        raise HTTPException(status_code=404, detail="Film project not found.")
    return {"deleted": project_id}


@app.post("/api/films/{project_id}/scenes")
async def add_scene(project_id: str, request: Request):
    await require_auth(request)
    data = await request.json()
    scene = films.add_scene(project_id, str(data.get("title", "")), str(data.get("bible_refs", "")))
    if scene is None:
        raise HTTPException(status_code=404, detail="Film project not found.")
    return scene


@app.delete("/api/films/{project_id}/scenes/{scene_id}")
async def delete_scene(project_id: str, scene_id: str, request: Request):
    await require_auth(request)
    if not films.delete_scene(project_id, scene_id):
        raise HTTPException(status_code=404, detail="Scene not found.")
    return {"deleted": scene_id}


@app.post("/api/films/{project_id}/scenes/{scene_id}/shots")
async def add_shot(project_id: str, scene_id: str, request: Request):
    await require_auth(request)
    data = await request.json()
    prompt = str(data.get("prompt", "")).strip()
    if not prompt:
        raise HTTPException(status_code=422, detail="A shot prompt is required.")
    shot = films.add_shot(project_id, scene_id, prompt,
                          model=str(data.get("model", "sd15")),
                          params=data.get("params") if isinstance(data.get("params"), dict) else None)
    if shot is None:
        raise HTTPException(status_code=404, detail="Film project or scene not found.")
    return shot


@app.post("/api/films/{project_id}/scenes/{scene_id}/shots/{shot_id}/status")
async def set_shot_status(project_id: str, scene_id: str, shot_id: str, request: Request):
    await require_auth(request)
    data = await request.json()
    shot = films.set_shot_status(project_id, scene_id, shot_id,
                                 str(data.get("status", "")), approved_by=data.get("approved_by"))
    if shot is None:
        raise HTTPException(status_code=404, detail="Shot not found or invalid status.")
    return shot
    return {"unloaded": True}

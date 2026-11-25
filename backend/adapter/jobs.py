"""Generation job queue.

One active GPU job by default (VRAM contention), FIFO, persisted to JSON so
the queue survives adapter restarts within the same Colab runtime.
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
import time
import uuid
from collections import deque
from typing import Any, Callable

from . import config
from pathlib import Path
from typing import Any

from . import config
from .comfyui import ComfyUIClient, ComfyUIError
from .workflows import WorkflowValidationError


def _now() -> float:
    return time.time()


class Job:
    STATUS_ORDER = ("queued", "loading_model", "generating", "processing", "saving", "completed", "failed", "cancelled")

    def __init__(self, job_type: str, params: dict[str, Any]):
        self.id = uuid.uuid4().hex[:12]
        self.type = job_type
        self.params = params
        self.status = "queued"
        self.stage = "queued"
        self.progress: float | None = None
        self.outputs: list[dict[str, Any]] = []
        self.error: str | None = None
        self.error_hint: str | None = None
        self.created_at = _now()
        self.started_at: float | None = None
        self.finished_at: float | None = None
        self._cancel = threading.Event()

    def public(self) -> dict[str, Any]:
        return {
            "job_id": self.id,
            "type": self.type,
            "status": self.status,
            "stage": self.stage,
            "progress": self.progress,
            "outputs": self.outputs,
            "error": self.error,
            "error_hint": self.error_hint,
            "params": self.params,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class JobManager:
    def __init__(self, client: ComfyUIClient, max_concurrent: int | None = None,
                 persist_path: Path | None = None,
                 on_change: "Callable[[Job], None] | None" = None):
        self.client = client
        self.max_concurrent = max_concurrent or config.MAX_CONCURRENT_JOBS
        self.jobs: dict[str, Job] = {}
        self.queue: deque[str] = deque()
        self.lock = threading.Lock()
        self._shutdown = threading.Event()
        self.persist_path = persist_path or (config.STATE_DIR / "jobs.json")
        self.on_change = on_change
        self._notified: set[Job] = set()
        self._load()
        self.worker = threading.Thread(target=self._run, name="job-worker", daemon=True)
        self.worker.start()

    # ---- persistence -----------------------------------------------------
    def _load(self) -> None:
        if not self.persist_path.exists():
            return
        try:
            raw = json.loads(self.persist_path.read_text())
        except (OSError, ValueError):
            return
        for item in raw:
            job = Job(item.get("type", "image"), item.get("params", {}))
            job.id = item["job_id"]
            job.status = item.get("status", "failed")
            # Anything in flight when the adapter died is failed, not running.
            if job.status in ("queued", "loading_model", "generating", "processing", "saving"):
                job.status = "failed"
                job.error = "Adapter restarted while this job was running."
            job.outputs = item.get("outputs", [])
            self.jobs[job.id] = job

    def _save(self) -> None:
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock:
            data = [j.public() for j in self.jobs.values()]
            changed = [j for j in self.jobs.values() if j not in self._notified]
        tmp = self.persist_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data))
        os.replace(tmp, self.persist_path)
        if self.on_change:
            for job in changed:
                self._notified.add(job)
                try:
                    self.on_change(job)
                except Exception:
                    pass  # listeners must never break the job loop

    # ---- queueing --------------------------------------------------------
    def submit(self, job_type: str, params: dict[str, Any]) -> Job:
        with self.lock:
            active = sum(1 for j in self.jobs.values() if j.status in ("loading_model", "generating", "processing", "saving"))
            if active >= self.max_concurrent:
                raise RuntimeError("queue_full")
        job = Job(job_type, params)
        with self.lock:
            self.jobs[job.id] = job
            self.queue.append(job.id)
        self._save()
        return job

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def list(self, since: float | None = None) -> list[Job]:
        jobs = sorted(self.jobs.values(), key=lambda j: j.created_at)
        if since is not None:
            jobs = [j for j in jobs if j.created_at > since]
        return jobs

    def cancel(self, job_id: str) -> Job | None:
        job = self.jobs.get(job_id)
        if job is None:
            return None
        if job.status == "queued":
            with self.lock:
                if job.id in self.queue:
                    self.queue.remove(job.id)
            job.status = "cancelled"
            job.stage = "cancelled"
            job.finished_at = _now()
            self._save()
        elif job.status in ("loading_model", "generating", "processing", "saving"):
            job._cancel.set()
        return job

    def delete(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if job is None:
            return False
        self.cancel(job_id)
        with self.lock:
            self.jobs.pop(job_id, None)
        self._save()
        return True

    def counts(self) -> dict[str, int]:
        counts = {s: 0 for s in Job.STATUS_ORDER}
        for job in self.jobs.values():
            counts[job.status] = counts.get(job.status, 0) + 1
        return counts

    # ---- worker ----------------------------------------------------------
    def _run(self) -> None:
        while not self._shutdown.is_set():
            try:
                job_id = self.queue.popleft()
            except IndexError:
                time.sleep(0.3)
                continue
            job = self.jobs.get(job_id)
            if job is None or job.status != "queued":
                continue
            self._execute(job)

    def _execute(self, job: Job) -> None:
        job.started_at = _now()
        job.status = "loading_model"
        job.stage = "loading_model"
        params = job.params
        try:
            graph = params.pop("_graph")
            prompt_id = asyncio.run(self.client.submit(graph))
            job.stage = "generating"
            job.status = "generating"

            def set_stage(stage: str) -> None:
                if job.stage not in ("generating", "processing"):
                    job.stage = stage

            history = asyncio.run(
                self.client.wait_for_history(prompt_id, should_continue=lambda: not job._cancel.is_set(), on_stage=set_stage)
            )
            if job._cancel.is_set():
                self._finish_cancelled(job)
                return
            job.status = "processing"
            job.stage = "processing"
            job.outputs = asyncio.run(self._collect_outputs(history))
            job.status = "saving"
            job.stage = "saving"
            job.outputs = asyncio.run(self._persist_outputs(job, history))
            job.status = "completed"
            job.stage = "completed"
            if self._settings_snapshot().get("unload_after_job"):
                try:
                    asyncio.run(self.client.free_memory())
                except ComfyUIError:
                    pass  # unload is best-effort; the job itself succeeded
        except WorkflowValidationError as exc:
            job.status = "failed"
            job.error = exc.message
            job.error_hint = exc.hint
        except ComfyUIError as exc:
            if job._cancel.is_set():
                self._finish_cancelled(job)
            else:
                job.status = "failed"
                job.error = str(exc)
                job.error_hint = "Your Colab runtime may have disconnected. Reconnect Colab and refresh the backend connection."
        except Exception as exc:  # noqa: BLE001 - surface any worker failure on the job
            job.status = "failed"
            job.error = f"Unexpected adapter error: {exc}"
        finally:
            job.finished_at = _now()
            job.params.pop("_graph", None)
            self._save()

    def _finish_cancelled(self, job: Job) -> None:
        job.status = "cancelled"
        job.stage = "cancelled"
        job.finished_at = _now()

    async def _collect_outputs(self, history: dict[str, Any]) -> list[dict[str, Any]]:
        raw: list[dict[str, Any]] = []
        for node_output in history.get("outputs", {}).values():
            for key in ("images", "gifs", "videos"):
                for item in node_output.get(key, []):
                    raw.append(item)
        return raw

    async def _persist_outputs(self, job: Job, history: dict[str, Any]) -> list[dict[str, Any]]:
        saved: list[dict[str, Any]] = []
        for item in await self._collect_outputs(history):
            filename = item.get("filename", "")
            subfolder = item.get("subfolder", "")
            folder_type = item.get("type", "output")
            try:
                content = await self.client.download_output(filename, subfolder, folder_type)
            except ComfyUIError as exc:
                job.error = f"Failed to fetch output {filename}: {exc}"
                continue
            out_name = f"{job.id}_{filename}"
            (config.OUTPUT_DIR / out_name).write_bytes(content)
            saved.append({
                "filename": out_name,
                "type": "video" if out_name.lower().endswith((".mp4", ".webm", ".gif")) else "image",
                "size_bytes": len(content),
            })
        if saved:
            self._mirror_to_drive(job, saved)
        return saved

    def _settings_snapshot(self) -> dict[str, Any]:
        """Read the persisted settings file directly (no import cycle with main)."""
        try:
            return json.loads((config.STATE_DIR / "settings.json").read_text())
        except (OSError, ValueError):
            return {}

    def _mirror_to_drive(self, job: Job, saved: list[dict[str, Any]]) -> None:
        """Copy finished outputs and a metadata sidecar to Google Drive, when mounted.

        Failures are recorded on the job but never fail the generation itself:
        the local copy in OUTPUT_DIR is already complete.
        """
        drive = config.DRIVE_DIR
        if drive is None or not job.params.get("save_to_drive"):
            return
        try:
            out_dir = drive / "outputs"
            out_dir.mkdir(parents=True, exist_ok=True)
            for item in saved:
                src = config.OUTPUT_DIR / item["filename"]
                (out_dir / item["filename"]).write_bytes(src.read_bytes())
            meta = {
                "job_id": job.id,
                "type": job.type,
                "params": {k: v for k, v in job.params.items() if not k.startswith("_")},
                "created_at": job.created_at,
                "outputs": saved,
            }
            (out_dir / f"{job.id}.json").write_text(json.dumps(meta, indent=2))
        except OSError as exc:
            job.error_hint = f"Google Drive save failed (output kept locally): {exc}"

    def shutdown(self) -> None:
        self._shutdown.set()

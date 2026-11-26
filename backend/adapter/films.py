"""Film Project data model and store.

Flat-JSON persistence under STATE_DIR/films/<project_id>/project.json, mirroring
the jobs.json sidecar pattern: no database while the studio is single-user on
one Colab VM. A project holds its Film Bible (logline, style guide, characters,
world), an ordered scene list and, per scene, shots with prompt/model/approval
state that later phases map onto the existing generation pipeline.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from . import config

SHOT_STATUSES = ("draft", "awaiting_approval", "approved", "rejected")
ARTIFACT_KINDS = ("concept", "treatment", "screenplay", "scene_breakdown", "storyboard")
ARTIFACT_STATUSES = ("draft", "approved")


def _now() -> float:
    return time.time()


class FilmStore:
    def __init__(self, root: Path | None = None):
        self.root = root or (config.STATE_DIR / "films")
        self.lock = threading.Lock()

    # ---- paths -----------------------------------------------------------
    def _dir(self, project_id: str) -> Path:
        return self.root / project_id

    def _path(self, project_id: str) -> Path:
        return self._dir(project_id) / "project.json"

    # ---- persistence -----------------------------------------------------
    def _read(self, project_id: str) -> dict[str, Any] | None:
        path = self._path(project_id)
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError):
            return None

    def _write(self, project: dict[str, Any]) -> None:
        path = self._path(project["id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(project, indent=1))
        os.replace(tmp, path)

    # ---- projects --------------------------------------------------------
    def list(self) -> list[dict[str, Any]]:
        with self.lock:
            projects = []
            if self.root.exists():
                for d in sorted(self.root.iterdir()):
                    if d.is_dir():
                        p = self._read(d.name)
                        if p:
                            projects.append(self._summary(p))
            return projects

    @staticmethod
    def _summary(p: dict[str, Any]) -> dict[str, Any]:
        shots = [s for sc in p.get("scenes", []) for s in sc.get("shots", [])]
        return {
            "id": p["id"],
            "title": p["title"],
            "logline": p.get("bible", {}).get("logline"),
            "scene_count": len(p.get("scenes", [])),
            "shot_count": len(shots),
            "approved_shots": sum(1 for s in shots if s.get("status") == "approved"),
            "created_at": p.get("created_at"),
            "updated_at": p.get("updated_at"),
        }

    def create(self, title: str, bible: dict[str, Any] | None = None) -> dict[str, Any]:
        now = _now()
        with self.lock:
            project_id = f"{now:.0f}-{uuid.uuid4().hex[:8]}"
            project = {
                "id": project_id,
                "title": title.strip() or "Untitled",
                "bible": bible or {"logline": "", "style_guide": "", "characters": [], "world": ""},
                "scenes": [],
                "created_at": now,
                "updated_at": now,
            }
            self._write(project)
            return project

    def get(self, project_id: str) -> dict[str, Any] | None:
        with self.lock:
            return self._read(project_id)

    def update(self, project_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        with self.lock:
            project = self._read(project_id)
            if project is None:
                return None
            if "title" in patch:
                project["title"] = str(patch["title"]).strip() or project["title"]
            if "bible" in patch and isinstance(patch["bible"], dict):
                project["bible"].update(patch["bible"])
            project["updated_at"] = _now()
            self._write(project)
            return project

    def delete(self, project_id: str) -> bool:
        with self.lock:
            d = self._dir(project_id)
            if not d.exists():
                return False
            import shutil
            shutil.rmtree(d)
            return True

    # ---- scenes ----------------------------------------------------------
    def add_scene(self, project_id: str, title: str, bible_refs: str = "") -> dict[str, Any] | None:
        with self.lock:
            project = self._read(project_id)
            if project is None:
                return None
            scene = {
                "id": uuid.uuid4().hex[:8],
                "order": len(project["scenes"]),
                "title": title.strip() or f"Scene {len(project['scenes']) + 1}",
                "bible_refs": bible_refs,
                "shots": [],
            }
            project["scenes"].append(scene)
            project["updated_at"] = _now()
            self._write(project)
            return scene

    def delete_scene(self, project_id: str, scene_id: str) -> bool:
        with self.lock:
            project = self._read(project_id)
            if project is None:
                return False
            before = len(project["scenes"])
            project["scenes"] = [s for s in project["scenes"] if s["id"] != scene_id]
            if len(project["scenes"]) == before:
                return False
            for i, s in enumerate(project["scenes"]):
                s["order"] = i
            project["updated_at"] = _now()
            self._write(project)
            return True

    # ---- shots -----------------------------------------------------------
    def add_shot(self, project_id: str, scene_id: str, prompt: str,
                 model: str = "sd15", params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        with self.lock:
            project = self._read(project_id)
            scene = self._find_scene(project, scene_id) if project else None
            if scene is None:
                return None
            shot = {
                "id": uuid.uuid4().hex[:8],
                "prompt": prompt,
                "model": model,
                "params": params or {},
                "status": "draft",
                "artifact_ids": [],
                "approved_by": None,
                "created_at": _now(),
            }
            scene["shots"].append(shot)
            project["updated_at"] = _now()
            self._write(project)
            return shot

    def set_shot_status(self, project_id: str, scene_id: str, shot_id: str,
                        status: str, approved_by: str | None = None) -> dict[str, Any] | None:
        if status not in SHOT_STATUSES:
            return None
        with self.lock:
            project = self._read(project_id)
            scene = self._find_scene(project, scene_id) if project else None
            shot = next((s for s in scene["shots"] if s["id"] == shot_id), None) if scene else None
            if shot is None:
                return None
            shot["status"] = status
            shot["approved_by"] = approved_by if status == "approved" else None
            project["updated_at"] = _now()
            self._write(project)
            return shot

    # ---- shot image generations (Phase 3A) --------------------------------
    @staticmethod
    def _find_shot(project: dict[str, Any], scene_id: str, shot_id: str) -> dict[str, Any] | None:
        scene = next((s for s in project.get("scenes", []) if s.get("id") == scene_id), None)
        if scene is None:
            return None
        return next((s for s in scene.get("shots", []) if s.get("id") == shot_id), None)

    def add_shot_generation(self, project_id: str, scene_id: str, shot_id: str,
                            job_id: str, workflow_id: str, prompt: str,
                            negative_prompt: str = "", model: str = "",
                            params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Record a submitted generation job on the shot (status: submitted)."""
        with self.lock:
            project = self._read(project_id)
            if project is None:
                return None
            shot = self._find_shot(project, scene_id, shot_id)
            if shot is None:
                return None
            shot.setdefault("generations", []).append({
                "job_id": job_id,
                "workflow_id": workflow_id,
                "model": model,
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "params": params or {},
                "status": "submitted",
                "output": None,
                "created_at": _now(),
            })
            project["updated_at"] = _now()
            self._write(project)
            return shot["generations"][-1]

    def attach_shot_output(self, project_id: str, scene_id: str, shot_id: str,
                           job_id: str, status: str, output: dict[str, Any] | None = None,
                           error: str | None = None) -> dict[str, Any] | None:
        """Update a submitted generation with its outcome.

        Completed image outputs are appended to shot["images"] and the newest
        one becomes the selected visual. Nothing is ever removed: earlier
        generations stay in the history, and an approved shot's images are
        never modified except by an explicit select call.
        """
        with self.lock:
            project = self._read(project_id)
            if project is None:
                return None
            shot = self._find_shot(project, scene_id, shot_id)
            if shot is None:
                return None
            entry = next((g for g in shot.get("generations", []) if g.get("job_id") == job_id), None)
            if entry is None:
                return None
            if entry.get("status") not in ("submitted",):
                return entry  # already attached; attaching is idempotent
            entry["status"] = status
            if error:
                entry["error"] = error
            if status == "completed" and output:
                entry["output"] = output
                image = {
                    "id": uuid.uuid4().hex[:8],
                    "job_id": job_id,
                    "filename": output.get("filename"),
                    "selected": False,
                    "created_at": _now(),
                }
                shot.setdefault("images", []).append(image)
                if not any(img.get("selected") for img in shot["images"][:-1]):
                    image["selected"] = True
            project["updated_at"] = _now()
            self._write(project)
            return entry

    def select_shot_image(self, project_id: str, scene_id: str, shot_id: str,
                          image_id: str) -> dict[str, Any] | None:
        with self.lock:
            project = self._read(project_id)
            if project is None:
                return None
            shot = self._find_shot(project, scene_id, shot_id)
            if shot is None or not any(img.get("id") == image_id for img in shot.get("images", [])):
                return None
            for img in shot["images"]:
                img["selected"] = img.get("id") == image_id
            project["updated_at"] = _now()
            self._write(project)
            return shot

    # ---- artifacts (versioned creative stages) ----------------------------
    def _ensure_artifacts(self, project: dict[str, Any]) -> None:
        project.setdefault("artifacts", {})

    def add_version(self, project_id: str, kind: str, data: Any, *,
                    source: str = "agent", usage: dict | None = None) -> dict[str, Any] | None:
        """Append a new version of an artifact kind and make it active.

        An approved artifact is stable: the caller must unapprove it first,
        so regeneration can never silently replace approved creative work.
        """
        if kind not in ARTIFACT_KINDS:
            return None
        with self.lock:
            project = self._read(project_id)
            if project is None:
                return None
            self._ensure_artifacts(project)
            bucket = project["artifacts"].setdefault(kind, {"versions": [], "active": None, "approved_version": None})
            current = self._artifact_by_version(bucket, bucket.get("active"))
            if current and current.get("status") == "approved":
                return None
            version = (max((v["version"] for v in bucket["versions"]), default=0)) + 1
            entry = {
                "version": version,
                "data": data,
                "source": source,
                "status": "draft",
                "created_at": _now(),
            }
            if usage:
                entry["usage"] = usage
            bucket["versions"].append(entry)
            bucket["active"] = version
            project["updated_at"] = _now()
            self._write(project)
            return entry

    @staticmethod
    def _artifact_by_version(bucket: dict, version: Any) -> dict | None:
        return next((v for v in bucket.get("versions", []) if v["version"] == version), None)

    def get_artifact(self, project_id: str, kind: str, version: int | None = None) -> dict | None:
        if kind not in ARTIFACT_KINDS:
            return None
        with self.lock:
            project = self._read(project_id)
            if project is None:
                return None
            bucket = project.get("artifacts", {}).get(kind)
            if not bucket:
                return None
            entry = self._artifact_by_version(bucket, version if version is not None else bucket.get("active"))
            if entry is None:
                return None
            return {
                "kind": kind,
                "project_id": project_id,
                **entry,
                "versions": [{"version": v["version"], "source": v["source"],
                              "status": v["status"], "created_at": v["created_at"]}
                             for v in bucket["versions"]],
                "active_version": bucket.get("active"),
                "approved_version": bucket.get("approved_version"),
            }

    def edit_artifact(self, project_id: str, kind: str, data: Any) -> dict | None:
        """Manual edit of the active artifact: saves a new version, keeps history."""
        if kind not in ARTIFACT_KINDS:
            return None
        with self.lock:
            project = self._read(project_id)
            if project is None:
                return None
            self._ensure_artifacts(project)
            bucket = project["artifacts"].setdefault(kind, {"versions": [], "active": None, "approved_version": None})
            active = self._artifact_by_version(bucket, bucket.get("active"))
            if active is None or active.get("status") == "approved":
                return None
            version = (max((v["version"] for v in bucket["versions"]), default=0)) + 1
            entry = {"version": version, "data": data, "source": "user_edit",
                     "status": "draft", "created_at": _now()}
            bucket["versions"].append(entry)
            bucket["active"] = version
            project["updated_at"] = _now()
            self._write(project)
            return entry

    def set_artifact_status(self, project_id: str, kind: str,
                            status: str | None = None, version: int | None = None) -> dict | None:
        """Approve (status='approved') or unapprove (status=None) the active artifact."""
        if kind not in ARTIFACT_KINDS:
            return None
        with self.lock:
            project = self._read(project_id)
            if project is None:
                return None
            bucket = project.get("artifacts", {}).get(kind)
            if not bucket:
                return None
            entry = self._artifact_by_version(bucket, version if version is not None else bucket.get("active"))
            if entry is None:
                return None
            if status == "approved":
                entry["status"] = "approved"
                bucket["approved_version"] = entry["version"]
            elif status is None:
                entry["status"] = "draft"
                if bucket.get("approved_version") == entry["version"]:
                    bucket["approved_version"] = None
            else:
                return None
            project["updated_at"] = _now()
            self._write(project)
            return entry

    def activate_version(self, project_id: str, kind: str, version: int) -> dict | None:
        with self.lock:
            project = self._read(project_id)
            if project is None:
                return None
            bucket = project.get("artifacts", {}).get(kind)
            entry = self._artifact_by_version(bucket, version) if bucket else None
            if entry is None:
                return None
            bucket["active"] = version
            project["updated_at"] = _now()
            self._write(project)
            return entry

    def list_artifacts(self, project_id: str) -> list[dict] | None:
        with self.lock:
            project = self._read(project_id)
            if project is None:
                return None
            out = []
            for kind in ARTIFACT_KINDS:
                bucket = project.get("artifacts", {}).get(kind)
                if not bucket or not bucket.get("versions"):
                    continue
                active = self._artifact_by_version(bucket, bucket.get("active"))
                out.append({
                    "kind": kind,
                    "active_version": bucket.get("active"),
                    "approved_version": bucket.get("approved_version"),
                    "status": active.get("status") if active else None,
                    "version_count": len(bucket["versions"]),
                })
            return out

    # ---- scene breakdown application -------------------------------------
    def apply_breakdown(self, project_id: str) -> dict | None:
        """Append scenes from the active scene_breakdown artifact.

        Existing scenes (and their shots/approvals) are never deleted or
        reordered by this — approved scenes stay stable. Returns counts.
        """
        with self.lock:
            project = self._read(project_id)
            if project is None:
                return None
            bucket = project.get("artifacts", {}).get("scene_breakdown")
            active = self._artifact_by_version(bucket, bucket.get("active")) if bucket else None
            if active is None or active.get("status") != "approved":
                return None
            scenes = active["data"].get("scenes") if isinstance(active["data"], dict) else None
            if not isinstance(scenes, list):
                return None
            added = 0
            for sc in scenes:
                scene = {
                    "id": uuid.uuid4().hex[:8],
                    "order": len(project["scenes"]),
                    "title": str(sc.get("title") or sc.get("slugline") or f"Scene {len(project['scenes']) + 1}"),
                    "bible_refs": json.dumps(sc.get("characters", [])),
                    "breakdown": sc,
                    "shots": [],
                }
                project["scenes"].append(scene)
                added += 1
            project["updated_at"] = _now()
            self._write(project)
            return {"scenes_added": added, "scene_count": len(project["scenes"])}

    # ---- helpers ---------------------------------------------------------
    @staticmethod
    def _find_scene(project: dict[str, Any] | None, scene_id: str) -> dict[str, Any] | None:
        if project is None:
            return None
        return next((s for s in project["scenes"] if s["id"] == scene_id), None)

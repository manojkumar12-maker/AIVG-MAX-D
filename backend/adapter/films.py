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

    # ---- helpers ---------------------------------------------------------
    @staticmethod
    def _find_scene(project: dict[str, Any] | None, scene_id: str) -> dict[str, Any] | None:
        if project is None:
            return None
        return next((s for s in project["scenes"] if s["id"] == scene_id), None)

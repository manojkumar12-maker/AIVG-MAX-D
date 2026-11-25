"""Workflow registry: load templates, validate params, render ComfyUI graphs."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import config, models_registry


class WorkflowValidationError(Exception):
    def __init__(self, code: str, message: str, hint: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint


class Workflow:
    def __init__(self, meta: dict[str, Any], template: dict[str, Any]):
        self.meta = meta
        self.template = template

    def public(self) -> dict[str, Any]:
        return {k: v for k, v in self.meta.items() if k != "param_map"}

    def render(self, params: dict[str, Any], model_file_map: dict[str, str]) -> dict[str, Any]:
        """Return a ComfyUI /prompt graph with params substituted via param_map."""
        graph = json.loads(json.dumps(self.template))  # deep copy
        for key, value in params.items():
            if value is None:
                continue
            mapping = self.meta.get("param_map", {}).get(key)
            if not mapping:
                continue
            node = graph[mapping["node"]]
            if key == "model":
                model_id = value
                mapped = model_file_map.get(model_id, value)
                node["inputs"][mapping["field"]] = mapped
            else:
                node["inputs"][mapping["field"]] = value
        return graph


class WorkflowRegistry:
    def __init__(self, workflow_dir: Path | None = None):
        self.workflow_dir = workflow_dir or config.WORKFLOW_DIR
        self.workflows: dict[str, Workflow] = {}
        self.reload()

    def reload(self) -> None:
        self.workflows = {}
        for path in sorted(self.workflow_dir.glob("*.json")):
            data = json.loads(path.read_text())
            meta = data.pop("_meta")
            self.workflows[meta["id"]] = Workflow(meta, data)

    def get(self, workflow_id: str) -> Workflow:
        wf = self.workflows.get(workflow_id)
        if wf is None:
            raise WorkflowValidationError("missing_workflow", f"Unknown workflow '{workflow_id}'.")
        return wf

    def for_type(self, gen_type: str) -> list[Workflow]:
        return [w for w in self.workflows.values() if w.meta["type"] == gen_type and not w.meta.get("experimental")]

    def all(self) -> list[Workflow]:
        return list(self.workflows.values())

    def validate(self, wf: Workflow, params: dict[str, Any], model_file_map: dict[str, str]) -> None:
        """Raise WorkflowValidationError with a user-actionable message on any problem."""
        meta = wf.meta
        # Required params that this workflow actually maps.
        required = {"prompt"} | ({"image"} if meta.get("needs_upload") else set())
        for key in required:
            value = params.get(key)
            if not value or not str(value).strip():
                raise WorkflowValidationError("validation", f"'{key}' is required for workflow '{meta['id']}'.")

        model_id = params.get("model") or meta.get("requires_model")
        model = models_registry.MODEL_BY_ID.get(model_id)
        if model is None:
            raise WorkflowValidationError("validation", f"Unknown model '{model_id}'.")
        if not model_file_map.get(model_id):
            raise WorkflowValidationError(
                "missing_model",
                "This workflow requires a model that is not installed.",
                hint=f"Model '{model['name']}' is missing. {meta.get('install_hint', '')}".strip(),
            )
        if params.get("model") and params["model"] != meta.get("requires_model"):
            raise WorkflowValidationError(
                "validation",
                f"Model '{params['model']}' cannot run workflow '{meta['id']}' (requires '{meta['requires_model']}').",
            )

        width = params.get("width")
        height = params.get("height")
        for name, value, maximum in (("width", width, meta.get("max_width")), ("height", height, meta.get("max_height"))):
            if value is None:
                continue
            if not isinstance(value, int) or value < 64:
                raise WorkflowValidationError("validation", f"{name} must be an integer >= 64.")
            if value % 8 != 0:
                raise WorkflowValidationError("validation", f"{name}={value} is not a multiple of 8.")
            if maximum and value > maximum:
                raise WorkflowValidationError(
                    "validation",
                    f"{name}={value} exceeds this workflow's maximum of {maximum}.",
                    hint="Use a lower resolution or a different aspect ratio preset.",
                )
        frames = params.get("frames")
        if frames is not None:
            if not isinstance(frames, int) or not (8 <= frames <= meta.get("max_frames", 121)):
                raise WorkflowValidationError(
                    "validation",
                    f"frames must be between 8 and {meta.get('max_frames', 121)}.",
                )
        if params.get("batch_size") is not None and not (1 <= params["batch_size"] <= 4):
            raise WorkflowValidationError("validation", "batch_size must be between 1 and 4.")

    def validate_nodes(self, wf: Workflow, object_info: dict[str, Any], comfy_models: dict[str, list[str]]) -> None:
        """Cross-check the rendered graph against the live ComfyUI node catalog."""
        missing = sorted(
            {node.get("class_type") for node in wf.template.values() if node.get("class_type") not in object_info}
        )
        if missing:
            raise WorkflowValidationError(
                "missing_dependency",
                "Required ComfyUI node is missing. Install the dependency from the notebook and restart the backend.",
                hint=f"Missing custom node classes: {', '.join(missing)}. {wf.meta.get('install_hint', '')}".strip(),
            )
        # Check the model file exists in the relevant ComfyUI folder listing.
        model = models_registry.MODEL_BY_ID.get(wf.meta.get("requires_model"))
        if model:
            folder = model["file"].split("/")[0]
            available = comfy_models.get(folder, [])
            if not any(model["file"].split("/")[-1] in a for a in available):
                raise WorkflowValidationError(
                    "missing_model",
                    "This workflow requires a model that is not installed.",
                    hint=f"Expected file {model['file']}. {wf.meta.get('install_hint', '')}".strip(),
                )

"""Thin async client for the local ComfyUI server.

The adapter never exposes ComfyUI directly: only these calls are used.
"""
from __future__ import annotations

import asyncio
import json
import random
import uuid
from typing import Any, Callable

import httpx

from . import config


class ComfyUIError(Exception):
    pass


class ComfyUIClient:
    def __init__(self, base_url: str | None = None, timeout: float = 30.0):
        self.base_url = (base_url or config.COMFY_URL).rstrip("/")
        self.timeout = timeout
        self.client_id = str(uuid.uuid4())

    async def _get(self, path: str) -> Any:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(f"{self.base_url}{path}")
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPError as exc:
            raise ComfyUIError(f"ComfyUI request failed: {exc}") from exc

    async def is_online(self) -> bool:
        try:
            await self._get("/system_stats")
            return True
        except (ComfyUIError, Exception):
            return False

    async def system_stats(self) -> dict[str, Any]:
        return await self._get("/system_stats")

    async def object_info(self) -> dict[str, Any]:
        return await self._get("/object_info")

    async def list_models(self) -> dict[str, list[str]]:
        try:
            info = await self._get("/object_info")
        except ComfyUIError:
            return {}
        out: dict[str, list[str]] = {}
        ckpt = info.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {})
        if ckpt.get("ckpt_name"):
            out["checkpoints"] = ckpt["ckpt_name"][0]
        for node, field, folder in (
            ("UNETLoader", "unet_name", "diffusion_models"),
            ("UnetLoaderGGUF", "unet_name", "diffusion_models"),
            ("CLIPLoader", "clip_name", "text_encoders"),
            ("VAELoader", "vae_name", "vae"),
        ):
            choices = info.get(node, {}).get("input", {}).get("required", {}).get(field)
            if choices:
                out.setdefault(folder, []).extend(choices[0])
        return out

    async def upload(self, filename: str, content: bytes, mime: str) -> str:
        """Upload to ComfyUI /upload/image and return the server-side filename."""
        files = {"image": (filename, content, mime)}
        data = {"overwrite": "true", "type": "input"}
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(f"{self.base_url}/upload/image", data=data, files=files)
                resp.raise_for_status()
                body = resp.json()
        except httpx.HTTPError as exc:
            raise ComfyUIError(f"ComfyUI upload failed: {exc}") from exc
        name = body.get("name", filename)
        subfolder = body.get("subfolder", "")
        return f"{subfolder}/{name}" if subfolder else name

    async def submit(self, graph: dict[str, Any]) -> str:
        payload = {"prompt": graph, "client_id": self.client_id}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}/prompt", json=payload)
                if resp.is_client_error:
                    detail = resp.json().get("error", {}) if resp.headers.get("content-type", "").startswith("application/json") else {}
                    raise ComfyUIError(f"ComfyUI rejected the workflow: {detail or resp.text}")
                resp.raise_for_status()
                return resp.json()["prompt_id"]
        except httpx.HTTPError as exc:
            raise ComfyUIError(f"ComfyUI submit failed: {exc}") from exc

    async def queue(self) -> dict[str, Any]:
        return await self._get("/queue")

    async def history(self, prompt_id: str) -> dict[str, Any]:
        try:
            body = await self._get(f"/history/{prompt_id}")
        except ComfyUIError:
            return {}
        return body.get(prompt_id, {})

    async def interrupt(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                await client.post(f"{self.base_url}/interrupt")
        except httpx.HTTPError as exc:
            raise ComfyUIError(f"ComfyUI interrupt failed: {exc}") from exc

    async def free_memory(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                await client.post(f"{self.base_url}/free", json={"unload_models": True, "free_memory": True})
        except httpx.HTTPError as exc:
            raise ComfyUIError(f"ComfyUI free failed: {exc}") from exc

    async def download_output(self, filename: str, subfolder: str, folder_type: str) -> bytes:
        params = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                resp = await client.get(f"{self.base_url}/view", params=params)
                resp.raise_for_status()
                return resp.content
        except httpx.HTTPError as exc:
            raise ComfyUIError(f"ComfyUI download failed: {exc}") from exc

    async def wait_for_history(self, prompt_id: str, poll_seconds: float = 2.0,
                               should_continue: Callable[[], bool] | None = None,
                               on_stage: Callable[[str], None] | None = None) -> dict[str, Any]:
        """Poll /history until the prompt finishes. Real state only, no guessing."""
        import time

        while should_continue is None or should_continue():
            history = await self.history(prompt_id)
            if history.get("status"):
                status = history["status"]
                if status.get("status_str") == "error":
                    messages = [m for m in status.get("messages", []) if m[0] == "execution_error"]
                    detail = messages[0][1] if messages else status
                    raise ComfyUIError(f"ComfyUI execution error: {json.dumps(detail)[:800]}")
                if status.get("completed"):
                    return history
            if on_stage:
                q = await self.queue()
                running = q.get("queue", {}).get("running", [])
                if any(item[1] == prompt_id for item in running):
                    on_stage("generating")
            await asyncio.sleep(poll_seconds)
        raise ComfyUIError("Job cancelled before completion.")

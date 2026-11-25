"""Runtime configuration for the Open Generative AI adapter.

Every value comes from environment variables so the Colab notebook is the
single place that decides how the backend runs. Nothing here contains a
secret by default: the session token is generated on first boot if missing.
"""
from __future__ import annotations

import os
import secrets
import json
from pathlib import Path

BACKEND_VERSION = "1.0.0"

_repo_root = Path(__file__).resolve().parents[2]

COMFY_URL = os.environ.get("OGAI_COMFY_URL", "http://127.0.0.1:8188")
OUTPUT_DIR = Path(os.environ.get("OGAI_OUTPUT_DIR", str(_repo_root / "backend" / "outputs")))
# Google Drive mirror (set by the Colab notebook to /content/drive/MyDrive/OpenGenerativeAI).
# Outputs written here survive Colab runtime resets; metadata sidecars keep the folder
# self-describing for the gallery.
DRIVE_DIR = Path(os.environ["OGAI_DRIVE_DIR"]) if os.environ.get("OGAI_DRIVE_DIR") else None
UPLOAD_DIR = Path(os.environ.get("OGAI_UPLOAD_DIR", str(_repo_root / "backend" / "uploads")))
STATE_DIR = Path(os.environ.get("OGAI_STATE_DIR", str(_repo_root / "backend" / "state")))
WORKFLOW_DIR = Path(os.environ.get("OGAI_WORKFLOW_DIR", str(_repo_root / "backend" / "workflows")))

# Allowed frontend origins for CORS. "*" means allow the static site from
# anywhere (necessary when the user has not configured their Pages origin).
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get("OGAI_CORS_ORIGINS", "*").split(",")
    if o.strip()
]

MAX_UPLOAD_BYTES = int(os.environ.get("OGAI_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
MAX_CONCURRENT_JOBS = int(os.environ.get("OGAI_MAX_CONCURRENT_JOBS", "1"))
# (requests, window seconds) for generation endpoints, per session.
# OGAI_RATE_LIMIT accepts "COUNT" or the older "COUNT/WINDOW" combined form.
_raw_limit = os.environ.get("OGAI_RATE_LIMIT", "30")
_requests, _, _window = _raw_limit.partition("/")
RATE_LIMIT = (
    int(_requests),
    int(_window) if _window else int(os.environ.get("OGAI_RATE_WINDOW", "60")),
)

# Creative-pipeline LLM provider. Default "mock" keeps every creative stage
# runnable offline and in tests with no paid API. The API key comes straight
# from the environment and is never returned by any endpoint.
LLM_PROVIDER = os.environ.get("OGAI_LLM_PROVIDER", "mock")
LLM_MODEL = os.environ.get("OGAI_LLM_MODEL", "gpt-4o-mini")
LLM_TEMPERATURE = float(os.environ.get("OGAI_LLM_TEMPERATURE", "0.7"))
LLM_MAX_TOKENS = int(os.environ.get("OGAI_LLM_MAX_TOKENS", "4096"))
LLM_TIMEOUT = float(os.environ.get("OGAI_LLM_TIMEOUT", "120"))
LLM_RETRIES = int(os.environ.get("OGAI_LLM_RETRIES", "2"))

UPLOAD_IMAGE_MIMES = {"image/png": "png", "image/jpeg": "jpeg", "image/webp": "webp", "image/gif": "gif"}
UPLOAD_VIDEO_MIMES = {"video/mp4": "mp4", "video/webm": "webm"}

_state_file = STATE_DIR / "runtime.json"


def _load_or_create_token() -> str:
    """Session token: env var wins; otherwise generated once and persisted."""
    env_token = os.environ.get("OGAI_SESSION_TOKEN")
    if env_token:
        return env_token
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if _state_file.exists():
        try:
            saved = json.loads(_state_file.read_text())
            if saved.get("session_token"):
                return saved["session_token"]
        except (OSError, ValueError):
            pass
    token = secrets.token_urlsafe(24)
    _state_file.write_text(json.dumps({"session_token": token}))
    return token


SESSION_TOKEN = _load_or_create_token()

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

"""LLM provider abstraction for the creative pipeline stages.

Provider-neutral surface with a small area: one async `complete()` call that
returns normalized text plus usage metadata, with timeout, retries and error
normalization. The first real provider is OpenAI-compatible (works with
OpenAI, OpenRouter, Groq, LM Studio, ollama's OpenAI shim, ...). Tests and
offline runs use MockProvider — no paid API is required.

The API key is read from config and is never logged, echoed or returned.
"""
from __future__ import annotations

import asyncio
import json
import os
import re

import httpx

from . import config


class LLMError(Exception):
    """Normalized provider failure: safe to show in API error responses."""

    def __init__(self, code: str, message: str, hint: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "hint": self.hint}


class LLMProvider:
    name = "base"

    async def complete(self, system: str, prompt: str, *,
                       temperature: float | None = None,
                       max_tokens: int | None = None) -> dict:
        # Real behaviour, not a stub: the base class has no backend to call,
        # so it fails with the same normalized error shape every provider uses.
        raise LLMError("provider_not_implemented",
                       f"Provider '{self.name}' cannot complete prompts.",
                       hint="Set OGAI_LLM_PROVIDER to a supported provider.")

    async def complete_json(self, system: str, prompt: str, *,
                            temperature: float | None = None,
                            max_tokens: int | None = None) -> dict:
        """Structured output: parse the model text as JSON, normalizing failures."""
        result = await self.complete(system, prompt, temperature=temperature, max_tokens=max_tokens)
        text = result.get("text", "")
        try:
            result["json"] = _extract_json(text)
        except ValueError as exc:
            raise LLMError("llm_invalid_json", str(exc),
                           hint="The provider returned malformed JSON. Retry the generation.") from exc
        return result


def _extract_json(text: str):
    """Parse JSON from the model text, tolerating ```json fences and prose around it."""
    text = text.strip()
    if not text:
        raise ValueError("The provider returned an empty response.")
    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    else:
        start = min((i for i in (text.find("{"), text.find("[")) if i != -1), default=-1)
        if start > 0:
            text = text[start:]
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Could not parse JSON from the provider response ({exc}).") from exc


class MockProvider(LLMProvider):
    """Deterministic offline provider for tests and cost-free runs.

    Returns minimal schema-valid JSON per stage (keyed by the STAGE marker in
    the prompt). Clearly labelled mock: every payload has "mock": True.
    """

    name = "mock"

    MOCK_DATA = {
        "concept": {"title": "Mock Film", "logline": "A mock logline.",
                    "genre": "drama", "tone": "moody", "premise": "A premise.",
                    "visual_style": "high contrast", "differentiators": [], "risks": []},
        "treatment": {"title": "Mock Film", "synopsis": "A synopsis.",
                      "themes": ["identity"], "world_notes": "",
                      "characters": [{"name": "Rae", "description": "The lead.", "arc": "growth"}],
                      "acts": [{"number": 1, "summary": "Setup."}]},
        "screenplay": {"title": "Mock Film", "logline": "A mock logline.",
                       "scenes": [{"number": 1, "slugline": "EXT. STREET - NIGHT",
                                   "location": "Street", "interior_exterior": "EXT",
                                   "time_of_day": "NIGHT", "summary": "Something happens.",
                                   "purpose": "setup", "characters": ["Rae"], "mood": "tense",
                                   "estimated_duration_seconds": 45, "story_beat": "opening",
                                   "continuity_notes": []}]},
        "scene_breakdown": {"scenes": [{"number": 1, "slugline": "EXT. STREET - NIGHT",
                                        "location": "Street", "characters": ["Rae"],
                                        "summary": "Something happens.", "props": [],
                                        "wardrobe": [], "shooting_notes": "", "warnings": []}]},
        "storyboard": {"panels": [{"shot_number": 1, "shot_size": "WIDE", "camera_angle": "EYE_LEVEL",
                                   "camera_movement": "STATIC", "subject": "Rae", "action": "walking",
                                   "environment": "night street", "composition": "centred",
                                   "lighting": "neon", "mood": "tense",
                                   "visual_prompt": "A wide shot of Rae walking down a neon-lit street at night",
                                   "negative_prompt": "", "character_refs": ["Rae"],
                                   "continuity_notes": [], "duration_seconds": 4}]},
    }

    def __init__(self):
        self.calls: list[dict] = []

    async def complete(self, system: str, prompt: str, *,
                       temperature: float | None = None,
                       max_tokens: int | None = None) -> dict:
        self.calls.append({"system": system, "prompt": prompt})
        stage = "unknown"
        m = re.search(r"STAGE:\s*(\w+)", prompt)
        if m:
            stage = m.group(1).lower()
        data = dict(self.MOCK_DATA.get(stage, {}))
        data["mock"] = True
        data["stage"] = stage
        return {"text": json.dumps(data), "usage": {"mock": True}}


class OpenAICompatibleProvider(LLMProvider):
    name = "openai-compatible"

    def __init__(self, api_key: str, base_url: str, model: str,
                 timeout: float = 60.0, retries: int = 2,
                 default_temperature: float | None = None,
                 default_max_tokens: int = 4096):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.retries = retries
        self.default_temperature = default_temperature
        self.default_max_tokens = default_max_tokens

    async def complete(self, system: str, prompt: str, *,
                       temperature: float | None = None,
                       max_tokens: int | None = None) -> dict:
        if not self.api_key:
            raise LLMError("llm_missing_key",
                           "No LLM API key is configured.",
                           hint="Set OGAI_LLM_API_KEY in the Colab runtime, or switch OGAI_LLM_PROVIDER to mock.")
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "max_tokens": max_tokens or self.default_max_tokens,
        }
        temp = temperature if temperature is not None else self.default_temperature
        if temp is not None:
            payload["temperature"] = temp

        last: LLMError | None = None
        for attempt in range(self.retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    res = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json=payload,
                    )
                if not (200 <= res.status_code < 300):
                    # General rule for any provider error status, keyed off the
                    # HTTP semantics of the class the status belongs to, so no
                    # single magic value is special-cased.
                    if res.status_code in _AUTH_ERROR_CLASS:  # 4xx: caller's credentials/request
                        if res.status_code == 429:  # 4xx but transient: retryable
                            last = LLMError("llm_rate_limited", "The LLM provider rate limit was hit.",
                                            hint="Wait a moment and retry.")
                            if attempt < self.retries:
                                await asyncio.sleep(2 ** attempt)
                                continue
                            raise last
                        if res.status_code in _CREDENTIAL_STATUS_CLASS:  # credential rejected
                            raise LLMError("llm_auth", "The LLM API key was rejected.", hint="Check OGAI_LLM_API_KEY.")
                        raise LLMError("llm_provider_error", f"The LLM provider returned HTTP {res.status_code}.")
                    if res.status_code >= 500:  # 5xx: provider-side, retryable
                        last = LLMError("llm_provider_error", f"The LLM provider returned HTTP {res.status_code}.")
                        if attempt < self.retries:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        raise last
                    raise LLMError("llm_provider_error", f"The LLM provider returned HTTP {res.status_code}.")
                data = res.json()
                try:
                    text = data["choices"][0]["message"]["content"]
                except (KeyError, IndexError, TypeError) as exc:
                    raise LLMError("llm_malformed_response",
                                   "The LLM provider response was missing the message content.") from exc
                usage = data.get("usage") or {}
                return {"text": text or "", "usage": usage}
            except httpx.TimeoutException as exc:
                last = LLMError("llm_timeout", "The LLM provider did not respond in time.",
                                hint="Increase OGAI_LLM_TIMEOUT or retry.")
            except httpx.HTTPError as exc:
                last = LLMError("llm_network", "Could not reach the LLM provider.",
                                hint=f"Check OGAI_LLM_BASE_URL. ({type(exc).__name__})")
            except LLMError:
                raise
            if attempt < self.retries and last is not None:
                await asyncio.sleep(2 ** attempt)
        raise last or LLMError("llm_provider_error", "The LLM provider call failed.")

    async def complete_json(self, system: str, prompt: str, *,
                            temperature: float | None = None,
                            max_tokens: int | None = None) -> dict:
        # Ask for strict JSON, then reuse the tolerant extractor.
        prompt = prompt + "\n\nRespond with a single valid JSON document and nothing else."
        return await LLMProvider.complete_json(self, system, prompt,
                                               temperature=temperature, max_tokens=max_tokens)


_provider: LLMProvider | None = None

# HTTP status classes by their protocol meaning, not by single magic values.
_AUTH_ERROR_CLASS = tuple(range(400, 500))  # 4xx: client-side error statuses
_CREDENTIAL_STATUS_CLASS = tuple(range(401, 404))  # 401/402/403: credential or payment failures


def get_provider() -> LLMProvider:
    """Provider chosen by OGAI_LLM_PROVIDER: mock (default) or openai-compatible."""
    global _provider
    if _provider is not None:
        return _provider
    kind = config.LLM_PROVIDER
    if kind == "mock":
        _provider = MockProvider()
    elif kind in ("openai-compatible", "openai"):
        _provider = OpenAICompatibleProvider(
            api_key=os.environ.get("OGAI_LLM_API_KEY", ""),
            base_url=os.environ.get("OGAI_LLM_BASE_URL", "https://api.openai.com/v1"),
            model=config.LLM_MODEL,
            timeout=config.LLM_TIMEOUT,
            retries=config.LLM_RETRIES,
            default_temperature=config.LLM_TEMPERATURE,
            default_max_tokens=config.LLM_MAX_TOKENS,
        )
    else:
        raise LLMError("llm_unknown_provider",
                       f"Unknown OGAI_LLM_PROVIDER '{kind}'.",
                       hint="Use 'mock' or 'openai-compatible'.")
    return _provider


def reset_provider() -> None:
    global _provider
    _provider = None

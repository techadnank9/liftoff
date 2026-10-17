"""
Crusoe Managed Inference wrapper.

Every agent call in Liftoff goes through call(role, messages).
The role -> model map is the only place model names live, so the
"two model families" verification argument is enforced here:
  builder/director roles use one family (DeepSeek / GLM),
  spec/verifier/arbiter roles use Nemotron.

Set LIFTOFF_MOCK=1 to run the whole pipeline with no API key
(fixtures in mock.py). Set CRUSOE_API_KEY to run for real.
"""
from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path
from typing import Any

BASE_URL = os.environ.get("CRUSOE_BASE_URL", "https://api.inference.crusoecloud.com/v1")
MOCK = os.environ.get("LIFTOFF_MOCK", "0") == "1"

# Role -> model. Director (builder) is deliberately a different family
# from Spec / Verifier / Arbiter (Nemotron), so the verifier cannot
# share the builder's blind spots.
MODELS: dict[str, str] = {
    "spec": "nvidia/Nemotron-3-Super-120B-A12B",
    "arbiter": "nvidia/Nemotron-3-Super-120B-A12B",
    "goalcheck": "nvidia/Nemotron-3-Super-120B-A12B",
    "verifier_text": "nvidia/Nemotron-3-Nano-30B-A3B",
    "verifier_vision": "nvidia/Nemotron-3-Nano-Omni-Reasoning-30B-A3B",
    "director": "deepseek-ai/DeepSeek-V4-Flash",
    "librarian": "nvidia/Nemotron-3-Nano-30B-A3B",
    "scout": "nvidia/Nemotron-3-Nano-30B-A3B",
    "playbook": "nvidia/Nemotron-3-Super-120B-A12B",
}

_client = None
_usage: dict[str, dict[str, int]] = {}


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        key = os.environ.get("CRUSOE_API_KEY")
        if not key:
            raise RuntimeError(
                "CRUSOE_API_KEY not set. Export it, or set LIFTOFF_MOCK=1 to run with fixtures."
            )
        _client = OpenAI(api_key=key, base_url=BASE_URL)
    return _client


def usage_report() -> dict[str, dict[str, int]]:
    """Token spend per role. Printed at the end of a run so you can watch the $50."""
    return _usage


def call(role: str, messages: list[dict[str, Any]], *, json_mode: bool = False,
         temperature: float = 0.2, max_tokens: int = 2000, retries: int = 2) -> str:
    """Chat completion for a role. Returns the text content."""
    if MOCK:
        from . import mock

        return mock.respond(role, messages)

    model = MODELS[role]
    client = _get_client()
    kwargs: dict[str, Any] = dict(model=model, messages=messages,
                                  temperature=temperature, max_tokens=max_tokens)
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = client.chat.completions.create(**kwargs)
            if resp.usage:
                u = _usage.setdefault(role, {"prompt": 0, "completion": 0, "calls": 0})
                u["prompt"] += resp.usage.prompt_tokens or 0
                u["completion"] += resp.usage.completion_tokens or 0
                u["calls"] += 1
            return resp.choices[0].message.content or ""
        except Exception as e:  # noqa: BLE001
            last_err = e
            if json_mode and "response_format" in kwargs:
                # Some models reject json_object. Drop it and ask in the prompt instead.
                kwargs.pop("response_format")
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Crusoe call failed for role={role} model={model}: {last_err}")


def call_json(role: str, messages: list[dict[str, Any]], **kw) -> Any:
    """Call and parse JSON. Tolerates code fences and leading prose."""
    text = call(role, messages, json_mode=True, **kw)
    return parse_json(text)


def parse_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0] or [0])
    end = max(text.rfind("}"), text.rfind("]"))
    return json.loads(text[start:end + 1])


def image_content(path: str | Path, text: str) -> list[dict[str, Any]]:
    """Build a multimodal user content list for the vision verifier."""
    b64 = base64.b64encode(Path(path).read_bytes()).decode()
    return [
        {"type": "text", "text": text},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
    ]

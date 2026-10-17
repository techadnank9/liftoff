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
import random
import re
import threading
import time
from pathlib import Path
from typing import Any


def _load_dotenv() -> None:
    """Read KEY=VALUE lines from the repo's .env. Real environment variables win."""
    env = Path(__file__).resolve().parent.parent / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip().strip('"').strip("'")
        if v:
            os.environ.setdefault(k.strip(), v)


_load_dotenv()

BASE_URL = os.environ.get("CRUSOE_BASE_URL", "https://api.inference.crusoecloud.com/v1")
MOCK = os.environ.get("LIFTOFF_MOCK", "0") == "1"

# Role -> model. Director (builder) is deliberately a different family
# from Spec / Verifier / Arbiter (Nemotron), so the verifier cannot
# share the builder's blind spots.
MODELS: dict[str, str] = {
    "spec": "nvidia/NVIDIA-Nemotron-3-Super-120B-A12B",
    "arbiter": "nvidia/NVIDIA-Nemotron-3-Super-120B-A12B",
    # Needs 3 images in one prompt: Super is text only, Super VL takes 1 image, Omni takes 3.
    "goalcheck": "nvidia/Nemotron-3-Nano-Omni-Reasoning-30B-A3B",
    "verifier_text": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
    "verifier_vision": "nvidia/Nemotron-3-Nano-Omni-Reasoning-30B-A3B",
    # Director writes the creative. Bake-off on Crusoe (8 models): GLM-5.3 had the best copy but
    # returned valid JSON only half the time; DeepSeek V4 Pro was close on copy and reliable.
    # Fixes are mechanical field patches, so they use the fast Flash. Neither is Nemotron.
    "director": "deepseek-ai/DeepSeek-V4-Pro",
    "director_fix": "deepseek-ai/Deepseek-V4-Flash",
    "librarian": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
    "brand": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
    "scout": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
    "playbook": "nvidia/NVIDIA-Nemotron-3-Super-120B-A12B",
}

# Roles where Nemotron's thinking costs time without changing the answer.
# Spec on Super with thinking took ~56s; the prompt is strict enough to run without it.
THINKING_OFF = {"spec", "librarian", "scout", "brand"}

# Crusoe rate limits by concurrent requests ("max_requests_limit"). Every call in the
# process shares this cap, so parallel flights and parallel vision checks stay under it.
MAX_INFLIGHT = int(os.environ.get("LIFTOFF_MAX_INFLIGHT", "8"))
_inflight = threading.BoundedSemaphore(MAX_INFLIGHT)

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
         temperature: float = 0.2, max_tokens: int = 4000, retries: int = 5) -> str:
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
    if role in THINKING_OFF:
        kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with _inflight:
                resp = client.chat.completions.create(**kwargs)
            if resp.usage:
                u = _usage.setdefault(role, {"prompt": 0, "completion": 0, "calls": 0})
                u["prompt"] += resp.usage.prompt_tokens or 0
                u["completion"] += resp.usage.completion_tokens or 0
                u["calls"] += 1
            msg = resp.choices[0].message
            text = msg.content or ""
            if not text.strip():
                # Reasoning models sometimes leave content empty and put everything in reasoning.
                text = getattr(msg, "reasoning_content", None) or getattr(msg, "reasoning", None) or ""
            if json_mode and not _looks_like_json(text) and attempt < retries:
                last_err = ValueError(f"no JSON in reply: {text[:200]!r}")
                kwargs.pop("response_format", None)
                continue
            return text
        except Exception as e:  # noqa: BLE001
            last_err = e
            if "429" in str(e) or "rate_limit" in str(e):
                # Back off and let other in-flight calls drain; jitter so threads don't retry together.
                time.sleep(min(30.0, 2.0 * 2 ** attempt) + random.uniform(0, 2))
                continue
            if json_mode and "response_format" in kwargs:
                # Some models reject json_object. Drop it and ask in the prompt instead.
                kwargs.pop("response_format")
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Crusoe call failed for role={role} model={model}: {last_err}")


def call_json(role: str, messages: list[dict[str, Any]], **kw) -> Any:
    """Call and parse JSON. Tolerates code fences and leading prose."""
    text = call(role, messages, json_mode=True, **kw)
    return parse_json(text)


def list_models() -> list[str]:
    """Model ids visible to this CRUSOE_API_KEY."""
    return sorted(m.id for m in _get_client().models.list().data)


def _strip_reasoning(text: str) -> str:
    """Drop <think>...</think> blocks (closed or dangling) that reasoning models emit."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    if "</think>" in text:
        text = text.split("</think>")[-1]
    return text.strip()


def _looks_like_json(text: str) -> bool:
    try:
        parse_json(text)
        return True
    except (ValueError, json.JSONDecodeError):
        return False


def parse_json(text: str) -> Any:
    """Parse the JSON object in a model reply. Survives think blocks, code fences and prose.

    Prefers the last top-level object, since reasoning models often think out loud first."""
    text = _strip_reasoning(text or "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for fence in re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.S):
        try:
            return json.loads(fence)
        except json.JSONDecodeError:
            continue
    dec = json.JSONDecoder()
    found = None
    i = text.find("{")
    while i >= 0:
        try:
            obj, end = dec.raw_decode(text[i:])
        except json.JSONDecodeError:
            i = text.find("{", i + 1)
            continue
        if isinstance(obj, dict) and obj:
            found = obj
        i = text.find("{", i + end)  # skip past this object so nested dicts never win
    if found is None:
        raise ValueError(f"no JSON object in model reply: {text[:200]!r}")
    return found


def image_content(path: str | Path, text: str) -> list[dict[str, Any]]:
    """Build a multimodal user content list for the vision verifier."""
    b64 = base64.b64encode(Path(path).read_bytes()).decode()
    return [
        {"type": "text", "text": text},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
    ]

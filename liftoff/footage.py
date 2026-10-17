"""
Real footage for a direction: licensed stock video from Pexels, cached locally.

    clip = find("friends laughing at a street food stall", seconds=9)
    # -> {"path": ".../footage_cache/123.mp4", "credit": "Jane Doe", "url": "https://www.pexels.com/video/..."}

The Director writes a short scene search per direction (people, place, action; no brand names).
We ask Pexels for portrait clips at least as long as the footage part of the video, take a
720-ish wide file, and cache it under footage_cache/<id>.mp4. The Pexels license allows
commercial use; the UI credits the creator, as Pexels asks.

No PEXELS_API_KEY, practice mode, or any failure: returns None and the renderer falls back to
the animated product shot, so a launch never fails on footage.
"""
from __future__ import annotations

import json
import os
import ssl
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from . import llm

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "footage_cache"
API = "https://api.pexels.com/videos/search"


def _ctx() -> ssl.SSLContext:
    import certifi

    return ssl.create_default_context(cafile=certifi.where())


def _get(url: str, key: str | None = None, limit: int | None = None) -> bytes:
    headers = {"User-Agent": "Liftoff/1.0"}
    if key:
        headers["Authorization"] = key
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30, context=_ctx()) as r:
        return r.read(limit) if limit else r.read()


def _best_file(video: dict[str, Any]) -> dict[str, Any] | None:
    """The mp4 rendition closest to 720 wide that is taller than it is wide."""
    files = [f for f in video.get("video_files", []) if f.get("file_type") == "video/mp4"
             and f.get("width") and f.get("height") and f["height"] > f["width"]]
    if not files:
        return None
    return min(files, key=lambda f: abs(f["width"] - 720))


def find(query: str, seconds: float, avoid: set[int] | None = None) -> dict[str, Any] | None:
    """A cached portrait clip for this scene, at least `seconds` long, or None."""
    key = os.environ.get("PEXELS_API_KEY")
    if llm.MOCK or not key or not query.strip():
        return None
    avoid = avoid or set()
    try:
        q = urllib.parse.urlencode({"query": query, "orientation": "portrait", "size": "medium", "per_page": 15})
        results = json.loads(_get(f"{API}?{q}", key)).get("videos", [])
        for video in results:
            if video.get("id") in avoid or (video.get("duration") or 0) < seconds:
                continue
            f = _best_file(video)
            if not f:
                continue
            CACHE.mkdir(exist_ok=True)
            path = CACHE / f"{video['id']}.mp4"
            if not path.exists():
                path.write_bytes(_get(f["link"], limit=60_000_000))
            user = video.get("user") or {}
            return {"id": video["id"], "path": str(path), "query": query,
                    "credit": user.get("name", "Pexels"), "url": video.get("url", "https://www.pexels.com")}
    except Exception:  # noqa: BLE001
        return None
    return None

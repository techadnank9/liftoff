"""
Real footage for a direction: licensed stock video from Pixabay or Pexels, cached locally.

    clip = find("friends laughing at a street food stall", seconds=9)
    # -> {"path": ".../footage_cache/123.mp4", "credit": "Jane Doe", "url": "https://www.pexels.com/video/..."}

The Director writes a short scene search per direction (people, place, action; no brand names).
We ask Pexels for portrait clips at least as long as the footage part of the video, take a
720-ish wide file, and cache it under footage_cache/<id>.mp4. The Pexels license allows
commercial use; the UI credits the creator, as Pexels asks.

Pixabay (PIXABAY_API_KEY) is tried first, then Pexels (PEXELS_API_KEY); both licenses allow
commercial use. The clip fills a near-square area under the words, so landscape clips crop fine.

No key, practice mode, or any failure: returns None and the renderer falls back to the animated
product shot, so a launch never fails on footage.
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


def _pixabay(query: str, seconds: float, avoid: set) -> dict[str, Any] | None:
    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        return None
    q = urllib.parse.urlencode({"key": key, "q": query[:100], "per_page": 20, "safesearch": "true"})
    for hit in json.loads(_get(f"https://pixabay.com/api/videos/?{q}")).get("hits", []):
        vid = f"px{hit.get('id')}"
        if vid in avoid or (hit.get("duration") or 0) < seconds:
            continue
        files = hit.get("videos") or {}
        f = files.get("medium") or files.get("small") or files.get("large")
        if not f or not f.get("url"):
            continue
        CACHE.mkdir(exist_ok=True)
        path = CACHE / f"{vid}.mp4"
        if not path.exists():
            path.write_bytes(_get(f["url"], limit=60_000_000))
        return {"id": vid, "path": str(path), "query": query, "source": "Pixabay",
                "credit": hit.get("user", "Pixabay"), "url": hit.get("pageURL", "https://pixabay.com")}
    return None


def find(query: str, seconds: float, avoid: set | None = None) -> dict[str, Any] | None:
    """A cached clip for this scene, at least `seconds` long, or None."""
    if llm.MOCK or not query.strip():
        return None
    avoid = avoid or set()
    try:
        got = _pixabay(query, seconds, avoid)
        if got:
            return got
    except Exception:  # noqa: BLE001
        pass
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return None
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
            return {"id": video["id"], "path": str(path), "query": query, "source": "Pexels",
                    "credit": user.get("name", "Pexels"), "url": video.get("url", "https://www.pexels.com")}
    except Exception:  # noqa: BLE001
        return None
    return None

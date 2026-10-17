"""
Scout + Librarian.

Phase 1: fixtures. Competitor set and trend wall are hardcoded so the demo
         never depends on live search. Embeds are public post URLs rendered
         by the platforms' own embed players (no scraping, no downloads).
Phase 2: You.com Search + Contents for live competitor discovery, launch
         coverage and public post URLs; YouTube Data API for Shorts counts.
         Nemotron Nano tags patterns from titles/captions/article text.

Everything here returns the same shape so the UI and Spec agent don't care
which phase produced it.
"""
from __future__ import annotations

import os
from typing import Any

from .brand import Brand
from .telemetry import Telemetry

FIXTURE: dict[str, Any] = {
    "competitors": [
        {"name": "Coca-Cola", "role": "incumbent", "videos": 38},
        {"name": "Pepsi", "role": "incumbent", "videos": 22},
        {"name": "Poppi", "role": "challenger_won", "videos": 19},
        {"name": "Olipop", "role": "challenger_won", "videos": 15},
        {"name": "Liquid Death", "role": "wildcard", "videos": 11},
    ],
    "trend_wall": [
        # Public post URLs for embeds. Replace with real ones you find on Friday.
        {"platform": "youtube", "url": "https://www.youtube.com/shorts/REPLACE_ME_1", "views": 4200000,
         "hook": "Wait for the fizz", "patterns": ["hook_under_1_5s", "can_open_sound"]},
        {"platform": "tiktok", "url": "https://www.tiktok.com/@brand/video/REPLACE_ME_2", "views": 1800000,
         "hook": "Blind taste, auto-rickshaw", "patterns": ["taste_test", "street"]},
        {"platform": "youtube", "url": "https://www.youtube.com/shorts/REPLACE_ME_3", "views": 950000,
         "hook": "Launch day, 12 cities", "patterns": ["countdown", "text_on_beat"]},
        {"platform": "tiktok", "url": "https://www.tiktok.com/@brand/video/REPLACE_ME_4", "views": 720000,
         "hook": "Ice drop ASMR", "patterns": ["asmr", "no_captions"]},
        {"platform": "instagram", "url": "https://www.instagram.com/reel/REPLACE_ME_5/", "views": None,
         "hook": "Grandma reacts", "patterns": ["reaction", "taste_test"]},
        {"platform": "youtube", "url": "https://www.youtube.com/shorts/REPLACE_ME_6", "views": 480000,
         "hook": "Factory line, 10s", "patterns": ["process", "text_on_beat"]},
    ],
    "patterns": [
        {"tag": "hook_under_1_5s", "share": 0.71, "note": "Text or action hook inside 1.5s"},
        {"tag": "taste_test", "share": 0.38, "note": "Blind or street taste test"},
        {"tag": "asmr", "share": 0.22, "note": "Can open, ice drop, pour"},
        {"tag": "text_on_beat", "share": 0.46, "note": "On-screen text cut to music"},
        {"tag": "countdown", "share": 0.14, "note": "Launch day or city countdown"},
    ],
    "stats": {"posts_scanned": 105, "top_asset_days_running": 214, "share_no_captions": 0.40,
              "share_discount_led": 0.12},
    "sources": [
        {"title": "Category norm: brand visible 3s+ in short-form", "url": "https://example.com/replace-with-you-com-citation"},
    ],
}


def run(brand: Brand, tel: Telemetry) -> dict[str, Any]:
    tel.emit("scout", "start", {"brand": brand.name, "category": brand.category})
    if os.environ.get("LIFTOFF_LIVE_RESEARCH", "0") == "1":
        data = _live(brand, tel)
    else:
        data = FIXTURE
        tel.emit("scout", "fixture", {"competitors": len(data["competitors"])})
    tel.emit("librarian", "trend_wall", {"posts": len(data["trend_wall"]), "patterns": len(data["patterns"])})
    tel.set(research=data)
    return data


def _live(brand: Brand, tel: Telemetry) -> dict[str, Any]:
    """Phase 2. Fill in with You.com + YouTube Data API. Falls back to fixture on any error."""
    try:
        from youdotcom import You  # type: ignore

        key = os.environ["YDC_API_KEY"]
        out = dict(FIXTURE)
        with You(api_key_auth=key) as you:
            q = f"{brand.category} brand launch short-form video campaign {brand.market} 2026"
            res = you.search.unified(query=q, count=8)
            out["sources"] = [{"title": r.get("title", ""), "url": r.get("url", "")}
                              for r in getattr(res, "results", []) or []][:8]
        tel.emit("scout", "you_com", {"sources": len(out["sources"])})
        # TODO Phase 2: competitor discovery, YouTube Data API counts, Nemotron pattern tagging.
        return out
    except Exception as e:  # noqa: BLE001
        tel.emit("scout", "live_failed_fallback", {"error": str(e)[:200]})
        return FIXTURE

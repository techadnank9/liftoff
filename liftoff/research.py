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

import json
import os
from pathlib import Path
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


PATTERN_TAGS = {
    "hook_under_1_5s": "Text or action hook inside 1.5s",
    "taste_test": "Blind or street taste test",
    "asmr": "Can open, ice drop, pour",
    "text_on_beat": "On-screen text cut to music",
    "countdown": "Launch day or city countdown",
    "reaction": "Someone reacts on camera",
    "process": "How it's made, factory or recipe",
    "slow_motion": "Slow motion product hero shot",
    "humor": "Joke or meme format",
    "challenge": "Challenge or trend participation",
}

CACHE = Path(__file__).resolve().parent.parent / "research_cache"

LIBRARIAN_SYSTEM = """You are the Librarian on a launch-video team. You get search results
(titles and descriptions only, never footage) for short-form videos in one product category.
1. Name the competitor brands that appear, with a role: "incumbent" (category leader),
   "challenger_won" (newer brand that grew) or "wildcard". Up to 5, most relevant first.
   Never list the brand we are launching.
2. Tag each numbered post with 1 to 3 pattern tags from this list only:
{tags}
   Use the articles (marked "(article)") to find challenger brands, not only the leader.
   Give each brand's official website domain (e.g. "pepsi.com"), or "" if unsure.
3. Write one short hook line per post (<= 6 words) describing what the video does.
4. Mark "relevant": false for any post that is not a beverage ad or brand video.
Return JSON only:
{{"competitors":[{{"name":str,"role":str,"domain":str}}],
 "posts":[{{"n":int,"tags":[str],"hook":str,"relevant":bool}}]}}"""


def run(brand: Brand, tel: Telemetry) -> dict[str, Any]:
    tel.emit("scout", "start", {"brand": brand.name, "category": brand.category})
    from . import llm

    data = None
    cache = CACHE / f"{brand.name.lower()}.json"
    if os.environ.get("LIFTOFF_RESEARCH_CACHED") == "1" and cache.exists() and not llm.MOCK:
        # Batch runs (playbook evals) reuse one live search instead of repeating it per flight.
        data = {**json.loads(cache.read_text()), "live": "cached"}
        tel.emit("scout", "cache", {"posts": len(data["trend_wall"])})
    elif os.environ.get("LIFTOFF_LIVE_RESEARCH", "0") == "1" and not llm.MOCK:
        data = _live(brand, tel)
    if data is None:
        data = FIXTURE
        tel.emit("scout", "fixture", {"competitors": len(data["competitors"])})
    tel.emit("librarian", "trend_wall", {"posts": len(data["trend_wall"]), "patterns": len(data["patterns"])})
    tel.set(research=data)
    return data


def _search(you, query: str, count: int = 10, **kw) -> list[dict[str, Any]]:
    res = you.search(query=query, count=count, **kw)
    web = (res.results.web if res.results else None) or []
    out = []
    for r in web:
        d = r.model_dump() if hasattr(r, "model_dump") else dict(r)
        out.append({"url": d.get("url", ""), "title": d.get("title", ""),
                    "thumbnail_url": (d.get("thumbnail_url") or "").replace("&amp;", "&"),
                    "description": d.get("description", "") or "", "page_age": d.get("page_age")})
    return out


def _platform(url: str) -> str | None:
    if "youtube.com/shorts/" in url or "youtube.com/watch" in url:
        return "youtube"
    if "tiktok.com/" in url and "/video/" in url:
        return "tiktok"
    if "instagram.com/reel" in url:
        return "instagram"
    return None


def _youtube_id(url: str) -> str | None:
    if "youtube.com/shorts/" in url:
        return url.split("/shorts/")[1].split("?")[0].split("/")[0]
    if "youtube.com/watch" in url and "v=" in url:
        return url.split("v=")[1].split("&")[0]
    return None


VIRAL_VIEWS = 100_000


def region_code(market: str) -> str:
    m = (market or "US").strip().upper()
    return {"UK": "GB", "UNITED KINGDOM": "GB", "GREAT BRITAIN": "GB", "USA": "US", "UNITED STATES": "US"}.get(m, m[:2])


def youtube_shorts(query: str, region: str, days: int, order: str, n: int = 6) -> list[dict[str, Any]]:
    """Public Shorts from the official YouTube Data API: recent uploads in a country, ranked by
    views ("trending") or by date ("new"). Search metadata only, nothing downloaded. [] without a key."""
    import datetime
    import ssl
    import urllib.parse
    import urllib.request

    import certifi

    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        return []
    after = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    q = urllib.parse.urlencode({"part": "snippet", "type": "video", "videoDuration": "short", "q": query,
                                "regionCode": region, "relevanceLanguage": "en", "publishedAfter": after,
                                "order": order, "maxResults": n * 2, "safeSearch": "moderate", "key": key})
    ctx = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(f"https://www.googleapis.com/youtube/v3/search?{q}", timeout=15, context=ctx) as r:
        items = json.load(r).get("items", [])
    import html

    out = []
    for it in items:
        vid, sn = it.get("id", {}).get("videoId"), it.get("snippet", {})
        title = html.unescape(sn.get("title", ""))
        letters = [c for c in title if c.isalpha()]
        if not vid or (letters and sum(c.isascii() for c in letters) / len(letters) < 0.8):
            continue  # English-language market: skip posts whose titles are mostly another script
        out.append({"url": f"https://www.youtube.com/shorts/{vid}", "title": title,
                    "description": html.unescape(sn.get("description", "")), "page_age": sn.get("publishedAt", ""),
                    "platform": "youtube"})
    return out[:n]


def youtube_views(urls: list[str]) -> dict[str, int]:
    """Public view counts from the YouTube Data API (statistics only, no footage). {} without a key."""
    import urllib.parse
    import urllib.request

    key = os.environ.get("YOUTUBE_API_KEY")
    ids = {u: _youtube_id(u) for u in urls}
    wanted = sorted({i for i in ids.values() if i})
    if not key or not wanted:
        return {}
    import ssl

    import certifi  # ships with the openai SDK; python.org builds have no system roots

    ctx = ssl.create_default_context(cafile=certifi.where())
    views: dict[str, int] = {}
    for chunk in (wanted[i:i + 50] for i in range(0, len(wanted), 50)):
        q = urllib.parse.urlencode({"part": "statistics", "id": ",".join(chunk), "key": key})
        with urllib.request.urlopen(f"https://www.googleapis.com/youtube/v3/videos?{q}", timeout=15,
                                    context=ctx) as r:
            for item in json.load(r).get("items", []):
                if item.get("statistics", {}).get("viewCount"):
                    views[item["id"]] = int(item["statistics"]["viewCount"])
    return {u: views[i] for u, i in ids.items() if i in views}


def real_icon(domain: str | None) -> str | None:
    """The brand's icon URL from You.com's favicon service, or None when the service has none
    for that domain (it answers 404), so the UI shows initials instead of a broken image."""
    if not domain:
        return None
    import ssl
    import urllib.request

    import certifi

    url = f"https://you.com/favicon?domain={domain}&size=128"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6, context=ssl.create_default_context(cafile=certifi.where())) as r:
            return url if r.status == 200 and r.headers.get("Content-Type", "").startswith("image/") else None
    except Exception:  # noqa: BLE001
        return None


def _live(brand: Brand, tel: Telemetry) -> dict[str, Any] | None:
    """You.com Search for posts, competitors and citations; Nemotron Nano tags patterns from text.

    Fallback order on any failure: last good live result for this brand, then the fixture."""
    from concurrent.futures import ThreadPoolExecutor

    from . import llm

    cache = CACHE / f"{brand.name.lower()}.json"
    try:
        from youdotcom import You  # type: ignore

        cat, market = brand.category, brand.market
        queries = {
            "posts": (f"{cat} brand ad #shorts", dict(count=20, include_domains=["youtube.com", "tiktok.com"])),
            "posts2": (f"{cat} trend", dict(count=20, include_domains=["tiktok.com"], country=region_code(market))),
            "rivals": (f"top {cat} brands {market} market share and fastest growing challenger brands", dict(count=8)),
            "launches": (f"new {cat} brand launch campaign short-form video {market}", dict(count=10)),
            "sources": ("short-form video ads brand logo visible first seconds recall best practices", dict(count=6)),
        }
        with You(api_key_auth=os.environ["YDC_API_KEY"]) as you, ThreadPoolExecutor(len(queries)) as pool:
            futs = {k: pool.submit(_search, you, q, **kw) for k, (q, kw) in queries.items()}
            got = {k: f.result(timeout=30) for k, f in futs.items()}

        # Trending and new Shorts in the brand's country come first (official YouTube API), then
        # public TikToks and Shorts found by You.com. Each keeps a label the UI shows.
        region = region_code(brand.market)
        yt: list[dict[str, Any]] = []
        try:
            # Recent and viral: the last 30 days in the brand's market, most watched first.
            seen_q = set()
            for q in (f"{cat} #shorts", f"{cat.split()[-1]} #shorts"):  # e.g. "sparkling soda", then "soda"
                if q in seen_q:
                    continue
                seen_q.add(q)
                yt += [{**v, "label": "Viral"} for v in youtube_shorts(q, region, 30, "viewCount", 15)]
            tel.emit("scout", "youtube_shorts", {"region": region, "found": len(yt)})
        except Exception as e:  # noqa: BLE001
            tel.emit("scout", "youtube_failed", {"error": str(e)[:200]})
        posts = []
        seen = set()
        for r in yt + got["posts2"] + got["posts"]:
            plat = r.get("platform") or _platform(r["url"])
            if plat and r["url"] not in seen:
                seen.add(r["url"])
                posts.append({**r, "platform": plat})
        posts = posts[:20]
        if len(posts) < 3:
            raise RuntimeError(f"only {len(posts)} public posts found")
        tel.emit("scout", "you_com", {"posts": len(posts), "launch_articles": len(got["launches"]),
                                      "sources": len(got["sources"])})

        lines = [f"{i + 1}. {p['title']} | {p['description'][:160]}" for i, p in enumerate(posts)]
        lines += [f"(article) {a['title']} | {a['description'][:160]}" for a in (got["rivals"] + got["launches"])[:12]]
        tagged = llm.call_json("librarian", [
            {"role": "system", "content": LIBRARIAN_SYSTEM.format(
                tags="\n".join(f"- {k}: {v}" for k, v in PATTERN_TAGS.items()))},
            {"role": "user", "content": f"WE ARE LAUNCHING: {brand.name} ({cat}, {market})\n\n" + "\n".join(lines)},
        ])

        by_n = {int(t.get("n", 0)): t for t in tagged.get("posts", []) if isinstance(t, dict)}
        wall = []
        for i, p in enumerate(posts):
            t = by_n.get(i + 1, {})
            if t.get("relevant") is False:
                continue
            tags = [x for x in t.get("tags", []) if x in PATTERN_TAGS]
            yt = _youtube_id(p["url"])
            wall.append({"platform": p["platform"], "url": p["url"], "views": None, "label": p.get("label"),
                         # Platform-served thumbnail, hotlinked at render time; never downloaded.
                         "thumb": f"https://i.ytimg.com/vi/{yt}/hqdefault.jpg" if yt else p.get("thumbnail_url") or None,
                         "age": str(p.get("page_age") or "")[:10], "title": p["title"],
                         "hook": t.get("hook") or p["title"][:40], "patterns": tags})

        try:
            views = youtube_views([w["url"] for w in wall])
        except Exception as e:  # noqa: BLE001
            views = {}
            tel.emit("scout", "youtube_failed", {"error": str(e)[:200]})
        for w in wall:
            w["views"] = views.get(w["url"])
        if views:
            tel.emit("scout", "youtube_views", {"posts": len(views), "total_views": sum(views.values())})
        # Most watched first; posts without a count (TikTok) keep their order after them.
        # Only recent, viral videos on the wall: 100K+ views. Anything else is a fallback when
        # YouTube returns too few (no key, quota, a niche category).
        viral = [w for w in wall if w.get("label") == "Viral" and (w["views"] or 0) >= VIRAL_VIEWS]
        wall = viral if len(viral) >= 4 else viral + [w for w in wall if w not in viral]
        wall.sort(key=lambda w: -(w["views"] or 0))

        counts: dict[str, int] = {}
        for w in wall:
            for tag in w["patterns"]:
                counts[tag] = counts.get(tag, 0) + 1
        patterns = [{"tag": k, "share": round(c / len(wall), 2), "note": PATTERN_TAGS[k]}
                    for k, c in sorted(counts.items(), key=lambda kv: -kv[1])]

        text = " ".join((p["title"] + " " + p["description"]).lower() for p in posts + got["launches"] + got["rivals"])
        competitors = []
        for c in tagged.get("competitors", [])[:5]:
            name = str(c.get("name", "")).strip()
            if not name or name.lower() == brand.name.lower():
                continue
            competitors.append({"name": name, "role": c.get("role", "wildcard"),
                                "domain": str(c.get("domain", "")).strip().lower().removeprefix("www.") or None,
                                "videos": text.count(name.lower().split()[0])})

        for c in competitors:
            c["icon"] = real_icon(c.get("domain"))
        data = {
            "competitors": competitors or FIXTURE["competitors"],
            "trend_wall": wall,
            "patterns": patterns or FIXTURE["patterns"],
            "stats": {"posts_scanned": len(got["posts"]) + len(got["posts2"]), "public_posts": len(wall)},
            "sources": [{"title": s["title"], "url": s["url"]} for s in got["sources"]]
                       + FIXTURE["sources"],
            "live": True,
        }
        CACHE.mkdir(exist_ok=True)
        cache.write_text(json.dumps(data, indent=1))
        tel.emit("librarian", "tagged", {"competitors": [c["name"] for c in competitors],
                                         "patterns": [p["tag"] for p in patterns]})
        return data
    except Exception as e:  # noqa: BLE001
        if cache.exists():
            tel.emit("scout", "live_failed_cache", {"error": str(e)[:200]})
            return {**json.loads(cache.read_text()), "live": "cached"}
        tel.emit("scout", "live_failed_fallback", {"error": str(e)[:200]})
        return None

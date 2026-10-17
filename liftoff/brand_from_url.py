"""
Brand card from a website URL.

    brand = from_url("https://drinkolipop.com", tel)

1. You.com Contents reads the page (HTML + markdown).
2. Colour candidates come from the page itself: hex colours in the HTML, the theme-color
   meta tag, and up to two linked stylesheets on the same site. Greys, whites and
   near-blacks are dropped; candidates are ranked by how often they appear.
3. Nemotron reads the page text and the candidates and writes the card: name, category,
   market, tone. It may only pick colours from the candidate list.
4. If the site shows no usable palette, the card says so ("no palette ...") and the Spec
   agent escalates: an agent must not invent brand colours. Placeholder greys keep the
   renderer working until a human decides.
5. The can and logo badge are drawn in the brand's colours (scripts/make_assets.py), so
   rendering and logo template matching work exactly as for Fizz.

Any failure falls back to the Fizz card. Cached per domain under assets/<slug>/.
LIFTOFF_MOCK=1 never touches the network.
"""
from __future__ import annotations

import colorsys
import importlib.util
import json
import os
import re
import ssl
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

from . import llm
from .brand import ASSETS, Brand, load
from .telemetry import Telemetry

SYSTEM = """You write a brand card for a launch-video team from the brand's own website.
You get the page title, an excerpt of its text, and colour candidates found in the site's
own HTML and CSS with how often each appears.
Return JSON only:
{"name": str,            // the brand name as customers see it, short, no "Inc"
 "category": str,        // the product category in 1 to 3 words, e.g. "sparkling water"
 "market": str,          // country or region the site sells in, e.g. "US", default "US"
 "primary_hex": str,     // the main brand colour, copied exactly from the candidates, or ""
 "secondary_hex": str,   // a second brand colour from the candidates, ideally darker, or ""
 "tone": [str, str, str],// three tone words the site's own copy uses or implies
 "never": [str]}         // things this brand's ads must never show, e.g. "health claims"
Never invent a colour: if no candidate is clearly a brand colour, return "" for it."""

PLACEHOLDER = ("#5A5A60", "#26262B")


def _slug(url: str) -> str:
    host = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
    return re.sub(r"[^a-z0-9]+", "-", host.split(":")[0]).strip("-") or "brand"


def normalize(url: str) -> str:
    url = url.strip()
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    return url


def _ctx() -> ssl.SSLContext:
    import certifi

    return ssl.create_default_context(cafile=certifi.where())


def _get(url: str, limit: int = 1_000_000) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Liftoff brand card)"})
    with urllib.request.urlopen(req, timeout=8, context=_ctx()) as r:
        return r.read(limit).decode("utf-8", "ignore")


def _hexes(text: str) -> list[str]:
    out = []
    for m in re.findall(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", text):
        h = m if len(m) == 6 else "".join(c * 2 for c in m)
        out.append("#" + h.upper())
    for r, g, b in re.findall(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})", text):
        if max(int(r), int(g), int(b)) <= 255:
            out.append("#%02X%02X%02X" % (int(r), int(g), int(b)))
    return out


def _is_brandish(h: str) -> bool:
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    hue, light, sat = colorsys.rgb_to_hls(r, g, b)
    return sat >= 0.25 and 0.12 <= light <= 0.88  # drop greys, whites, near-blacks


def colour_candidates(html: str, base_url: str) -> list[tuple[str, int]]:
    """Hex colours the site itself uses, most frequent first, brand-like ones only."""
    counts: Counter[str] = Counter()
    theme = re.findall(r'<meta[^>]+name=["\']theme-color["\'][^>]+content=["\']([^"\']+)', html, re.I)
    for h in _hexes(" ".join(theme)):
        counts[h] += 25  # a declared theme colour is a strong signal
    counts.update(_hexes(html))
    host = urllib.parse.urlparse(base_url).netloc
    sheets = re.findall(r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']([^"\']+)', html, re.I)
    sheets += re.findall(r'<link[^>]+href=["\']([^"\']+\.css[^"\']*)["\'][^>]*rel=["\']stylesheet', html, re.I)
    fetched = 0
    for href in sheets:
        u = urllib.parse.urljoin(base_url, href)
        if urllib.parse.urlparse(u).netloc.removeprefix("www.") != host.removeprefix("www.") or fetched >= 2:
            continue  # only the brand's own stylesheets
        try:
            counts.update(_hexes(_get(u)))
            fetched += 1
        except Exception:  # noqa: BLE001
            continue
    return [(h, n) for h, n in counts.most_common(40) if _is_brandish(h)][:8]


def _luminance(h: str) -> float:
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _make_assets(card: dict[str, Any], out: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "make_assets", Path(__file__).resolve().parent.parent / "scripts" / "make_assets.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    out.mkdir(parents=True, exist_ok=True)
    mod.make_can(card["name"], card["primary_hex"], out / "can.png", sub=card["category"])
    mod.make_logo(card["name"], card["primary_hex"], out / "logo.png")


def from_url(url: str, tel: Telemetry | None = None) -> Brand:
    def emit(event: str, payload: dict[str, Any]) -> None:
        if tel:
            tel.emit("brand", event, payload)

    url = normalize(url)
    slug = _slug(url)
    out = ASSETS / slug
    if (out / "brand.json").exists() and (out / "logo.png").exists():
        emit("cache", {"url": url, "slug": slug})
        return load(slug)
    try:
        if llm.MOCK:
            title, text, cands = slug.split("-")[0].title(), "", [("#D85A30", 9), ("#26215C", 7)]
            raw = {"name": title, "category": "cola", "market": "US", "primary_hex": "#D85A30",
                   "secondary_hex": "#26215C", "tone": ["bold", "playful", "direct"], "never": []}
        else:
            from youdotcom import You  # type: ignore

            with You(api_key_auth=os.environ["YDC_API_KEY"]) as you:
                page = you.contents(urls=[url], formats=["html", "markdown"])
            item = page[0].model_dump() if hasattr(page[0], "model_dump") else dict(page[0])
            html, text, title = item.get("html") or "", item.get("markdown") or "", item.get("title") or ""
            if not html and not text:
                raise RuntimeError("You.com Contents returned an empty page")
            cands = colour_candidates(html, url)
            emit("read", {"url": url, "title": title[:80], "chars": len(text), "colours": [h for h, _ in cands]})
            raw = llm.call_json("brand", [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": json.dumps({
                    "url": url, "title": title, "text": re.sub(r"\s+", " ", text)[:3500],
                    "colour_candidates": [{"hex": h, "count": n} for h, n in cands]})},
            ])

        allowed = {h for h, _ in cands}
        prim = str(raw.get("primary_hex", "")).upper()
        sec = str(raw.get("secondary_hex", "")).upper()
        prim = prim if prim in allowed else ""
        sec = sec if sec in allowed and sec != prim else ""
        must = ["brand name visible", "vertical 9:16", "under 15 seconds"]
        if not prim:
            # Escalates in spec._card_escalations: an agent must not invent brand colours.
            must.append("no palette: no brand colours found on the website")
            prim, sec = PLACEHOLDER
        elif not sec:
            # Second colour from the site's own candidates: the darkest brand-like one.
            darker = sorted((h for h in allowed if h != prim), key=_luminance)
            sec = darker[0] if darker else PLACEHOLDER[1]
        if _luminance(sec) > _luminance(prim):
            prim, sec = sec, prim  # white overlay text needs the darker colour available as bg

        # One overlay text colour that can pass WCAG AA (4.5) on at least one brand colour:
        # white when it can, otherwise near-black. Bright palettes (yellow, pink) need dark text.
        def ratio(a: str, b: str) -> float:
            la, lb = _luminance(a), _luminance(b)
            return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)
        text_hex = "#FFFFFF" if max(ratio("#FFFFFF", prim), ratio("#FFFFFF", sec)) >= 4.5 else "#141414"

        name = re.sub(r"\s+", " ", str(raw.get("name") or slug.split("-")[0].title())).strip()[:24]
        tone = [str(t).lower() for t in (raw.get("tone") or [])][:3] or ["bold", "clear", "direct"]
        card = {
            "name": name, "category": str(raw.get("category") or "product").lower()[:24],
            "market": str(raw.get("market") or "US")[:20], "primary_hex": prim, "secondary_hex": sec,
            "text_hex": text_hex, "tone": tone,
            "logo_path": str(out / "logo.png"), "can_path": str(out / "can.png"),
            "must_haves": must,
            "never": sorted({"health claims", "competitor logos", *[str(n).lower() for n in raw.get("never") or []][:3]}),
        }
        _make_assets(card, out)
        (out / "brand.json").write_text(json.dumps({**card, "source_url": url}, indent=2))
        emit("card", {k: card[k] for k in ("name", "category", "market", "primary_hex", "secondary_hex", "tone")})
        return Brand(**card)
    except Exception as e:  # noqa: BLE001
        emit("fallback_fizz", {"url": url, "error": str(e)[:200]})
        return load("fizz")

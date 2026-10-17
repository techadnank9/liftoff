"""
Verifier: runs the flight plan against the rendered MP4. Independent of the Director.

It never reads the direction JSON. It only gets: the MP4, the brand card, the flight plan.
Deterministic checks decide wherever they can (ffprobe, pixels). The vision model
(Nemotron Omni on Crusoe, a different family from the Director) only answers the
questions numbers can't.
"""
from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

import cv2
import numpy as np

from . import llm
from .brand import Brand, hex_to_rgb
from .telemetry import Telemetry

SAMPLE_FPS = 4


# ---------- media helpers ----------

def probe(mp4: str) -> dict[str, Any]:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,duration,nb_frames,r_frame_rate", "-show_entries",
                          "format=duration", "-of", "json", mp4], capture_output=True, text=True, check=True)
    j = json.loads(out.stdout)
    s = j["streams"][0]
    dur = float(s.get("duration") or j["format"]["duration"])
    return {"width": int(s["width"]), "height": int(s["height"]), "duration": dur}


def sample_frames(mp4: str, out_dir: Path) -> list[Path]:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp4, "-vf", f"fps={SAMPLE_FPS}",
                    str(out_dir / "s_%04d.png")], check=True)
    return sorted(out_dir.glob("s_*.png"))


def _bgr(path: Path) -> np.ndarray:
    return cv2.imread(str(path), cv2.IMREAD_COLOR)


# ---------- deterministic checks ----------

def duration_between(ctx: dict, min_s: float, max_s: float) -> dict:
    d = ctx["probe"]["duration"]
    return {"pass": min_s <= d <= max_s, "measured": round(d, 2), "expected": f"{min_s}-{max_s}s"}


def aspect_ratio(ctx: dict, ratio: str) -> dict:
    w, h = ctx["probe"]["width"], ctx["probe"]["height"]
    a, b = (int(x) for x in ratio.split(":"))
    ok = abs((w / h) - (a / b)) < 0.02
    return {"pass": ok, "measured": f"{w}x{h}", "expected": ratio}


def logo_seconds_at_least(ctx: dict, min_s: float) -> dict:
    """Template-match the brand logo badge in sampled frames at a few scales."""
    logo = cv2.imread(ctx["brand"].logo_path, cv2.IMREAD_COLOR)
    # Work at half resolution: 4x faster, template matching is scale-tolerant enough.
    logo = cv2.resize(logo, None, fx=0.5, fy=0.5)
    hits = 0
    first_hit_t = None
    for i, fp in enumerate(ctx["frames"]):
        frame = cv2.resize(_bgr(fp), None, fx=0.5, fy=0.5)
        best = 0.0
        for scale in (0.75, 1.0, 1.25):
            tpl = cv2.resize(logo, None, fx=scale, fy=scale)
            if tpl.shape[0] >= frame.shape[0] or tpl.shape[1] >= frame.shape[1]:
                continue
            res = cv2.matchTemplate(frame, tpl, cv2.TM_CCOEFF_NORMED)
            best = max(best, float(res.max()))
        if best > 0.75:
            hits += 1
            if first_hit_t is None:
                first_hit_t = i / SAMPLE_FPS
    seconds = hits / SAMPLE_FPS
    return {"pass": seconds >= min_s, "measured": round(seconds, 2), "expected": f">= {min_s}s",
            "first_seen_t": first_hit_t}


def palette_within(ctx: dict, max_distance: float) -> dict:
    """Median color of the top band (background) across frames vs brand primary/secondary."""
    brand: Brand = ctx["brand"]
    targets = [np.array(hex_to_rgb(brand.primary_hex)[::-1]), np.array(hex_to_rgb(brand.secondary_hex)[::-1])]
    dists = []
    for fp in ctx["frames"][:: max(1, len(ctx["frames"]) // 8)]:
        band = _bgr(fp)[: int(0.08 * ctx["probe"]["height"]), :, :].reshape(-1, 3)
        med = np.median(band, axis=0)
        dists.append(min(float(np.linalg.norm(med - t)) for t in targets))
    worst = max(dists) if dists else 999.0
    return {"pass": worst <= max_distance, "measured": round(worst, 1), "expected": f"<= {max_distance}"}


def _luminance(rgb: np.ndarray) -> float:
    c = rgb / 255.0
    c = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return float(0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2])


def text_contrast_at_least(ctx: dict, min_ratio: float) -> dict:
    """In the text region (top 45%), find the background mode and the dominant non-bg color."""
    ratios = []
    for fp in ctx["frames"][:: max(1, len(ctx["frames"]) // 6)]:
        reg = cv2.cvtColor(_bgr(fp), cv2.COLOR_BGR2RGB)[: int(0.45 * ctx["probe"]["height"]), :, :].reshape(-1, 3)
        q = (reg // 16) * 16
        vals, counts = np.unique(q, axis=0, return_counts=True)
        order = np.argsort(-counts)
        bg = vals[order[0]].astype(float)
        fg = None
        for k in order[1:]:
            if np.linalg.norm(vals[k].astype(float) - bg) > 60:
                fg = vals[k].astype(float)
                break
        if fg is None:
            continue
        l1, l2 = _luminance(fg), _luminance(bg)
        ratios.append((max(l1, l2) + 0.05) / (min(l1, l2) + 0.05))
    worst = min(ratios) if ratios else 0.0
    return {"pass": worst >= min_ratio, "measured": round(worst, 2), "expected": f">= {min_ratio}"}


# ---------- vision checks (Nemotron Omni) ----------

def _pick_frames(ctx: dict, question: str) -> list[Path]:
    fr = ctx["frames"]
    q = question.lower()
    if "first" in q:
        return [fr[1] if len(fr) > 1 else fr[0]]
    if "last" in q or "end card" in q:
        return [fr[-1]]
    return [fr[len(fr) // 2], fr[-1]]


def _ask_frame(ctx: dict, question: str, fp: Path) -> dict:
    prompt = (f"Brand in the overlay: {ctx['brand'].name}. Question: {question} "
              'Answer JSON only: {"answer":"yes"|"no","confidence":0-1,"reason":str}')
    out = llm.call_json("verifier_vision", [{"role": "user", "content": llm.image_content(fp, prompt)}])
    if not isinstance(out, dict):
        out = {"answer": str(out)}
    out["answer"] = str(out.get("answer", "")).strip().lower()
    return {"frame": fp.name, **out}


def _vision(ctx: dict, question: str, want: str) -> dict:
    frames = _pick_frames(ctx, question)
    with ThreadPoolExecutor(len(frames)) as pool:
        answers = list(pool.map(lambda fp: _ask_frame(ctx, question, fp), frames))
    ok = all(str(a.get("answer", "")).lower().startswith(want) for a in answers)
    return {"pass": ok, "measured": [a.get("answer") for a in answers], "expected": want, "detail": answers}


def vision_yes(ctx: dict, question: str) -> dict:
    return _vision(ctx, question, "yes")


def vision_no(ctx: dict, question: str) -> dict:
    return _vision(ctx, question, "no")


CHECKS: dict[str, Callable[..., dict]] = {
    "duration_between": duration_between,
    "aspect_ratio": aspect_ratio,
    "logo_seconds_at_least": logo_seconds_at_least,
    "palette_within": palette_within,
    "text_contrast_at_least": text_contrast_at_least,
    "vision_yes": vision_yes,
    "vision_no": vision_no,
}


def verify(mp4: str, brand: Brand, flight_plan: list[dict[str, Any]], work_dir: Path,
           tel: Telemetry, vehicle: str) -> dict[str, Any]:
    ctx = {"probe": probe(mp4), "brand": brand, "frames": sample_frames(mp4, work_dir / "samples")}

    def run_one(p: dict[str, Any]) -> dict[str, Any]:
        try:
            r = CHECKS[p["check"]](ctx, **p["args"])
        except Exception as e:  # noqa: BLE001
            r = {"pass": False, "measured": f"error: {e}", "expected": p["args"]}
        r["id"] = p["id"]
        r["check"] = p["check"]
        tel.emit("verifier", "check", {"id": p["id"], "pass": r["pass"], "measured": r["measured"],
                                       "expected": r["expected"]}, vehicle=vehicle)
        return r

    # Vision checks are network bound, so they all run at once (llm.call caps concurrency);
    # pixel checks are CPU bound and quick. Results keep flight plan order.
    with ThreadPoolExecutor(max(1, len(flight_plan))) as pool:
        results = list(pool.map(run_one, flight_plan))
    passed = sum(1 for r in results if r["pass"])
    verdict = {"pass": passed == len(results), "passed": passed, "total": len(results), "results": results}
    tel.emit("verifier", "poll", {"go": verdict["pass"], "passed": passed, "total": len(results)}, vehicle=vehicle)
    return verdict

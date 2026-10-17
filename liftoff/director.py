"""
Director: patterns + brand card -> N direction briefs -> rendered MP4 vehicles.

Rendering is Pillow frames + ffmpeg. No Blender, no Remotion, no generative
video. 540x960 at 12 fps. A 9s vehicle is 108 PNGs and renders in seconds.

Timeline per vehicle:
  [0, hook_s)                      hook text, can
  [hook_s, duration - logo_s)      body text, can
  [duration - logo_s, duration)    end card: logo badge + end_card text
The logo badge appears ONLY on the end card, so "logo seconds" is a real,
independently measurable quantity (verifier template-matches assets/<brand>/logo.png).
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from . import footage, llm, motion, playbook_files
from .brand import Brand, hex_to_rgb
from .telemetry import Telemetry

W, H, FPS = 540, 960, 12
HOOK_S = 1.2

SYSTEM = """You are the Director on a launch-video team. Using the brand card and the
pattern list from research, propose exactly {n} short vertical video directions.
Each must be buildable from: a hook line (<= 6 words), a body line (<= 8 words),
an end_card line (<= 5 words, must include the brand name), duration_s (6 to 15),
logo_seconds (how long the end card with the logo badge holds), bg ("primary"|"secondary"),
the pattern tag it draws from, and footage_query: a 3 to 6 word stock video search for the real
scene under the words (people, place, action, e.g. "friends laughing street food stall"), never a
brand or product name, never a logo. Nothing on the brand card's "never" list may appear in any
line: for "health claims" that means no wellness, gut, digestion, immunity, sugar or "good for you"
claims, even if the brand's own website makes them. Return JSON only:
{{"directions":[{{"id":"A","name":str,"pattern":str,"hook":str,"body":str,"end_card":str,
 "duration_s":int,"logo_seconds":float,"bg":str,"footage_query":str,"notes":str}}]}}"""

FIX_SYSTEM = """You are the Director. A vehicle failed verification. You get the direction
JSON and the failing checks with measured values. Return ONLY the JSON fields to change
(e.g. {"logo_seconds": 3.4, "notes": "..."}). Change the minimum needed. Never change the
brand name or remove the end card. Notes alone change nothing in the render; you must
change a field. The levers the renderer obeys:
- logo seconds too low: raise "logo_seconds" a little above the threshold (e.g. 3.4 for 3.0).
- text contrast too low: the overlay text colour is fixed by the brand card; set "bg" to the
  other brand colour (the one the text contrasts with more).
- a "never" check failed (health claim, other brand's logo): rewrite "hook", "body" and
  "end_card" so no line says it.
- background palette off: set "bg" to "primary" or "secondary".
- duration out of range: set "duration_s" inside the range.
- hook, end card or wording problems: rewrite "hook", "body" or "end_card".
- another brand's logo or anything forbidden showing in the scene: set a different
  "footage_query" (a different scene), so a new real clip is used."""


def plan(brand: Brand, research: dict[str, Any], tel: Telemetry, n: int = 3,
         plant_failure: bool = True, mission: str = "") -> list[dict[str, Any]]:
    tel.emit("director", "plan_start", {"n": n})
    user = (f"MISSION (every direction must deliver exactly this; put its specific ask, such as an offer,"
            f" a product, a setting or a length, into the hook, body or end card): {mission}\n\n"
            f"BRAND CARD:\n{json.dumps(brand.to_dict(), indent=1)}\n\n"
            f"PATTERNS:\n{json.dumps(research.get('patterns', []), indent=1)}\n\nPropose {n} directions.")
    msgs = [{"role": "system", "content": SYSTEM.format(n=n) + playbook_files.read("director")},
            {"role": "user", "content": user}]
    try:
        out = llm.call_json("director", msgs, temperature=0.7)
        if len(out.get("directions", [])) < n:
            raise ValueError(f"only {len(out.get('directions', []))} directions")
    except Exception as e:  # noqa: BLE001
        # A flight never dies on one bad creative reply: the fast model takes over.
        tel.emit("director", "fallback", {"error": str(e)[:160], "model": llm.MODELS["director_fix"]})
        out = llm.call_json("director_fix", msgs)
    dirs = out.get("directions", [])[:n]
    for i, d in enumerate(dirs):
        d.setdefault("id", "ABCDEFG"[i])
        d["duration_s"] = int(max(6, min(15, d.get("duration_s", 9))))
        d["logo_seconds"] = float(d.get("logo_seconds", 3.5))
        d.setdefault("bg", "primary")
        d["footage"] = footage.find(str(d.get("footage_query", "")), d["duration_s"] - d["logo_seconds"])
        if d["footage"]:
            tel.emit("director", "footage", {"query": d["footage"]["query"], "credit": d["footage"]["credit"]},
                     vehicle=d["id"])
    # Three directions should look like three different videos: give each a distinct style,
    # preferring the one its pattern suggests.
    used: set[str] = set()
    for d in dirs:
        want = motion.scene_style(str(d.get("pattern", "")))
        d["style"] = want if want not in used else next(
            (st for st in ("split", "macro", "kinetic", "hero") if st not in used), want)
        used.add(d["style"])
    if plant_failure and dirs:
        # Demo move: make vehicle A miss the logo threshold so the verifier catches it live.
        dirs[0]["logo_seconds"] = min(dirs[0]["logo_seconds"], 2.4)
        dirs[0]["notes"] = (dirs[0].get("notes", "") + " [planted: logo under threshold]").strip()
    for d in dirs:
        tel.emit("director", "direction", {k: d[k] for k in ("name", "pattern", "hook", "duration_s", "logo_seconds")},
                 vehicle=d["id"])
    return dirs


def fix(direction: dict[str, Any], failing: list[dict[str, Any]], tel: Telemetry,
        switch_strategy: bool = False) -> dict[str, Any]:
    user = (f"DIRECTION:\n{json.dumps(direction, indent=1)}\n\nFAILING CHECKS:\n{json.dumps(failing, indent=1)}\n\n"
            "Return only the fields to change so these checks pass.")
    if switch_strategy:
        # The arbiter saw the same check fail with the same measurement twice: the last fix
        # did nothing. Push for a different lever and loosen sampling so we don't repeat it.
        user += ("\n\nLOOP DETECTED: your last fix left these measurements unchanged. Do not repeat it. "
                 "Change a different field than last time (another bg, rewrite hook/body/end_card, "
                 "or a different pattern), and say which lever you switched to in notes.")
        tel.emit("director", "strategy_switch", {"failing": [f.get("id") for f in failing]},
                 vehicle=direction["id"])
    patch = llm.call_json("director_fix", [{"role": "system", "content": FIX_SYSTEM + playbook_files.read("director")},
                                       {"role": "user", "content": user}],
                          temperature=0.8 if switch_strategy else 0.2)
    patch = {k: v for k, v in patch.items() if k in direction or k in ("notes",)}
    new = {**direction, **patch}
    new["duration_s"] = int(max(6, min(15, new["duration_s"])))
    new["logo_seconds"] = float(min(new["logo_seconds"], new["duration_s"] - HOOK_S - 0.5))
    if new.get("footage") or new.get("footage_query"):
        # A new scene search, or a clip that showed something it shouldn't: fetch a different clip.
        need = new["duration_s"] - new["logo_seconds"]
        clip_failed = any(f.get("check") == "vision_no" for f in failing)  # something showed that must not
        if patch.get("footage_query") or clip_failed or not new.get("footage"):
            old = {new["footage"]["id"]} if new.get("footage") else set()
            new["footage"] = footage.find(str(new.get("footage_query", "")), need, avoid=old) or new.get("footage")
    tel.emit("director", "fix", {"patch": patch}, vehicle=direction["id"])
    return new


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
              "C:/Windows/Fonts/arialbd.ttf"):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size=size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _text_block(img: Image.Image, text: str, size: int, color, y_center: int) -> None:
    d = ImageDraw.Draw(img)
    f = _font(size)
    lines = _wrap(d, text, f, W - 80)
    lh = int(size * 1.15)
    y = y_center - (len(lines) * lh) // 2
    for ln in lines:
        tw = d.textlength(ln, font=f)
        d.text(((W - tw) / 2, y), ln, font=f, fill=color)
        y += lh


def render(direction: dict[str, Any], brand: Brand, out_dir: Path, tel: Telemetry,
           attempt: int) -> dict[str, Any]:
    """Render one vehicle. Returns {"mp4": path, "frames_dir": path, "fps": FPS}."""
    vid = direction["id"]
    frames_dir = out_dir / f"vehicle_{vid}_a{attempt}_frames"
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True)
    mp4 = out_dir / f"vehicle_{vid}_a{attempt}.mp4"

    n_frames = motion.frames(direction, brand, frames_dir)
    dur, logo_s = direction["duration_s"], direction["logo_seconds"]

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(motion.FPS),
           "-i", str(frames_dir / "f_%04d.png"), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
           "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", str(mp4)]
    subprocess.run(cmd, check=True)
    tel.emit("director", "rendered", {"mp4": mp4.name, "frames": n_frames, "duration_s": dur,
                                      "logo_seconds": logo_s}, vehicle=vid)
    return {"mp4": str(mp4), "frames_dir": str(frames_dir), "fps": motion.FPS}

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

from . import llm
from .brand import Brand, hex_to_rgb
from .telemetry import Telemetry

W, H, FPS = 540, 960, 12
HOOK_S = 1.2

SYSTEM = """You are the Director on a launch-video team. Using the brand card and the
pattern list from research, propose exactly {n} short vertical video directions.
Each must be buildable from: a hook line (<= 6 words), a body line (<= 8 words),
an end_card line (<= 5 words, must include the brand name), duration_s (6 to 15),
logo_seconds (how long the end card with the logo badge holds), bg ("primary"|"secondary"),
and the pattern tag it draws from. Return JSON only:
{{"directions":[{{"id":"A","name":str,"pattern":str,"hook":str,"body":str,"end_card":str,
 "duration_s":int,"logo_seconds":float,"bg":str,"notes":str}}]}}"""

FIX_SYSTEM = """You are the Director. A vehicle failed verification. You get the direction
JSON and the failing checks with measured values. Return ONLY the JSON fields to change
(e.g. {"logo_seconds": 3.4, "notes": "..."}). Change the minimum needed. Never change the
brand name or remove the end card."""


def plan(brand: Brand, research: dict[str, Any], tel: Telemetry, n: int = 3,
         plant_failure: bool = True) -> list[dict[str, Any]]:
    tel.emit("director", "plan_start", {"n": n})
    user = (f"BRAND CARD:\n{json.dumps(brand.to_dict(), indent=1)}\n\n"
            f"PATTERNS:\n{json.dumps(research.get('patterns', []), indent=1)}\n\nPropose {n} directions.")
    out = llm.call_json("director", [{"role": "system", "content": SYSTEM.format(n=n)},
                                     {"role": "user", "content": user}])
    dirs = out.get("directions", [])[:n]
    for i, d in enumerate(dirs):
        d.setdefault("id", "ABCDEFG"[i])
        d["duration_s"] = int(max(6, min(15, d.get("duration_s", 9))))
        d["logo_seconds"] = float(d.get("logo_seconds", 3.5))
        d.setdefault("bg", "primary")
    if plant_failure and dirs:
        # Demo move: make vehicle A miss the logo threshold so the verifier catches it live.
        dirs[0]["logo_seconds"] = min(dirs[0]["logo_seconds"], 2.4)
        dirs[0]["notes"] = (dirs[0].get("notes", "") + " [planted: logo under threshold]").strip()
    for d in dirs:
        tel.emit("director", "direction", {k: d[k] for k in ("name", "pattern", "hook", "duration_s", "logo_seconds")},
                 vehicle=d["id"])
    return dirs


def fix(direction: dict[str, Any], failing: list[dict[str, Any]], tel: Telemetry) -> dict[str, Any]:
    user = (f"DIRECTION:\n{json.dumps(direction, indent=1)}\n\nFAILING CHECKS:\n{json.dumps(failing, indent=1)}\n\n"
            "Return only the fields to change so these checks pass.")
    patch = llm.call_json("director", [{"role": "system", "content": FIX_SYSTEM},
                                       {"role": "user", "content": user}])
    patch = {k: v for k, v in patch.items() if k in direction or k in ("notes",)}
    new = {**direction, **patch}
    new["duration_s"] = int(max(6, min(15, new["duration_s"])))
    new["logo_seconds"] = float(min(new["logo_seconds"], new["duration_s"] - HOOK_S - 0.5))
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

    bg_hex = brand.primary_hex if direction.get("bg") == "primary" else brand.secondary_hex
    bg = hex_to_rgb(bg_hex)
    fg = hex_to_rgb(brand.text_hex)
    can = Image.open(brand.can_path).convert("RGBA")
    can = can.resize((int(can.width * (420 / can.height)), 420))
    logo = Image.open(brand.logo_path).convert("RGBA")

    dur = direction["duration_s"]
    logo_s = direction["logo_seconds"]
    n_frames = int(dur * FPS)
    end_start = dur - logo_s

    for i in range(n_frames):
        t = i / FPS
        img = Image.new("RGB", (W, H), bg)
        if t < end_start:
            # can with a slow rise
            rise = int(40 * min(1.0, t / 2.0))
            img.paste(can, ((W - can.width) // 2, H - can.height - 60 - rise), can)
            if t < HOOK_S:
                _text_block(img, direction["hook"], 64, fg, 300)
            else:
                _text_block(img, direction["body"], 48, fg, 300)
        else:
            img.paste(logo, ((W - logo.width) // 2, 320), logo)
            _text_block(img, direction["end_card"], 44, fg, 320 + logo.height + 80)
        img.save(frames_dir / f"f_{i:04d}.png")

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS),
           "-i", str(frames_dir / "f_%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", str(mp4)]
    subprocess.run(cmd, check=True)
    tel.emit("director", "rendered", {"mp4": mp4.name, "frames": n_frames, "duration_s": dur,
                                      "logo_seconds": logo_s}, vehicle=vid)
    return {"mp4": str(mp4), "frames_dir": str(frames_dir), "fps": FPS}

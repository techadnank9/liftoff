"""
Generate brand assets with Pillow so nobody needs a designer tonight.

    python scripts/make_assets.py --name Fizz --primary "#D85A30" --secondary "#26215C"

Writes assets/<name_lower>/{can.png, logo.png, brand.json}.
logo.png is an opaque white badge with the brand name in the primary color,
so the verifier can template-match it on any background.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent


def font(size: int):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size=size)


def hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def lighten(rgb, f=0.25):
    return tuple(int(c + (255 - c) * f) for c in rgb)


def darken(rgb, f=0.25):
    return tuple(int(c * (1 - f)) for c in rgb)


def make_can(name: str, primary: str, out: Path) -> None:
    W, H = 300, 600
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    p = hex_to_rgb(primary)
    body = (40, 60, 260, 560)
    d.rounded_rectangle(body, radius=40, fill=p)
    # highlight strip and shadow strip for a bit of volume
    d.rounded_rectangle((60, 70, 95, 550), radius=18, fill=lighten(p, 0.35))
    d.rounded_rectangle((215, 70, 245, 550), radius=18, fill=darken(p, 0.3))
    # top rim and lid
    d.ellipse((40, 30, 260, 90), fill=(200, 200, 205))
    d.ellipse((55, 38, 245, 82), fill=(225, 225, 230))
    d.ellipse((120, 50, 180, 70), fill=(170, 170, 178))
    # label band
    d.rectangle((40, 220, 260, 400), fill=(255, 255, 255))
    f = font(72)
    tw = d.textlength(name, font=f)
    d.text(((W - tw) / 2, 265), name, font=f, fill=p)
    f2 = font(22)
    sub = "COLA"
    tw2 = d.textlength(sub, font=f2)
    d.text(((W - tw2) / 2, 350), sub, font=f2, fill=darken(p, 0.4))
    img.save(out)


def make_logo(name: str, primary: str, out: Path) -> None:
    f = font(84)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    tw = int(tmp.textlength(name, font=f))
    W, H = tw + 80, 150
    img = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, W - 1, H - 1), radius=28, fill=(255, 255, 255), outline=hex_to_rgb(primary), width=6)
    d.text((40, 24), name, font=f, fill=hex_to_rgb(primary))
    img.save(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="Fizz")
    ap.add_argument("--category", default="cola")
    ap.add_argument("--market", default="US")
    ap.add_argument("--primary", default="#D85A30")
    ap.add_argument("--secondary", default="#26215C")
    ap.add_argument("--tone", default="bold,playful,direct")
    a = ap.parse_args()
    out = ROOT / "assets" / a.name.lower()
    out.mkdir(parents=True, exist_ok=True)
    make_can(a.name, a.primary, out / "can.png")
    make_logo(a.name, a.primary, out / "logo.png")
    card = {
        "name": a.name, "category": a.category, "market": a.market,
        "primary_hex": a.primary, "secondary_hex": a.secondary, "text_hex": "#FFFFFF",
        "tone": a.tone.split(","), "logo_path": str(out / "logo.png"), "can_path": str(out / "can.png"),
        "must_haves": ["brand name visible", "vertical 9:16", "under 15 seconds"],
        "never": ["health claims", "competitor logos"],
    }
    (out / "brand.json").write_text(json.dumps(card, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

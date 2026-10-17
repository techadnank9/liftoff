"""
Motion renderer: a direction becomes a short vertical ad. Pillow frames + ffmpeg only.

Built so every check the verifier runs still measures something real:
  - the top 45% of every frame is the exact brand colour (palette_within, text contrast)
  - overlay text is white on the chosen background (text_contrast_at_least)
  - the logo badge is pasted at its true size on the end card (logo_seconds_at_least)

Look: brand colour gradient with a soft light behind the product, a rim-lit can that drops
in and floats, rising fizz, word-by-word kinetic type, and a logo pop on the end card.
"""
from __future__ import annotations

import math
import random
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 540, 960, 24
HOOK_S = 1.2

HEAVY = ("/System/Library/Fonts/Supplemental/Arial Black.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "C:/Windows/Fonts/ariblk.ttf")
BOLD = ("/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf")


@lru_cache(maxsize=64)
def font(size: int, heavy: bool = True):
    for p in (HEAVY if heavy else BOLD):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size=size)


def rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def mix(a, b, t: float):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def ease_out_back(t: float, s: float = 1.6) -> float:
    t = max(0.0, min(1.0, t)) - 1
    return t * t * ((s + 1) * t + s) + 1


def ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


# ---------- static layers, built once per vehicle ----------

def background(color) -> Image.Image:
    """Exact brand colour across the top band, deepening downward, light behind the product, vignette."""
    base = Image.new("RGB", (W, H), color)
    dark = mix(color, (0, 0, 0), 0.42)
    grad = Image.new("L", (1, H))
    for y in range(H):
        # Flat brand colour through the text zone (top 45%): the contrast check measures the
        # real background behind the words, not a darker shade further down.
        t = 0.0 if y < H * 0.45 else ((y - H * 0.45) / (H * 0.55)) ** 1.3
        grad.putpixel((0, y), int(255 * t))
    base = Image.composite(Image.new("RGB", (W, H), dark), base, grad.resize((W, H)))
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse((W * 0.08, H * 0.42, W * 0.92, H * 0.98), fill=150)
    glow = glow.filter(ImageFilter.GaussianBlur(70))
    base = Image.composite(Image.new("RGB", (W, H), mix(color, (255, 255, 255), 0.35)), base, glow)
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).rectangle((0, int(H * 0.12), W, H), fill=0)
    edge = Image.new("L", (W, H), 255)
    ImageDraw.Draw(edge).ellipse((-W * 0.25, H * 0.05, W * 1.25, H * 1.15), fill=0)
    edge = edge.filter(ImageFilter.GaussianBlur(90))
    top_guard = Image.new("L", (W, H), 255)
    ImageDraw.Draw(top_guard).rectangle((0, 0, W, int(H * 0.45)), fill=0)
    edge = ImageChops.multiply(edge, top_guard.filter(ImageFilter.GaussianBlur(12)))
    return Image.composite(Image.new("RGB", (W, H), mix(color, (0, 0, 0), 0.6)), base, edge.point(lambda v: int(v * 0.55)))


def lit_can(can: Image.Image, height: int) -> Image.Image:
    """Can with a white rim light and halo so it reads on any background, even its own colour."""
    can = can.resize((int(can.width * height / can.height), height), Image.LANCZOS)
    pad = 40
    out = Image.new("RGBA", (can.width + 2 * pad, can.height + 2 * pad), (0, 0, 0, 0))
    a = Image.new("L", out.size, 0)
    a.paste(can.getchannel("A"), (pad, pad))
    halo = a.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(14)).point(lambda v: int(v * 0.55))
    out.paste(Image.new("RGBA", out.size, (255, 255, 255, 255)), (0, 0), halo)
    rim = a.filter(ImageFilter.MaxFilter(5))
    out.paste(Image.new("RGBA", out.size, (255, 255, 255, 255)), (0, 0), rim)
    out.alpha_composite(can, (pad, pad))
    return out


def shadow(width: int) -> Image.Image:
    s = Image.new("RGBA", (width + 80, 90), (0, 0, 0, 0))
    ImageDraw.Draw(s).ellipse((40, 30, width + 40, 60), fill=(0, 0, 0, 120))
    return s.filter(ImageFilter.GaussianBlur(12))


# ---------- per-frame drawing ----------

def bubbles(seed: int, n: int):
    rnd = random.Random(seed)
    return [(rnd.uniform(0.25, 0.75), rnd.uniform(0, 1), rnd.uniform(3, 11), rnd.uniform(0.18, 0.45), rnd.uniform(0, 6.28))
            for _ in range(n)]


def draw_bubbles(layer: ImageDraw.ImageDraw, parts, t: float, speed: float, top: int, bottom: int) -> None:
    span = bottom - top
    for x, phase, r, v, wob in parts:
        p = (phase + t * v * speed) % 1.0
        y = bottom - p * span
        xx = x * W + math.sin(t * 2.2 + wob) * 14 * p
        a = int(170 * (1 - p) * min(1.0, p * 6))
        layer.ellipse((xx - r, y - r, xx + r, y + r), outline=(255, 255, 255, a), width=2)
        layer.ellipse((xx - r * 0.35 - 1, y - r * 0.55, xx - r * 0.35 + 1.5, y - r * 0.55 + 2.5), fill=(255, 255, 255, a))


def wrap(d: ImageDraw.ImageDraw, words: list[str], f, max_w: int) -> list[list[str]]:
    lines, cur = [], []
    for w in words:
        if cur and d.textlength(" ".join(cur + [w]), font=f) > max_w:
            lines.append(cur)
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(cur)
    return lines


def kinetic(img: Image.Image, text: str, size: int, color, y_center: int, t: float, stagger: float = 0.09) -> None:
    """Words pop in one after another; settled text is plain white on the background."""
    d = ImageDraw.Draw(img)
    f = font(size)
    words = text.split()
    lines = wrap(d, words, f, W - 70)
    while len(lines) > 3 and size > 30:
        size -= 4
        f = font(size)
        lines = wrap(d, words, f, W - 70)
    lh = int(size * 1.12)
    y = y_center - (len(lines) * lh) // 2
    k = 0
    space = d.textlength(" ", font=f)
    for ln in lines:
        lw = sum(d.textlength(w, font=f) for w in ln) + space * (len(ln) - 1)
        x = (W - lw) / 2
        for w in ln:
            p = ease_out_back((t - k * stagger) / 0.28)
            ww = d.textlength(w, font=f)
            if p > 0.02:
                dy = int((1 - min(1.0, p)) * 26)
                d.text((x, y + dy), w, font=f, fill=color)
            x += ww + space
            k += 1
        y += lh


PANEL_H = int(H * 0.45)


def scene_style(pattern: str) -> str:
    """Which visual style a direction gets, from the pattern it draws on."""
    p = pattern.lower()
    if any(k in p for k in ("taste", "challenge", "versus", "vs", "swap", "reaction")):
        return "split"
    if any(k in p for k in ("asmr", "slow", "process", "pour")):
        return "macro"
    if any(k in p for k in ("countdown", "humor", "hook", "beat", "meme", "launch")):
        return "kinetic"
    return "hero"


def mystery(can: Image.Image) -> Image.Image:
    """The rival can in a taste test: greyed out, label hidden behind a big question mark."""
    from PIL import ImageOps

    g = ImageOps.grayscale(can.convert("RGB")).convert("RGBA")
    g.putalpha(can.getchannel("A"))
    g = Image.blend(g, Image.new("RGBA", g.size, (120, 120, 126, 255)), 0.35)
    g.putalpha(can.getchannel("A"))
    d = ImageDraw.Draw(g)
    f = font(int(g.width * 0.55))
    w = d.textlength("?", font=f)
    d.text(((g.width - w) / 2, g.height * 0.38), "?", font=f, fill=(255, 255, 255, 255))
    return g


def droplets(seed: int, n: int):
    rnd = random.Random(seed + 7)
    return [(rnd.uniform(0.15, 0.85), rnd.uniform(0, 1), rnd.uniform(2.5, 6), rnd.uniform(0.05, 0.16)) for _ in range(n)]


def footage_frames(clip: dict | None, seconds: float, out_dir: Path) -> list[Path]:
    """Frames of the real clip, scaled and cropped to fill the area under the brand panel."""
    import subprocess

    if not clip or not Path(clip.get("path", "")).exists():
        return []
    d = Path(out_dir).parent / (Path(out_dir).name + "_clip")
    d.mkdir(parents=True, exist_ok=True)
    for old in d.glob("c_*.png"):
        old.unlink()
    h = H - PANEL_H
    vf = f"fps={FPS},scale={W}:{h}:force_original_aspect_ratio=increase,crop={W}:{h}"
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-t", f"{seconds + 0.2:.2f}", "-i", clip["path"],
                        "-vf", vf, str(d / "c_%04d.png")], check=True, timeout=120)
    except Exception:  # noqa: BLE001
        return []
    return sorted(d.glob("c_*.png"))


def frames(direction: dict, brand, out_dir: Path) -> int:
    """Render every frame of one vehicle into out_dir as f_0000.png... Returns the frame count."""
    bg_hex = brand.primary_hex if direction.get("bg") == "primary" else brand.secondary_hex
    color, fg = rgb(bg_hex), rgb(brand.text_hex)
    pattern = str(direction.get("pattern", ""))
    slow = "slow" in pattern
    fizz = 70 if ("asmr" in pattern or "pour" in pattern) else 42

    bg = background(color)
    can = lit_can(Image.open(brand.can_path).convert("RGBA"), 430)
    sh = shadow(int(can.width * 0.7))
    logo = Image.open(brand.logo_path).convert("RGBA")
    parts = bubbles(hash(direction.get("id", "A")) & 0xFFFF, fizz)

    dur = float(direction["duration_s"])
    logo_s = float(direction["logo_seconds"])
    n = int(dur * FPS)
    end_start = dur - logo_s
    speed = 0.55 if slow else 1.0

    style = direction.get("style") or scene_style(pattern)
    other = rgb(brand.secondary_hex if direction.get("bg") == "primary" else brand.primary_hex)
    if style == "split":
        half_can = lit_can(Image.open(brand.can_path).convert("RGBA"), 300)
        rival = mystery(half_can)
    if style == "macro":
        big_can = lit_can(Image.open(brand.can_path).convert("RGBA"), 980)
        drops = droplets(hash(direction.get("id", "A")) & 0xFFFF, 26)
        parts = bubbles(hash(direction.get("id", "A")) & 0xFFFF, 90)
    if style == "kinetic":
        mini_can = lit_can(Image.open(brand.can_path).convert("RGBA"), 300)
    clip_frames = footage_frames(direction.get("footage"), end_start, out_dir) if direction.get("footage") else []
    if clip_frames:
        panel = Image.new("RGB", (W, H), color)  # flat brand colour behind the words (top 45%)
        small_can = lit_can(Image.open(brand.can_path).convert("RGBA"), 250)

    for i in range(n):
        t = i / FPS
        img = bg.copy()
        if t < end_start and clip_frames:
            # "Text on top, real video below": the common Reels/TikTok ad format. The words sit on
            # flat brand colour, so readability and brand-colour checks measure the real thing.
            img = panel.copy()
            fr = clip_frames[min(i, len(clip_frames) - 1)]
            img.paste(Image.open(fr).convert("RGB"), (0, PANEL_H))
            # product in the corner of the real scene, gently floating
            fy = int(math.sin(t * 2.0) * 5)
            pop = ease_out_back(t / 0.5, 1.4)
            if pop > 0.05:
                c = small_can if pop >= 0.999 else small_can.resize(
                    (max(1, int(small_can.width * pop)), max(1, int(small_can.height * pop))), Image.BILINEAR)
                img.paste(c, (W - c.width - 6, H - c.height - 10 + fy), c)
            if t < HOOK_S:
                kinetic(img, direction["hook"], 66, fg, PANEL_H // 2 + 10, t)
            else:
                kinetic(img, direction["body"], 54, fg, PANEL_H // 2 + 10, t - HOOK_S, stagger=0.06)
            if 0 <= t - HOOK_S < 2 / FPS:
                img = Image.blend(img, Image.new("RGB", (W, H), (255, 255, 255)), 0.2)
        elif t < end_start and style == "split":
            # Taste test: a mystery can on one side, yours on the other; your side takes over.
            take = ease_out(max(0.0, (t - end_start * 0.55) / 0.6))  # 0 -> 1 near the end
            mid = int(W / 2 - take * W / 2)
            lower = Image.new("RGB", (W, H - PANEL_H), mix(other, (0, 0, 0), 0.25))
            ImageDraw.Draw(lower).rectangle((mid, 0, W, H), fill=mix(color, (255, 255, 255), 0.18))
            img.paste(lower, (0, PANEL_H))
            d = ImageDraw.Draw(img)
            fl = font(54)
            if mid > 40:
                d.text((mid / 2 - 18, PANEL_H + 24), "A", font=fl, fill=(255, 255, 255))
                img.paste(rival, (int(mid / 2 - rival.width / 2), H - rival.height - 40 + int(math.sin(t * 2.6) * 5)), rival)
            d.text(((mid + W) / 2 - 18, PANEL_H + 24), "B", font=fl, fill=fg)
            bob = int(math.sin(t * 2.6 + 1.5) * 5)
            img.paste(half_can, (int((mid + W) / 2 - half_can.width / 2), H - half_can.height - 40 + bob), half_can)
            if t < HOOK_S:
                kinetic(img, direction["hook"], 76, fg, PANEL_H // 2, t)
            else:
                kinetic(img, direction["body"], 60, fg, PANEL_H // 2, t - HOOK_S, stagger=0.06)
        elif t < end_start and style == "macro":
            # Close-up: the can fills the frame, condensation runs down it, a slow push-in.
            z = 1 + 0.10 * ease_out(t / max(1.0, end_start))
            c = big_can.resize((int(big_can.width * z), int(big_can.height * z)), Image.BILINEAR)
            # the label sits mid-frame; the can's top runs behind the word panel
            cx, cy = (W - c.width) // 2, int(PANEL_H - c.height * 0.30 + (1 - ease_out(t / 0.8)) * 220)
            img.paste(c, (cx, cy), c)
            ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            od = ImageDraw.Draw(ov)
            for x, ph, r, v in drops:  # drops slide down the can face, below the words
                y = PANEL_H + 20 + ((ph + t * v) % 1.0) * (H - PANEL_H - 40)
                xx = cx + c.width * x
                od.ellipse((xx - r, y - r * 1.4, xx + r, y + r * 1.4), fill=(255, 255, 255, 120))
                od.ellipse((xx - r * 0.3, y - r * 0.9, xx + r * 0.15, y - r * 0.4), fill=(255, 255, 255, 220))
            draw_bubbles(od, parts, t, 0.6, PANEL_H + 10, H)
            img.paste(ov, (0, 0), ov)
            img.paste(Image.new("RGB", (W, PANEL_H), color), (0, 0))  # keep the words on flat brand colour
            if t < HOOK_S:
                kinetic(img, direction["hook"], 76, fg, PANEL_H // 2, t)
            else:
                kinetic(img, direction["body"], 60, fg, PANEL_H // 2, t - HOOK_S, stagger=0.09)
        elif t < end_start and style == "kinetic":
            # Kinetic type: big words land on the beat, stripes pulse, a small can bounces in time.
            beat = 0.42
            k = (t % beat) / beat
            d = ImageDraw.Draw(img)
            shade = mix(color, (0, 0, 0), 0.18)
            off = int((t * 160) % 80)
            for x0 in range(-H, W + H, 80):  # diagonal stripes below the words
                d.polygon([(x0 + off, H), (x0 + 40 + off, H), (x0 + 40 + off - (H - PANEL_H), PANEL_H),
                           (x0 + off - (H - PANEL_H), PANEL_H)], fill=shade)
            img.paste(Image.new("RGB", (W, PANEL_H), color), (0, 0))
            hop = int(abs(math.sin(math.pi * k)) * 36)
            img.paste(mini_can, ((W - mini_can.width) // 2, H - mini_can.height - 50 - hop), mini_can)
            words = direction["hook"] if t < HOOK_S else direction["body"]
            tt = t if t < HOOK_S else t - HOOK_S
            kinetic(img, words, 92 if t < HOOK_S else 74, fg, PANEL_H // 2, tt, stagger=0.16)
            if k < 0.12 and t > 0.3:  # a short flash on each beat
                img = Image.blend(img, Image.new("RGB", (W, H), (255, 255, 255)), 0.10)
        elif t < end_start:
            # product: drop in with a bounce, then float and slowly push in
            drop = ease_out_back(t / (0.9 if slow else 0.6), 1.3)
            push = 1 + 0.07 * ease_out(t / max(1.0, end_start))
            float_y = math.sin(t * (1.6 if slow else 2.4)) * 7
            ch = int(can.height * push)
            cw = int(can.width * push)
            c = can.resize((cw, ch), Image.BILINEAR).rotate(math.sin(t * 1.7) * (1.5 if slow else 3), resample=Image.BICUBIC, expand=False)
            cx = (W - cw) // 2
            target_y = H - ch - 30
            cy = int(-ch + (target_y + ch) * drop + float_y)
            img.paste(sh, ((W - sh.width) // 2, H - 120), sh)
            overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            draw_bubbles(ImageDraw.Draw(overlay), parts, t, speed, int(H * 0.47), H - 140)
            img.paste(overlay, (0, 0), overlay)
            img.paste(c, (cx, cy), c)
            if t < HOOK_S:
                kinetic(img, direction["hook"], 82, fg, 250, t)
            else:
                kinetic(img, direction["body"], 62, fg, 250, t - HOOK_S, stagger=0.06)
            # a two-frame flash marks the cut from hook to body
            if 0 <= t - HOOK_S < 2 / FPS:
                img = Image.blend(img, Image.new("RGB", (W, H), (255, 255, 255)), 0.25)
        else:
            te = t - end_start
            overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            draw_bubbles(ImageDraw.Draw(overlay), parts, t, speed * 0.6, int(H * 0.2), H)
            img.paste(overlay, (0, 0), overlay)
            # logo pops, then sits at exactly its true size (the verifier template-matches it)
            s = ease_out_back(te / 0.22, 2.0) if te < 0.22 else 1.0
            lg = logo if s == 1.0 else logo.resize((max(1, int(logo.width * s)), max(1, int(logo.height * s))), Image.BILINEAR)
            img.paste(lg, ((W - lg.width) // 2, 320 + (logo.height - lg.height) // 2), lg)
            kinetic(img, direction["end_card"], 54, fg, 320 + logo.height + 95, te - 0.15, stagger=0.07)
        img.save(out_dir / f"f_{i:04d}.png", compress_level=1)
    return n

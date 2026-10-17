"""
Brand card. Phase 1: a fixture (Fizz). Phase 2: learned from a URL via You.com.

The brand card is the shared project file every agent reads first.
Keep it small and explicit; the Spec agent turns it into predicates.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"


@dataclass
class Brand:
    name: str
    category: str
    market: str
    primary_hex: str
    secondary_hex: str
    text_hex: str
    tone: list[str]
    logo_path: str
    can_path: str
    must_haves: list[str] = field(default_factory=list)
    never: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


FIZZ = Brand(
    name="Fizz",
    category="cola",
    market="US",
    primary_hex="#D85A30",
    secondary_hex="#26215C",
    text_hex="#FFFFFF",
    tone=["bold", "playful", "direct"],
    logo_path=str(ASSETS / "fizz" / "logo.png"),
    can_path=str(ASSETS / "fizz" / "can.png"),
    must_haves=["brand name visible", "vertical 9:16", "under 15 seconds"],
    never=["health claims", "competitor logos"],
)


def load(name: str = "fizz") -> Brand:
    """Phase 1: fixtures only. Phase 2: look up assets/<name>/brand.json or learn from URL."""
    p = ASSETS / name / "brand.json"
    if p.exists():
        data = json.loads(p.read_text())
        return Brand(**{k: v for k, v in data.items() if k in Brand.__dataclass_fields__})
    if name.lower() == "fizz":
        return FIZZ
    raise FileNotFoundError(f"No brand card for {name}. Add assets/{name}/brand.json or run scripts/make_assets.py")


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]

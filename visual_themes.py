"""Selectable visual presets; applying a preset is the only destructive action."""
from __future__ import annotations

from copy import deepcopy


THEME_TECHNICAL = "Painel Técnico"
THEME_REBEL = "Rebel"


TECHNICAL_PORTRAIT = {
    "cpu": {"y": 54, "h": 52}, "gpu": {"y": 112, "h": 52}, "ram": {"y": 170, "h": 52},
    "disks": {"y": 228, "h": 30}, "art": {"x": 70, "y": 66, "size": 180},
    "title": {"x": 160, "y": 284}, "artist": {"x": 160, "y": 316},
    "state": {"x": 160, "y": 344}, "progress": {"x": 28, "y": 375, "w": 264},
}

TECHNICAL_HORIZONTAL = {
    **TECHNICAL_PORTRAIT,
    "cpu": {"y": 50, "h": 48}, "gpu": {"y": 104, "h": 48}, "ram": {"y": 158, "h": 48},
    "disks": {"y": 216, "h": 30}, "art": {"x": 70, "y": 64, "size": 180},
}

# Native cassette-futurism template: independent profiles, no external asset.
REBEL_PORTRAIT = {
    "cpu": {"y": 64, "h": 58}, "gpu": {"y": 130, "h": 58}, "ram": {"y": 198, "h": 50},
    "disks": {"y": 266, "h": 27}, "art": {"x": 66, "y": 72, "size": 188},
    "title": {"x": 160, "y": 290}, "artist": {"x": 160, "y": 321},
    "state": {"x": 160, "y": 349}, "progress": {"x": 26, "y": 382, "w": 268},
}
REBEL_HORIZONTAL = {
    **REBEL_PORTRAIT,
    "cpu": {"y": 58, "h": 54}, "gpu": {"y": 120, "h": 54}, "ram": {"y": 182, "h": 48},
    "disks": {"y": 246, "h": 27}, "art": {"x": 66, "y": 68, "size": 188},
}


def available_themes() -> tuple[str, str]:
    return THEME_REBEL, THEME_TECHNICAL


def layout_templates(name: str, defaults: dict) -> dict[str, dict]:
    """Return independent portrait/landscape profiles for an explicit apply."""
    if name == THEME_TECHNICAL:
        return {"vertical": deepcopy(TECHNICAL_PORTRAIT), "horizontal": deepcopy(TECHNICAL_HORIZONTAL)}
    return {"vertical": deepcopy(REBEL_PORTRAIT), "horizontal": deepcopy(REBEL_HORIZONTAL)}

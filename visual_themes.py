"""Selectable visual presets; applying a preset is the only destructive action."""
from __future__ import annotations

from copy import deepcopy


THEME_TECHNICAL = "Painel Técnico"
THEME_REBEL = "Rebel"
THEME_CASSETTE = "Cassette Futurism"


# Soundwave G1-inspired cassette-futurism palette.  These are semantic tokens
# so the renderer can remain structural instead of carrying scattered hex values.
SOUNDWAVE_PALETTE = {
    "background_primary": "#08111A",
    "background_secondary": "#0D1B28",
    "background_inset": "#101E2C",
    "background_inactive": "#1A2633",
    "blue_primary": "#243D91",
    "blue_secondary": "#163E6A",
    "blue_accent": "#245F9E",
    "blue_light": "#6FA8D6",
    "silver_primary": "#C7CCD3",
    "silver_secondary": "#9EA7B3",
    "steel_dark": "#667180",
    "red_visor": "#C62835",
    "red_dark": "#8E1D28",
    "amber_primary": "#E7BD46",
    "amber_secondary": "#C6921A",
    "purple_decepticon": "#75469A",
    "text_primary": "#D9DEE5",
    "text_secondary": "#AEB8C5",
    "text_muted": "#718093",
    "text_disabled": "#526071",
    "border_primary": "#3B5269",
    "border_subtle": "#223142",
    "border_highlight": "#4E6278",
    "cassette_body": "#AEB8C5",
    "cassette_body_shadow": "#667180",
    "cassette_body_highlight": "#C7CCD3",
    "cassette_border": "#163E6A",
    "cassette_window": "#101E2C",
    "cassette_window_border": "#243D91",
    "cassette_window_text": "#AEB8C5",
    "cassette_window_accent": "#E7BD46",
}


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

CASSETTE_PORTRAIT = {
    "cpu": {"y": 58, "h": 50}, "gpu": {"y": 114, "h": 50}, "ram": {"y": 170, "h": 46},
    "disks": {"y": 226, "h": 28}, "art": {"x": 72, "y": 65, "size": 176},
    "title": {"x": 160, "y": 267}, "artist": {"x": 160, "y": 298},
    "state": {"x": 160, "y": 326}, "progress": {"x": 26, "y": 365, "w": 268},
}
CASSETTE_HORIZONTAL = {
    **CASSETTE_PORTRAIT,
    "cpu": {"y": 54, "h": 46}, "gpu": {"y": 106, "h": 46}, "ram": {"y": 158, "h": 42},
    "disks": {"y": 210, "h": 26}, "art": {"x": 72, "y": 62, "size": 176},
}


def available_themes() -> tuple[str, str]:
    return THEME_REBEL, THEME_TECHNICAL, THEME_CASSETTE


def layout_templates(name: str, defaults: dict) -> dict[str, dict]:
    """Return independent portrait/landscape profiles for an explicit apply."""
    if name == THEME_TECHNICAL:
        return {"vertical": deepcopy(TECHNICAL_PORTRAIT), "horizontal": deepcopy(TECHNICAL_HORIZONTAL)}
    if name == THEME_CASSETTE:
        return {"vertical": deepcopy(CASSETTE_PORTRAIT), "horizontal": deepcopy(CASSETTE_HORIZONTAL)}
    return {"vertical": deepcopy(REBEL_PORTRAIT), "horizontal": deepcopy(REBEL_HORIZONTAL)}

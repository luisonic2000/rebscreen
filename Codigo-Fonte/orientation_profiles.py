"""Persistence-safe independent layout profiles for each preview geometry."""
from __future__ import annotations

from copy import deepcopy


PORTRAIT_SIZE = (320, 480)
LANDSCAPE_SIZE = (480, 320)


def canvas_dimensions(orientation: str) -> tuple[int, int]:
    return LANDSCAPE_SIZE if orientation == "horizontal" else PORTRAIT_SIZE


def make_profiles(portrait_layout: dict[str, dict[str, int]]) -> dict[str, dict[str, dict[str, int]]]:
    """Create independent profile objects; never alias portrait and landscape."""
    return {"vertical": deepcopy(portrait_layout), "horizontal": deepcopy(portrait_layout)}


def profile_for(profiles: dict[str, dict[str, dict[str, int]]], orientation: str) -> dict[str, dict[str, int]]:
    # Inverted is the portrait layout displayed upside down, not a third design.
    return profiles["horizontal" if orientation == "horizontal" else "vertical"]

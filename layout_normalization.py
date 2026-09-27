"""Repair malformed persisted layout values without resetting valid customization."""
from __future__ import annotations

from collections.abc import MutableMapping


def _clamp(value: object, low: int, high: int, default: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def normalize_profile(profile: MutableMapping[str, MutableMapping[str, object]], defaults: dict[str, dict[str, int]]) -> bool:
    """Keep every module visible on the 320×480 logical canvas.

    It changes only malformed/out-of-range fields and leaves all valid user
    choices intact. Horizontal preview uses its own profile but the same
    logical canvas before rotation.
    """
    changed = False
    for key, default in defaults.items():
        item = profile.setdefault(key, dict(default))
        for field, fallback in default.items():
            if field not in item:
                item[field] = fallback
                changed = True
    for key in ("cpu", "gpu", "ram", "disks"):
        item, default = profile[key], defaults[key]
        y = _clamp(item.get("y"), 55, 420, default["y"])
        h = _clamp(item.get("h"), 28, 150, default["h"])
        if (item.get("y"), item.get("h")) != (y, h):
            item["y"], item["h"] = y, h; changed = True
    art, default = profile["art"], defaults["art"]
    size = _clamp(art.get("size"), 56, 300, default["size"])
    x = _clamp(art.get("x"), 0, 320 - size, default["x"])
    y = _clamp(art.get("y"), 55, 480 - size, default["y"])
    if (art.get("x"), art.get("y"), art.get("size")) != (x, y, size):
        art["x"], art["y"], art["size"] = x, y, size; changed = True
    progress, default = profile["progress"], defaults["progress"]
    width = _clamp(progress.get("w"), 80, 300, default["w"])
    x = _clamp(progress.get("x"), 0, 320 - width, default["x"])
    y = _clamp(progress.get("y"), 55, 440, default["y"])
    if (progress.get("x"), progress.get("y"), progress.get("w")) != (x, y, width):
        progress["x"], progress["y"], progress["w"] = x, y, width; changed = True
    profile.pop("lyrics", None)  # retired Player module in pre-vNext layouts
    for key in ("title", "artist", "state"):
        item, default = profile[key], defaults[key]
        x = _clamp(item.get("x"), 20, 300, default["x"])
        y = _clamp(item.get("y"), 55, 455, default["y"])
        if (item.get("x"), item.get("y")) != (x, y):
            item["x"], item["y"] = x, y; changed = True
    return changed

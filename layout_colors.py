"""Per-item editor color preferences, stored inside a layout profile."""
from __future__ import annotations

COLOR_FIELDS = ("text_color", "accent_color", "background_color", "alert_color")


def set_item_color(item: dict, field: str, color: str | None) -> None:
    if field not in COLOR_FIELDS: raise ValueError(field)
    if color in (None, "", "transparent"):
        item.pop(field, None)
    else:
        item[field] = color


def reset_item_colors(item: dict) -> None:
    for field in COLOR_FIELDS: item.pop(field, None)

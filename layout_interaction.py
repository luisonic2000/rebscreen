"""Fast, testable layout-edit rules.  They do no rendering, I/O, or device work."""
from __future__ import annotations

from typing import MutableMapping


MODULE_KEYS = {"cpu", "gpu", "ram", "disks"}


def apply_drag(item: MutableMapping[str, int], key: str, mode: str, dx: int, dy: int) -> bool:
    """Mutate one layout item within the 320 x 480 vertical design bounds.

    Returning ``True`` means only the inexpensive canvas overlay needs updating.
    The caller renders and persists once the gesture ends.
    """
    if not dx and not dy:
        return False
    if mode == "resize":
        if key == "art":
            item["size"] = max(56, min(300, item["size"] + max(dx, dy)))
        elif key == "progress":
            item["w"] = max(80, min(300, item["w"] + dx))
        elif key in MODULE_KEYS:
            item["h"] = max(28, min(150, item["h"] + dy))
        return True
    if key == "art":
        item["x"] = max(0, min(320 - item["size"], item["x"] + dx))
        item["y"] = max(55, min(480 - item["size"], item["y"] + dy))
    elif key == "progress":
        item["x"] = max(0, min(320 - item["w"], item["x"] + dx))
        item["y"] = max(55, min(440, item["y"] + dy))
    elif key in MODULE_KEYS:
        item["y"] = max(55, min(420, item["y"] + dy))
    else:
        item["x"] = max(20, min(300, item["x"] + dx))
        item["y"] = max(55, min(455, item["y"] + dy))
    return True

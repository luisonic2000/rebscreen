"""Small native vector-style source marks; no downloaded brand asset needed."""
from __future__ import annotations


def source_kind(source: str) -> str:
    value = (source or "").casefold()
    if "spotify" in value: return "spotify"
    if "vlc" in value: return "vlc"
    if any(name in value for name in ("edge", "chrome", "firefox", "browser", "navegador")): return "browser"
    if "windows" in value: return "windows"
    return "unknown"


def draw_source_icon(draw, xy: tuple[int, int], source: str) -> str:
    """Render a crisp 14px identifier and return its resolved kind."""
    x, y = xy; kind = source_kind(source)
    if kind == "spotify":
        draw.ellipse((x, y, x+14, y+14), fill="#1ed760")
        for offset in (4, 7, 10): draw.arc((x+3, y+offset-2, x+11, y+offset+3), 200, 340, fill="#101315", width=1)
    elif kind == "vlc":
        draw.polygon(((x+7,y),(x+12,y+13),(x+2,y+13)), fill="#f28b2f")
    elif kind == "browser":
        draw.ellipse((x, y, x+14, y+14), outline="#50bce8", width=2); draw.line((x+1,y+7,x+13,y+7), fill="#50bce8")
    elif kind == "windows":
        draw.rectangle((x,y,x+6,y+6), fill="#4aa8ff"); draw.rectangle((x+8,y,x+14,y+6), fill="#4aa8ff"); draw.rectangle((x,y+8,x+6,y+14), fill="#4aa8ff"); draw.rectangle((x+8,y+8,x+14,y+14), fill="#4aa8ff")
    return kind

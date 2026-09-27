"""Protocol capability declaration.

Revision A frame protocol has an evidenced image command only; it has no
documented brightness command, so the application must never pretend to set
hardware brightness.
"""

HARDWARE_BRIGHTNESS_SUPPORTED = False


def brightness_status(value: int) -> str:
    return f"Brilho da prévia: {max(10, min(100, int(value)))}%"

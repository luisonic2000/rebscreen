"""Brightness policy for Revision A displays.

The protocol has no documented PWM/backlight command.  Rebscreen therefore
applies brightness to the RGB frame before it is sent, which changes the
visible brightness of the physical display without pretending to alter its
firmware or backlight register.
"""

HARDWARE_BRIGHTNESS_SUPPORTED = False


def brightness_status(value: int) -> str:
    return f"Brilho enviado à tela: {max(10, min(100, int(value)))}%"

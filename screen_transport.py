"""USB serial transport for compatible 320×480 Rebscreen displays.

This module owns protocol bytes and serial access. UI code should queue these
functions in a background worker instead of opening a port directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
import threading
import time


RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
FULL_FRAME_RESYNC_INTERVAL = 300.0
SERIAL_RETRY_BASE = 5.0
SERIAL_RETRY_MAX = 60.0
FONT_FILES = {
    "title": RESOURCE_DIR / "assets" / "fonts" / "Coolvetica Rg.otf",
    "metric": RESOURCE_DIR / "assets" / "fonts" / "Coolvetica Rg Cond.otf",
    "aux": RESOURCE_DIR / "assets" / "fonts" / "CreatoDisplay-Light.otf",
}


class TuringScreenTransport:
    """Revision A protocol: portrait 320×480 RGB565 at 115200 baud."""

    WIDTH, HEIGHT = 320, 480

    def __init__(self, port: str = "COM3") -> None:
        self.port = port

    @staticmethod
    def _pil_font(role: str, size: int):
        from PIL import ImageFont
        return ImageFont.truetype(str(FONT_FILES[role]), size)

    @staticmethod
    def _command(x: int, y: int, ex: int, ey: int, command: int) -> bytes:
        return bytes((x >> 2, ((x & 3) << 6) | (y >> 4),
                      ((y & 15) << 4) | (ex >> 6), ((ex & 63) << 2) | (ey >> 8),
                      ey & 255, command))

    @staticmethod
    def _rgb565_bytes(image) -> bytes:
        pixels = bytearray()
        for red, green, blue in image.convert("RGB").getdata():
            value = ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)
            pixels.extend((value & 0xFF, value >> 8))
        return bytes(pixels)

    @staticmethod
    def _orientation_command(width: int, height: int) -> bytes:
        orientation = bytearray(16)
        orientation[5] = 121
        orientation[6] = 100
        orientation[7:11] = bytes((width >> 8, width & 255, height >> 8, height & 255))
        return bytes(orientation)

    def send_pil_image(self, image) -> None:
        """Send one complete image without changing firmware or persistent state."""
        try:
            import serial
        except ImportError as exc:
            raise RuntimeError("pyserial não está disponível neste Python.") from exc
        if image.size != (self.WIDTH, self.HEIGHT):
            image = image.resize((self.WIDTH, self.HEIGHT))
        rgb = image.convert("RGB")
        pixels = bytearray()
        for red, green, blue in rgb.getdata():
            value = ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)
            pixels.extend((value & 0xFF, value >> 8))
        orientation = bytearray(16)
        orientation[5] = 121
        orientation[6] = 100
        orientation[7:11] = bytes((self.WIDTH >> 8, self.WIDTH & 255,
                                    self.HEIGHT >> 8, self.HEIGHT & 255))
        with serial.Serial(self.port, 115200, timeout=1, write_timeout=5, rtscts=True) as device:
            device.write(orientation)
            device.write(self._command(0, 0, self.WIDTH - 1, self.HEIGHT - 1, 197))
            for start in range(0, len(pixels), self.WIDTH * 8):
                device.write(pixels[start:start + self.WIDTH * 8])
            device.flush()

    def send_changed_image(self, image, previous) -> int:
        """Send only changed RGB565 pixel runs through the existing window command."""
        try:
            import serial
        except ImportError as exc:
            raise RuntimeError("pyserial não está disponível neste Python.") from exc
        if image.size != (self.WIDTH, self.HEIGHT):
            image = image.resize((self.WIDTH, self.HEIGHT))
        if previous.size != (self.WIDTH, self.HEIGHT):
            previous = previous.resize((self.WIDTH, self.HEIGHT))
        pixels = self._rgb565_bytes(image)
        old_pixels = self._rgb565_bytes(previous)
        changed = sum(pixels[index:index + 2] != old_pixels[index:index + 2] for index in range(0, len(pixels), 2))
        if not changed:
            return 0
        with serial.Serial(self.port, 115200, timeout=1, write_timeout=5, rtscts=True) as device:
            device.write(self._orientation_command(self.WIDTH, self.HEIGHT))
            for y in range(self.HEIGHT):
                row_start = y * self.WIDTH * 2
                x = 0
                while x < self.WIDTH:
                    offset = row_start + x * 2
                    if pixels[offset:offset + 2] == old_pixels[offset:offset + 2]:
                        x += 1
                        continue
                    start = x
                    x += 1
                    while x < self.WIDTH:
                        offset = row_start + x * 2
                        if pixels[offset:offset + 2] == old_pixels[offset:offset + 2]:
                            break
                        x += 1
                    end = x - 1
                    device.write(self._command(start, y, end, y, 197))
                    left = row_start + start * 2
                    right = row_start + (end + 1) * 2
                    device.write(pixels[left:right])
            device.flush()
        return changed


@dataclass(frozen=True)
class IncrementalSendResult:
    full_refresh: bool
    changed_pixels: int = 0


class IncrementalFrameSender:
    """Serialize full/delta frames and preserve a safe recovery path after errors."""

    def __init__(self, port: str, transport=None, clock=time.monotonic,
                 full_refresh_interval: float = FULL_FRAME_RESYNC_INTERVAL):
        self.port = port
        self.transport = transport or TuringScreenTransport(port)
        self.clock = clock
        self.full_refresh_interval = full_refresh_interval
        self.previous = None
        self.last_full_refresh = float("-inf")
        self.retry_at = 0.0
        self.retry_delay = SERIAL_RETRY_BASE
        self._lock = threading.Lock()

    def can_send(self, now: float | None = None) -> bool:
        return (self.clock() if now is None else now) >= self.retry_at

    def invalidate(self) -> None:
        """Force the next automatic frame to resynchronize the physical display."""
        with self._lock:
            self.previous = None

    def send_frame(self, image) -> IncrementalSendResult:
        with self._lock:
            now = self.clock()
            if not self.can_send(now):
                raise RuntimeError("serial transport is in backoff")
            full_refresh = self.previous is None or now - self.last_full_refresh >= self.full_refresh_interval
            try:
                if full_refresh:
                    self.transport.send_pil_image(image)
                    self.previous = image.copy()
                    self.last_full_refresh = now
                    changed = self.WIDTH_HEIGHT_PIXELS
                else:
                    changed = self.transport.send_changed_image(image, self.previous)
                    self.previous = image.copy()
                self.retry_delay = SERIAL_RETRY_BASE
                return IncrementalSendResult(full_refresh=full_refresh, changed_pixels=changed)
            except OSError:
                self.previous = None
                self.retry_at = now + self.retry_delay
                self.retry_delay = min(SERIAL_RETRY_MAX, self.retry_delay * 2)
                raise

    @property
    def WIDTH_HEIGHT_PIXELS(self) -> int:
        return TuringScreenTransport.WIDTH * TuringScreenTransport.HEIGHT


def send_incremental_frame_to_display(sender: IncrementalFrameSender, frame) -> str:
    """Queue-facing adapter that keeps the sender's frame cache in one worker."""
    sender.send_frame(frame)
    return f"Prévia enviada para {sender.port}."

    def send_test_frame(self, label: str = "CONEXAO OK") -> None:
        """Send a reversible diagnostic frame."""
        try:
            from PIL import Image, ImageDraw
        except ImportError as exc:
            raise RuntimeError("Pillow não está disponível neste Python.") from exc
        image = Image.new("RGB", (self.WIDTH, self.HEIGHT), "#10151f")
        draw = ImageDraw.Draw(image)
        draw.rectangle((18, 18, 302, 462), outline="#5b8cff", width=3)
        draw.text((38, 140), "REBSCREEN", fill="#f3f6fb", font=self._pil_font("title", 25))
        draw.text((38, 190), label, fill="#72d68b", font=self._pil_font("metric", 20))
        draw.text((38, 238), "REVISION A / USB", fill="#aeb8c8", font=self._pil_font("aux", 15))
        draw.text((38, 272), "320 x 480 / RGB565", fill="#aeb8c8", font=self._pil_font("aux", 15))
        draw.text((38, 332), "Teste reversível - sem firmware", fill="#aeb8c8", font=self._pil_font("aux", 14))
        self.send_pil_image(image)

    def send_diagnostic_pattern(self) -> None:
        """Send color corners to verify byte order and orientation."""
        try:
            from PIL import Image, ImageDraw
        except ImportError as exc:
            raise RuntimeError("Pillow não está disponível neste Python.") from exc
        image = Image.new("RGB", (self.WIDTH, self.HEIGHT), "#000000")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 159, 239), fill="#ff0000")
        draw.rectangle((160, 0, 319, 239), fill="#00ff00")
        draw.rectangle((160, 240, 319, 479), fill="#ffffff")
        draw.rectangle((0, 240, 159, 479), fill="#0000ff")
        self.send_pil_image(image)


def send_frame_to_display(port: str, frame) -> str:
    TuringScreenTransport(port).send_pil_image(frame)
    return f"Prévia enviada para {port}."


def send_test_frame_to_display(port: str) -> str:
    TuringScreenTransport(port).send_test_frame("PAGINA DE DEMONSTRACAO")
    return f"Teste enviado: 320 × 480 em {port}."


def check_display_port(port: str) -> str:
    import serial
    with serial.Serial(port, 115200, timeout=1, write_timeout=1, rtscts=True):
        pass
    return f"{port} disponível. Envio continua manual e desligado."

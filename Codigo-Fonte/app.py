"""Rebscreen — local Windows companion for compatible USB displays.

The provider classes deliberately separate UI data from the future USB screen
transport.  Replace DemoMetricsProvider/SpotifyDemoProvider and implement
TuringScreenTransport to move from this prototype to live hardware.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import cycle
from io import BytesIO
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import ctypes
import asyncio
import json
import os
import random
import sys
import threading
import time
import tkinter as tk
from tkinter import colorchooser, ttk
from layout_interaction import apply_drag
from hardware_status import explain_serial_error
from layout_normalization import normalize_profile
from media_display import artwork_for_display, page_after_media_refresh
from media_runtime import query_timed_out, should_render_media, snapshot_key
from media_selection import select_preferred_active
from orientation_profiles import canvas_dimensions, make_profiles, profile_for
from app_lifecycle import close_action
from brightness_protocol import HARDWARE_BRIGHTNESS_SUPPORTED, brightness_status
from rotation import next_enabled_page, rotation_due
from telemetry_mapping import disk_label, normalize_disks
from single_instance import SingleInstance
from visual_themes import THEME_STANDARD, THEME_TECHNICAL, THEME_REBEL, available_themes, layout_templates
from rebscreen_identity import APP_NAME, header_state
from source_icons import draw_source_icon
from lhm_telemetry import disk_rows, query_lhm
from network_telemetry import NetworkRates
from telemetry_history import aggregate_point, rate_label
from layout_colors import reset_item_colors, set_item_color


RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
APP_DATA_DIR = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / APP_NAME
SETTINGS_PATH = APP_DATA_DIR / "settings.json"
LAYOUT_PATH = APP_DATA_DIR / "panel_layout.json"
LEGACY_APP_DATA_DIRS = (
    Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "Telinha",
    Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "TURZX Panel V2",
    Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "TURZX Panel",
)
LEGACY_LAYOUT_PATH = Path(__file__).with_name("panel_layout.json")
FONT_DIR = RESOURCE_DIR / "assets" / "fonts"
FONT_FILES = {
    "title": FONT_DIR / "Coolvetica Rg.otf",
    "metric": FONT_DIR / "Coolvetica Rg Cond.otf",
    "aux": FONT_DIR / "CreatoDisplay-Light.otf",
}
CUSTOM_FONT_FAMILIES = {"title": "Coolvetica", "metric": "Coolvetica Cond", "aux": "Creato Display Light"}

class SettingsStore:
    default = {"dark": True, "accent": "#5b8cff", "custom_fonts": True, "font_scale": 1.0,
               "auto_switch_media": False, "auto_send": True, "send_interval": 1.0, "port": "COM3", "orientation": "vertical",
               "geometry": "1180x760", "rotation_enabled": False, "rotation_interval": 10.0,
               "rotation_pages": [True, True], "preview_brightness": 100, "monitor_style": "cards", "visual_theme": THEME_REBEL}
    def __init__(self) -> None:
        self.data = dict(self.default)
        try:
            sources = (SETTINGS_PATH, *(path / "settings.json" for path in LEGACY_APP_DATA_DIRS))
            source = next((path for path in sources if path.exists()), None)
            if source is not None:
                self.data.update(json.loads(source.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    def save(self) -> None:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        temporary = SETTINGS_PATH.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        temporary.replace(SETTINGS_PATH)


def register_private_fonts() -> None:
    """Expose bundled fonts to this process only; never installs them system-wide."""
    if os.name != "nt":
        return
    for path in FONT_FILES.values():
        if path.exists():
            ctypes.windll.gdi32.AddFontResourceExW(str(path), 0x10, 0)


@dataclass
class Disk:
    name: str
    temperature: int | None
    health: str


@dataclass
class Metrics:
    cpu_usage: int
    cpu_temperature: int
    gpu_usage: int
    gpu_temperature: int
    ram_usage: int
    disks: list[Disk]


@dataclass
class Track:
    title: str
    artist: str
    elapsed: int
    duration: int


@dataclass
class MediaSnapshot:
    track: Track
    source: str
    playing: bool
    art_image: object | None = None
    art_status: str = "Sem imagem publicada pelo Windows; usando placeholder."
    playback_label: str = "tocando"


def vlc_window_snapshot() -> MediaSnapshot | None:
    """Use VLC's visible window title when it does not publish a GSMTC session."""
    if os.name != "nt":
        return None
    from ctypes import wintypes
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    process_query = 0x1000
    titles: list[str] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def inspect(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        handle = kernel32.OpenProcess(process_query, False, pid.value)
        if not handle:
            return True
        try:
            path = ctypes.create_unicode_buffer(32768)
            length = wintypes.DWORD(len(path))
            if not kernel32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(length)):
                return True
            if Path(path.value).name.lower() != "vlc.exe":
                return True
            title_length = user32.GetWindowTextLengthW(hwnd)
            if title_length:
                title = ctypes.create_unicode_buffer(title_length + 1)
                user32.GetWindowTextW(hwnd, title, len(title))
                titles.append(title.value)
        finally:
            kernel32.CloseHandle(handle)
        return True

    user32.EnumWindows(callback_type(inspect), 0)
    for title in titles:
        clean = title.rsplit(" - ", 1)[0].strip() if " - " in title else ""
        if clean and clean.lower() not in ("vlc media player", "reprodutor de mídias vlc"):
            return MediaSnapshot(Track(clean, "VLC", 0, 1), "VLC (título da janela)", True,
                                 art_status="VLC sem imagem GSMTC; usando placeholder.",
                                 playback_label="estado não informado pelo VLC")
    return None


def spotify_window_snapshot() -> MediaSnapshot | None:
    """Last-resort local title fallback when the Windows GSMTC service stalls.

    This never claims GSMTC metadata, playback position, or cover art. It is
    deliberately limited to the visible Spotify desktop window.
    """
    if os.name != "nt":
        return None
    from ctypes import wintypes
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    process_query = 0x1000
    titles: list[str] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def inspect(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        handle = kernel32.OpenProcess(process_query, False, pid.value)
        if not handle:
            return True
        try:
            path = ctypes.create_unicode_buffer(32768)
            length = wintypes.DWORD(len(path))
            if not kernel32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(length)):
                return True
            if Path(path.value).name.lower() != "spotify.exe":
                return True
            title_length = user32.GetWindowTextLengthW(hwnd)
            if title_length:
                title = ctypes.create_unicode_buffer(title_length + 1)
                user32.GetWindowTextW(hwnd, title, len(title))
                titles.append(title.value.strip())
        finally:
            kernel32.CloseHandle(handle)
        return True

    user32.EnumWindows(callback_type(inspect), 0)
    for window_title in titles:
        snapshot = parse_spotify_window_title(window_title)
        if snapshot is not None:
            return snapshot
    return None


def parse_spotify_window_title(window_title: str) -> MediaSnapshot | None:
    """Turn Spotify's local artist-title window caption into an honest fallback."""
    clean = window_title.strip()
    if " - " not in clean or clean.lower() in ("spotify", "spotify premium"):
        return None
    artist, track = clean.split(" - ", 1)
    if not artist or not track:
        return None
    return MediaSnapshot(Track(track, artist, 0, 1), "Spotify (título da janela)", True,
                         art_status="GSMTC indisponível; Spotify não publicou capa/progresso.",
                         playback_label="estado não publicado")


class LayoutStore:
    default = {"cpu": {"y": 68, "h": 74}, "gpu": {"y": 154, "h": 74}, "ram": {"y": 240, "h": 74}, "disks": {"y": 355, "h": 31},
               "art": {"x": 52, "y": 63, "size": 216}, "title": {"x": 160, "y": 294}, "artist": {"x": 160, "y": 326},
               "state": {"x": 160, "y": 351}, "progress": {"x": 24, "y": 371, "w": 272}}
    def __init__(self) -> None:
        self.profiles = make_profiles(self.default)
        self.orientation = "vertical"
        repaired = False
        try:
            sources = (LAYOUT_PATH, *(path / "panel_layout.json" for path in LEGACY_APP_DATA_DIRS), LEGACY_LAYOUT_PATH)
            source = next((path for path in sources if path.exists()), None)
            if source is None:
                return
            saved = json.loads(source.read_text(encoding="utf-8"))
            if isinstance(saved.get("profiles"), dict):
                for profile_name in ("vertical", "horizontal"):
                    for key, value in saved["profiles"].get(profile_name, {}).items():
                        if key in self.profiles[profile_name] and isinstance(value, dict):
                            self.profiles[profile_name][key].update(value)
            else:  # Migrate the former single portrait layout without losing it.
                for key, value in saved.items():
                    if key in self.profiles["vertical"] and isinstance(value, dict):
                        self.profiles["vertical"][key].update(value)
                self.profiles["horizontal"] = json.loads(json.dumps(self.profiles["vertical"]))
        except (OSError, ValueError):
            pass
        for profile in self.profiles.values():
            # Lyrics were retired; ignore the old key while preserving all
            # remaining user positioning.
            profile.pop("lyrics", None)
            repaired = normalize_profile(profile, self.default) or repaired
        if repaired:
            # Writes only Telinha's profile file.  The legacy source remains intact.
            self.save()

    @property
    def data(self) -> dict[str, dict[str, int]]:
        return profile_for(self.profiles, self.orientation)

    def activate(self, orientation: str) -> None:
        self.orientation = "horizontal" if orientation == "horizontal" else "vertical"

    def save(self) -> None:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        LAYOUT_PATH.write_text(json.dumps({"profiles": self.profiles}, indent=2), encoding="utf-8")
    def reset(self) -> None:
        self.profiles = make_profiles(self.default); self.save()

    def apply_template(self, name: str) -> None:
        """Explicitly replace both orientation profiles with a named preset."""
        self.profiles = layout_templates(name, self.default)
        for profile in self.profiles.values():
            normalize_profile(profile, self.default)
        self.save()


class WindowsMediaProvider:
    """Authorized Windows GSMTC reader; no player automation, browser scraping, or private API."""
    def __init__(self) -> None:
        self.diagnostics: list[str] = []
        self._art_key: str | None = None
        self._art_image = None
        self._manager = None
        try:
            from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
            self.manager_type, self.available, self.reason = GlobalSystemMediaTransportControlsSessionManager, True, "GSMTC via winrt"
        except ImportError:
            try:
                from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
                self.manager_type, self.available, self.reason = GlobalSystemMediaTransportControlsSessionManager, True, "GSMTC via winsdk"
            except ImportError:
                self.manager_type, self.available, self.reason = None, False, "Binding GSMTC ausente (requer Python 3.9+ com winrt-Windows.Media.Control)"

    @staticmethod
    def select_playing(items: list[MediaSnapshot]) -> MediaSnapshot | None:
        return select_preferred_active(items)

    @staticmethod
    def _source_label(source: str) -> str:
        """Make a GSMTC application identifier readable without hiding it."""
        lowered = source.lower()
        if "spotify" in lowered:
            return "Spotify"
        if "msedge" in lowered:
            return "Microsoft Edge"
        if "chrome" in lowered:
            return "Google Chrome"
        if "firefox" in lowered:
            return "Firefox"
        if "vlc" in lowered:
            return "VLC media player"
        if "wmplayer" in lowered or "windowsmediaplayer" in lowered:
            return "Windows Media Player"
        if "microsoft.zune" in lowered or "mediaplayer" in lowered:
            return "Media Player"
        return source.rsplit("!", 1)[-1] or "Windows Media"

    @staticmethod
    def _playback_state(playback) -> str:
        """WinRT enums stringify as numbers; use their symbolic name instead."""
        state = playback.playback_status
        name = getattr(state, "name", None)
        if name:
            return str(name).upper()
        # Compatibility with alternate bindings that expose plain values.
        return str(state).rsplit(".", 1)[-1].upper()

    @staticmethod
    def _state_label(state: str) -> str:
        return {"PLAYING": "tocando", "PAUSED": "pausado", "STOPPED": "parado", "CLOSED": "fechado"}.get(state, state.lower())

    async def _read_thumbnail(self, thumbnail, key: str) -> tuple[object | None, str]:
        """Decode the GSMTC thumbnail in memory; no art is written or cached on disk."""
        if thumbnail is None:
            self._art_key, self._art_image = None, None
            return None, "Sem imagem publicada pelo Windows; usando placeholder."
        if key == self._art_key and self._art_image is not None:
            return self._art_image, "Capa GSMTC em memória."
        stream = reader = None
        try:
            from PIL import Image
            from winrt.windows.storage.streams import DataReader
            stream = await thumbnail.open_read_async()
            reader = DataReader(stream)
            count = await reader.load_async(stream.size)
            payload = bytearray(count)
            reader.read_bytes(payload)
            with Image.open(BytesIO(payload)) as decoded:
                decoded.load()
                self._art_image = decoded.convert("RGB").copy()
            self._art_key = key
            return self._art_image, "Capa GSMTC em memória."
        except Exception as exc:
            self._art_key, self._art_image = None, None
            return None, "Thumbnail indisponível; usando placeholder."
        finally:
            if reader is not None:
                reader.close()
            if stream is not None:
                stream.close()

    async def _read_async(self) -> MediaSnapshot | None:
        # GSMTC occasionally stalls while a legacy desktop player changes state.
        # Bound each Windows call so one stalled provider never freezes media updates.
        if self._manager is None:
            self._manager = await asyncio.wait_for(self.manager_type.request_async(), timeout=1.5)
        manager = self._manager
        candidates: list[tuple[MediaSnapshot, object | None, str]] = []
        sessions = manager.get_sessions()
        self.diagnostics = []
        if not sessions:
            self.reason = "GSMTC ativo; nenhuma sessão publicada pelo Windows"
            self.diagnostics.append("Nenhuma sessão publicada pelo Windows.")
            return None
        for session in sessions:
            playback = session.get_playback_info()
            state = self._playback_state(playback)
            source = session.source_app_user_model_id or "Windows Media"
            label = self._source_label(source)
            self.diagnostics.append(f"{label} — {self._state_label(state)}")
            if state != "PLAYING":
                continue
            try:
                props = await asyncio.wait_for(session.try_get_media_properties_async(), timeout=1.5)
                timeline = session.get_timeline_properties()
                elapsed = int(timeline.position.total_seconds())
                duration = max(1, int(timeline.end_time.total_seconds()))
                track = Track(props.title or "Sem título", props.artist or "Artista desconhecido", elapsed, duration)
                candidates.append((MediaSnapshot(track, label, True), props.thumbnail, f"{source}|{track.title}|{track.artist}"))
            except Exception as exc:
                self.diagnostics[-1] += " (metadados indisponíveis)"
        selected = self.select_playing([item[0] for item in candidates])
        if selected:
            _, thumbnail, art_key = next(item for item in candidates if item[0] is selected)
            selected.art_image, selected.art_status = await self._read_thumbnail(thumbnail, art_key)
            self.diagnostics.append(f"Selecionado: {selected.source} — tocando")
            self.diagnostics.append(selected.art_status)
        self.reason = (
            f"GSMTC ativo: {selected.source} em reprodução"
            if selected else "GSMTC ativo; nenhuma sessão em reprodução"
        )
        return selected

    def read(self) -> MediaSnapshot | None:
        if not self.available:
            return None
        try:
            return asyncio.run(self._read_async())
        except Exception as exc:
            self.reason = "Falha GSMTC: " + str(exc)
            self.diagnostics = [self.reason]
            return None


@dataclass
class LyricLine:
    timestamp: int
    text: str


class DemoMetricsProvider:
    """Local usage plus all mounted Windows volumes; sensor gaps remain visible."""
    def __init__(self):
        self.sensor_status = "Sensores de disco: verificando Libre Hardware Monitor…"

    def disks(self) -> list[Disk]:
        if os.name != "nt":
            return [Disk("Armazenamento local", None, "Sensor de saúde indisponível")]
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        volumes = [f"Volume {chr(letter)}:" for letter in range(26) if mask & (1 << letter)]
        sensors, self.sensor_status = query_lhm()
        return [Disk(item["name"], item["temperature"], item["health"]) for item in disk_rows(sensors, volumes)]
    def read(self) -> Metrics:
        return Metrics(
            cpu_usage=random.randint(18, 76), cpu_temperature=random.randint(46, 89),
            gpu_usage=random.randint(8, 92), gpu_temperature=random.randint(42, 84),
            ram_usage=random.randint(42, 78),
            disks=self.disks(),
        )


class SpotifyDemoProvider:
    """Temporary source; later connect to Spotify Web API/desktop client."""
    def __init__(self) -> None:
        self.track = Track("Midnight City", "M83", 87, 244)

    def read(self) -> Track:
        self.track.elapsed = (self.track.elapsed + 1) % self.track.duration
        return self.track


class LyricsProvider:
    """Reads user-supplied LRC files; never fetches or scrapes song lyrics."""
    demo_lines = [
        LyricLine(0, "[Demonstração] A música começa"),
        LyricLine(25, "[Demonstração] A linha acompanha o tempo"),
        LyricLine(58, "[Demonstração] Destaque da linha atual"),
        LyricLine(92, "[Demonstração] Próxima frase local"),
        LyricLine(128, "[Demonstração] Letras por arquivo .lrc"),
    ]

    def __init__(self, lrc_path: Path | None = None) -> None:
        self.lines = self._read_lrc(lrc_path) if lrc_path and lrc_path.exists() else self.demo_lines
        self.source = "Arquivo .lrc local" if lrc_path and lrc_path.exists() else "Letras de demonstração"

    @staticmethod
    def _read_lrc(path: Path) -> list[LyricLine]:
        import re
        lines: list[LyricLine] = []
        pattern = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\](.*)")
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            match = pattern.match(raw.strip())
            if match:
                lines.append(LyricLine(int(match.group(1)) * 60 + int(float(match.group(2))), match.group(3).strip()))
        return sorted(lines, key=lambda item: item.timestamp) or LyricsProvider.demo_lines

    def current(self, elapsed: int) -> tuple[str, str]:
        active = 0
        for index, line in enumerate(self.lines):
            if line.timestamp <= elapsed:
                active = index
            else:
                break
        current = self.lines[active].text
        upcoming = self.lines[active + 1].text if active + 1 < len(self.lines) else ""
        return current, upcoming


class TuringScreenTransport:
    """Turing/UsbMonitor Revision A transport: 320×480 portrait, serial 115200 RTS/CTS.

    It only sends frames when called explicitly; the UI never transmits by
    default. This avoids accidental writes while the prototype is being tuned.
    """
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

    def send_pil_image(self, image) -> None:
        """Send one 320×480 portrait RGB565 frame; does not change firmware."""
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
        # Revision A defines PORTRAIT as 0; the protocol encodes it as 100.
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

    def send_test_frame(self, label: str = "CONEXAO OK") -> None:
        """A reversible diagnostic frame, intentionally neutral and non-persistent."""
        try:
            from PIL import Image, ImageDraw
        except ImportError as exc:
            raise RuntimeError("Pillow não está disponível neste Python.") from exc
        image = Image.new("RGB", (self.WIDTH, self.HEIGHT), "#10151f")
        draw = ImageDraw.Draw(image)
        draw.rectangle((18, 18, 302, 462), outline="#5b8cff", width=3)
        draw.text((38, 140), "TELINHA", fill="#f3f6fb", font=self._pil_font("title", 25))
        draw.text((38, 190), label, fill="#72d68b", font=self._pil_font("metric", 20))
        draw.text((38, 238), "REVISION A / COM3", fill="#aeb8c8", font=self._pil_font("aux", 15))
        draw.text((38, 272), "320 x 480 / RGB565", fill="#aeb8c8", font=self._pil_font("aux", 15))
        draw.text((38, 332), "Teste reversivel - sem firmware", fill="#aeb8c8", font=self._pil_font("aux", 14))
        self.send_pil_image(image)

    def send_diagnostic_pattern(self) -> None:
        """One frame with corner colors to visually verify byte order and orientation."""
        try:
            from PIL import Image, ImageDraw
        except ImportError as exc:
            raise RuntimeError("Pillow não está disponível neste Python.") from exc
        image = Image.new("RGB", (self.WIDTH, self.HEIGHT), "#000000")
        draw = ImageDraw.Draw(image)
        # Clockwise from upper left: red, green, white, blue.
        draw.rectangle((0, 0, 159, 239), fill="#ff0000")
        draw.rectangle((160, 0, 319, 239), fill="#00ff00")
        draw.rectangle((160, 240, 319, 479), fill="#ffffff")
        draw.rectangle((0, 240, 159, 479), fill="#0000ff")
        self.send_pil_image(image)


LIGHT = {"bg": "#f6f7fb", "card": "#ffffff", "text": "#182131", "muted": "#667085", "line": "#d9deea"}
DARK = {"bg": "#10151f", "card": "#1b2330", "text": "#f3f6fb", "muted": "#aeb8c8", "line": "#334054"}


class PanelFrameRenderer:
    """The single 320×480 renderer used by both preview and physical display."""
    def __init__(self, theme: dict[str, str], accent: str, use_custom_fonts: bool, font_scale: float = 1.0, layout: dict | None = None, monitor_style: str = "cards", visual_theme: str = THEME_STANDARD) -> None:
        from PIL import Image, ImageDraw, ImageFont
        self.Image = Image
        self.Draw = ImageDraw
        self.ImageFont = ImageFont
        self.theme, self.accent, self.use_custom_fonts = theme, accent, use_custom_fonts
        self.font_scale, self.layout, self.monitor_style, self.visual_theme = font_scale, layout or LayoutStore.default, monitor_style, visual_theme

    def font(self, role: str, size: int):
        if self.use_custom_fonts:
            return self.ImageFont.truetype(str(FONT_FILES[role]), max(10, int(size * self.font_scale)))
        return self.ImageFont.load_default()

    def text(self, draw, xy: tuple[int, int], value: str, role: str, size: int, color: str, anchor: str = "la") -> None:
        draw.text(xy, value, fill=color, font=self.font(role, size), anchor=anchor)

    def text_item(self, draw, key: str, xy, value: str, role: str, size: int, color: str, anchor: str = "la") -> None:
        scale = float(self.layout.get(key, {}).get("font_scale", 1.0))
        draw.text(xy, value, fill=self.layout.get(key, {}).get("text_color", color), font=self.font(role, max(8, int(size * scale))), anchor=anchor)

    @staticmethod
    def time_label(value: int) -> str:
        return f"{value // 60}:{value % 60:02d}"

    def render(self, page: int, metrics: Metrics, track: Track, *args, history: list[int] | None = None, network: tuple[float, float] = (0.0, 0.0)) -> object:
        """Render current UI; accepts the retired lyrics argument from old callers."""
        if len(args) == 4:  # legacy: lyrics, alert, label, art
            _, alert, media_label, album_art = args
        else:
            alert, media_label, album_art = args
        image = self.Image.new("RGB", (320, 480), self.theme["bg"])
        self.current_image = image
        draw = self.Draw.Draw(image)
        if self.visual_theme == THEME_TECHNICAL:
            image.paste("#101315", (0, 0, 320, 480))
            if page == 0:
                self._technical_monitor(draw, metrics, history or [])
            else:
                self._technical_player(draw, track, media_label, album_art)
            return image
        if self.visual_theme == THEME_REBEL:
            image.paste("#16191a", (0, 0, 320, 480))
            if page == 0:
                self._rebel_monitor(draw, metrics, history or [], alert, network)
            else:
                self._rebel_player(draw, track, media_label, album_art)
            return image
        if page == 0:
            self._monitor(draw, metrics, history or [])
        else:
            self._spotify(draw, track, media_label, album_art)
        if alert:
            draw.rectangle((0, 446, 319, 479), fill="#ef5350")
            self.text(draw, (160, 463), alert, "metric", 9, "#111111", "mm")
        return image

    def _rebel_frame(self, draw, title: str):
        cyan, cream, muted = "#73aeb1", "#f2d98a", "#718082"
        clock, date = header_state()
        draw.rounded_rectangle((8, 8, 312, 472), radius=7, fill="#1d2223", outline="#3b4749", width=3)
        draw.line((18, 48, 302, 48), fill=cyan, width=1)
        self.text(draw, (20, 21), "REBSCREEN // " + title, "aux", 10, cream)
        self.text(draw, (300, 18), clock, "metric", 15, cream, "ra")
        self.text(draw, (300, 36), date, "aux", 8, muted, "ra")
        return cyan, cream, muted

    def _segmented(self, draw, x: int, y: int, width: int, percent: int, color: str):
        for index in range(10):
            left = x + index * (width // 10 + 2)
            draw.rectangle((left, y, left + width // 10 - 2, y + 6), fill=color if index < percent / 10 else "#323b3c")

    def _rebel_monitor(self, draw, metrics: Metrics, history: list[int], alert: str, network: tuple[float, float]) -> None:
        cyan, cream, muted = self._rebel_frame(draw, "MONITOR")
        cards = ((20, "CPU", metrics.cpu_usage, metrics.cpu_temperature), (166, "GPU", metrics.gpu_usage, metrics.gpu_temperature))
        for x, label, usage, temp in cards:
            draw.polygon(((x,64),(x+132,64),(x+138,70),(x+138,151),(x,151)), fill="#202829", outline=cyan)
            self.text(draw, (x+10, 75), label, "aux", 11, cyan)
            self.text(draw, (x+10, 94), f"{temp}°C", "metric", 24, cream)
            self.text(draw, (x+124, 104), f"{usage}%", "aux", 10, muted, "ra")
            self._segmented(draw, x+10, 127, 115, usage, cyan)
            draw.line((x+10,143,x+122,136), fill="#567d80", width=1)
        draw.rectangle((20,164,300,218), fill="#202829", outline="#5e5534")
        self.text(draw, (31,174), "RAM", "aux", 11, cream)
        self.text(draw, (100,170), f"{metrics.ram_usage}%", "metric", 23, cream)
        self.text(draw, (286,178), "EM USO", "aux", 8, muted, "ra")
        self._segmented(draw, 31, 202, 255, metrics.ram_usage, "#d5a94c")
        self.text(draw, (20,232), "DISCOS // UNIDADE       SAÚDE       TEMP.", "aux", 9, cyan)
        for index, disk in enumerate(metrics.disks[:3]):
            y=252+index*25; draw.line((20,y-4,300,y-4), fill="#354244")
            self.text(draw,(25,y),disk.name[:17],"aux",10,cream)
            self.text(draw,(212,y),disk.health[:10],"aux",8,"#80ba82" if disk.temperature is not None else muted)
            self.text(draw,(292,y),f"{disk.temperature}°" if disk.temperature is not None else "—","aux",9,cream,"ra")
        points=(history or [{"usage": metrics.cpu_usage, "temperature": None}])[-30:]
        if not isinstance(points[0], dict): points=[{"usage": value, "temperature": None} for value in points]
        points=points*2 if len(points)==1 else points
        draw.rectangle((20,337,300,420), outline="#3c5557")
        draw.line([(20+i*280/(len(points)-1),412-max(0,min(100,p["usage"]))*62/100) for i,p in enumerate(points)], fill=cyan, width=2)
        temps=[p["temperature"] for p in points]
        if any(value is not None for value in temps):
            draw.line([(20+i*280/(len(points)-1),412-max(0,min(100,p["temperature"] or 0))*62/100) for i,p in enumerate(points)], fill="#f2d98a", width=2)
        self.text(draw,(24,342),"USO % (CIANO) / TEMP °C (CREME)","aux",7,muted)
        self.text(draw,(22,426),"Sinal " + rate_label(network[0]), "aux",9,"#80ba82")
        self.text(draw,(150,426),"Link " + rate_label(network[1]), "aux",9,"#d5a94c")
        draw.rectangle((20,444,300,460), fill="#572f32" if alert else "#293032")
        self.text(draw,(28,447), alert[:40] if alert else "SISTEMA ESTÁVEL // ALERTAS EM ESPERA", "aux",8,"#f0abb0" if alert else muted)

    def _rebel_player(self, draw, track: Track, media_label: str, album_art=None) -> None:
        cyan, cream, muted = self._rebel_frame(draw, "NOW PLAYING")
        x,y,size=66,68,188
        draw.ellipse((x-8,y-8,x+size+8,y+size+8),outline="#3d5557",width=2)
        draw.line((160,y-16,160,y+size+16),fill=cyan); draw.line((x-16,y+size//2,x+size+16,y+size//2),fill=cyan)
        if album_art is not None:
            art=album_art.resize((size,size),self.Image.Resampling.LANCZOS); mask=self.Image.new("L",(size,size),0); self.Draw.Draw(mask).ellipse((0,0,size-1,size-1),fill=255); self.current_image.paste(art,(x,y),mask)
        else:
            draw.ellipse((x,y,x+size,y+size),fill="#252d2e",outline=cream,width=2); self.text(draw,(160,157),"SEM CAPA","aux",10,muted,"ma")
        self.text(draw,(160,283),track.title[:28],"title",25,cream,"ma")
        self.text(draw,(160,315),track.artist[:32],"aux",14,muted,"ma")
        self.text(draw,(160,340),media_label[:34],"aux",10,cyan,"ma")
        self._segmented(draw,26,373,268,int(100*track.elapsed/max(1,track.duration)),cyan)
        self.text(draw,(26,391),self.time_label(track.elapsed),"aux",9,muted); self.text(draw,(294,391),self.time_label(track.duration),"aux",9,muted,"ra")
        self.text(draw,(22,432),"SINAL  ●", "aux",9,"#80ba82"); self.text(draw,(104,432),"LINK  ●", "aux",9,"#d5a94c")
        self.text(draw,(294,432),"REBEL", "aux",9,cream,"ra")

    def _technical_monitor(self, draw, metrics: Metrics, history: list[int]) -> None:
        cyan, white, muted, amber, green = "#14d7e8", "#f4f7f8", "#8fa3a8", "#f5b63d", "#65d47d"
        clock, date = header_state()
        draw.rounded_rectangle((10, 10, 310, 470), radius=13, outline=cyan, width=2)
        self.text(draw, (22, 22), "REBSCREEN | MONITOR", "aux", 10, cyan)
        self.text(draw, (298, 20), clock, "metric", 16, white, "ra")
        self.text(draw, (298, 39), date, "aux", 8, muted, "ra")
        self.text(draw, (22, 52), "◉ CPU", "aux", 14, muted)
        self.text(draw, (112, 42), f"{metrics.cpu_usage:02d}%", "metric", 34, white)
        self.text(draw, (226, 50), f"{metrics.cpu_temperature}°C", "aux", 13, cyan)
        self.text(draw, (22, 98), "◆ GPU", "aux", 14, muted)
        self.text(draw, (112, 88), f"{metrics.gpu_usage:02d}%", "metric", 34, white)
        self.text(draw, (226, 96), f"{metrics.gpu_temperature}°C", "aux", 13, cyan)
        self.text(draw, (22, 144), "▣ RAM", "aux", 14, muted)
        self.text(draw, (112, 134), f"{metrics.ram_usage:02d}%", "metric", 34, white)
        draw.rounded_rectangle((22, 181, 298, 193), radius=5, fill="#283238")
        draw.rounded_rectangle((22, 181, 22 + int(276 * metrics.ram_usage / 100), 193), radius=5, fill=amber)
        self.text(draw, (22, 207), "DISCOS       SAÚDE                 TEMP.", "aux", 9, cyan)
        for index, disk in enumerate(metrics.disks[:2]):
            y = 226 + index * 28
            self.text(draw, (22, y), disk.name[:17], "aux", 11, white)
            label = disk_label(vars(disk))
            self.text(draw, (298, y), label[:24], "aux", 9, green if disk.temperature is not None else muted, "ra")
        top, bottom, left, right = 300, 422, 22, 298
        draw.rounded_rectangle((left, top, right, bottom), radius=8, outline="#2e5155", width=1)
        self.text(draw, (left, 280), "CPU // ÚLTIMOS 60 SEGUNDOS", "aux", 10, cyan)
        values = (history or [metrics.cpu_usage])[-60:]
        if len(values) == 1: values = values * 2
        points = [(left + i * (right-left)/(len(values)-1), bottom-12-max(0,min(100,v))*(bottom-top-24)/100) for i,v in enumerate(values)]
        draw.line(points, fill=cyan, width=3)
        self.text(draw, (left, 434), "60 SEGUNDOS", "aux", 9, muted)
        self.text(draw, (right, 434), "AGORA", "aux", 9, muted, "ra")
        draw.rounded_rectangle((22, 443, 298, 462), radius=5, fill="#4a282c")
        self.text(draw, (30, 448), "ALERTAS: monitoramento ativo", "aux", 9, "#ed9ba2")

    def _technical_player(self, draw, track: Track, media_label: str, album_art=None) -> None:
        cyan, white, muted = "#14d7e8", "#f4f7f8", "#8fa3a8"
        clock, date = header_state()
        draw.rounded_rectangle((10, 10, 310, 470), radius=13, outline=cyan, width=2)
        self.text(draw, (22, 22), "REBSCREEN | NOW PLAYING", "aux", 10, cyan)
        self.text(draw, (298, 20), clock, "metric", 16, white, "ra")
        self.text(draw, (298, 39), date, "aux", 8, muted, "ra")
        x, y, size = 70, 58, 180
        if album_art is not None:
            resized = album_art.resize((size, size), self.Image.Resampling.LANCZOS)
            mask = self.Image.new("L", (size, size), 0); self.Draw.Draw(mask).ellipse((0,0,size-1,size-1), fill=255)
            self.current_image.paste(resized, (x,y), mask)
        else:
            draw.ellipse((x,y,x+size,y+size), fill="#263036", outline=cyan, width=2)
            draw.ellipse((x+47,y+47,x+133,y+133), outline="#52636a", width=3)
            self.text(draw, (160, 151), "SEM CAPA", "aux", 11, muted, "ma")
        draw.ellipse((x,y,x+size,y+size), outline=cyan, width=2)
        self.text(draw, (160, 263), track.title[:28], "title", 25, white, "ma")
        self.text(draw, (160, 295), track.artist[:32], "aux", 14, muted, "ma")
        kind = draw_source_icon(draw, (78, 316), media_label)
        self.text(draw, (98, 323), media_label[:28] if kind != "unknown" else "Fonte não identificada", "aux", 10, cyan if kind != "unknown" else muted, "la")
        px, py, pw = 26, 357, 268
        draw.rounded_rectangle((px,py,px+pw,py+8), radius=4, fill="#2e3a40")
        fill = 0 if track.duration <= 1 else int(pw * track.elapsed / track.duration)
        draw.rounded_rectangle((px,py,px+fill,py+8), radius=4, fill=cyan)
        self.text(draw, (px, 377), self.time_label(track.elapsed), "aux", 10, muted)
        self.text(draw, (px+pw, 377), self.time_label(track.duration), "aux", 10, muted, "ra")

    def _monitor(self, draw, metrics: Metrics, history: list[int]) -> None:
        if self.monitor_style == "graph":
            self._monitor_graph(draw, metrics, history)
            return
        t = self.theme
        self.text(draw, (18, 16), "MONITOR DO PC", "title", 20, t["text"])
        self.text(draw, (18, 42), "Dados de demonstracao", "aux", 11, t["muted"])
        cards = [(self.layout["cpu"]["y"], self.layout["cpu"]["h"], "CPU", f"{metrics.cpu_usage}%", f"{metrics.cpu_temperature} C"),
                 (self.layout["gpu"]["y"], self.layout["gpu"]["h"], "GPU", f"{metrics.gpu_usage}%", f"{metrics.gpu_temperature} C"),
                 (self.layout["ram"]["y"], self.layout["ram"]["h"], "MEMORIA", f"{metrics.ram_usage}%", "RAM em uso")]
        for y, height, title, value, sub in cards:
            draw.rectangle((18, y, 302, y + height), fill=t["card"], outline=t["line"])
            self.text(draw, (30, y + 10), title, "aux", 11, t["muted"])
            self.text(draw, (30, y + 31), value, "metric", 28, self.accent)
            self.text(draw, (168, y + 38), sub, "aux", 13, t["muted"])
        self.text(draw, (18, 335), "ARMAZENAMENTO", "aux", 11, t["muted"])
        for index, disk in enumerate(metrics.disks):
            y = self.layout["disks"]["y"] + index * (self.layout["disks"]["h"] + 6)
            draw.rectangle((18, y, 302, y + self.layout["disks"]["h"]), fill=t["card"], outline=t["line"])
            self.text(draw, (28, y + 8), disk.name, "aux", 11, t["text"])
            self.text(draw, (292, y + 8), disk_label(vars(disk)), "aux", 9, t["muted"], "ra")
        self.text(draw, (18, 426), "Use Proxima pagina para validar o ciclo.", "aux", 9, t["muted"])

    def _monitor_graph(self, draw, metrics: Metrics, history: list[int]) -> None:
        """Compact vertical telemetry inspired by the supplied reference."""
        t = self.theme
        self.text(draw, (18, 18), "TELEMETRIA", "title", 20, t["text"])
        rows = (("CPU", f"{metrics.cpu_usage}%", f"{metrics.cpu_temperature} °C"),
                ("GPU", f"{metrics.gpu_usage}%", f"{metrics.gpu_temperature} °C"),
                ("RAM", f"{metrics.ram_usage}%", "uso da memória"))
        for index, (label, value, sub) in enumerate(rows):
            y = 62 + index * 48
            draw.rectangle((18, y, 302, y + 40), fill=t["card"], outline=t["line"])
            self.text(draw, (30, y + 9), label, "aux", 13, t["muted"])
            self.text(draw, (132, y + 7), value, "metric", 24, self.accent)
            self.text(draw, (224, y + 13), sub, "aux", 10, t["muted"], "ma")
        self.text(draw, (18, 224), "CPU — ÚLTIMOS 60 SEGUNDOS", "aux", 11, t["muted"])
        left, top, right, bottom = 18, 250, 302, 408
        draw.rectangle((left, top, right, bottom), fill=t["card"], outline=t["line"])
        values = (history or [metrics.cpu_usage])[-60:]
        if len(values) == 1: values = values * 2
        points = []
        for index, value in enumerate(values):
            x = left + index * (right - left) / (len(values) - 1)
            y = bottom - 14 - max(0, min(100, value)) * (bottom - top - 28) / 100
            points.append((x, y))
        draw.line(points, fill=self.accent, width=3)
        self.text(draw, (left, 418), "60 SEGUNDOS", "aux", 10, t["muted"])
        self.text(draw, (right, 418), "AGORA", "aux", 10, t["muted"], "ra")

    def _spotify(self, draw, track: Track, media_label: str, album_art=None) -> None:
        t = self.theme
        p = self.layout
        no_media = media_label == "Nenhuma mídia ativa"
        self.text(draw, (160, 18), "NENHUMA MÍDIA ATIVA" if no_media else "TOCANDO AGORA", "title", 20, t["text"], "ma")
        self.text(draw, (160, 43), media_label, "aux", 10, t["muted"], "ma")
        art_x, art_y, art_size = p["art"]["x"], p["art"]["y"], p["art"]["size"]
        art_box = (art_x, art_y, art_x + art_size, art_y + art_size)
        if album_art is not None:
            width, height = album_art.size
            scale = max(art_size / width, art_size / height)
            resized = album_art.resize((round(width * scale), round(height * scale)), self.Image.Resampling.LANCZOS)
            left, top = (resized.width - art_size) // 2, (resized.height - art_size) // 2
            cover = resized.crop((left, top, left + art_size, top + art_size))
            mask = self.Image.new("L", (art_size, art_size), 0)
            self.Draw.Draw(mask).ellipse((0, 0, art_size - 1, art_size - 1), fill=255)
            self.current_image.paste(cover, (art_x, art_y), mask)
        else:
            # Explicit fallback when the media session does not publish a thumbnail.
            # A neutral placeholder makes it clear that the *current* session
            # did not publish artwork; it must never resemble cached demo art.
            for inset, color in ((0, "#303842"), (8, "#46515f"), (17, "#637080"), (35, "#1a2028")):
                draw.ellipse((art_x + inset, art_y + inset, art_x + art_size - inset, art_y + art_size - inset), fill=color)
            center = art_x + art_size // 2
            draw.ellipse((center - 18, art_y + art_size // 2 - 18, center + 18, art_y + art_size // 2 + 18), fill="#e7eaf2")
            self.text(draw, (center, art_y + art_size // 2 + 28), "SEM CAPA", "aux", 10, "#e7eaf2", "ma")
        draw.ellipse(art_box, outline="#f3f6fb", width=2)
        self.text_item(draw, "title", (p["title"]["x"], p["title"]["y"]), track.title[:28], "title", 28, t["text"], "ma")
        self.text_item(draw, "artist", (p["artist"]["x"], p["artist"]["y"]), track.artist[:34], "aux", 16, t["muted"], "ma")
        title_only = "título da janela" in media_label
        state_text = "AGUARDANDO PLAYER" if no_media else ("ESTADO NÃO PUBLICADO" if title_only else "EM REPRODUCAO")
        self.text_item(draw, "state", (p["state"]["x"], p["state"]["y"]), state_text, "metric", 13, self.accent, "ma")
        px, py, pw = p["progress"]["x"], p["progress"]["y"], p["progress"]["w"]
        draw.rectangle((px, py, px + pw, py + 8), fill=t["line"])
        fill = 0 if title_only or no_media else int(pw * track.elapsed / track.duration)
        draw.rectangle((px, py, px + fill, py + 8), fill=self.accent)
        draw.ellipse((max(px - 4, px + fill - 4), py - 4, max(px + 4, px + fill + 4), py + 12), fill="#f3f6fb")
        self.text(draw, (px, py + 17), "--:--" if title_only or no_media else self.time_label(track.elapsed), "aux", 11, t["muted"])
        self.text(draw, (px + pw, py + 17), "--:--" if title_only or no_media else self.time_label(track.duration), "aux", 11, t["muted"], "ra")


class PanelApp(tk.Tk):
    def __init__(self) -> None:
        register_private_fonts()
        self.single_instance = SingleInstance()
        if not self.single_instance.acquire():
            raise SystemExit(0)
        super().__init__()
        self.title(APP_NAME)
        self.minsize(980, 640)
        self.settings = SettingsStore()
        self.geometry(self.settings.data["geometry"])
        self.metrics_provider = DemoMetricsProvider()
        self.spotify_provider = SpotifyDemoProvider()
        self.media_provider = WindowsMediaProvider()
        self.layout_store = LayoutStore()
        self.page = 0
        self.dark = bool(self.settings.data["dark"])
        self.accent = self.settings.data["accent"]
        self.custom_fonts_enabled = bool(self.settings.data["custom_fonts"])
        self.font_scale = float(self.settings.data["font_scale"])
        # Older preference files may contain this value.  Navigation is now
        # always manual, so refreshes cannot take the user away from a page.
        self.auto_switch_media = False
        # Release smoke checks can explicitly suppress physical I/O.
        self.auto_send_enabled = not bool(os.getenv("REBSCREEN_SAFE_START"))
        self.preview_orientation = self.settings.data.get("orientation", "vertical")
        self.layout_store.activate(self.preview_orientation)
        self.edit_layout = False
        self.layout_selection = None
        self.layout_drag_origin = None
        self.send_interval = max(1.0, float(self.settings.data["send_interval"]))
        self.last_auto_send = 0.0
        self.rotation_enabled = bool(self.settings.data.get("rotation_enabled", False))
        self.rotation_interval = max(2.0, float(self.settings.data.get("rotation_interval", 10)))
        self.rotation_pages = tuple(self.settings.data.get("rotation_pages", [True, True]))
        self.last_page_change = time.monotonic()
        self.preview_brightness = int(self.settings.data.get("preview_brightness", 100))
        self.monitor_style = self.settings.data.get("monitor_style", "cards")
        self.visual_theme = self.settings.data.get("visual_theme", THEME_STANDARD)
        self.media_label = "Dados de demonstracao"
        self.album_art = None
        self.limits = self.settings.data.get("limits", {"CPU": 85, "GPU": 82, "Discos": 60, "RAM": 90})
        self.limits.setdefault("RAM", 90)
        self.enabled = self.settings.data.get("enabled", {"CPU": True, "GPU": True, "Discos": True, "RAM": True})
        self.enabled.setdefault("RAM", True)
        self.alerts: list[str] = []
        self.alert_cycle = cycle([""])
        self.current_alert = ""
        self.last_metrics = self.metrics_provider.read()
        self.cpu_history: list[int] = [self.last_metrics.cpu_usage]
        self.telemetry_history: list[dict] = [aggregate_point(self.last_metrics.cpu_usage, self.last_metrics.gpu_usage, self.last_metrics.ram_usage, [self.last_metrics.cpu_temperature, self.last_metrics.gpu_temperature])]
        self.network_rates = NetworkRates()
        self.rx_rate, self.tx_rate = self.network_rates.read()
        self.preview_static_frame = None
        self.track = Track("Nenhuma mídia ativa", "Inicie Spotify ou outro player compatível", 0, 1)
        self.media_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="telinha-media")
        self.media_future = None
        self.media_query_started = 0.0
        self.media_query_timed_out = False
        self.last_media_key: tuple[object, ...] | None = None
        self.last_metrics_update = 0.0
        self.tray_icon = None
        self.protocol("WM_DELETE_WINDOW", self.on_main_window_close)
        self._build_ui()
        self.single_instance.listen(lambda: self.after(0, self.show_from_tray))
        self.bind_all("<Control-Key-1>", lambda _event: self.set_page(0))
        self.bind_all("<Control-Key-2>", lambda _event: self.set_page(1))
        self.start_tray()
        self.refresh()

    @property
    def theme(self) -> dict[str, str]:
        return DARK if self.dark else LIGHT

    def font_tuple(self, role: str, size: int, bold: bool = False) -> tuple:
        family = CUSTOM_FONT_FAMILIES[role] if self.custom_fonts_enabled else "Segoe UI"
        return (family, size, "bold" if bold else "normal")

    def _build_ui(self) -> None:
        self.configure(bg=self.theme["bg"])
        root = tk.Frame(self, bg=self.theme["bg"], padx=16, pady=14)
        root.pack(fill="both", expand=True)
        main = tk.Frame(root, bg=self.theme["bg"]); main.pack(side="left", fill="both", expand=True)
        side = tk.Frame(root, bg=self.theme["card"], width=310, padx=16, pady=14); side.pack(side="right", fill="y", padx=(16, 0)); side.pack_propagate(False)
        tk.Label(main, text="TELINHA", font=self.font_tuple("title", 20, True), bg=self.theme["bg"], fg=self.theme["text"]).pack(anchor="w")
        self.subtitle = tk.Label(main, text="Prévia e controle da sua tela", font=self.font_tuple("aux", 10), bg=self.theme["bg"], fg=self.theme["muted"]); self.subtitle.pack(anchor="w", pady=(2, 10))
        pages = tk.Frame(main, bg=self.theme["bg"]); pages.pack(anchor="w", pady=(0, 8))
        ttk.Button(pages, text="Monitor", command=lambda: self.set_page(0)).pack(side="left")
        ttk.Button(pages, text="Player", command=lambda: self.set_page(1)).pack(side="left", padx=6)
        self.page_label = tk.Label(pages, text="", bg=self.theme["bg"], fg=self.accent, font=self.font_tuple("aux", 10, True)); self.page_label.pack(side="left", padx=8)
        self.orientation_var = tk.StringVar(value=self.preview_orientation)
        for value, label in (("vertical", "Vertical"), ("horizontal", "Horizontal"), ("inverted", "Cabeça para baixo")):
            tk.Radiobutton(pages, text=label, value=value, variable=self.orientation_var, command=self.set_orientation, bg=self.theme["bg"], fg=self.theme["text"], selectcolor=self.theme["card"]).pack(side="left", padx=2)
        width, height = canvas_dimensions(self.preview_orientation)
        self.canvas = tk.Canvas(main, width=width, height=height, highlightthickness=0, bg=self.theme["bg"]); self.canvas.pack(anchor="w")
        self.canvas.bind("<Button-1>", self.layout_pointer_down); self.canvas.bind("<B1-Motion>", self.layout_pointer_move); self.canvas.bind("<ButtonRelease-1>", self.layout_pointer_up)
        ttk.Button(main, text="Alternar tema", command=self.toggle_theme).pack(anchor="w", pady=(10, 0))
        ttk.Button(main, text="Salvar configuração", command=self.save_configuration).pack(anchor="w", pady=(5, 0))
        self.save_status = tk.Label(main, text="", bg=self.theme["bg"], fg="#3fae68", font=self.font_tuple("aux", 9)); self.save_status.pack(anchor="w")

        tk.Label(side, text="Estado", font=self.font_tuple("title", 15, True), bg=self.theme["card"], fg=self.theme["text"]).pack(anchor="w")
        self.hardware_status = tk.Label(side, text="Procurando tela compatível…", wraplength=275, justify="left", bg=self.theme["card"], fg=self.theme["muted"]); self.hardware_status.pack(anchor="w", pady=(8, 0))
        self.sensor_status = tk.Label(side, text="Sensores de disco: Libre Hardware Monitor (WMI) opcional. Abra o LHM e habilite WMI para temperatura/SMART; sem ele, valores ficam Indisponíveis.", wraplength=275, justify="left", bg=self.theme["card"], fg=self.theme["muted"]); self.sensor_status.pack(anchor="w", pady=(4, 0))
        self.media_status = tk.Label(side, text="Mídia: verificando…", wraplength=275, justify="left", bg=self.theme["card"], fg=self.theme["muted"]); self.media_status.pack(anchor="w", pady=(5, 0))
        tk.Label(side, text="Envio automático: a cada 1 segundo quando a tela compatível estiver disponível.", wraplength=275, justify="left", bg=self.theme["card"], fg="#3fae68").pack(anchor="w", pady=(5, 14))
        tk.Label(side, text="Aparência", font=self.font_tuple("title", 11, True), bg=self.theme["card"], fg=self.theme["muted"]).pack(anchor="w")
        ttk.Button(side, text="Cor de destaque", command=self.choose_accent).pack(anchor="w", pady=(5, 0))
        theme_row = tk.Frame(side, bg=self.theme["card"]); theme_row.pack(fill="x", pady=(6, 0))
        tk.Label(theme_row, text="Tema do painel", bg=self.theme["card"], fg=self.theme["text"]).pack(anchor="w")
        self.visual_theme_var = tk.StringVar(value=self.visual_theme)
        ttk.Combobox(theme_row, textvariable=self.visual_theme_var, state="readonly", values=available_themes(), width=20).pack(anchor="w")
        ttk.Button(theme_row, text="Aplicar tema e layout", command=self.apply_visual_theme).pack(anchor="w", pady=(3, 7))
        tk.Label(theme_row, text="Visual da telemetria", bg=self.theme["card"], fg=self.theme["text"]).pack(anchor="w")
        self.monitor_style_var = tk.StringVar(value=self.monitor_style)
        ttk.Combobox(theme_row, textvariable=self.monitor_style_var, state="readonly", values=("cards", "graph"), width=20).pack(anchor="w")
        ttk.Button(theme_row, text="Aplicar visual", command=self.set_monitor_style).pack(anchor="w", pady=3)
        self.edit_layout_var = tk.BooleanVar(value=self.edit_layout)
        tk.Checkbutton(side, text="Editar layout", variable=self.edit_layout_var, command=self.toggle_layout_edit, bg=self.theme["card"], fg=self.theme["text"], selectcolor=self.theme["card"]).pack(anchor="w", pady=(7, 0))
        self.editor = tk.Frame(side, bg=self.theme["card"])
        self.layout_help = tk.Label(self.editor, text="Clique em um item da prévia para editar.", wraplength=275, justify="left", bg=self.theme["card"], fg=self.theme["muted"]); self.layout_help.pack(anchor="w", pady=(6, 0))
        self.font_choice = tk.BooleanVar(value=self.custom_fonts_enabled)
        tk.Checkbutton(self.editor, text="Usar fontes personalizadas", variable=self.font_choice, command=self.toggle_font_set, bg=self.theme["card"], fg=self.theme["text"], selectcolor=self.theme["card"]).pack(anchor="w", pady=(5, 0))
        self.inspector = tk.Frame(self.editor, bg=self.theme["card"])
        self.inspector_label = tk.Label(self.inspector, text="", bg=self.theme["card"], fg=self.theme["text"]); self.inspector_label.pack(anchor="w")
        self.item_scale_var = tk.DoubleVar(value=1.0)
        tk.Label(self.inspector, text="Tamanho da fonte", bg=self.theme["card"], fg=self.theme["text"]).pack(anchor="w", pady=(5, 0))
        tk.Scale(self.inspector, from_=0.7, to=1.8, resolution=0.1, orient="horizontal", variable=self.item_scale_var, command=lambda _value: self.set_selected_scale(), bg=self.theme["card"], fg=self.theme["text"], highlightthickness=0).pack(anchor="w")
        tk.Spinbox(self.inspector, from_=0.7, to=1.8, increment=0.1, width=5, textvariable=self.item_scale_var, command=self.set_selected_scale).pack(anchor="w", pady=3)
        for field, label in (("text_color", "Cor do texto"), ("accent_color", "Cor de destaque/linha"), ("background_color", "Cor de fundo"), ("alert_color", "Cor de alerta")):
            ttk.Button(self.inspector, text=label, command=lambda key=field: self.choose_item_color(key)).pack(anchor="w", pady=1)
        ttk.Button(self.inspector, text="Fundo transparente", command=lambda: self.set_item_color("background_color", None)).pack(anchor="w", pady=1)
        ttk.Button(self.inspector, text="Restaurar cores do item", command=self.reset_selected_colors).pack(anchor="w", pady=1)
        ttk.Button(self.inspector, text="Restaurar item", command=self.reset_selected_item).pack(anchor="w")
        tk.Label(side, text="Rotação de páginas", font=self.font_tuple("title", 11, True), bg=self.theme["card"], fg=self.theme["muted"]).pack(anchor="w", pady=(16, 3))
        self.rotation_var = tk.BooleanVar(value=self.rotation_enabled)
        tk.Checkbutton(side, text="Alternar Monitor e Player", variable=self.rotation_var, command=self.set_rotation, bg=self.theme["card"], fg=self.theme["text"], selectcolor=self.theme["card"]).pack(anchor="w")
        self.rotation_interval_var = tk.DoubleVar(value=self.rotation_interval)
        tk.Spinbox(side, from_=2, to=120, increment=1, width=6, textvariable=self.rotation_interval_var, command=self.set_rotation).pack(anchor="w", pady=3)
        tk.Label(side, text="Manual continua disponível; ao tocar em Monitor/Player, a contagem reinicia.", wraplength=275, justify="left", bg=self.theme["card"], fg=self.theme["muted"]).pack(anchor="w")
        tk.Label(side, text="Alertas", font=self.font_tuple("title", 11, True), bg=self.theme["card"], fg=self.theme["muted"]).pack(anchor="w", pady=(14, 3))
        self.limit_vars, self.enabled_vars = {}, {}
        for key, label, low, high, suffix in (("CPU", "CPU", 30, 110, "°C"), ("GPU", "GPU", 30, 110, "°C"), ("Discos", "Discos", 30, 110, "°C"), ("RAM", "Uso de RAM", 1, 100, "%")):
            row=tk.Frame(side,bg=self.theme["card"]); row.pack(fill="x", pady=2)
            self.enabled_vars[key]=tk.BooleanVar(value=self.enabled.get(key, True)); tk.Checkbutton(row,text=label,variable=self.enabled_vars[key],command=self.save_alerts,bg=self.theme["card"],fg=self.theme["text"],selectcolor=self.theme["card"]).pack(side="left")
            self.limit_vars[key]=tk.IntVar(value=self.limits.get(key, 85)); tk.Spinbox(row,from_=low,to=high,width=4,textvariable=self.limit_vars[key],command=self.save_alerts).pack(side="right")
            tk.Label(row,text=suffix,bg=self.theme["card"],fg=self.theme["muted"]).pack(side="right")
        ttk.Button(side, text="Conexão avançada", command=self.toggle_connection_details).pack(anchor="w", pady=(12, 0))
        self.connection = tk.Frame(side, bg=self.theme["card"])
        self.port_var = tk.StringVar(value=self.settings.data["port"])
        tk.Entry(self.connection, textvariable=self.port_var, width=10).pack(anchor="w", pady=3)
        self.brightness_var = tk.IntVar(value=self.preview_brightness)
        tk.Scale(self.connection, from_=10, to=100, orient="horizontal", variable=self.brightness_var, command=self.set_brightness, label="Brilho da prévia", bg=self.theme["card"], fg=self.theme["text"], highlightthickness=0).pack(anchor="w")
        ttk.Button(self.connection, text="Verificar porta", command=self.check_port_status).pack(anchor="w")
        if self.edit_layout: self.editor.pack(fill="x", pady=(4, 0))
        return
        root = tk.Frame(self, bg=self.theme["bg"], padx=18, pady=16)
        root.pack(fill="both", expand=True)
        left = tk.Frame(root, bg=self.theme["bg"])
        left.pack(side="left", fill="both", expand=True)
        right_shell = tk.Frame(root, bg=self.theme["card"], width=270)
        right_shell.pack(side="right", fill="y", padx=(18, 0))
        right_canvas = tk.Canvas(right_shell, bg=self.theme["card"], highlightthickness=0, width=270)
        right_scroll = ttk.Scrollbar(right_shell, orient="vertical", command=right_canvas.yview)
        right_canvas.configure(yscrollcommand=right_scroll.set)
        right_scroll.pack(side="right", fill="y")
        right_canvas.pack(side="left", fill="both", expand=True)
        right = tk.Frame(right_canvas, bg=self.theme["card"], padx=18, pady=18)
        right_window = right_canvas.create_window((0, 0), window=right, anchor="nw")
        right.bind("<Configure>", lambda _event: right_canvas.configure(scrollregion=right_canvas.bbox("all")))
        right_canvas.bind("<Configure>", lambda event: right_canvas.itemconfigure(right_window, width=event.width))

        tk.Label(left, text="TELINHA", font=self.font_tuple("title", 18, True), bg=self.theme["bg"], fg=self.theme["text"]).pack(anchor="w")
        self.subtitle = tk.Label(left, text="Prévia local para tela USB compatível / 320 × 480", font=self.font_tuple("aux", 10), bg=self.theme["bg"], fg=self.theme["muted"])
        self.subtitle.pack(anchor="w", pady=(2, 16))
        preview_width, preview_height = canvas_dimensions(self.preview_orientation)
        self.canvas = tk.Canvas(left, width=preview_width, height=preview_height, highlightthickness=0, bg=self.theme["bg"])
        self.canvas.pack(anchor="w")
        self.canvas.bind("<Button-1>", self.layout_pointer_down)
        self.canvas.bind("<B1-Motion>", self.layout_pointer_move)
        self.canvas.bind("<ButtonRelease-1>", self.layout_pointer_up)
        orientation_controls = tk.Frame(left, bg=self.theme["bg"])
        orientation_controls.pack(anchor="w", pady=(10, 0))
        tk.Label(orientation_controls, text="Orientação e perfil da prévia", bg=self.theme["bg"], fg=self.theme["muted"]).pack(side="left", padx=(0, 8))
        self.orientation_var = tk.StringVar(value=self.preview_orientation)
        for value, label in (("vertical", "Vertical"), ("horizontal", "Horizontal"), ("inverted", "Cabeça para baixo")):
            tk.Radiobutton(orientation_controls, text=label, value=value, variable=self.orientation_var, command=self.set_orientation,
                bg=self.theme["bg"], fg=self.theme["text"], selectcolor=self.theme["card"]).pack(side="left", padx=3)
        controls = tk.Frame(left, bg=self.theme["bg"])
        controls.pack(anchor="w", pady=20)
        ttk.Button(controls, text="Monitor", command=lambda: self.set_page(0)).pack(side="left")
        ttk.Button(controls, text="Player", command=lambda: self.set_page(1)).pack(side="left", padx=6)
        ttk.Button(controls, text="Alternar tema", command=self.toggle_theme).pack(side="left", padx=(4, 10))
        ttk.Button(controls, text="Cor de destaque", command=self.choose_accent).pack(side="left")

        tk.Label(right, text="Configuracoes", font=self.font_tuple("title", 15, True), bg=self.theme["card"], fg=self.theme["text"]).pack(anchor="w")
        tk.Label(right, text="Alertas termicos", font=self.font_tuple("title", 11, True), bg=self.theme["card"], fg=self.theme["muted"]).pack(anchor="w", pady=(20, 6))
        self.limit_vars: dict[str, tk.IntVar] = {}
        self.enabled_vars: dict[str, tk.BooleanVar] = {}
        for key, label in [("CPU", "CPU"), ("GPU", "GPU"), ("Discos", "Discos")]:
            row = tk.Frame(right, bg=self.theme["card"])
            row.pack(fill="x", pady=7)
            enabled = tk.BooleanVar(value=True)
            self.enabled_vars[key] = enabled
            tk.Checkbutton(row, text=label, variable=enabled, command=self.save_alerts, bg=self.theme["card"], fg=self.theme["text"], selectcolor=self.theme["card"], activebackground=self.theme["card"], activeforeground=self.theme["text"]).pack(side="left")
            var = tk.IntVar(value=self.limits[key])
            self.limit_vars[key] = var
            spin = tk.Spinbox(row, from_=30, to=110, width=4, textvariable=var, command=self.save_alerts)
            spin.pack(side="right")
            tk.Label(row, text="°C", bg=self.theme["card"], fg=self.theme["muted"]).pack(side="right", padx=(0, 4))
        ttk.Button(right, text="Restaurar recomendações", command=self.restore_recommendations).pack(anchor="w", pady=(12, 0))
        tk.Label(right, text="Recomendado: CPU 85 °C • GPU 82 °C • discos 60 °C", wraplength=220, justify="left", font=("Segoe UI", 9), bg=self.theme["card"], fg=self.theme["muted"]).pack(anchor="w", pady=(12, 0))
        tk.Label(right, text="Tela fisica (opcional)", font=self.font_tuple("title", 11, True), bg=self.theme["card"], fg=self.theme["muted"]).pack(anchor="w", pady=(20, 4))
        port_row = tk.Frame(right, bg=self.theme["card"])
        port_row.pack(fill="x")
        tk.Label(port_row, text="Porta", bg=self.theme["card"], fg=self.theme["text"]).pack(side="left")
        self.port_var = tk.StringVar(value=self.settings.data["port"])
        tk.Entry(port_row, textvariable=self.port_var, width=9).pack(side="right")
        ttk.Button(right, text="Verificar porta", command=self.check_port_status).pack(anchor="w", pady=(5, 0))
        ttk.Button(right, text="Enviar esta previa para a tela", command=self.send_preview_to_screen).pack(anchor="w", pady=(7, 0))
        ttk.Button(right, text="Enviar calibracao de cores", command=self.send_screen_test).pack(anchor="w", pady=(6, 0))
        self.hardware_status = tk.Label(right, text="Envio real desligado até clicar no teste.", wraplength=220, justify="left", font=("Segoe UI", 9), bg=self.theme["card"], fg=self.theme["muted"])
        self.hardware_status.pack(anchor="w", pady=(5, 0))
        tk.Label(right, text="Mídia", font=self.font_tuple("title", 11, True), bg=self.theme["card"], fg=self.theme["muted"]).pack(anchor="w", pady=(18, 4))
        self.media_status = tk.Label(right, text="Midia: verificando GSMTC...", wraplength=220, justify="left", font=("Segoe UI", 9), bg=self.theme["card"], fg=self.theme["muted"])
        self.media_status.pack(anchor="w", pady=(7, 0))
        self.media_diagnostics = tk.Label(right, text="Diagnóstico GSMTC: aguardando consulta.", wraplength=220, justify="left", font=("Segoe UI", 8), bg=self.theme["card"], fg=self.theme["muted"])
        self.media_diagnostics.pack(anchor="w", pady=(3, 0))
        tk.Label(right, text="Sincronização automática: ligada (1 s)", wraplength=220, justify="left", font=("Segoe UI", 8), bg=self.theme["card"], fg="#3fae68").pack(anchor="w", pady=(3, 0))
        ttk.Button(right, text="Atualizar mídia agora", command=self.refresh_media_now).pack(anchor="w", pady=(5, 0))
        self.auto_send_var = tk.BooleanVar(value=self.auto_send_enabled)
        tk.Checkbutton(right, text="Enviar automaticamente a tela", variable=self.auto_send_var, command=self.set_auto_send, bg=self.theme["card"], fg=self.theme["text"], selectcolor=self.theme["card"]).pack(anchor="w", pady=(8, 0))
        cadence_row = tk.Frame(right, bg=self.theme["card"]); cadence_row.pack(fill="x")
        tk.Label(cadence_row, text="Cadencia (s)", bg=self.theme["card"], fg=self.theme["text"]).pack(side="left")
        self.send_interval_var = tk.DoubleVar(value=self.send_interval)
        tk.Spinbox(cadence_row, from_=1.5, to=30, increment=0.5, width=5, textvariable=self.send_interval_var, command=self.set_send_interval).pack(side="right")
        tk.Label(right, text="A mídia atualiza a cada 1 s; a página só muda pelos botões Monitor/Player ou Ctrl+1/Ctrl+2.", wraplength=220, justify="left", font=("Segoe UI", 8), bg=self.theme["card"], fg=self.theme["muted"]).pack(anchor="w", pady=(4, 0))
        tk.Label(right, text="Aparência", font=self.font_tuple("title", 11, True), bg=self.theme["card"], fg=self.theme["muted"]).pack(anchor="w", pady=(16, 3))
        scale_row = tk.Frame(right, bg=self.theme["card"]); scale_row.pack(fill="x", pady=(6, 0))
        tk.Label(scale_row, text="Escala de fonte", bg=self.theme["card"], fg=self.theme["text"]).pack(side="left")
        self.font_scale_var = tk.DoubleVar(value=self.font_scale)
        tk.Spinbox(scale_row, from_=0.8, to=1.5, increment=0.1, width=4, textvariable=self.font_scale_var, command=self.set_font_scale).pack(side="right")
        tk.Label(right, text="Layout", font=self.font_tuple("title", 11, True), bg=self.theme["card"], fg=self.theme["muted"]).pack(anchor="w", pady=(14, 3))
        self.module_var = tk.StringVar(value="cpu")
        ttk.Combobox(right, state="readonly", width=18, textvariable=self.module_var, values=("cpu", "gpu", "ram", "disks")).pack(anchor="w")
        module_buttons = tk.Frame(right, bg=self.theme["card"]); module_buttons.pack(anchor="w", pady=(5, 0))
        ttk.Button(module_buttons, text="Subir", command=lambda: self.edit_module(-8, 0)).pack(side="left")
        ttk.Button(module_buttons, text="Descer", command=lambda: self.edit_module(8, 0)).pack(side="left", padx=3)
        ttk.Button(module_buttons, text="+ Tamanho", command=lambda: self.edit_module(0, 8)).pack(side="left")
        ttk.Button(right, text="Restaurar layout", command=self.restore_layout).pack(anchor="w", pady=(4, 0))
        self.edit_layout_var = tk.BooleanVar(value=getattr(self, "edit_layout", False))
        tk.Checkbutton(right, text="Editar layout na prévia", variable=self.edit_layout_var, command=self.toggle_layout_edit, bg=self.theme["card"], fg=self.theme["text"], selectcolor=self.theme["card"]).pack(anchor="w", pady=(8, 0))
        self.layout_help = tk.Label(right, text="Edição desligada", wraplength=220, justify="left", font=("Segoe UI", 8), bg=self.theme["card"], fg=self.theme["muted"])
        self.layout_help.pack(anchor="w", pady=(2, 0))
        self.font_choice = tk.BooleanVar(value=self.custom_fonts_enabled)
        tk.Checkbutton(right, text="Usar fontes personalizadas", variable=self.font_choice, command=self.toggle_font_set, bg=self.theme["card"], fg=self.theme["text"], selectcolor=self.theme["card"], activebackground=self.theme["card"], activeforeground=self.theme["text"]).pack(anchor="w", pady=(16, 0))
        self.page_label = tk.Label(right, text="", font=self.font_tuple("title", 11, True), bg=self.theme["card"], fg=self.accent)
        self.page_label.pack(anchor="w", pady=(26, 0))

    def save_alerts(self) -> None:
        for key in self.limits:
            self.limits[key] = self.limit_vars[key].get()
            self.enabled[key] = self.enabled_vars[key].get()
        self.save_preferences()

    def save_preferences(self) -> None:
        self.settings.data.update({"dark": self.dark, "accent": self.accent, "custom_fonts": self.custom_fonts_enabled,
            "font_scale": self.font_scale, "auto_switch_media": False, "auto_send": self.auto_send_enabled,
            "send_interval": self.send_interval, "port": self.port_var.get() if hasattr(self, "port_var") else "COM3", "orientation": self.preview_orientation,
            "rotation_enabled": self.rotation_enabled, "rotation_interval": self.rotation_interval, "rotation_pages": list(self.rotation_pages), "preview_brightness": self.preview_brightness,
            "monitor_style": self.monitor_style,
            "visual_theme": self.visual_theme,
            "limits": self.limits, "enabled": self.enabled, "geometry": self.geometry()})
        self.settings.save()

    def save_configuration(self) -> None:
        self.layout_store.save()
        self.save_preferences()
        if hasattr(self, "save_status"):
            self.save_status.configure(text="Configuração salva.")

    def set_monitor_style(self) -> None:
        self.monitor_style = self.monitor_style_var.get()
        self.save_preferences()
        self.draw(force=True)

    def apply_visual_theme(self) -> None:
        """This explicit action is the only time a theme replaces layouts."""
        self.visual_theme = self.visual_theme_var.get()
        self.layout_store.apply_template(self.visual_theme)
        self.save_preferences()
        self.save_status.configure(text=f"{self.visual_theme} aplicado com layout próprio.")
        self.draw(force=True)

    def restore_recommendations(self) -> None:
        for key, value in {"CPU": 85, "GPU": 82, "Discos": 60}.items():
            self.limit_vars[key].set(value)
            self.enabled_vars[key].set(True)
        self.save_alerts()

    def next_page(self) -> None:
        self.page = (self.page + 1) % 2
        self.draw(force=True)

    def set_page(self, page: int) -> None:
        """Explicit user navigation; media polling never calls this method."""
        self.page = page
        self.last_page_change = time.monotonic()
        self.draw(force=True)

    def on_main_window_close(self) -> None:
        if close_action() == "exit":
            self.quit_app()
        else:
            self.hide_to_tray()

    def toggle_connection_details(self) -> None:
        if self.connection.winfo_manager():
            self.connection.pack_forget()
        else:
            self.connection.pack(fill="x", pady=(4, 0))

    def set_rotation(self) -> None:
        self.rotation_enabled = self.rotation_var.get()
        self.rotation_interval = max(2.0, float(self.rotation_interval_var.get()))
        self.last_page_change = time.monotonic()
        self.save_preferences()

    def set_brightness(self, _value=None) -> None:
        self.preview_brightness = int(self.brightness_var.get())
        self.save_preferences()
        if hasattr(self, "hardware_status"):
            self.hardware_status.configure(text=brightness_status(self.preview_brightness) + "; o protocolo desta tela não documenta brilho físico.", fg=self.theme["muted"])
        self.draw(force=True)

    def toggle_theme(self) -> None:
        self.dark = not self.dark
        self.save_preferences()
        self._rebuild()

    def start_tray(self) -> None:
        """Create a lightweight tray loop; failure leaves normal window behavior intact."""
        try:
            import pystray
            from PIL import Image, ImageDraw
            icon_image = Image.new("RGB", (64, 64), "#10151f")
            icon_draw = ImageDraw.Draw(icon_image)
            icon_draw.ellipse((8, 8, 56, 56), fill="#5b8cff")
            icon_draw.rectangle((29, 17, 35, 47), fill="#f3f6fb")
            self.tray_icon = pystray.Icon("telinha", icon_image, "Telinha",
                pystray.Menu(pystray.MenuItem("Abrir", lambda *_: self.after(0, self.show_from_tray)),
                             pystray.MenuItem("Encerrar Rebscreen", lambda *_: self.after(0, self.quit_app))))
            threading.Thread(target=self.tray_icon.run, name="telinha-tray", daemon=True).start()
        except Exception:
            self.tray_icon = None

    def show_from_tray(self) -> None:
        self.deiconify(); self.lift(); self.focus_force()

    def hide_to_tray(self) -> None:
        self.save_preferences()
        if self.tray_icon is None:
            self.destroy()
        else:
            self.withdraw()

    def quit_app(self) -> None:
        self.save_preferences()
        self.auto_send_enabled = False
        if self.tray_icon is not None:
            self.tray_icon.stop()
        self.media_executor.shutdown(wait=False, cancel_futures=True)
        self.single_instance.close()
        self.destroy()

    def choose_accent(self) -> None:
        selected = colorchooser.askcolor(self.accent, parent=self)[1]
        if selected:
            self.accent = selected
            self.save_preferences()
            self.draw(force=True)

    def toggle_font_set(self) -> None:
        self.custom_fonts_enabled = self.font_choice.get()
        self.save_preferences()
        self._rebuild()

    def set_font_scale(self) -> None:
        self.font_scale = float(self.font_scale_var.get()); self.save_preferences(); self.draw()

    def set_auto_send(self) -> None:
        self.auto_send_enabled = self.auto_send_var.get()
        self.save_preferences()
        self.hardware_status.configure(text="Envio automatico ATIVO." if self.auto_send_enabled else "Envio automatico desligado.", fg="#ef9b3e" if self.auto_send_enabled else self.theme["muted"])

    def set_send_interval(self) -> None:
        self.send_interval = max(1.5, float(self.send_interval_var.get()))
        self.save_preferences()

    def set_orientation(self) -> None:
        self.preview_orientation = self.orientation_var.get()
        self.layout_store.activate(self.preview_orientation)
        width, height = canvas_dimensions(self.preview_orientation)
        self.canvas.configure(width=width, height=height)
        self.save_preferences()
        self.draw(force=True)

    def edit_module(self, delta_y: int, delta_h: int) -> None:
        item = self.layout_store.data[self.module_var.get()]
        item["y"] = max(60, min(400, item["y"] + delta_y)); item["h"] = max(28, min(115, item["h"] + delta_h))
        self.layout_store.save(); self.draw(force=True)

    def restore_layout(self) -> None:
        self.layout_store.reset(); self.draw(force=True)

    def toggle_layout_edit(self) -> None:
        self.edit_layout = self.edit_layout_var.get()
        if not self.edit_layout:
            self.layout_store.save()
            self.layout_selection = None
        profile = "horizontal" if self.preview_orientation == "horizontal" else "vertical"
        self.layout_help.configure(text=f"Clique em um item e arraste; perfil {profile} salvo automaticamente." if self.edit_layout else "Edição desligada; cada orientação mantém seu próprio perfil.")
        if self.edit_layout:
            self.editor.pack(fill="x", pady=(4, 0))
        else:
            self.editor.pack_forget()
        self.draw(force=True)

    def layout_bounds(self, key: str) -> tuple[int, int, int, int]:
        data = self.layout_store.data
        if self.page == 0:
            base = (18, data[key]["y"], 302, data[key]["y"] + data[key]["h"] * 2 + 6) if key == "disks" else (18, data[key]["y"], 302, data[key]["y"] + data[key]["h"])
        elif key == "art":
            item = data[key]; base = (item["x"], item["y"], item["x"] + item["size"], item["y"] + item["size"])
        elif key == "progress":
            item = data[key]; base = (item["x"], item["y"] - 6, item["x"] + item["w"], item["y"] + 30)
        else:
            item = data[key]
            widths = {"title": 250, "artist": 220, "state": 180}
            heights = {"title": 32, "artist": 24, "state": 22}
            base = (item["x"] - widths[key] // 2, item["y"] - 15, item["x"] + widths[key] // 2, item["y"] + heights[key])
        if self.preview_orientation == "horizontal":
            x1, y1, x2, y2 = base
            return 480 - y2, x1, 480 - y1, x2
        return base

    def layout_keys(self) -> tuple[str, ...]:
        return ("cpu", "gpu", "ram", "disks") if self.page == 0 else ("art", "title", "artist", "state", "progress")

    def draw_layout_overlay(self) -> None:
        if not getattr(self, "edit_layout", False): return
        width, height = canvas_dimensions(self.preview_orientation)
        for pos in range(0, width + 1, 40): self.canvas.create_line(pos, 0, pos, height, fill="#5b8cff", stipple="gray25", tags="layout_overlay")
        for pos in range(0, height + 1, 40): self.canvas.create_line(0, pos, width, pos, fill="#5b8cff", stipple="gray25", tags="layout_overlay")
        if self.layout_selection:
            x1, y1, x2, y2 = self.layout_bounds(self.layout_selection)
            self.canvas.create_rectangle(x1, y1, x2, y2, outline="#70d6ff", width=2, tags="layout_overlay")
            self.canvas.create_rectangle(x2 - 5, y2 - 5, x2 + 5, y2 + 5, fill="#70d6ff", outline="", tags="layout_overlay")

    def update_layout_overlay(self) -> None:
        """Pointer moves only update Tk's cheap overlay, never Pillow or disk."""
        self.canvas.delete("layout_overlay")
        self.draw_layout_overlay()

    def layout_pointer_down(self, event) -> None:
        if not getattr(self, "edit_layout", False): return
        for key in reversed(self.layout_keys()):
            x1, y1, x2, y2 = self.layout_bounds(key)
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self.layout_selection = key
                self.inspector_label.configure(text=f"Item selecionado: {key}")
                self.item_scale_var.set(float(self.layout_store.data[key].get("font_scale", 1.0)))
                self.inspector.pack(fill="x", pady=(6, 0))
                self.layout_drag_origin = (event.x, event.y)
                self.layout_drag_mode = "resize" if event.x >= x2 - 12 and event.y >= y2 - 12 else "move"
                self.update_layout_overlay(); return
        self.layout_selection = None; self.update_layout_overlay()

    def layout_pointer_move(self, event) -> None:
        if not getattr(self, "layout_selection", None) or not hasattr(self, "layout_drag_origin"): return
        dx, dy = event.x - self.layout_drag_origin[0], event.y - self.layout_drag_origin[1]
        if not dx and not dy: return
        key, item = self.layout_selection, self.layout_store.data[self.layout_selection]
        logical_dx, logical_dy = (dy, -dx) if self.preview_orientation == "horizontal" else (dx, dy)
        if not apply_drag(item, key, self.layout_drag_mode, logical_dx, logical_dy):
            return
        self.layout_drag_origin = (event.x, event.y)
        self.update_layout_overlay()

    def layout_pointer_up(self, _event) -> None:
        if getattr(self, "layout_selection", None): self.layout_store.save()
        self.layout_drag_origin = None
        # Commit once after a gesture; no Pillow, GSMTC, settings, or serial I/O
        # occurs while the pointer is moving.
        self.draw(force=True)

    def set_selected_scale(self) -> None:
        if not self.layout_selection:
            return
        item = self.layout_store.data[self.layout_selection]
        factor = float(self.item_scale_var.get())
        if self.layout_selection in ("title", "artist", "state"):
            item["font_scale"] = factor
        elif "size" in item: item["size"] = max(56, min(300, int(216 * factor)))
        elif "w" in item: item["w"] = max(80, min(300, int(272 * factor)))
        elif "h" in item: item["h"] = max(28, min(150, int(74 * factor)))
        self.layout_store.save(); self.draw(force=True)

    def choose_item_color(self, field: str) -> None:
        if not self.layout_selection: return
        current = self.layout_store.data[self.layout_selection].get(field, self.accent)
        selected = colorchooser.askcolor(current, parent=self)[1]
        if selected: self.set_item_color(field, selected)

    def set_item_color(self, field: str, color: str | None) -> None:
        if not self.layout_selection: return
        set_item_color(self.layout_store.data[self.layout_selection], field, color)
        self.layout_store.save(); self.draw(force=True)

    def reset_selected_colors(self) -> None:
        if self.layout_selection:
            reset_item_colors(self.layout_store.data[self.layout_selection])
            self.layout_store.save(); self.draw(force=True)

    def reset_selected_item(self) -> None:
        if self.layout_selection:
            self.layout_store.data[self.layout_selection] = dict(LayoutStore.default[self.layout_selection])
            self.layout_store.save(); self.draw(force=True)

    def send_screen_test(self) -> None:
        """User-initiated only: write the neutral reversible test frame once."""
        try:
            TuringScreenTransport(self.port_var.get().strip()).send_test_frame("PAGINA DE DEMONSTRACAO")
            self.hardware_status.configure(text="Teste enviado: 320 × 480 em " + self.port_var.get(), fg="#3fae68")
        except Exception as exc:
            self.hardware_status.configure(text=explain_serial_error(exc), fg="#ef5350")

    def check_port_status(self) -> None:
        """A manual open/close check; it sends no bytes and leaves no stream open."""
        port = self.port_var.get().strip()
        try:
            import serial
            with serial.Serial(port, 115200, timeout=1, write_timeout=1, rtscts=True):
                pass
            self.hardware_status.configure(text=f"{port} disponível. Envio continua manual e desligado.", fg="#3fae68")
        except Exception as exc:
            self.hardware_status.configure(text=explain_serial_error(exc), fg="#ef5350")

    def render_live_frame(self):
        """The live frame is for the physical display, never the static preview."""
        frame = PanelFrameRenderer(self.theme, self.accent, self.custom_fonts_enabled, self.font_scale, self.layout_store.data, self.monitor_style, self.visual_theme).render(
            self.page, self.last_metrics, self.track, self.current_alert, self.media_label, self.album_art, history=self.telemetry_history, network=(self.rx_rate, self.tx_rate))
        from PIL import Image
        if self.preview_orientation == "horizontal": return frame.transpose(Image.Transpose.ROTATE_270)
        if self.preview_orientation == "inverted": return frame.transpose(Image.Transpose.ROTATE_180)
        return frame

    def render_current_frame(self):
        return self.render_live_frame()

    def render_preview_frame(self):
        """Cosmetic snapshot: brightness and motion are intentionally local only."""
        from PIL import ImageEnhance
        frame = self.render_live_frame()
        return ImageEnhance.Brightness(frame).enhance(self.preview_brightness / 100)

    def send_preview_to_screen(self) -> None:
        """User-initiated only: sends the exact image currently used in the preview."""
        if self.preview_orientation != "vertical":
            self.hardware_status.configure(text="Envio físico bloqueado: valide primeiro a orientação vertical do protocolo.", fg="#ef9b3e")
            return
        try:
            TuringScreenTransport(self.port_var.get().strip()).send_pil_image(self.render_live_frame())
            self.hardware_status.configure(text="Previa enviada com sucesso.", fg="#3fae68")
        except Exception as exc:
            self.hardware_status.configure(text=explain_serial_error(exc), fg="#ef5350")

    def _rebuild(self) -> None:
        for child in self.winfo_children(): child.destroy()
        self._build_ui(); self.draw(force=True)

    def _text(self, x: int, y: int, text: str, size: int, color: str | None = None, bold: bool = False, anchor: str = "nw", role: str = "aux") -> None:
        self.canvas.create_text(x, y, text=text, fill=color or self.theme["text"], anchor=anchor, font=self.font_tuple(role, size, bold))

    def draw(self, force: bool = False) -> None:
        from PIL import ImageTk
        c = self.canvas
        c.delete("all"); c.configure(bg=self.theme["bg"])
        if force or self.preview_static_frame is None:
            self.preview_static_frame = self.render_preview_frame()
        self.preview_frame = self.preview_static_frame
        self.preview_photo = ImageTk.PhotoImage(self.preview_frame)
        c.create_image(0, 0, image=self.preview_photo, anchor="nw")
        self.draw_layout_overlay()
        labels = ["Página 1 de 2 — Monitor do PC", "Página 2 de 2 — Spotify: Tocando agora"]
        self.page_label.configure(text=labels[self.page])

    def draw_monitor(self) -> None:
        t, m = self.theme, self.last_metrics
        self._text(18, 16, "MONITOR DO PC", 17, bold=True, role="title")
        self._text(18, 41, "Dados de demonstracao", 9, t["muted"])
        cards = [(18, 68, "CPU", f"{m.cpu_usage}%", f"{m.cpu_temperature} C"), (18, 154, "GPU", f"{m.gpu_usage}%", f"{m.gpu_temperature} C"), (18, 240, "MEMORIA", f"{m.ram_usage}%", "RAM em uso")]
        for x, y, title, value, sub in cards:
            self.canvas.create_rectangle(x, y, x+284, y+74, fill=t["card"], outline=t["line"])
            self._text(x+12, y+10, title, 9, t["muted"], True)
            self._text(x+12, y+28, value, 22, self.accent, True, role="metric")
            self._text(x+150, y+37, sub, 11, t["muted"])
        self._text(18, 335, "ARMAZENAMENTO", 9, t["muted"], True)
        for i, disk in enumerate(m.disks):
            y = 355 + i * 37
            self.canvas.create_rectangle(18, y, 302, y+31, fill=t["card"], outline=t["line"])
            self._text(28, y+8, disk.name, 10, bold=True)
            self._text(292, y+8, f"{disk.temperature} C / {disk.health}", 8, t["muted"], anchor="ne")
        self._text(18, 426, "Use Proxima pagina para validar o ciclo.", 8, t["muted"])

    def draw_spotify(self) -> None:
        t, s = self.theme, self.track
        self._text(18, 16, "TOCANDO AGORA", 17, bold=True, role="title")
        self._text(18, 41, "Spotify / dados de demonstracao", 9, t["muted"])
        # Abstract generated album art placeholder, requiring no external media.
        self.canvas.create_rectangle(70, 64, 250, 244, fill="#4d2b78", outline="")
        self.canvas.create_oval(98, 92, 222, 216, fill=self.accent, outline="")
        self.canvas.create_oval(132, 126, 188, 182, fill="#111827", outline="")
        self._text(160, 254, s.title, 17, anchor="n", bold=True, role="title")
        self._text(160, 277, s.artist, 11, t["muted"], anchor="n")
        self.canvas.create_rectangle(28, 310, 292, 315, fill=t["line"], outline="")
        progress = 264 * s.elapsed / s.duration
        self.canvas.create_rectangle(28, 310, 28+progress, 315, fill=self.accent, outline="")
        self._text(28, 320, self.format_time(s.elapsed), 9, t["muted"])
        self._text(292, 320, self.format_time(s.duration), 9, t["muted"], anchor="ne")
        current, upcoming = self.lyrics_provider.current(s.elapsed)
        self._text(18, 352, self.lyrics_provider.source, 8, t["muted"])
        self._text(18, 372, current, 10, self.accent, True)
        if upcoming:
            self._text(18, 395, upcoming, 8, t["muted"])

    @staticmethod
    def format_time(value: int) -> str:
        return f"{value // 60}:{value % 60:02d}"

    def update_alerts(self) -> None:
        m = self.last_metrics
        found: list[str] = []
        if self.enabled["CPU"] and m.cpu_temperature >= self.limits["CPU"]:
            found.append(f"ALERTA CPU: {m.cpu_temperature} °C • limite {self.limits['CPU']} °C")
        if self.enabled["GPU"] and m.gpu_temperature >= self.limits["GPU"]:
            found.append(f"ALERTA GPU: {m.gpu_temperature} °C • limite {self.limits['GPU']} °C")
        for d in m.disks:
            if self.enabled["Discos"] and d.temperature is not None and d.temperature >= self.limits["Discos"]:
                found.append(f"ALERTA {d.name}: {d.temperature} °C • limite {self.limits['Discos']} °C")
        if self.enabled["RAM"] and m.ram_usage >= self.limits["RAM"]:
            found.append(f"ALERTA RAM: {m.ram_usage}% em uso • limite {self.limits['RAM']}%")
        if found != self.alerts:
            self.alerts = found
            self.alert_cycle = cycle(found or [""])
        self.current_alert = next(self.alert_cycle)

    def apply_media(self, media) -> bool:
        """Apply a completed background GSMTC read on the Tk thread."""
        changed = should_render_media(self.last_media_key, media)
        if media:
            self.track, self.media_label, self.album_art = media.track, media.source, artwork_for_display(media.art_image)
            self.media_status.configure(text=f"Mídia: {media.source} / {media.playback_label} / {media.track.title}", fg="#3fae68")
        else:
            self.track = Track("Nenhuma mídia ativa", "Inicie Spotify ou outro player compatível", 0, 1)
            self.media_label, self.album_art = "Nenhuma mídia ativa", None
            state = self.media_provider.reason
            self.media_status.configure(text="Mídia: nenhuma sessão ativa. " + state, fg="#ef9b3e")
        self.page = page_after_media_refresh(self.page)
        details = "\n".join(self.media_provider.diagnostics) or "Nenhuma sessão publicada pelo Windows."
        if media and media.source.startswith("VLC ("):
            details += "\nVLC detectado pelo título da janela; estado, progresso e capa não publicados via GSMTC."
        self.media_diagnostics.configure(text="Diagnóstico GSMTC:\n" + details)
        self.last_media_key = snapshot_key(media)
        return changed

    def poll_media(self) -> bool:
        """Never run WinRT/thumbnail I/O on Tk's event loop."""
        changed = False
        if self.media_future is not None and self.media_future.done():
            try:
                snapshot = self.media_future.result()
                changed = self.apply_media(snapshot or spotify_window_snapshot() or vlc_window_snapshot())
            except Exception as exc:
                self.media_status.configure(text="Mídia: falha em segundo plano: " + str(exc), fg="#ef5350")
            self.media_future = None
            changed = True
        elif self.media_future is not None:
            # A WinRT request can block at the Windows service boundary.  Do
            # not let that turn the Player page into fictitious demo content.
            elapsed = time.monotonic() - self.media_query_started
            fallback = spotify_window_snapshot() or vlc_window_snapshot()
            if fallback and (self.media_label != fallback.source or self.track.title != fallback.track.title):
                changed = self.apply_media(fallback)
            elif query_timed_out(self.media_query_started, time.monotonic()) and not self.media_query_timed_out:
                self.media_provider.reason = "GSMTC não respondeu em 4 s; tente Atualizar mídia após reiniciar o serviço/jogador."
                self.media_provider.diagnostics = ["Solicitação GSMTC excedeu 4 s.", "Nenhum fallback de título de janela foi encontrado."]
                changed = self.apply_media(None)
                self.media_query_timed_out = True
                changed = True
        if self.media_future is None:
            self.media_future = self.media_executor.submit(self.media_provider.read)
            self.media_query_started = time.monotonic()
            self.media_query_timed_out = False
        return changed

    def refresh_media_now(self) -> None:
        """Queue a safe inspection; normal synchronization is already automatic."""
        self.poll_media()

    def refresh(self) -> None:
        now = time.monotonic()
        metrics_changed = now - self.last_metrics_update >= 2.0
        if metrics_changed:
            self.last_metrics = self.metrics_provider.read()
            if hasattr(self, "sensor_status"):
                self.sensor_status.configure(text="Sensores de disco: " + self.metrics_provider.sensor_status, fg=self.theme["muted"])
            self.cpu_history = (self.cpu_history + [self.last_metrics.cpu_usage])[-60:]
            temperatures = [self.last_metrics.cpu_temperature, self.last_metrics.gpu_temperature, *(disk.temperature for disk in self.last_metrics.disks)]
            self.telemetry_history = (self.telemetry_history + [aggregate_point(self.last_metrics.cpu_usage, self.last_metrics.gpu_usage, self.last_metrics.ram_usage, temperatures)])[-60:]
            self.rx_rate, self.tx_rate = self.network_rates.read()
            self.last_metrics_update = now
            self.update_alerts()
        media_changed = self.poll_media()
        # The app preview is deliberately static and cosmetic.  Live data is
        # still rendered below for the physical display.
        if rotation_due(self.rotation_enabled, self.last_page_change, now, self.rotation_interval):
            self.page = next_enabled_page(self.page, self.rotation_pages)
            self.last_page_change = now
            self.draw(force=True)
        if self.auto_send_enabled and self.preview_orientation == "vertical" and now - self.last_auto_send >= self.send_interval:
            try:
                import serial.tools.list_ports
                port = self.port_var.get().strip()
                detected = {item.device.upper() for item in serial.tools.list_ports.comports()}
                if port.upper() not in detected:
                    self.hardware_status.configure(text=f"Aguardando tela compatível em {port}; nenhum envio foi feito.", fg=self.theme["muted"])
                else:
                    TuringScreenTransport(port).send_pil_image(self.render_live_frame())
                    self.last_auto_send = now
                    self.hardware_status.configure(text="Tela conectada: atualização enviada a cada 1 s.", fg="#3fae68")
            except Exception as exc:
                self.hardware_status.configure(text="Envio aguardando disponibilidade: " + explain_serial_error(exc), fg="#ef5350")
        self.after(1000, self.refresh)


if __name__ == "__main__":
    PanelApp().mainloop()

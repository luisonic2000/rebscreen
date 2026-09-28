"""Rebscreen — local Windows companion for compatible USB displays.

The provider classes deliberately separate UI data from the future USB screen
transport.  Replace DemoMetricsProvider/SpotifyDemoProvider and implement
TuringScreenTransport to move from this prototype to live hardware.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import cycle
from io import BytesIO
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import ctypes
import asyncio
import importlib.util
import json
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import colorchooser, messagebox, ttk
from layout_interaction import apply_drag
from hardware_status import explain_serial_error
from layout_normalization import normalize_profile
from media_display import artwork_for_display, page_after_media_refresh
from media_runtime import query_timed_out, should_render_media, snapshot_key
from media_selection import select_preferred_active
from orientation_profiles import canvas_dimensions, make_profiles, profile_for
from app_lifecycle import close_action
from rotation import next_enabled_page, rotation_due
from telemetry_mapping import disk_label, normalize_disks
from single_instance import SingleInstance
from visual_themes import SOUNDWAVE_PALETTE, THEME_TECHNICAL, THEME_REBEL, THEME_CASSETTE, available_themes, layout_templates
from rebscreen_identity import APP_NAME, APP_VERSION, header_state
from source_icons import draw_source_icon
from network_telemetry import NetworkRates
from telemetry_history import aggregate_point, rate_label
from layout_colors import reset_item_colors, set_item_color
from process_telemetry import ProcessSampler, ProcessRow
from background_runtime import LatestTask
from auto_send_policy import MINIMUM_SEND_INTERVAL, initial_auto_send, send_interval
from page_navigation import normalize_page, normalize_rotation_pages
from screen_transport import (
    IncrementalFrameSender,
    TuringScreenTransport,
    check_display_port as _check_display_port,
    send_frame_to_display as _send_frame_to_display,
    send_incremental_frame_to_display as _send_incremental_frame_to_display,
    send_test_frame_to_display as _send_test_frame_to_display,
)
from panel_models import Disk, MediaSnapshot, Metrics, Track
from sample_telemetry import SampleMetricsProvider
from localization import (
    DEFAULT_LANGUAGE, LANGUAGE_NAMES, localize_media_runtime_message,
    localize_sensor_status, localize_transport_status, normalize_language, translate,
)
from dependency_help import build_help_text, detect_dependency_issues

# Compatibility name for existing integrations; values remain explicitly marked
# as demonstration data by SampleMetricsProvider.
DemoMetricsProvider = SampleMetricsProvider


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
               "auto_switch_media": False, "auto_send": False, "auto_send_approved": False, "send_interval": MINIMUM_SEND_INTERVAL, "port": "COM3", "orientation": "vertical",
               "geometry": "1180x760", "rotation_enabled": False, "rotation_interval": 10.0,
               "rotation_pages": [True, True, True], "preview_brightness": 100, "monitor_style": "cards", "visual_theme": THEME_REBEL,
               "language": DEFAULT_LANGUAGE}
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


def module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def register_private_fonts() -> None:
    """Expose bundled fonts to this process only; never installs them system-wide."""
    if os.name != "nt":
        return
    for path in FONT_FILES.values():
        if path.exists():
            ctypes.windll.gdi32.AddFontResourceExW(str(path), 0x10, 0)


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


LIGHT = {"bg": "#f6f7fb", "card": "#ffffff", "text": "#182131", "muted": "#667085", "line": "#d9deea"}
DARK = {"bg": "#10151f", "card": "#1b2330", "text": "#f3f6fb", "muted": "#aeb8c8", "line": "#334054"}
CASSETTE_DESKTOP = {
    "bg": SOUNDWAVE_PALETTE["background_primary"], "card": SOUNDWAVE_PALETTE["background_secondary"],
    "text": SOUNDWAVE_PALETTE["text_primary"], "muted": SOUNDWAVE_PALETTE["text_muted"],
    "line": SOUNDWAVE_PALETTE["border_primary"],
}


class PanelFrameRenderer:
    """The single 320×480 renderer used by both preview and physical display."""
    def __init__(self, theme: dict[str, str], accent: str, use_custom_fonts: bool, font_scale: float = 1.0, layout: dict | None = None, monitor_style: str = "cards", visual_theme: str = THEME_REBEL, language: str = DEFAULT_LANGUAGE) -> None:
        from PIL import Image, ImageDraw, ImageFont
        self.Image = Image
        self.Draw = ImageDraw
        self.ImageFont = ImageFont
        self.theme, self.accent, self.use_custom_fonts = theme, accent, use_custom_fonts
        self.font_scale, self.layout, self.monitor_style, self.visual_theme = font_scale, layout or LayoutStore.default, monitor_style, visual_theme
        self.language = normalize_language(language)

    def tr(self, key: str, **values: object) -> str:
        instance_state = object.__getattribute__(self, "__dict__")
        language = instance_state.get("language", "pt-BR")
        return translate(language, key, **values)

    def font(self, role: str, size: int):
        font_dir = Path(os.getenv("WINDIR", r"C:\Windows")) / "Fonts"
        fallback_names = {
            "ru": ("arial.ttf", "segoeui.ttf"),
            "zh-CN": ("msyh.ttc", "simhei.ttf", "simsun.ttc"),
        }.get(self.language, ())
        for name in fallback_names:
            path = font_dir / name
            if path.exists():
                try:
                    return self.ImageFont.truetype(str(path), max(10, int(size * self.font_scale)))
                except OSError:
                    continue
        if self.use_custom_fonts:
            try:
                return self.ImageFont.truetype(str(FONT_FILES[role]), max(10, int(size * self.font_scale)))
            except OSError:
                pass
        return self.ImageFont.load_default()

    def text(self, draw, xy: tuple[int, int], value: str, role: str, size: int, color: str, anchor: str = "la") -> None:
        draw.text(xy, value, fill=color, font=self.font(role, size), anchor=anchor)

    def text_item(self, draw, key: str, xy, value: str, role: str, size: int, color: str, anchor: str = "la") -> None:
        scale = float(self.layout.get(key, {}).get("font_scale", 1.0))
        draw.text(xy, value, fill=self.layout.get(key, {}).get("text_color", color), font=self.font(role, max(8, int(size * scale))), anchor=anchor)

    @staticmethod
    def time_label(value: int) -> str:
        return f"{value // 60}:{value % 60:02d}"

    def render(self, page: int, metrics: Metrics, track: Track, *args, history: list[int] | None = None, network: tuple[float, float] = (0.0, 0.0), processes: list[ProcessRow] | None = None) -> object:
        """Render current UI; accepts the retired lyrics argument from old callers."""
        if len(args) == 4:  # legacy: lyrics, alert, label, art
            _, alert, media_label, album_art = args
        else:
            alert, media_label, album_art = args
        image = self.Image.new("RGB", (320, 480), self.theme["bg"])
        self.current_image = image
        draw = self.Draw.Draw(image)
        if self.visual_theme == THEME_CASSETTE:
            image.paste(SOUNDWAVE_PALETTE["background_primary"], (0, 0, 320, 480))
            if page == 0:
                self._cassette_monitor(draw, metrics, history or [])
            elif page == 2:
                self._processes(draw, processes or [], cassette=True)
            else:
                self._cassette_player(draw, track, media_label, album_art)
            return image
        if self.visual_theme == THEME_TECHNICAL:
            image.paste("#101315", (0, 0, 320, 480))
            if page == 0:
                self._technical_monitor(draw, metrics, history or [])
            elif page == 2:
                self._processes(draw, processes or [], technical=True)
            else:
                self._technical_player(draw, track, media_label, album_art)
            return image
        if self.visual_theme == THEME_REBEL:
            image.paste("#16191a", (0, 0, 320, 480))
            if page == 0:
                self._rebel_monitor(draw, metrics, history or [], alert, network)
            elif page == 2:
                self._processes(draw, processes or [], technical=False)
            else:
                self._rebel_player(draw, track, media_label, album_art)
            return image
        if page == 0:
            self._monitor(draw, metrics, history or [])
        elif page == 2:
            self._processes(draw, processes or [], technical=False)
        else:
            self._spotify(draw, track, media_label, album_art)
        if alert:
            draw.rectangle((0, 446, 319, 479), fill="#ef5350")
            self.text(draw, (160, 463), alert, "metric", 9, "#111111", "mm")
        return image

    def _processes(self, draw, processes: list[ProcessRow], technical: bool = False, cassette: bool = False) -> None:
        if cassette:
            cyan, cream, muted = self._cassette_frame(draw, self.tr("screen.processes"))
        elif technical:
            cyan, cream, muted = "#52c7d8", "#e5edf6", "#8493a5"
        else:
            cyan, cream, muted = self._rebel_frame(draw, self.tr("screen.processes"))
        if technical:
            self.text(draw, (18, 18), "REBSCREEN // " + self.tr("screen.processes"), "aux", 10, cream)
            draw.line((18, 48, 302, 48), fill=cyan)
        self.text(draw, (20, 62), self.tr("screen.top_processes"), "aux", 8, cyan)
        if not processes:
            self.text(draw, (160, 230), self.tr("screen.collecting"), "aux", 11, muted, "mm")
            return
        for index, row in enumerate(processes[:10]):
            y = 83 + index * 35
            row_fill = "#202829" if not technical else "#182126"
            row_outline = "#36484b"
            if cassette:
                row_fill, row_outline = SOUNDWAVE_PALETTE["background_secondary"], SOUNDWAVE_PALETTE["border_primary"]
            draw.rectangle((18, y, 302, y + 29), fill=row_fill, outline=row_outline)
            self.text(draw, (25, y + 8), row.name[:17], "aux", 9, cream)
            self.text(draw, (181, y + 8), f"{row.cpu:.0f}%", "aux", 8, cyan, "ra")
            self.text(draw, (221, y + 8), f"{row.memory_percent:.0f}%", "aux", 8, cream, "ra")
            self.text(draw, (260, y + 8), f"{row.disk_percent:.0f}%", "aux", 8, cream, "ra")
            network = "—" if row.network_kbps is None else (f"{row.network_kbps / 1024:.1f}M" if row.network_kbps >= 1024 else f"{row.network_kbps:.0f}K")
            self.text(draw, (296, y + 8), network, "aux", 8, muted, "ra")
        self.text(draw, (20, 445), self.tr("screen.process_order"), "aux", 8, muted)

    def _rebel_frame(self, draw, title: str):
        cyan, cream, muted = "#73aeb1", "#f2d98a", "#718082"
        clock, date = header_state()
        draw.rounded_rectangle((8, 8, 312, 472), radius=7, fill="#1d2223", outline="#3b4749", width=3)
        draw.line((18, 48, 302, 48), fill=cyan, width=1)
        self.text(draw, (20, 21), "REBSCREEN // " + title, "aux", 10, cream)
        self.text(draw, (300, 18), clock, "metric", 15, cream, "ra")
        self.text(draw, (300, 36), date, "aux", 8, muted, "ra")
        return cyan, cream, muted

    def _cassette_frame(self, draw, title: str):
        palette = SOUNDWAVE_PALETTE
        amber, cream, muted = palette["amber_primary"], palette["silver_primary"], palette["text_secondary"]
        clock, date = header_state()
        draw.rounded_rectangle((8, 8, 312, 472), radius=4, fill=palette["background_secondary"], outline=palette["blue_secondary"], width=2)
        for x, y in ((16, 16), (304, 16), (16, 464), (304, 464)):
            draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=palette["silver_primary"])
        draw.rectangle((18, 18, 43, 29), fill=palette["background_inset"], outline=palette["border_highlight"])
        draw.ellipse((22, 21, 28, 27), fill=palette["blue_light"])
        self.text(draw, (32, 20), "ON", "aux", 6, cream)
        self.text(draw, (52, 19), "REBSCREEN // " + title, "aux", 9, cream)
        self.text(draw, (300, 16), clock, "metric", 14, amber, "ra")
        self.text(draw, (300, 34), date, "aux", 7, muted, "ra")
        draw.line((18, 49, 302, 49), fill=palette["border_primary"], width=1)
        for index in range(10):
            x = 20 + index * 28
            color = palette["red_visor"] if index == 9 else (palette["blue_accent"] if index in (0, 1) else palette["border_subtle"])
            draw.line((x, 51, x + 12, 51), fill=color, width=2)
        return amber, cream, muted

    def _cassette_monitor(self, draw, metrics: Metrics, history: list[int]) -> None:
        palette = SOUNDWAVE_PALETTE
        amber, cream, muted = self._cassette_frame(draw, self.tr("screen.monitor"))
        self.text(draw, (20, 60), self.tr("screen.demo_notice", items="/".join(sorted(metrics.demo_components))) if metrics.demo_components else self.tr("screen.stable"), "aux", 7, amber)
        rows = (
            ("metric.cpu", metrics.cpu_usage, metrics.cpu_temperature),
            ("metric.gpu", metrics.gpu_usage, metrics.gpu_temperature),
        )
        for index, (label_key, usage, temperature) in enumerate(rows):
            top = 78 + index * 57
            draw.rectangle((18, top, 302, top + 49), fill=palette["background_secondary"], outline=palette["border_primary"])
            self.text(draw, (28, top + 8), self.tr(label_key), "aux", 10, cream)
            self.text(draw, (288, top + 5), f"{usage:02d}%", "metric", 20, amber, "ra")
            self.text(draw, (28, top + 27), f"{temperature} °C", "aux", 9, muted)
            self._segmented(draw, 112, top + 31, 166, usage, palette["blue_accent"], palette["background_inactive"])
            for tick in range(0, 101, 20):
                x = 112 + int(166 * tick / 100)
                draw.line((x, top + 41, x, top + 45), fill=palette["steel_dark"])
        draw.rectangle((18, 194, 302, 232), fill=palette["background_secondary"], outline=palette["border_primary"])
        self.text(draw, (28, 202), self.tr("metric.ram"), "aux", 9, cream)
        self.text(draw, (288, 198), f"{metrics.ram_usage:02d}%", "metric", 17, amber, "ra")
        self._segmented(draw, 28, 222, 258, metrics.ram_usage, palette["amber_primary"], palette["background_inactive"])
        self.text(draw, (20, 242), self.tr("screen.disk_usage_temp"), "aux", 7, amber)
        disks = metrics.disks[:4]
        for index, disk in enumerate(disks):
            x = 18 + (index % 2) * 144
            y = 256 + (index // 2) * 35
            draw.rectangle((x, y, x + 138, y + 30), fill=palette["background_secondary"], outline=palette["border_primary"])
            self.text(draw, (x + 6, y + 4), disk.name[:12], "aux", 7, cream)
            usage = f"{disk.usage}%" if disk.usage is not None else self.tr("screen.not_available")
            temperature = f"{disk.temperature}°" if disk.temperature is not None else "--"
            self.text(draw, (x + 132, y + 4), usage, "aux", 7, amber, "ra")
            self.text(draw, (x + 6, y + 17), ",".join(disk.units) or self.tr("screen.no_volume"), "aux", 6, muted)
            self.text(draw, (x + 132, y + 17), temperature, "aux", 7, cream, "ra")
        if not disks:
            self.text(draw, (160, 280), self.tr("screen.no_disks"), "aux", 8, muted, "mm")
        draw.rectangle((18, 332, 302, 414), fill=palette["background_primary"], outline=palette["border_primary"])
        self.text(draw, (25, 337), self.tr("screen.cpu_history"), "aux", 7, amber)
        values = (history or [metrics.cpu_usage])[-30:]
        values = [value.get("usage", metrics.cpu_usage) if isinstance(value, dict) else value for value in values]
        if len(values) == 1:
            values *= 2
        points = [(22 + i * 274 / (len(values) - 1), 405 - max(0, min(100, value)) * 54 / 100) for i, value in enumerate(values)]
        draw.line(points, fill=palette["blue_light"], width=2)
        self.text(draw, (20, 425), self.tr("screen.last_60"), "aux", 7, muted)
        self.text(draw, (300, 425), self.tr("screen.now"), "aux", 7, muted, "ra")
        self.text(draw, (20, 447), self.tr("screen.stable"), "aux", 7, cream)

    def _cassette_player(self, draw, track: Track, media_label: str, album_art=None) -> None:
        palette = SOUNDWAVE_PALETTE
        amber, cream, muted = self._cassette_frame(draw, self.tr("screen.player"))
        draw.rounded_rectangle((28, 64, 292, 246), radius=5, fill=palette["cassette_body"], outline=palette["cassette_border"], width=2)
        draw.rectangle((39, 75, 281, 139), fill=palette["cassette_window"], outline=palette["cassette_window_border"])
        if album_art is not None:
            art = album_art.resize((112, 58), self.Image.Resampling.LANCZOS)
            self.current_image.paste(art, (151, 79))
        else:
            self.text(draw, (160, 104), self.tr("screen.no_cover"), "aux", 9, cream, "mm")
        self.text(draw, (48, 84), track.title[:19], "aux", 8, cream)
        self.text(draw, (48, 101), track.artist[:19], "aux", 7, muted)
        self.text(draw, (48, 122), media_label[:18], "aux", 6, amber)
        for center_x in (91, 229):
            draw.ellipse((center_x - 28, 155, center_x + 28, 211), fill=palette["background_inactive"], outline=palette["steel_dark"], width=2)
            draw.ellipse((center_x - 8, 175, center_x + 8, 191), fill=palette["silver_primary"], outline=palette["cassette_body_shadow"])
            for spoke in range(8):
                angle_x = center_x + int(20 * __import__("math").cos(spoke * 0.785398))
                angle_y = 183 + int(20 * __import__("math").sin(spoke * 0.785398))
                draw.ellipse((angle_x - 2, angle_y - 2, angle_x + 2, angle_y + 2), fill=amber)
        draw.line((105, 183, 215, 183), fill=palette["steel_dark"], width=2)
        for index, color in enumerate((palette["red_visor"], palette["amber_primary"], palette["blue_primary"], palette["silver_secondary"], palette["red_visor"])):
            left = 52 + index * 44
            draw.rectangle((left, 220, left + 26, 230), fill=color, outline=palette["border_primary"])
        draw.rectangle((24, 272, 296, 397), fill=palette["background_secondary"], outline=palette["border_primary"])
        self.text(draw, (160, 286), track.title[:25], "title", 18, cream, "ma")
        self.text(draw, (160, 314), track.artist[:28], "aux", 10, muted, "ma")
        self.text(draw, (160, 338), media_label[:28], "aux", 8, amber, "ma")
        self._segmented(draw, 34, 365, 252, int(100 * track.elapsed / max(1, track.duration)), palette["blue_accent"], palette["background_inactive"])
        self.text(draw, (34, 379), self.time_label(track.elapsed), "aux", 8, muted)
        self.text(draw, (286, 379), self.time_label(track.duration), "aux", 8, muted, "ra")
        self.text(draw, (24, 426), self.tr("screen.signal") + "  ●", "aux", 8, palette["blue_light"])
        self.text(draw, (160, 426), self.tr("screen.link") + "  ●", "aux", 8, amber, "ma")
        self.text(draw, (296, 426), "CASSETTE", "aux", 7, cream, "ra")

    def _segmented(self, draw, x: int, y: int, width: int, percent: int, color: str, inactive: str = "#323b3c"):
        for index in range(10):
            left = x + index * (width // 10 + 2)
            draw.rectangle((left, y, left + width // 10 - 2, y + 6), fill=color if index < percent / 10 else inactive)

    def _rebel_monitor(self, draw, metrics: Metrics, history: list[int], alert: str, network: tuple[float, float]) -> None:
        cyan, cream, muted = self._rebel_frame(draw, self.tr("screen.monitor"))
        if metrics.demo_components:
            items = "/".join(sorted(metrics.demo_components))
            self.text(draw, (300, 54), self.tr("screen.demo_notice", items=items), "aux", 6, muted, "ra")
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
        self.text(draw, (286,178), self.tr("screen.ram_in_use"), "aux", 8, muted, "ra")
        self._segmented(draw, 31, 202, 255, metrics.ram_usage, "#d5a94c")
        self.text(draw, (20,232), self.tr("screen.disk_usage_temp"), "aux", 8, cyan)
        self._disk_blocks(draw, metrics.disks[:6], 20, 246, 300, 326, cyan, cream, muted)
        points=(history or [{"usage": metrics.cpu_usage, "temperature": None}])[-30:]
        if not isinstance(points[0], dict): points=[{"usage": value, "temperature": None, "disk_temperature": None} for value in points]
        points=points*2 if len(points)==1 else points
        draw.rectangle((20,337,300,420), outline="#3c5557")
        draw.line([(20+i*280/(len(points)-1),412-max(0,min(100,p["usage"]))*62/100) for i,p in enumerate(points)], fill=cyan, width=2)
        temps=[p["temperature"] for p in points]
        if any(value is not None for value in temps):
            draw.line([(20+i*280/(len(points)-1),412-max(0,min(100,p["temperature"] or 0))*62/100) for i,p in enumerate(points)], fill="#f2d98a", width=2)
        disk_temps=[p.get("disk_temperature") for p in points]
        if any(value is not None for value in disk_temps):
            draw.line([(20+i*280/(len(points)-1),412-max(0,min(100,p.get("disk_temperature") or 0))*62/100) for i,p in enumerate(points)], fill="#d98ad5", width=1)
        self.text(draw,(24,342),self.tr("screen.history_labels"), "aux",7,muted)
        self.text(draw,(22,426),self.tr("screen.download") + " " + rate_label(network[0]), "aux",9,"#80ba82")
        self.text(draw,(150,426),self.tr("screen.upload") + " " + rate_label(network[1]), "aux",9,"#d5a94c")
        draw.rectangle((20,444,300,460), fill="#572f32" if alert else "#293032")
        self.text(draw,(28,447), alert[:40] if alert else self.tr("screen.stable"), "aux",8,"#f0abb0" if alert else muted)

    def _disk_blocks(self, draw, disks: list[Disk], left: int, top: int, right: int, bottom: int, cyan: str, cream: str, muted: str) -> None:
        """Draw one adaptive, self-contained history card for each physical disk."""
        disks = disks[:6]
        if not disks:
            self.text(draw, ((left + right) // 2, (top + bottom) // 2), self.tr("screen.no_disks"), "aux", 9, muted, "mm")
            return
        count = len(disks)
        columns = 1 if count == 1 else 2 if count in (2, 4) else 3
        rows = 1 if count <= 3 else 2
        gap = 4
        width = (right - left - gap * (columns - 1)) // columns
        height = (bottom - top - gap * (rows - 1)) // rows
        for index, disk in enumerate(disks):
            col, row = index % columns, index // columns
            x, y = left + col * (width + gap), top + row * (height + gap)
            draw.rectangle((x, y, x + width, y + height), fill="#202829", outline="#465b5d")
            font = 8 if columns == 1 else 7 if columns == 2 else 6
            name = disk.name[:20 if columns == 1 else 12 if columns == 2 else 9]
            unit = ",".join(disk.units) if disk.units else self.tr("screen.no_volume")
            usage = f"{disk.usage}%" if disk.usage is not None else "—"
            temp = f"{disk.temperature}°" if disk.temperature is not None else "—"
            # Labels sit on the card's solid upper band, so graphs never make
            # the drive name, letter or usage hard to read.
            self.text(draw, (x + 4, y + 3), name, "aux", font, cream)
            self.text(draw, (x + width - 4, y + 3), usage, "aux", font, cyan, "ra")
            self.text(draw, (x + 4, y + 12), unit, "aux", max(5, font - 1), muted)
            self.text(draw, (x + width - 4, y + 12), temp, "aux", max(5, font - 1), cream, "ra")
            graph_top, graph_bottom = y + min(23, height - 10), y + height - 4
            usage_history = disk.usage_history or ([disk.usage] if disk.usage is not None else [0])
            temp_history = disk.temperature_history or ([disk.temperature] if disk.temperature is not None else [])
            if len(usage_history) == 1:
                usage_history = usage_history * 2
            if graph_bottom > graph_top:
                points = [(x + 3 + i * (width - 6) / (len(usage_history) - 1), graph_bottom - max(0, min(100, value or 0)) * (graph_bottom - graph_top) / 100) for i, value in enumerate(usage_history)]
                draw.line(points, fill=cyan, width=1)
                usable_temps = [value for value in temp_history if value is not None]
                if len(usable_temps) >= 2:
                    values = temp_history[-len(usage_history):]
                    if len(values) == 1:
                        values *= 2
                    temp_points = [(x + 3 + i * (width - 6) / (len(values) - 1), graph_bottom - max(0, min(100, value or 0)) * (graph_bottom - graph_top) / 100) for i, value in enumerate(values)]
                    draw.line(temp_points, fill=cream, width=1)

    def _rebel_player(self, draw, track: Track, media_label: str, album_art=None) -> None:
        cyan, cream, muted = self._rebel_frame(draw, self.tr("screen.player"))
        x,y,size=66,68,188
        draw.ellipse((x-8,y-8,x+size+8,y+size+8),outline="#3d5557",width=2)
        draw.line((160,y-16,160,y+size+16),fill=cyan); draw.line((x-16,y+size//2,x+size+16,y+size//2),fill=cyan)
        if album_art is not None:
            art=album_art.resize((size,size),self.Image.Resampling.LANCZOS); mask=self.Image.new("L",(size,size),0); self.Draw.Draw(mask).ellipse((0,0,size-1,size-1),fill=255); self.current_image.paste(art,(x,y),mask)
        else:
            draw.ellipse((x,y,x+size,y+size),fill="#252d2e",outline=cream,width=2); self.text(draw,(160,157),self.tr("screen.no_cover"),"aux",10,muted,"ma")
        self.text(draw,(160,283),track.title[:28],"title",25,cream,"ma")
        self.text(draw,(160,315),track.artist[:32],"aux",14,muted,"ma")
        self.text(draw,(160,340),media_label[:34],"aux",10,cyan,"ma")
        self._segmented(draw,26,373,268,int(100*track.elapsed/max(1,track.duration)),cyan)
        self.text(draw,(26,391),self.time_label(track.elapsed),"aux",9,muted); self.text(draw,(294,391),self.time_label(track.duration),"aux",9,muted,"ra")
        self.text(draw,(22,432),self.tr("screen.signal") + "  ●", "aux",9,"#80ba82"); self.text(draw,(104,432),self.tr("screen.link") + "  ●", "aux",9,"#d5a94c")
        self.text(draw,(294,432),"REBEL", "aux",9,cream,"ra")

    def _technical_monitor(self, draw, metrics: Metrics, history: list[int]) -> None:
        cyan, white, muted, amber, green = "#14d7e8", "#f4f7f8", "#8fa3a8", "#f5b63d", "#65d47d"
        clock, date = header_state()
        draw.rounded_rectangle((10, 10, 310, 470), radius=13, outline=cyan, width=2)
        self.text(draw, (22, 22), "REBSCREEN | " + self.tr("screen.monitor"), "aux", 10, cyan)
        self.text(draw, (298, 20), clock, "metric", 16, white, "ra")
        self.text(draw, (298, 39), date, "aux", 8, muted, "ra")
        if metrics.demo_components:
            items = "/".join(sorted(metrics.demo_components))
            self.text(draw, (22, 39), self.tr("screen.demo_notice", items=items), "aux", 7, muted)
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
        self.text(draw, (22, 207), self.tr("screen.disk_health") + "      " + self.tr("screen.temperature"), "aux", 9, cyan)
        for index, disk in enumerate(metrics.disks[:2]):
            y = 226 + index * 28
            self.text(draw, (22, y), disk.name[:17], "aux", 11, white)
            label = disk_label(vars(disk))
            self.text(draw, (298, y), label[:24], "aux", 9, green if disk.temperature is not None else muted, "ra")
        top, bottom, left, right = 300, 422, 22, 298
        draw.rounded_rectangle((left, top, right, bottom), radius=8, outline="#2e5155", width=1)
        self.text(draw, (left, 280), self.tr("screen.cpu_history"), "aux", 10, cyan)
        values = (history or [metrics.cpu_usage])[-60:]
        values = [value.get("usage", metrics.cpu_usage) if isinstance(value, dict) else value for value in values]
        if len(values) == 1: values = values * 2
        points = [(left + i * (right-left)/(len(values)-1), bottom-12-max(0,min(100,v))*(bottom-top-24)/100) for i,v in enumerate(values)]
        draw.line(points, fill=cyan, width=3)
        self.text(draw, (left, 434), self.tr("screen.last_60"), "aux", 9, muted)
        self.text(draw, (right, 434), self.tr("screen.now"), "aux", 9, muted, "ra")
        draw.rounded_rectangle((22, 443, 298, 462), radius=5, fill="#4a282c")
        self.text(draw, (30, 448), self.tr("screen.alert_monitoring"), "aux", 9, "#ed9ba2")

    def _technical_player(self, draw, track: Track, media_label: str, album_art=None) -> None:
        cyan, white, muted = "#14d7e8", "#f4f7f8", "#8fa3a8"
        clock, date = header_state()
        draw.rounded_rectangle((10, 10, 310, 470), radius=13, outline=cyan, width=2)
        self.text(draw, (22, 22), "REBSCREEN | " + self.tr("screen.player"), "aux", 10, cyan)
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
            self.text(draw, (160, 151), self.tr("screen.no_cover"), "aux", 11, muted, "ma")
        draw.ellipse((x,y,x+size,y+size), outline=cyan, width=2)
        self.text(draw, (160, 263), track.title[:28], "title", 25, white, "ma")
        self.text(draw, (160, 295), track.artist[:32], "aux", 14, muted, "ma")
        kind = draw_source_icon(draw, (78, 316), media_label)
        self.text(draw, (98, 323), media_label[:28] if kind != "unknown" else self.tr("screen.source_unknown"), "aux", 10, cyan if kind != "unknown" else muted, "la")
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
        self.text(draw, (18, 16), self.tr("screen.monitor_pc"), "title", 20, t["text"])
        self.text(draw, (18, 42), self.tr("screen.demo_data"), "aux", 11, t["muted"])
        cards = [(self.layout["cpu"]["y"], self.layout["cpu"]["h"], "CPU", f"{metrics.cpu_usage}%", f"{metrics.cpu_temperature} C"),
                 (self.layout["gpu"]["y"], self.layout["gpu"]["h"], "GPU", f"{metrics.gpu_usage}%", f"{metrics.gpu_temperature} C"),
                 (self.layout["ram"]["y"], self.layout["ram"]["h"], "MEMORIA", f"{metrics.ram_usage}%", "RAM em uso")]
        for y, height, title, value, sub in cards:
            draw.rectangle((18, y, 302, y + height), fill=t["card"], outline=t["line"])
            self.text(draw, (30, y + 10), title, "aux", 11, t["muted"])
            self.text(draw, (30, y + 31), value, "metric", 28, self.accent)
            self.text(draw, (168, y + 38), sub, "aux", 13, t["muted"])
        self.text(draw, (18, 335), self.tr("screen.storage"), "aux", 11, t["muted"])
        for index, disk in enumerate(metrics.disks):
            y = self.layout["disks"]["y"] + index * (self.layout["disks"]["h"] + 6)
            draw.rectangle((18, y, 302, y + self.layout["disks"]["h"]), fill=t["card"], outline=t["line"])
            self.text(draw, (28, y + 8), disk.name, "aux", 11, t["text"])
            self.text(draw, (292, y + 8), disk_label(vars(disk)), "aux", 9, t["muted"], "ra")
        self.text(draw, (18, 426), self.tr("screen.next_page_hint"), "aux", 9, t["muted"])

    def _monitor_graph(self, draw, metrics: Metrics, history: list[int]) -> None:
        """Compact vertical telemetry inspired by the supplied reference."""
        t = self.theme
        self.text(draw, (18, 18), self.tr("screen.telemetry"), "title", 20, t["text"])
        rows = (("CPU", f"{metrics.cpu_usage}%", f"{metrics.cpu_temperature} °C"),
                ("GPU", f"{metrics.gpu_usage}%", f"{metrics.gpu_temperature} °C"),
                ("RAM", f"{metrics.ram_usage}%", "uso da memória"))
        for index, (label, value, sub) in enumerate(rows):
            y = 62 + index * 48
            draw.rectangle((18, y, 302, y + 40), fill=t["card"], outline=t["line"])
            self.text(draw, (30, y + 9), label, "aux", 13, t["muted"])
            self.text(draw, (132, y + 7), value, "metric", 24, self.accent)
            self.text(draw, (224, y + 13), sub, "aux", 10, t["muted"], "ma")
        self.text(draw, (18, 224), self.tr("screen.cpu_history"), "aux", 11, t["muted"])
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
        self.text(draw, (left, 418), self.tr("screen.last_60"), "aux", 10, t["muted"])
        self.text(draw, (right, 418), self.tr("screen.now"), "aux", 10, t["muted"], "ra")

    def _spotify(self, draw, track: Track, media_label: str, album_art=None) -> None:
        t = self.theme
        p = self.layout
        no_media = media_label == self.tr("media.none_label")
        self.text(draw, (160, 18), self.tr("screen.no_media") if no_media else self.tr("screen.playing_now"), "title", 20, t["text"], "ma")
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
            self.text(draw, (center, art_y + art_size // 2 + 28), self.tr("screen.no_cover"), "aux", 10, "#e7eaf2", "ma")
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
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.minsize(980, 640)
        self.settings = SettingsStore()
        self.language = normalize_language(self.settings.data.get("language", DEFAULT_LANGUAGE))
        self.settings.data["language"] = self.language
        self.geometry(self.settings.data["geometry"])
        self.metrics_provider = SampleMetricsProvider()
        self.spotify_provider = SpotifyDemoProvider()
        self.media_provider = WindowsMediaProvider()
        self._serial_support_available = module_available("serial")
        self._process_support_available = module_available("psutil")
        self._tray_support_available = module_available("pystray")
        self.layout_store = LayoutStore()
        self.process_sampler = ProcessSampler()
        self.runtime_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="rebscreen-runtime")
        self.metrics_task = LatestTask(self.runtime_executor)
        self.process_task = LatestTask(self.runtime_executor)
        self.network_task = LatestTask(self.runtime_executor)
        self.serial_task = LatestTask(self.runtime_executor)
        self.processes: list[ProcessRow] = []
        self.page = 0
        self.dark = bool(self.settings.data["dark"])
        self.accent = self.settings.data["accent"]
        self.custom_fonts_enabled = bool(self.settings.data["custom_fonts"])
        self.font_scale = float(self.settings.data["font_scale"])
        # Older preference files may contain this value.  Navigation is now
        # always manual, so refreshes cannot take the user away from a page.
        self.auto_switch_media = False
        # Automatic USB writes require an explicit choice. This also prevents
        # old preferences from enabling a high-bandwidth loop unexpectedly.
        self.auto_send_enabled = initial_auto_send(self.settings.data, bool(os.getenv("REBSCREEN_SAFE_START")))
        self.preview_orientation = self.settings.data.get("orientation", "vertical")
        self.layout_store.activate(self.preview_orientation)
        self.edit_layout = False
        self.layout_selection = None
        self.layout_drag_origin = None
        self.send_interval = send_interval(self.settings.data.get("send_interval", MINIMUM_SEND_INTERVAL))
        self.last_auto_send = 0.0
        self.incremental_sender = IncrementalFrameSender(self.settings.data.get("port", "COM3"))
        self.rotation_enabled = bool(self.settings.data.get("rotation_enabled", False))
        self.rotation_interval = max(2.0, float(self.settings.data.get("rotation_interval", 10)))
        self.rotation_pages = normalize_rotation_pages(self.settings.data.get("rotation_pages", [True, True, True]))
        self.last_page_change = time.monotonic()
        self.preview_brightness = int(self.settings.data.get("preview_brightness", 100))
        self.monitor_style = self.settings.data.get("monitor_style", "cards")
        self.visual_theme = self.settings.data.get("visual_theme", THEME_REBEL)
        if self.visual_theme not in available_themes():
            self.visual_theme = THEME_REBEL
        self.media_label = self.tr("screen.demo_data_short")
        self.album_art = None
        self.limits = self.settings.data.get("limits", {"CPU": 85, "GPU": 82, "Discos": 60, "RAM": 90})
        self.limits.setdefault("RAM", 90)
        self.enabled = self.settings.data.get("enabled", {"CPU": True, "GPU": True, "Discos": True, "RAM": True})
        self.enabled.setdefault("RAM", True)
        self.alerts: list[str] = []
        self.alert_cycle = cycle([""])
        self.current_alert = ""
        # Start with a neutral frame. Slow sensors are requested after Tk is
        # ready, so opening the window never waits on PowerShell or LHM.
        self.last_metrics = Metrics(0, 0, 0, 0, 0, [])
        self.cpu_history: list[int] = [self.last_metrics.cpu_usage]
        self.telemetry_history: list[dict] = [aggregate_point(self.last_metrics.cpu_usage, self.last_metrics.gpu_usage, self.last_metrics.ram_usage, [self.last_metrics.cpu_temperature, self.last_metrics.gpu_temperature], [disk.temperature for disk in self.last_metrics.disks])]
        self.network_rates = NetworkRates()
        self.rx_rate, self.tx_rate = 0.0, 0.0
        self.preview_static_frame = None
        self.track = Track(self.tr("screen.no_media"), self.tr("media.start_player"), 0, 1)
        self._dependency_issue_snapshot: tuple[str, ...] | None = None
        self.media_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="telinha-media")
        self.media_future = None
        self.media_query_started = 0.0
        self.media_query_timed_out = False
        self.last_media_key: tuple[object, ...] | None = None
        self.last_metrics_update = 0.0
        self.last_metrics_request = 0.0
        self.tray_icon = None
        self.protocol("WM_DELETE_WINDOW", self.on_main_window_close)
        self._build_ui()
        self._draw_initial_preview()
        self.single_instance.listen(lambda: self.after(0, self.show_from_tray))
        self.bind_all("<Control-Key-1>", lambda _event: self.set_page(0))
        self.bind_all("<Control-Key-2>", lambda _event: self.set_page(1))
        self.start_tray()
        self.refresh()

    @property
    def theme(self) -> dict[str, str]:
        if self.visual_theme == THEME_CASSETTE:
            return CASSETTE_DESKTOP
        return DARK if self.dark else LIGHT

    def font_tuple(self, role: str, size: int, bold: bool = False) -> tuple:
        if self.language == "ru":
            family = "Arial"
        elif self.language == "zh-CN":
            family = "Microsoft YaHei UI"
        else:
            family = CUSTOM_FONT_FAMILIES[role] if self.custom_fonts_enabled else "Segoe UI"
        return (family, size, "bold" if bold else "normal")

    def tr(self, key: str, **values: object) -> str:
        instance_state = object.__getattribute__(self, "__dict__")
        language = instance_state.get("language", "pt-BR")
        return translate(language, key, **values)

    def _build_ui(self) -> None:
        self.configure(bg=self.theme["bg"])
        style = ttk.Style(self)
        if self.visual_theme == THEME_CASSETTE:
            style.theme_use("clam")
            style.configure("TButton", background="#354035", foreground="#e2ddca", bordercolor="#879078", padding=(8, 5))
            style.map("TButton", background=[("active", "#4b5543"), ("pressed", "#28312a")], foreground=[("disabled", "#a7ad9f")])
            style.configure("TNotebook", background=CASSETTE_DESKTOP["bg"], bordercolor=CASSETTE_DESKTOP["line"])
            style.configure("TNotebook.Tab", background="#28312a", foreground=CASSETTE_DESKTOP["muted"], padding=(9, 5))
            style.map("TNotebook.Tab", background=[("selected", "#45513e")], foreground=[("selected", CASSETTE_DESKTOP["text"])])
            style.configure("TCombobox", fieldbackground="#222c27", background="#354035", foreground=CASSETTE_DESKTOP["text"], arrowcolor="#f0b34b")
        else:
            windows_theme = "vista" if "vista" in style.theme_names() else "clam"
            style.theme_use(windows_theme)
        root = tk.Frame(self, bg=self.theme["bg"], padx=16, pady=14)
        root.pack(fill="both", expand=True)
        main = tk.Frame(root, bg=self.theme["bg"]); main.pack(side="left", fill="both", expand=True)
        side = tk.Frame(root, bg=self.theme["card"], width=310, padx=12, pady=12); side.pack(side="right", fill="y", padx=(16, 0)); side.pack_propagate(False)
        tk.Label(main, text=APP_NAME, font=self.font_tuple("title", 20, True), bg=self.theme["bg"], fg=self.theme["text"]).pack(anchor="w")
        self.subtitle = tk.Label(main, text=self.tr("app.subtitle"), font=self.font_tuple("aux", 10), bg=self.theme["bg"], fg=self.theme["muted"]); self.subtitle.pack(anchor="w", pady=(2, 10))
        pages = tk.Frame(main, bg=self.theme["bg"]); pages.pack(anchor="w", pady=(0, 8))
        ttk.Button(pages, text=self.tr("page.monitor"), command=lambda: self.set_page(0)).pack(side="left")
        ttk.Button(pages, text=self.tr("page.player"), command=lambda: self.set_page(1)).pack(side="left", padx=6)
        ttk.Button(pages, text=self.tr("page.processes"), command=lambda: self.set_page(2)).pack(side="left", padx=6)
        self.page_label = tk.Label(pages, text="", bg=self.theme["bg"], fg=self.accent, font=self.font_tuple("aux", 10, True)); self.page_label.pack(side="left", padx=8)
        self.orientation_var = tk.StringVar(value=self.preview_orientation)
        tk.Label(pages, text=self.tr("orientation.label"), bg=self.theme["bg"], fg=self.theme["muted"]).pack(side="left", padx=(8, 2))
        for value, key in (("vertical", "orientation.vertical"), ("horizontal", "orientation.horizontal"), ("inverted", "orientation.inverted")):
            label = self.tr(key)
            tk.Radiobutton(pages, text=label, value=value, variable=self.orientation_var, command=self.set_orientation, bg=self.theme["bg"], fg=self.theme["text"], selectcolor=self.theme["card"]).pack(side="left", padx=2)
        width, height = canvas_dimensions(self.preview_orientation)
        self.canvas = tk.Canvas(main, width=width, height=height, highlightthickness=0, bg=self.theme["bg"]); self.canvas.pack(anchor="w")
        self.canvas.bind("<Button-1>", self.layout_pointer_down); self.canvas.bind("<B1-Motion>", self.layout_pointer_move); self.canvas.bind("<ButtonRelease-1>", self.layout_pointer_up)
        if self.visual_theme != THEME_CASSETTE:
            ttk.Button(main, text=self.tr("action.toggle_theme"), command=self.toggle_theme).pack(anchor="w", pady=(10, 0))
        ttk.Button(main, text=self.tr("action.save"), command=self.save_configuration).pack(anchor="w", pady=(5, 0))
        self.save_status = tk.Label(main, text="", bg=self.theme["bg"], fg="#3fae68", font=self.font_tuple("aux", 9)); self.save_status.pack(anchor="w")

        tabs = ttk.Notebook(side); tabs.pack(fill="both", expand=True)
        overview = tk.Frame(tabs, bg=self.theme["card"], padx=10, pady=10)
        appearance = tk.Frame(tabs, bg=self.theme["card"], padx=10, pady=10)
        alerts_tab = tk.Frame(tabs, bg=self.theme["card"], padx=10, pady=10)
        connection_tab = tk.Frame(tabs, bg=self.theme["card"], padx=10, pady=10)
        tabs.add(overview, text=self.tr("tab.overview")); tabs.add(appearance, text=self.tr("tab.appearance"))
        tabs.add(alerts_tab, text=self.tr("tab.alerts")); tabs.add(connection_tab, text=self.tr("tab.display"))
        tk.Label(overview, text=self.tr("state.title"), font=self.font_tuple("title", 15, True), bg=self.theme["card"], fg=self.theme["text"]).pack(anchor="w")
        self.hardware_status = tk.Label(overview, text=self.tr("state.display_checking"), wraplength=255, justify="left", bg=self.theme["card"], fg=self.theme["muted"]); self.hardware_status.pack(anchor="w", pady=(8, 0))
        self.sensor_status = tk.Label(overview, text=self.tr("state.sensor_checking"), wraplength=255, justify="left", bg=self.theme["card"], fg=self.theme["muted"]); self.sensor_status.pack(anchor="w", pady=(4, 0))
        self.media_status = tk.Label(overview, text=self.tr("state.media_checking"), wraplength=255, justify="left", bg=self.theme["card"], fg=self.theme["muted"]); self.media_status.pack(anchor="w", pady=(5, 0))
        self.media_diagnostics = tk.Label(overview, text=self.tr("media.diagnostics_heading") + "\n" + self.tr("media.no_windows_session"), wraplength=255, justify="left", bg=self.theme["card"], fg=self.theme["muted"]); self.media_diagnostics.pack(anchor="w", pady=(3, 0))
        self.dependency_help_button = ttk.Button(overview, text=self.tr("help.button"), command=self.open_dependency_help)
        self.dependency_help_button.pack_forget()
        tk.Label(overview, text=self.tr("state.display_auto"), wraplength=255, justify="left", bg=self.theme["card"], fg="#3fae68").pack(anchor="w", pady=(5, 14))
        tk.Label(appearance, text=self.tr("appearance.title"), font=self.font_tuple("title", 13, True), bg=self.theme["card"], fg=self.theme["text"]).pack(anchor="w")
        ttk.Button(appearance, text=self.tr("appearance.accent"), command=self.choose_accent).pack(anchor="w", pady=(8, 0))
        language_row = tk.Frame(appearance, bg=self.theme["card"])
        language_row.pack(fill="x", pady=(10, 0))
        tk.Label(language_row, text=self.tr("language.label"), bg=self.theme["card"], fg=self.theme["text"]).pack(anchor="w")
        self.language_var = tk.StringVar(value=LANGUAGE_NAMES[self.language])
        language_picker = ttk.Combobox(language_row, textvariable=self.language_var, state="readonly", values=tuple(LANGUAGE_NAMES.values()), width=20)
        language_picker.pack(anchor="w")
        language_picker.bind("<<ComboboxSelected>>", self.set_language)
        theme_row = tk.Frame(appearance, bg=self.theme["card"]); theme_row.pack(fill="x", pady=(10, 0))
        tk.Label(theme_row, text=self.tr("appearance.panel_theme"), bg=self.theme["card"], fg=self.theme["text"]).pack(anchor="w")
        self.theme_labels = {
            self.tr("theme.rebel"): THEME_REBEL,
            self.tr("theme.technical"): THEME_TECHNICAL,
            self.tr("theme.cassette"): THEME_CASSETTE,
        }
        self.visual_theme_var = tk.StringVar(value=next((label for label, theme_id in self.theme_labels.items() if theme_id == self.visual_theme), self.tr("theme.rebel")))
        ttk.Combobox(theme_row, textvariable=self.visual_theme_var, state="readonly", values=tuple(self.theme_labels), width=20).pack(anchor="w")
        ttk.Button(theme_row, text=self.tr("appearance.apply_theme"), command=self.apply_visual_theme).pack(anchor="w", pady=(3, 7))
        tk.Label(theme_row, text=self.tr("appearance.telemetry_style"), bg=self.theme["card"], fg=self.theme["text"]).pack(anchor="w")
        self.monitor_style_labels = {self.tr("appearance.cards"): "cards", self.tr("appearance.graph"): "graph"}
        current_style = next((label for label, style_id in self.monitor_style_labels.items() if style_id == self.monitor_style), self.tr("appearance.cards"))
        self.monitor_style_var = tk.StringVar(value=current_style)
        ttk.Combobox(theme_row, textvariable=self.monitor_style_var, state="readonly", values=tuple(self.monitor_style_labels), width=20).pack(anchor="w")
        ttk.Button(theme_row, text=self.tr("appearance.apply"), command=self.set_monitor_style).pack(anchor="w", pady=3)
        self.edit_layout_var = tk.BooleanVar(value=self.edit_layout)
        tk.Checkbutton(appearance, text=self.tr("layout.edit"), variable=self.edit_layout_var, command=self.toggle_layout_edit, bg=self.theme["card"], fg=self.theme["text"], selectcolor=self.theme["card"]).pack(anchor="w", pady=(14, 0))
        self.editor = tk.Frame(appearance, bg=self.theme["card"])
        self.layout_help = tk.Label(self.editor, text=self.tr("layout.instruction"), wraplength=275, justify="left", bg=self.theme["card"], fg=self.theme["muted"]); self.layout_help.pack(anchor="w", pady=(6, 0))
        self.font_choice = tk.BooleanVar(value=self.custom_fonts_enabled)
        tk.Checkbutton(self.editor, text=self.tr("fonts.custom"), variable=self.font_choice, command=self.toggle_font_set, bg=self.theme["card"], fg=self.theme["text"], selectcolor=self.theme["card"]).pack(anchor="w", pady=(5, 0))
        self.inspector = tk.Frame(self.editor, bg=self.theme["card"])
        self.inspector_label = tk.Label(self.inspector, text="", bg=self.theme["card"], fg=self.theme["text"]); self.inspector_label.pack(anchor="w")
        self.item_scale_var = tk.DoubleVar(value=1.0)
        tk.Label(self.inspector, text=self.tr("layout.font_size"), bg=self.theme["card"], fg=self.theme["text"]).pack(anchor="w", pady=(5, 0))
        tk.Scale(self.inspector, from_=0.7, to=1.8, resolution=0.1, orient="horizontal", variable=self.item_scale_var, command=lambda _value: self.set_selected_scale(), bg=self.theme["card"], fg=self.theme["text"], highlightthickness=0).pack(anchor="w")
        tk.Spinbox(self.inspector, from_=0.7, to=1.8, increment=0.1, width=5, textvariable=self.item_scale_var, command=self.set_selected_scale).pack(anchor="w", pady=3)
        for field, key in (("text_color", "color.text"), ("accent_color", "color.accent"), ("background_color", "color.background"), ("alert_color", "color.alert")):
            label = self.tr(key)
            ttk.Button(self.inspector, text=label, command=lambda key=field: self.choose_item_color(key)).pack(anchor="w", pady=1)
        ttk.Button(self.inspector, text=self.tr("color.transparent"), command=lambda: self.set_item_color("background_color", None)).pack(anchor="w", pady=1)
        ttk.Button(self.inspector, text=self.tr("color.reset"), command=self.reset_selected_colors).pack(anchor="w", pady=1)
        ttk.Button(self.inspector, text=self.tr("layout.reset"), command=self.reset_selected_item).pack(anchor="w")
        tk.Label(overview, text=self.tr("rotation.title"), font=self.font_tuple("title", 11, True), bg=self.theme["card"], fg=self.theme["muted"]).pack(anchor="w", pady=(16, 3))
        self.rotation_var = tk.BooleanVar(value=self.rotation_enabled)
        tk.Checkbutton(overview, text=self.tr("rotation.toggle"), variable=self.rotation_var, command=self.set_rotation, bg=self.theme["card"], fg=self.theme["text"], selectcolor=self.theme["card"]).pack(anchor="w")
        self.rotation_interval_var = tk.DoubleVar(value=self.rotation_interval)
        tk.Spinbox(overview, from_=2, to=120, increment=1, width=6, textvariable=self.rotation_interval_var, command=self.set_rotation).pack(anchor="w", pady=3)
        tk.Label(overview, text=self.tr("rotation.hint"), wraplength=255, justify="left", bg=self.theme["card"], fg=self.theme["muted"]).pack(anchor="w")
        tk.Label(alerts_tab, text=self.tr("alerts.title"), font=self.font_tuple("title", 13, True), bg=self.theme["card"], fg=self.theme["text"]).pack(anchor="w", pady=(2, 6))
        self.limit_vars, self.enabled_vars = {}, {}
        for key, translation_key, low, high, suffix in (("CPU", "metric.cpu", 30, 110, "°C"), ("GPU", "metric.gpu", 30, 110, "°C"), ("Discos", "metric.disks", 30, 110, "°C"), ("RAM", "alerts.ram", 1, 100, "%")):
            label = self.tr(translation_key)
            row=tk.Frame(alerts_tab,bg=self.theme["card"]); row.pack(fill="x", pady=4)
            self.enabled_vars[key]=tk.BooleanVar(value=self.enabled.get(key, True)); tk.Checkbutton(row,text=label,variable=self.enabled_vars[key],command=self.save_alerts,bg=self.theme["card"],fg=self.theme["text"],selectcolor=self.theme["card"]).pack(side="left")
            self.limit_vars[key]=tk.IntVar(value=self.limits.get(key, 85)); tk.Spinbox(row,from_=low,to=high,width=4,textvariable=self.limit_vars[key],command=self.save_alerts).pack(side="right")
            tk.Label(row,text=suffix,bg=self.theme["card"],fg=self.theme["muted"]).pack(side="right")
        tk.Label(connection_tab, text=self.tr("tab.display"), font=self.font_tuple("title", 13, True), bg=self.theme["card"], fg=self.theme["text"]).pack(anchor="w", pady=(2, 8))
        self.connection = tk.Frame(connection_tab, bg=self.theme["card"]); self.connection.pack(fill="x")
        self.port_var = tk.StringVar(value=self.settings.data["port"])
        tk.Label(self.connection, text=self.tr("display.port"), bg=self.theme["card"], fg=self.theme["text"]).pack(anchor="w")
        tk.Entry(self.connection, textvariable=self.port_var, width=10).pack(anchor="w", pady=3)
        self.brightness_var = tk.IntVar(value=self.preview_brightness)
        tk.Scale(self.connection, from_=10, to=100, orient="horizontal", variable=self.brightness_var, command=self.set_brightness, label=self.tr("display.brightness"), bg=self.theme["card"], fg=self.theme["text"], highlightthickness=0).pack(anchor="w")
        ttk.Button(self.connection, text=self.tr("display.check_port"), command=self.check_port_status).pack(anchor="w")
        ttk.Button(self.connection, text=self.tr("display.send_preview"), command=self.send_preview_to_screen).pack(anchor="w", pady=(6, 0))
        ttk.Button(self.connection, text=self.tr("display.calibrate"), command=self.send_screen_test).pack(anchor="w", pady=(3, 0))
        self.auto_send_var = tk.BooleanVar(value=self.auto_send_enabled)
        tk.Checkbutton(self.connection, text=self.tr("display.auto_send"), variable=self.auto_send_var, command=self.set_auto_send, bg=self.theme["card"], fg=self.theme["text"], selectcolor=self.theme["card"]).pack(anchor="w", pady=(12, 0))
        cadence_row = tk.Frame(self.connection, bg=self.theme["card"]); cadence_row.pack(fill="x", pady=(3, 0))
        tk.Label(cadence_row, text=self.tr("display.interval"), bg=self.theme["card"], fg=self.theme["text"]).pack(side="left")
        self.send_interval_var = tk.DoubleVar(value=self.send_interval)
        tk.Spinbox(cadence_row, from_=MINIMUM_SEND_INTERVAL, to=300, increment=1, width=5, textvariable=self.send_interval_var, command=self.set_send_interval).pack(side="right")
        tk.Label(self.connection, text=self.tr("display.auto_hint"), wraplength=255, justify="left", bg=self.theme["card"], fg=self.theme["muted"]).pack(anchor="w", pady=(3, 0))
        if self.edit_layout: self.editor.pack(fill="x", pady=(6, 0))
        return

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
            "visual_theme": self.visual_theme, "language": self.language,
            "limits": self.limits, "enabled": self.enabled, "geometry": self.geometry()})
        self.settings.save()

    def save_configuration(self) -> None:
        self.layout_store.save()
        self.save_preferences()
        if hasattr(self, "save_status"):
            self.save_status.configure(text=self.tr("status.saved"))

    def set_monitor_style(self) -> None:
        self.monitor_style = self.monitor_style_labels.get(self.monitor_style_var.get(), "cards")
        self.save_preferences()
        self.draw(force=True)

    def set_language(self, _event=None) -> None:
        selected = next((code for code, label in LANGUAGE_NAMES.items() if label == self.language_var.get()), DEFAULT_LANGUAGE)
        if selected == self.language:
            return
        self.language = selected
        self.save_preferences()
        self._rebuild()
        if self.tray_icon is not None:
            try:
                import pystray
                self.tray_icon.menu = self._tray_menu(pystray)
            except Exception:
                pass

    def apply_visual_theme(self) -> None:
        """This explicit action is the only time a theme replaces layouts."""
        self.visual_theme = self.theme_labels.get(self.visual_theme_var.get(), THEME_REBEL)
        self.layout_store.apply_template(self.visual_theme)
        self.save_preferences()
        self._rebuild()
        applied_label = next((label for label, theme_id in self.theme_labels.items() if theme_id == self.visual_theme), self.visual_theme)
        self.save_status.configure(text=self.tr("status.theme_applied", theme=applied_label))

    def restore_recommendations(self) -> None:
        for key, value in {"CPU": 85, "GPU": 82, "Discos": 60}.items():
            self.limit_vars[key].set(value)
            self.enabled_vars[key].set(True)
        self.save_alerts()

    def next_page(self) -> None:
        self.page = normalize_page(self.page + 1)
        self.draw(force=True)

    def set_page(self, page: int) -> None:
        """Explicit user navigation; media polling never calls this method."""
        self.page = normalize_page(page)
        self.last_page_change = time.monotonic()
        self.draw(force=True)

    def _draw_initial_preview(self) -> None:
        """Populate the canvas immediately instead of waiting for a refresh tick."""
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
            self.hardware_status.configure(text=self.tr("status.brightness", value=self.preview_brightness), fg=self.theme["muted"])
        self.draw(force=True)
        # The changed frame is also sent immediately when the user explicitly
        # moves the slider. This is visual brightness on the real panel, not a
        # firmware/backlight command.
        if self.auto_send_enabled and self.preview_orientation == "vertical":
            self.last_auto_send = 0.0

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
            self.tray_icon = pystray.Icon("rebscreen", icon_image, f"{APP_NAME} {APP_VERSION}", self._tray_menu(pystray))
            threading.Thread(target=self.tray_icon.run, name="telinha-tray", daemon=True).start()
        except Exception:
            self.tray_icon = None

    def _tray_menu(self, pystray):
        return pystray.Menu(
            pystray.MenuItem(self.tr("tray.open"), lambda *_: self.after(0, self.show_from_tray)),
            pystray.MenuItem(self.tr("tray.exit"), lambda *_: self.after(0, self.quit_app)),
        )

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
        self.runtime_executor.shutdown(wait=False, cancel_futures=True)
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
        self.settings.data["auto_send_approved"] = True
        self.save_preferences()
        status_key = "status.auto_usb_on" if self.auto_send_enabled else "status.auto_usb_off"
        self.hardware_status.configure(text=PanelApp.tr(self, status_key), fg="#ef9b3e" if self.auto_send_enabled else self.theme["muted"])

    def set_send_interval(self) -> None:
        self.send_interval = send_interval(self.send_interval_var.get())
        self.send_interval_var.set(self.send_interval)
        self.save_preferences()

    def set_orientation(self) -> None:
        self.preview_orientation = self.orientation_var.get()
        self.incremental_sender.invalidate()
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
        self.layout_help.configure(text=self.tr("layout.profile_saved", profile=self.tr("orientation." + profile)) if self.edit_layout else self.tr("editor.off"))
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
        if self.page == 0:
            return ("cpu", "gpu", "ram", "disks")
        if self.page == 1:
            return ("art", "title", "artist", "state", "progress")
        return ()

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
                self.inspector_label.configure(text=self.tr("editor.selected", item=key))
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
        self.incremental_sender.invalidate()
        self._queue_serial_operation(_send_test_frame_to_display, self.tr("status.sending_test"), self.port_var.get().strip())

    def check_port_status(self) -> None:
        """A manual open/close check; it sends no bytes and leaves no stream open."""
        port = self.port_var.get().strip()
        self._queue_serial_operation(_check_display_port, self.tr("status.checking_port"), port)

    def render_live_frame(self):
        """The live frame is for the physical display, never the static preview."""
        frame = PanelFrameRenderer(self.theme, self.accent, self.custom_fonts_enabled, self.font_scale, self.layout_store.data, self.monitor_style, self.visual_theme, getattr(self, "language", DEFAULT_LANGUAGE)).render(
            self.page, self.last_metrics, self.track, self.current_alert, self.media_label, self.album_art, history=self.telemetry_history, network=(self.rx_rate, self.tx_rate), processes=self.processes)
        from PIL import Image
        if self.preview_orientation == "horizontal": frame = frame.transpose(Image.Transpose.ROTATE_270)
        elif self.preview_orientation == "inverted": frame = frame.transpose(Image.Transpose.ROTATE_180)
        from PIL import ImageEnhance
        return ImageEnhance.Brightness(frame).enhance(self.preview_brightness / 100)

    def render_current_frame(self):
        return self.render_live_frame()

    def render_preview_frame(self):
        """Preview mirrors exactly the brightness of the outgoing frame."""
        return self.render_live_frame()

    def send_preview_to_screen(self) -> None:
        """User-initiated only: sends the exact image currently used in the preview."""
        if self.preview_orientation != "vertical":
            self.hardware_status.configure(text=self.tr("status.orientation_blocked"), fg="#ef9b3e")
            return
        self.incremental_sender.invalidate()
        self._queue_serial_operation(_send_frame_to_display, self.tr("status.sending_preview"), self.port_var.get().strip(), self.render_live_frame())

    def _rebuild(self) -> None:
        for child in self.winfo_children(): child.destroy()
        self._build_ui(); self.draw(force=True)

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
        page = normalize_page(self.page)
        page_keys = ("page.monitor", "page.player", "page.processes")
        self.page_label.configure(text=self.tr("page.caption", current=page + 1, name=self.tr(page_keys[page])))

    def update_alerts(self) -> None:
        m = self.last_metrics
        found: list[str] = []
        language = getattr(self, "language", "pt-BR")
        tr = lambda key, **values: translate(language, key, **values)
        if "CPU" not in m.demo_components and self.enabled["CPU"] and m.cpu_temperature >= self.limits["CPU"]:
            found.append(tr("alert.temperature", name=tr("metric.cpu"), value=m.cpu_temperature, limit=self.limits["CPU"]))
        if "GPU" not in m.demo_components and self.enabled["GPU"] and m.gpu_temperature >= self.limits["GPU"]:
            found.append(tr("alert.temperature", name=tr("metric.gpu"), value=m.gpu_temperature, limit=self.limits["GPU"]))
        for d in m.disks:
            if self.enabled["Discos"] and d.temperature is not None and d.temperature >= self.limits["Discos"]:
                found.append(tr("alert.temperature", name=d.name, value=d.temperature, limit=self.limits["Discos"]))
        if "RAM" not in m.demo_components and self.enabled["RAM"] and m.ram_usage >= self.limits["RAM"]:
            found.append(tr("alert.ram", value=m.ram_usage, limit=self.limits["RAM"]))
        if found != self.alerts:
            self.alerts = found
            self.alert_cycle = cycle(found or [""])
        self.current_alert = next(self.alert_cycle)

    def apply_media(self, media) -> bool:
        """Apply a completed background GSMTC read on the Tk thread."""
        changed = should_render_media(self.last_media_key, media)
        if media:
            self.track, self.media_label, self.album_art = media.track, media.source, artwork_for_display(media.art_image)
            playback_keys = {"tocando": "media.playing", "pausado": "media.paused", "parado": "media.stopped", "fechado": "media.closed"}
            playback_label = self.tr(playback_keys[media.playback_label]) if media.playback_label in playback_keys else media.playback_label
            self.media_status.configure(text=self.tr("media.status_active", source=media.source, state=playback_label, title=media.track.title), fg="#3fae68")
        else:
            self.track = Track(self.tr("screen.no_media"), self.tr("media.start_player"), 0, 1)
            self.media_label, self.album_art = self.tr("media.none_label"), None
            state = localize_media_runtime_message(self.language, self.media_provider.reason)
            self.media_status.configure(text=self.tr("media.status_none", reason=state), fg="#ef9b3e")
        self.page = page_after_media_refresh(self.page)
        details = "\n".join(localize_media_runtime_message(self.language, item) for item in self.media_provider.diagnostics) or self.tr("media.no_windows_session")
        if media and media.source.startswith("VLC ("):
            details += "\n" + self.tr("media.vlc_title_fallback")
        self.media_diagnostics.configure(text=self.tr("media.diagnostics_heading") + "\n" + details)
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
                self.media_status.configure(text=self.tr("status.media_failed", reason=str(exc)), fg="#ef5350")
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
                self.media_provider.reason = self.tr("media.timeout_reason")
                self.media_provider.diagnostics = [self.tr("media.timeout_diagnostic"), self.tr("media.no_fallback")]
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

    def _queue_serial_operation(self, operation, status: str, *operation_args) -> bool:
        """Queue one serial operation and reject overlaps without blocking Tk."""
        if not self.serial_task.start(operation, *operation_args):
            self.hardware_status.configure(text=PanelApp.tr(self, "status.usb_busy"), fg=self.theme["muted"])
            return False
        self.hardware_status.configure(text=status, fg=self.theme["muted"])
        return True

    def _apply_metrics(self, metrics, now: float) -> None:
        self.last_metrics = metrics
        if hasattr(self, "sensor_status"):
            if metrics.demo_components:
                items = ", ".join(sorted(metrics.demo_components))
                source_status = self.tr("status.demo_components", items=items)
            else:
                source_status = self.tr("status.live_sources")
            sensor_state = localize_sensor_status(self.language, self.metrics_provider.sensor_status)
            self.sensor_status.configure(text=source_status + "\n" + sensor_state, fg=self.theme["muted"])
            self._update_dependency_help()
        self.cpu_history = (self.cpu_history + [metrics.cpu_usage])[-60:]
        system_temperatures = [metrics.cpu_temperature, metrics.gpu_temperature]
        disk_temperatures = [disk.temperature for disk in metrics.disks]
        point = aggregate_point(metrics.cpu_usage, metrics.gpu_usage, metrics.ram_usage, system_temperatures, disk_temperatures)
        self.telemetry_history = (self.telemetry_history + [point])[-60:]
        self.last_metrics_update = now
        self.update_alerts()

    def _dependency_issues(self) -> tuple[str, ...]:
        return detect_dependency_issues(
            self.metrics_provider.sensor_status,
            self.media_provider.available,
            self._serial_support_available,
            self._process_support_available,
            self._tray_support_available,
        )

    def _update_dependency_help(self) -> None:
        if not hasattr(self, "dependency_help_button"):
            return
        self._dependency_issue_snapshot = self._dependency_issues()
        if self._dependency_issue_snapshot:
            if not self.dependency_help_button.winfo_manager():
                self.dependency_help_button.pack(anchor="w", pady=(6, 0))
        else:
            self.dependency_help_button.pack_forget()

    def open_dependency_help(self) -> None:
        issues = self.__dict__.get("_dependency_issue_snapshot")
        if issues is None:
            issues = self._dependency_issues()
        path = APP_DATA_DIR / f"Rebscreen-help-{self.language}.txt"
        try:
            APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(build_help_text(self.language, issues), encoding="utf-8")
            opener = getattr(os, "startfile", None)
            if opener is None:
                raise OSError("Windows default text editor is unavailable")
            opener(str(path))
        except (OSError, RuntimeError) as exc:
            messagebox.showerror(
                self.tr("help.button"),
                self.tr("help.open_failed", path=str(path), reason=str(exc)),
                parent=self,
            )

    def _poll_background_results(self, now: float) -> None:
        """Apply completed work on Tk's thread; never wait for a worker here."""
        metrics = self.metrics_task.take_completed()
        if metrics is not None:
            if metrics.error is None:
                self._apply_metrics(metrics.result, now)
            elif hasattr(self, "sensor_status"):
                self.sensor_status.configure(text=self.tr("status.sensor_unavailable", reason=str(metrics.error)), fg="#ef5350")
                self._update_dependency_help()
        processes = self.process_task.take_completed()
        if processes is not None and processes.error is None:
            self.processes = processes.result
        network = self.network_task.take_completed()
        if network is not None and network.error is None:
            self.rx_rate, self.tx_rate = network.result
        serial = self.serial_task.take_completed()
        if serial is not None:
            if serial.error is None:
                self.hardware_status.configure(text=localize_transport_status(self.language, serial.result), fg="#3fae68")
            else:
                self.hardware_status.configure(text=explain_serial_error(serial.error, self.language), fg="#ef5350")

    def _request_background_telemetry(self, now: float) -> None:
        """Request the next samples only when the previous request was consumed."""
        if now - self.last_metrics_request < 2.0:
            return
        started = self.metrics_task.start(self.metrics_provider.read)
        self.process_task.start(self.process_sampler.read)
        self.network_task.start(self.network_rates.read)
        if started:
            self.last_metrics_request = now

    def refresh(self) -> None:
        now = time.monotonic()
        self._poll_background_results(now)
        self._request_background_telemetry(now)
        media_changed = self.poll_media()
        # The app preview is deliberately static and cosmetic.  Live data is
        # still rendered below for the physical display.
        if rotation_due(self.rotation_enabled, self.last_page_change, now, self.rotation_interval):
            self.page = next_enabled_page(self.page, self.rotation_pages)
            self.last_page_change = now
            self.draw(force=True)
        if self.auto_send_enabled and self.preview_orientation == "vertical" and now - self.last_auto_send >= self.send_interval:
            port = self.port_var.get().strip()
            if self.incremental_sender.port != port:
                self.incremental_sender = IncrementalFrameSender(port)
            if self._queue_serial_operation(_send_incremental_frame_to_display, self.tr("status.auto_sending"), self.incremental_sender, self.render_live_frame()):
                self.last_auto_send = now
        self.after(1000, self.refresh)


if __name__ == "__main__":
    PanelApp().mainloop()

"""Localized, action-focused explanations for unavailable optional features."""
from __future__ import annotations

from localization import DEFAULT_LANGUAGE, normalize_language, translate


_COMPONENT_KEYS = {
    "sensors": "help.sensors",
    "media": "help.media",
    "serial": "help.serial",
    "processes": "help.processes",
    "tray": "help.tray",
}


def detect_dependency_issues(
    sensor_status: str,
    media_available: bool,
    serial_available: bool,
    process_available: bool,
    tray_available: bool = True,
) -> tuple[str, ...]:
    """Classify missing optional features from already-collected runtime state."""
    issues = []
    status = (sensor_status or "").casefold()
    if any(marker in status for marker in ("indisponível", "indisponible", "unavailable", "ative options", "porta 8085", "port 8085")):
        issues.append("sensors")
    if not media_available:
        issues.append("media")
    if not serial_available:
        issues.append("serial")
    if not process_available:
        issues.append("processes")
    if not tray_available:
        issues.append("tray")
    return tuple(issues)


def build_help_text(language: str, missing_components: list[str] | tuple[str, ...]) -> str:
    language = normalize_language(language)
    lines = [translate(language, "help.title"), "=" * 24, "", translate(language, "help.intro"), ""]
    recognized = [key for key in _COMPONENT_KEYS if key in set(missing_components)]
    if not recognized:
        lines.append(translate(language, "help.none"))
    else:
        lines.extend("- " + translate(language, _COMPONENT_KEYS[key]) for key in recognized)
    lines.append("")
    return "\n".join(lines)
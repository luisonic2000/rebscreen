"""User-facing serial diagnostics that do not open or write to a device."""
from __future__ import annotations

import re

from localization import DEFAULT_LANGUAGE, translate


def explain_serial_error(error: BaseException, language: str = "pt-BR") -> str:
    message = str(error).lower()
    port_match = re.search(r"\bCOM\d+\b", str(error), flags=re.IGNORECASE)
    port = port_match.group(0).upper() if port_match else "COM"
    if "acesso negado" in message or "permissionerror" in message or "access is denied" in message:
        return translate(language or DEFAULT_LANGUAGE, "runtime.serial.busy", port=port)
    if "could not open port" in message or "file not found" in message:
        return translate(language or DEFAULT_LANGUAGE, "runtime.serial.missing")
    return translate(language or DEFAULT_LANGUAGE, "runtime.serial.failed", reason=error)

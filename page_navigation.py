"""Shared page names and safe preference migration for the Rebscreen preview."""
from __future__ import annotations


PAGE_LABELS = (
    "Página 1 de 3 — Monitor do PC",
    "Página 2 de 3 — Player: Tocando agora",
    "Página 3 de 3 — Processos",
)


def normalize_page(page: int) -> int:
    """Keep stale or malformed page indexes inside the available page range."""
    return page if isinstance(page, int) and 0 <= page < len(PAGE_LABELS) else 0


def normalize_rotation_pages(values) -> tuple[bool, ...]:
    """Migrate prior Monitor/Player settings by enabling the new Processes page."""
    saved = list(values) if isinstance(values, (list, tuple)) else []
    return tuple(bool(saved[index]) if index < len(saved) else True for index in range(len(PAGE_LABELS)))

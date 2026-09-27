"""Regras puras para escolher a sessão de mídia exibida pelo painel."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, TypeVar


class PlayingMedia(Protocol):
    source: str
    playing: bool


T = TypeVar("T", bound=PlayingMedia)


def select_preferred_active(items: Iterable[T]) -> T | None:
    """Escolhe Spotify somente se ele estiver tocando; caso contrário, outro ativo."""
    active = [item for item in items if item.playing]
    return next((item for item in active if "spotify" in item.source.lower()), active[0] if active else None)

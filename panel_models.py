"""Shared data contracts used by collection, rendering and the interface."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Disk:
    name: str
    temperature: int | None
    health: str
    units: list[str] = field(default_factory=list)
    usage: int | None = None
    usage_history: list[int] = field(default_factory=list)
    temperature_history: list[int | None] = field(default_factory=list)


@dataclass
class Metrics:
    cpu_usage: int
    cpu_temperature: int
    gpu_usage: int
    gpu_temperature: int
    ram_usage: int
    disks: list[Disk]
    demo_components: frozenset[str] = field(default_factory=frozenset)


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

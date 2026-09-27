"""Pure media refresh decisions: coalesce visible changes and isolate timeouts."""
from __future__ import annotations

from typing import Protocol


class SnapshotLike(Protocol):
    source: str
    playing: bool
    art_image: object | None
    playback_label: str
    track: object


def snapshot_key(snapshot: SnapshotLike | None) -> tuple[object, ...]:
    if snapshot is None:
        return ("none",)
    track = snapshot.track
    return (snapshot.source, snapshot.playing, snapshot.playback_label,
            getattr(track, "title", ""), getattr(track, "artist", ""),
            getattr(track, "elapsed", 0), getattr(track, "duration", 0),
            id(snapshot.art_image) if snapshot.art_image is not None else None)


def should_render_media(previous: tuple[object, ...] | None, current: SnapshotLike | None) -> bool:
    return previous != snapshot_key(current)


def query_timed_out(started_at: float, now: float, timeout_seconds: float = 4.0) -> bool:
    return now - started_at >= timeout_seconds

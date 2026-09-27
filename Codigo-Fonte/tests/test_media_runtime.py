from dataclasses import dataclass

from media_runtime import query_timed_out, should_render_media, snapshot_key


@dataclass
class Track:
    title: str
    artist: str
    elapsed: int = 0
    duration: int = 1


@dataclass
class Snapshot:
    source: str
    playing: bool
    track: Track
    art_image: object | None = None
    playback_label: str = "tocando"


def test_identical_media_state_is_coalesced():
    state = Snapshot("Spotify", True, Track("A", "B"))
    assert should_render_media(snapshot_key(state), state) is False


def test_track_or_artwork_change_requests_a_render_and_missing_art_has_own_key():
    old = Snapshot("Spotify", True, Track("A", "B"), object())
    no_art = Snapshot("Spotify", True, Track("A", "B"), None)
    changed = Snapshot("Spotify", True, Track("C", "B"), None)
    assert should_render_media(snapshot_key(old), no_art) is True
    assert should_render_media(snapshot_key(no_art), changed) is True


def test_timeout_isolated_from_polling_schedule():
    assert query_timed_out(10.0, 13.9) is False
    assert query_timed_out(10.0, 14.0) is True

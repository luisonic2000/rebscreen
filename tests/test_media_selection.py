from dataclasses import dataclass

from media_selection import select_preferred_active


@dataclass
class FakeSession:
    source: str
    playing: bool


def test_spotify_wins_when_actively_playing():
    browser = FakeSession("Microsoft Edge", True)
    spotify = FakeSession("Spotify", True)
    assert select_preferred_active([browser, spotify]) is spotify


def test_paused_spotify_does_not_block_vlc():
    spotify = FakeSession("Spotify", False)
    vlc = FakeSession("VLC media player", True)
    assert select_preferred_active([spotify, vlc]) is vlc


def test_returns_first_active_non_spotify_source():
    player = FakeSession("Windows Media Player", True)
    browser = FakeSession("Google Chrome", True)
    assert select_preferred_active([player, browser]) is player


def test_returns_none_when_everything_is_not_playing():
    assert select_preferred_active([FakeSession("Spotify", False), FakeSession("VLC", False)]) is None

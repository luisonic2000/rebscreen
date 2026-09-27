from app import parse_spotify_window_title


def test_spotify_window_title_produces_now_playing_metadata_without_gstmtc():
    snapshot = parse_spotify_window_title("Linkin Park - Heavy Is the Crown")
    assert snapshot is not None
    assert snapshot.source == "Spotify (título da janela)"
    assert snapshot.track.artist == "Linkin Park"
    assert snapshot.track.title == "Heavy Is the Crown"
    assert snapshot.art_image is None

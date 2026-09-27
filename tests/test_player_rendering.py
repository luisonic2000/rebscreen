from pathlib import Path

from app import DARK, DemoMetricsProvider, LayoutStore, LyricsProvider, PanelFrameRenderer, Track
from layout_normalization import normalize_profile


def test_invalid_player_geometry_is_repaired_without_touching_valid_other_profile():
    defaults = LayoutStore.default
    portrait = {key: dict(value) for key, value in defaults.items()}
    landscape = {key: dict(value) for key, value in defaults.items()}
    portrait["art"] = {"x": -900, "y": 900, "size": 999}
    portrait["title"] = {"x": 999, "y": -1}
    assert normalize_profile(portrait, defaults) is True
    assert portrait["art"] == {"x": 0, "y": 180, "size": 300}
    assert portrait["title"] == {"x": 300, "y": 55}
    assert landscape["art"] == defaults["art"]


def test_player_renders_neutral_cover_and_text_when_no_media_exists():
    renderer = PanelFrameRenderer(DARK, "#5b8cff", False, 1.0, LayoutStore.default)
    image = renderer.render(1, DemoMetricsProvider().read(), Track("Nenhuma mídia ativa", "Inicie Spotify", 0, 1), LyricsProvider(Path("missing.lrc")), "", "Nenhuma mídia ativa", None)
    assert image.size == (320, 480)
    assert image.getpixel((160, 171)) != DARK["bg"]


def test_player_renders_fallback_track_without_artwork():
    renderer = PanelFrameRenderer(DARK, "#5b8cff", False, 1.0, LayoutStore.default)
    image = renderer.render(1, DemoMetricsProvider().read(), Track("Faixa real", "Artista real", 0, 1), LyricsProvider(Path("missing.lrc")), "", "Spotify (título da janela)", None)
    assert image.getpixel((160, 171)) != DARK["bg"]

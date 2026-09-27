from datetime import datetime

from app import APP_DATA_DIR, LEGACY_APP_DATA_DIRS, DARK, DemoMetricsProvider, LayoutStore, PanelFrameRenderer, Track
from rebscreen_identity import APP_NAME, header_state
from source_icons import source_kind
from visual_themes import THEME_TECHNICAL, layout_templates
from visual_themes import THEME_REBEL, available_themes


def test_rebscreen_uses_new_data_folder_and_reads_telinha_as_legacy_only():
    assert APP_NAME == "Rebscreen"
    assert APP_DATA_DIR.name == "Rebscreen"
    assert any(path.name == "Telinha" for path in LEGACY_APP_DATA_DIRS)


def test_portuguese_header_time_and_date_state_is_deterministic():
    assert header_state(datetime(2026, 9, 27, 8, 5)) == ("08:05", "27 set. 2026")


def test_source_icon_mapping_has_safe_unknown_fallback():
    assert source_kind("Spotify") == "spotify"
    assert source_kind("VLC (título da janela)") == "vlc"
    assert source_kind("mídia desconhecida") == "unknown"


def test_detailed_technical_theme_fits_portrait_monitor_and_player():
    layout = layout_templates(THEME_TECHNICAL, LayoutStore.default)["vertical"]
    renderer = PanelFrameRenderer(DARK, "#5b8cff", False, layout=layout, visual_theme=THEME_TECHNICAL)
    monitor = renderer.render(0, DemoMetricsProvider().read(), Track("", "", 0, 1), "", "", None, history=list(range(60)))
    player = renderer.render(1, DemoMetricsProvider().read(), Track("Faixa", "Artista", 30, 200), "", "Spotify", None)
    assert monitor.size == (320, 480)
    assert player.size == (320, 480)
    assert monitor.getpixel((160, 450)) != (16, 19, 21)


def test_rebel_is_registered_and_has_independent_portrait_and_landscape_profiles():
    assert THEME_REBEL in available_themes()
    profiles = layout_templates(THEME_REBEL, LayoutStore.default)
    assert profiles["vertical"] is not profiles["horizontal"]
    assert profiles["vertical"]["cpu"]["h"] != profiles["horizontal"]["cpu"]["h"]
    renderer = PanelFrameRenderer(DARK, "#5b8cff", False, layout=profiles["vertical"], visual_theme=THEME_REBEL)
    assert renderer.render(0, DemoMetricsProvider().read(), Track("", "", 0, 1), "", "", None, history=[40, 55]).size == (320, 480)
    assert renderer.render(1, DemoMetricsProvider().read(), Track("Faixa", "Artista", 2, 100), "", "Spotify", None).size == (320, 480)

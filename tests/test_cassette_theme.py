from app import DARK, Disk, LayoutStore, Metrics, PanelFrameRenderer, Track
from localization import LANGUAGES
from visual_themes import SOUNDWAVE_PALETTE, THEME_CASSETTE, THEME_REBEL, THEME_TECHNICAL, available_themes, layout_templates


def test_cassette_theme_is_an_additive_preset_with_independent_layouts():
    assert THEME_CASSETTE in available_themes()
    assert THEME_REBEL in available_themes()
    assert THEME_TECHNICAL in available_themes()

    profiles = layout_templates(THEME_CASSETTE, LayoutStore.default)
    assert profiles["vertical"] is not profiles["horizontal"]
    assert profiles["vertical"]["cpu"]["h"] != profiles["horizontal"]["cpu"]["h"]


def test_cassette_theme_renders_all_pages_at_the_display_resolution():
    profiles = layout_templates(THEME_CASSETTE, LayoutStore.default)
    renderer = PanelFrameRenderer(
        DARK, "#5b8cff", False, layout=profiles["vertical"], visual_theme=THEME_CASSETTE
    )
    metrics = Metrics(41, 55, 27, 48, 63, [Disk("NVMe", 42, "Good", ["C:"], usage=38)])
    track = Track("Signal Lost", "Station 7", 30, 200)

    for page in range(3):
        image = renderer.render(page, metrics, track, "", "Spotify", None, history=[30, 45, 51])
        assert image.size == (320, 480)
        assert image.getpixel((0, 0)) == (8, 17, 26)


def test_cassette_theme_uses_the_centralized_soundwave_palette():
    assert SOUNDWAVE_PALETTE["background_primary"] == "#08111A"
    assert SOUNDWAVE_PALETTE["blue_primary"] == "#243D91"
    assert SOUNDWAVE_PALETTE["silver_primary"] == "#C7CCD3"
    assert SOUNDWAVE_PALETTE["red_visor"] == "#C62835"
    assert SOUNDWAVE_PALETTE["amber_primary"] == "#E7BD46"
    assert SOUNDWAVE_PALETTE["purple_decepticon"] == "#75469A"


def test_cassette_monitor_accepts_the_structured_telemetry_history_used_by_the_app():
    renderer = PanelFrameRenderer(DARK, "#5b8cff", False, visual_theme=THEME_CASSETTE)
    metrics = Metrics(41, 55, 27, 48, 63, [Disk("NVMe", 42, "Good", ["C:"], usage=38)])
    history = [{"usage": 37, "temperature": 44, "disk_temperature": 42}, {"usage": 51, "temperature": 48, "disk_temperature": 43}]

    image = renderer.render(0, metrics, Track("Title", "Artist", 0, 10), "", "Spotify", None, history=history)

    assert image.size == (320, 480)


def test_cassette_theme_panel_copy_uses_selected_locale():
    metrics = Metrics(41, 55, 27, 48, 63, [Disk("NVMe", 42, "Good", ["C:"], usage=38)])
    for language in LANGUAGES:
        renderer = PanelFrameRenderer(
            DARK, "#5b8cff", False, visual_theme=THEME_CASSETTE, language=language
        )
        assert renderer.tr("screen.monitor")
        assert renderer.render(0, metrics, Track("Title", "Artist", 0, 10), "", "", None).size == (320, 480)

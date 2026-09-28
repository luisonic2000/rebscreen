from itertools import cycle
from types import SimpleNamespace

from PIL import Image, ImageDraw

from localization import (
    CATALOGS, DEFAULT_LANGUAGE, LANGUAGES, localize_media_runtime_message,
    localize_sensor_status, localize_transport_status, translate,
)


def test_catalogs_cover_every_supported_language_with_the_same_keys():
    assert DEFAULT_LANGUAGE == "en"
    assert set(CATALOGS) == set(LANGUAGES)
    keys = set(CATALOGS[DEFAULT_LANGUAGE])
    assert keys
    assert all(set(catalog) == keys for catalog in CATALOGS.values())


def test_language_selection_and_unknown_entries_fall_back_to_english():
    assert translate("en", "language.label") == "Language"
    assert translate("pt-BR", "language.label") == "Idioma"
    assert translate("zh-CN", "language.label") == "语言"
    assert translate("unknown", "language.label") == "Language"
    assert translate("ru", "not.in.catalog") == "not.in.catalog"


def test_translated_messages_support_named_values():
    assert translate("en", "sensor.unavailable", name="Disk 1") == "Disk 1: unavailable"
    assert translate("es", "sensor.unavailable", name="Disco 1") == "Disco 1: no disponible"


def test_new_install_uses_english_when_no_language_is_saved():
    from app import SettingsStore

    assert SettingsStore.default["language"] == DEFAULT_LANGUAGE


def test_this_iteration_is_identified_as_the_beta_version():
    from rebscreen_identity import APP_VERSION

    assert APP_VERSION == "0.2-beta"


def test_panel_translation_uses_the_selected_language_without_starting_tk():
    from app import PanelApp

    panel = object.__new__(PanelApp)
    panel.language = "ru"

    assert PanelApp.tr(panel, "page.processes") == "Процессы"


def test_language_selection_persists_and_rebuilds_the_existing_window():
    from app import PanelApp

    panel = object.__new__(PanelApp)
    panel.language = "en"
    panel.language_var = SimpleNamespace(get=lambda: "简体中文")
    panel.tray_icon = None
    saved = []
    rebuilt = []
    panel.save_preferences = lambda: saved.append(panel.language)
    panel._rebuild = lambda: rebuilt.append(True)

    PanelApp.set_language(panel)

    assert panel.language == "zh-CN"
    assert saved == ["zh-CN"]
    assert rebuilt == [True]


def test_page_caption_is_localized_and_interpolates_the_page_name():
    assert translate("en", "page.caption", current=2, name="Player") == "Page 2 of 3 — Player"
    assert translate("pt-BR", "page.caption", current=2, name="Player") == "Página 2 de 3 — Player"


def test_temperature_alert_uses_selected_language_and_keeps_demo_alerts_off():
    from app import Disk, Metrics, PanelApp

    metrics = Metrics(99, 99, 99, 99, 20, [Disk("SSD", 40, "Good")])
    panel = SimpleNamespace(
        language="ru",
        last_metrics=metrics,
        enabled={"CPU": True, "GPU": True, "Discos": True, "RAM": True},
        limits={"CPU": 85, "GPU": 82, "Discos": 60, "RAM": 90},
        alerts=[],
        alert_cycle=cycle([""]),
        current_alert="",
    )

    PanelApp.update_alerts(panel)

    assert panel.alerts == ["ОПОВЕЩЕНИЕ ЦП: 99 °C · предел 85 °C", "ОПОВЕЩЕНИЕ ГП: 99 °C · предел 82 °C"]

    metrics.demo_components = frozenset({"CPU", "GPU", "RAM"})
    PanelApp.update_alerts(panel)
    assert panel.alerts == []


def test_all_themes_render_every_page_in_all_languages_without_hardware():
    from app import DARK, Disk, LayoutStore, Metrics, PanelFrameRenderer, Track
    from visual_themes import THEME_CASSETTE, THEME_REBEL, THEME_TECHNICAL, layout_templates

    metrics = Metrics(41, 55, 27, 48, 63, [Disk("NVMe", 42, "Good", ["C:"], usage=38)])
    themes = (THEME_REBEL, THEME_TECHNICAL, THEME_CASSETTE)
    for theme in themes:
        profiles = layout_templates(theme, LayoutStore.default)
        for language in LANGUAGES:
            renderer = PanelFrameRenderer(
                DARK, "#5b8cff", False, layout=profiles["vertical"], visual_theme=theme, language=language
            )
            for page in range(3):
                image = renderer.render(page, metrics, Track("Title", "Artist", 2, 60), "", "Player", None, history=[20, 30, 40])
                assert image.size == (320, 480)


def test_known_windows_sensor_and_transport_statuses_are_localized_before_display():
    assert "indispon" not in localize_sensor_status("ru", "Libre Hardware Monitor indisponível").casefold()
    assert "GSMTC" in localize_media_runtime_message("zh-CN", "Binding GSMTC ausente (requer Python 3.9+ com winrt-Windows.Media.Control)")
    assert localize_transport_status("ru", "Prévia enviada para COM9.").endswith("COM9.")


def test_russian_and_chinese_screen_labels_fit_the_320_pixel_rendering_area():
    from app import DARK, LayoutStore, PanelFrameRenderer

    draw = ImageDraw.Draw(Image.new("RGB", (320, 480)))
    for language in ("ru", "zh-CN"):
        renderer = PanelFrameRenderer(DARK, "#5b8cff", False, layout=LayoutStore.default, language=language)
        for key in ("screen.top_processes", "screen.history_labels", "screen.disk_usage_temp", "screen.alert_monitoring"):
            width = draw.textbbox((0, 0), translate(language, key), font=renderer.font("aux", 10))[2]
            assert width <= 280

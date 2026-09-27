from app_lifecycle import close_action
from brightness_protocol import HARDWARE_BRIGHTNESS_SUPPORTED, brightness_status
from rotation import next_enabled_page, rotation_due
from telemetry_mapping import disk_label, normalize_disks
from layout_normalization import normalize_profile
from app import LayoutStore
from app import DARK, DemoMetricsProvider, PanelFrameRenderer, Track
from single_instance import executable_identity, ipc_port
from visual_themes import THEME_TECHNICAL, layout_templates


def test_main_window_close_minimizes_to_tray_and_explicit_tray_action_exits():
    assert close_action() == "tray"


def test_rotation_uses_only_enabled_pages_and_manual_page_can_be_current():
    assert next_enabled_page(0, (True, True)) == 1
    assert next_enabled_page(1, (True, True)) == 0
    assert next_enabled_page(0, (True, False)) == 0
    assert rotation_due(True, 10, 15, 5)
    assert not rotation_due(False, 10, 99, 5)


def test_disk_mapping_keeps_unavailable_and_removes_duplicates():
    disks = normalize_disks([
        {"id": "C", "name": "Sistema", "temperature": None},
        {"id": "C", "name": "Sistema", "temperature": 42, "health": "Saudável"},
        {"id": "D", "name": "Jogos", "temperature": None},
    ])
    assert len(disks) == 2
    assert disks[0]["temperature"] == 42
    assert "Temperatura indisponível" in disk_label(disks[1])


def test_brightness_is_honest_about_frame_based_physical_dimming():
    assert not HARDWARE_BRIGHTNESS_SUPPORTED
    assert brightness_status(150) == "Brilho enviado à tela: 100%"


def test_old_layout_migrates_by_removing_only_retired_lyrics():
    profile = {key: dict(value) for key, value in LayoutStore.default.items()}
    profile["lyrics"] = {"x": 160, "y": 416}
    normalize_profile(profile, LayoutStore.default)
    assert "lyrics" not in profile
    assert profile["title"] == LayoutStore.default["title"]


def test_same_executable_identity_uses_one_deterministic_local_channel():
    identity = executable_identity(r"C:\Apps\Telinha-vNext\Telinha.exe")
    assert identity == executable_identity(r"c:\apps\telinha-vnext\telinha.exe")
    assert ipc_port(identity) == ipc_port(identity)


def test_graph_telemetry_theme_renders_the_60_second_history():
    image = PanelFrameRenderer(DARK, "#5b8cff", False, layout=LayoutStore.default, monitor_style="graph").render(
        0, DemoMetricsProvider().read(), Track("", "", 0, 1), "", "", None, history=[10, 20, 30, 40])
    assert image.size == (320, 480)


def test_technical_theme_has_independent_orientation_templates_and_renders_both_pages():
    templates = layout_templates(THEME_TECHNICAL, LayoutStore.default)
    assert templates["vertical"] is not templates["horizontal"]
    assert templates["vertical"]["cpu"]["h"] != templates["horizontal"]["cpu"]["h"]
    renderer = PanelFrameRenderer(DARK, "#5b8cff", False, layout=templates["vertical"], visual_theme=THEME_TECHNICAL)
    assert renderer.render(0, DemoMetricsProvider().read(), Track("", "", 0, 1), "", "", None, history=[30, 42]).size == (320, 480)
    assert renderer.render(1, DemoMetricsProvider().read(), Track("Faixa", "Artista", 4, 200), "", "Spotify", None).size == (320, 480)

from types import SimpleNamespace

from app import PanelApp
from page_navigation import PAGE_LABELS, normalize_page, normalize_rotation_pages
from rotation import next_enabled_page


def test_process_page_has_a_real_label_and_all_page_indexes_are_bounded():
    assert PAGE_LABELS[2] == "Página 3 de 3 — Processos"
    assert normalize_page(2) == 2
    assert normalize_page(99) == 0


def test_old_two_page_rotation_preferences_gain_the_processes_page():
    assert normalize_rotation_pages([True, True]) == (True, True, True)
    assert normalize_rotation_pages([True, False, True]) == (True, False, True)
    assert next_enabled_page(2, (True, True, True)) == 0


def test_preview_is_drawn_once_immediately_after_building_the_window():
    calls = []
    panel = SimpleNamespace(draw=lambda *, force: calls.append(force))

    PanelApp._draw_initial_preview(panel)

    assert calls == [True]

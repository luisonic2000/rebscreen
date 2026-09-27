from layout_interaction import apply_drag
from orientation_profiles import LANDSCAPE_SIZE, PORTRAIT_SIZE, canvas_dimensions, make_profiles, profile_for


def test_art_drag_stays_inside_the_design_canvas():
    art = {"x": 120, "y": 180, "size": 100}
    assert apply_drag(art, "art", "move", 999, 999)
    assert art == {"x": 220, "y": 380, "size": 100}


def test_progress_resize_is_bounded():
    progress = {"x": 18, "y": 320, "w": 200}
    apply_drag(progress, "progress", "resize", -999, 0)
    assert progress["w"] == 80
    apply_drag(progress, "progress", "resize", 999, 0)
    assert progress["w"] == 300


def test_move_rule_only_reports_overlay_work_not_rendering_or_persistence():
    cpu = {"y": 100, "h": 70}
    assert apply_drag(cpu, "cpu", "move", 0, 8) is True
    assert cpu["y"] == 108


def test_orientation_profiles_are_isolated_and_have_their_own_canvas_geometry():
    profiles = make_profiles({"art": {"x": 52, "y": 63, "size": 216}})
    profile_for(profiles, "horizontal")["art"]["x"] = 200
    assert profile_for(profiles, "vertical")["art"]["x"] == 52
    assert canvas_dimensions("vertical") == PORTRAIT_SIZE
    assert canvas_dimensions("horizontal") == LANDSCAPE_SIZE

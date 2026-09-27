from layout_colors import reset_item_colors, set_item_color
from orientation_profiles import make_profiles


def test_item_colors_persist_independently_by_profile_and_can_be_transparent():
    profiles = make_profiles({"title": {"x": 1, "y": 2}})
    set_item_color(profiles["vertical"]["title"], "text_color", "#ffcc00")
    set_item_color(profiles["vertical"]["title"], "background_color", None)
    assert profiles["vertical"]["title"]["text_color"] == "#ffcc00"
    assert "background_color" not in profiles["vertical"]["title"]
    assert "text_color" not in profiles["horizontal"]["title"]


def test_reset_removes_only_color_overrides_not_geometry():
    item = {"x": 10, "y": 20, "text_color": "#fff", "alert_color": "#f00"}
    reset_item_colors(item)
    assert item == {"x": 10, "y": 20}

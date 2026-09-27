from app import APP_DATA_DIR, LEGACY_APP_DATA_DIRS


def test_new_preferences_are_saved_under_rebscreen_name():
    assert APP_DATA_DIR.name == "Rebscreen"


def test_legacy_preferences_are_only_import_candidates():
    assert {path.name for path in LEGACY_APP_DATA_DIRS} == {"Telinha", "TURZX Panel", "TURZX Panel V2"}

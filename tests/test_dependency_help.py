from dependency_help import build_help_text, detect_dependency_issues


def test_help_text_is_localized_and_mentions_only_detected_issues():
    text = build_help_text("es", ["sensors"])

    assert "Guía para resolver" in text
    assert "Libre Hardware Monitor" in text
    assert "Python" not in text


def test_help_text_lists_multiple_missing_optional_components():
    text = build_help_text("en", ["media", "serial"])

    assert "Windows media session support" in text
    assert "USB serial support" in text
    assert "disk sensors" not in text


def test_help_text_falls_back_to_english_for_unknown_languages():
    assert build_help_text("unknown", ["display"]).startswith("Rebscreen help")


def test_dependency_detection_uses_existing_status_and_optional_capabilities():
    assert detect_dependency_issues("Libre Hardware Monitor indisponível", False, False, True, False) == (
        "sensors", "media", "serial", "tray"
    )
    assert detect_dependency_issues("Libre Hardware Monitor (REST local)", True, True, True, True) == ()


def test_open_help_writes_utf8_text_and_uses_the_default_editor(monkeypatch, tmp_path):
    import app

    opened = []
    monkeypatch.setattr(app, "APP_DATA_DIR", tmp_path)
    monkeypatch.setattr(app.os, "startfile", lambda path: opened.append(path), raising=False)
    panel = object.__new__(app.PanelApp)
    panel.language = "es"
    panel._dependency_issues = lambda: ("sensors",)

    app.PanelApp.open_dependency_help(panel)

    help_path = tmp_path / "Rebscreen-help-es.txt"
    text = help_path.read_text(encoding="utf-8")
    assert "Guía para resolver" in text
    assert "Libre Hardware Monitor" in text
    assert opened == [str(help_path)]


def test_help_button_is_shown_only_when_optional_features_are_missing():
    import app

    class Button:
        manager = ""

        def winfo_manager(self):
            return self.manager

        def pack(self, **_kwargs):
            self.manager = "pack"

        def pack_forget(self):
            self.manager = ""

    panel = type("Panel", (), {})()
    panel.dependency_help_button = Button()
    panel._dependency_issues = lambda: ("sensors",)

    app.PanelApp._update_dependency_help(panel)
    assert panel.dependency_help_button.manager == "pack"

    panel._dependency_issues = lambda: ()
    app.PanelApp._update_dependency_help(panel)
    assert panel.dependency_help_button.manager == ""


def test_help_open_failure_shows_localized_error_and_keeps_path(monkeypatch, tmp_path):
    import app

    errors = []
    monkeypatch.setattr(app, "APP_DATA_DIR", tmp_path)
    monkeypatch.setattr(app.os, "startfile", lambda _path: (_ for _ in ()).throw(OSError("denied")), raising=False)
    monkeypatch.setattr(app.messagebox, "showerror", lambda *args, **kwargs: errors.append((args, kwargs)))
    panel = object.__new__(app.PanelApp)
    panel.language = "en"
    panel._dependency_issues = lambda: ("serial",)

    app.PanelApp.open_dependency_help(panel)

    assert errors
    assert str(tmp_path / "Rebscreen-help-en.txt") in errors[0][0][1]
    assert "denied" in errors[0][0][1]


def test_open_help_uses_the_last_collected_issue_snapshot_without_redetecting(monkeypatch, tmp_path):
    import app

    opened = []
    monkeypatch.setattr(app, "APP_DATA_DIR", tmp_path)
    monkeypatch.setattr(app.os, "startfile", lambda path: opened.append(path), raising=False)
    panel = object.__new__(app.PanelApp)
    panel.language = "en"
    panel._dependency_issue_snapshot = ("serial",)
    panel._dependency_issues = lambda: (_ for _ in ()).throw(AssertionError("must not re-detect"))

    app.PanelApp.open_dependency_help(panel)

    assert opened
    assert "USB serial support" in (tmp_path / "Rebscreen-help-en.txt").read_text(encoding="utf-8")

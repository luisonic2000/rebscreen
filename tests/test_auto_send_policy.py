from types import SimpleNamespace

from auto_send_policy import MINIMUM_SEND_INTERVAL, initial_auto_send, send_interval
from app import SettingsStore


def test_new_installations_keep_automatic_usb_sending_off():
    assert SettingsStore.default["auto_send"] is False
    assert initial_auto_send({}) is False


def test_saved_explicit_preference_is_restored_on_restart():
    assert initial_auto_send({"auto_send": True, "auto_send_approved": True}) is True
    assert initial_auto_send({"auto_send": False}) is False


def test_safe_start_overrides_a_saved_automatic_send_preference():
    assert initial_auto_send({"auto_send": True, "auto_send_approved": True}, safe_start=True) is False


def test_cadence_allows_one_second_incremental_frames_after_the_initial_sync():
    assert MINIMUM_SEND_INTERVAL == 1.0
    assert send_interval(0.2) == 1.0
    assert send_interval(1) == 1.0
    assert send_interval(60) == 60


def test_panel_records_explicit_auto_send_consent_before_saving():
    saved = []

    class Variable:
        def get(self):
            return True

    class Label:
        def configure(self, **kwargs):
            self.latest = kwargs

    panel = SimpleNamespace(
        auto_send_var=Variable(), settings=SimpleNamespace(data={}),
        hardware_status=Label(), theme={"muted": "muted"}, save_preferences=lambda: saved.append(True),
    )
    from app import PanelApp
    PanelApp.set_auto_send(panel)

    assert panel.auto_send_enabled is True
    assert panel.settings.data["auto_send_approved"] is True
    assert saved == [True]

import app
import panel_models


def test_app_reexports_shared_panel_models_from_the_data_module():
    assert app.Metrics is panel_models.Metrics
    assert app.Track is panel_models.Track
    assert app.Disk is panel_models.Disk

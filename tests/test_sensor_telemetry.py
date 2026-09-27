from lhm_telemetry import disk_rows, parse_lhm_rest_tree, query_lhm_rest
from telemetry_history import aggregate_point, rate_label


def test_lhm_snapshot_maps_temperature_and_never_invents_health():
    rows = disk_rows([{"parent": "NVMe X", "type": "Temperature", "value": 41}, {"parent": "NVMe X", "type": "Health", "value": "Good"}], ["Volume C:"])
    assert rows == [{"name": "NVMe X", "temperature": 41, "health": "Good"}]


def test_no_lhm_uses_explicit_unknown_volume_rows():
    assert disk_rows([], ["Volume C:"])[0]["health"] == "Indisponível"


def test_dual_graph_aggregation_omits_missing_temperature_and_formats_network():
    assert aggregate_point(30, 60, 90, [None, 40]) == {"usage": 60, "temperature": 40}
    assert aggregate_point(30, 60, 90, [None])["temperature"] is None
    assert rate_label(1536) == "1.5 KB/s"


def test_rest_tree_parses_lhm_temperature_and_health_snapshot():
    tree = {"Text": "LHM", "Children": [{"Text": "NVMe", "Children": [{"Text": "Temperature", "SensorType": "Temperature", "Value": "41.5 °C"}, {"Text": "Health", "SensorType": "Level", "Value": "98 %"}]}]}
    rows = disk_rows(parse_lhm_rest_tree(tree), [])
    assert rows[0]["name"] == "NVMe"
    assert rows[0]["temperature"] == 41


def test_rest_query_fallback_is_empty_when_local_server_is_unavailable():
    def unavailable(*_args, **_kwargs): raise OSError("offline")
    assert query_lhm_rest(unavailable) == ([], "")

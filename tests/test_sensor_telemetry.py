from lhm_telemetry import LhmSession, disk_rows, parse_lhm_rest_tree, query_lhm, query_lhm_rest
from telemetry_history import aggregate_point, rate_label


def test_lhm_snapshot_maps_temperature_and_never_invents_health():
    rows = disk_rows([{"parent": "NVMe X", "type": "Temperature", "value": 41}, {"parent": "NVMe X", "type": "Health", "value": "Good"}], ["Volume C:"])
    assert rows == [{"name": "NVMe X", "temperature": 41, "health": "Good"}]


def test_no_lhm_uses_explicit_unknown_volume_rows():
    assert disk_rows([], ["Volume C:"])[0]["health"] == "Indisponível"


def test_dual_graph_aggregation_omits_missing_temperature_and_formats_network():
    assert aggregate_point(30, 60, 90, [None, 40], [35, 45]) == {"usage": 60, "temperature": 40, "disk_temperature": 40}
    assert aggregate_point(30, 60, 90, [None])["temperature"] is None
    assert rate_label(1536) == "1.5 KB/s"


def test_rest_tree_parses_lhm_temperature_and_health_snapshot():
    tree = {"Text": "LHM", "Children": [{"Text": "NVMe", "HardwareId": "/hdd/0", "ImageURL": "images_icon/hdd.png", "Children": [{"Text": "Temperature", "SensorType": "Temperature", "Value": "41,5 °C"}, {"Text": "Health", "SensorType": "Level", "Value": "98 %"}]}]}
    rows = disk_rows(parse_lhm_rest_tree(tree), [])
    assert rows[0]["name"] == "NVMe"
    assert rows[0]["temperature"] == 42


def test_disk_rows_rejects_voltage_and_generic_temperature_groups():
    rows = disk_rows([
        {"name": "Voltage #1", "type": "Voltage", "value": 3.3, "parent": "Voltages"},
        {"name": "Temperature #1", "type": "Temperature", "value": 48.0, "parent": "Temperatures"},
        {"name": "Temperature", "type": "Temperature", "value": 41.0, "parent": "Real SSD", "hardware_kind": "hdd.png"},
    ], ["Fallback C:"])
    assert rows == [{"name": "Real SSD", "temperature": 41, "health": "Indisponível"}]


def test_rest_query_fallback_is_empty_when_local_server_is_unavailable():
    def unavailable(*_args, **_kwargs): raise OSError("offline")
    assert query_lhm_rest(unavailable) == ([], "")


def test_unavailable_lhm_discovery_runs_only_once_for_the_app_session():
    attempts = []

    def unavailable_discovery():
        attempts.append("discover")
        return [], "Libre Hardware Monitor indisponível"

    session = LhmSession(discover=unavailable_discovery)

    assert session.snapshot() == ([], "Libre Hardware Monitor indisponível")
    assert session.snapshot() == ([], "Libre Hardware Monitor indisponível")
    assert attempts == ["discover"]


def test_periodic_unavailable_reads_do_not_repeat_the_powershell_wmi_fallback():
    wmi_attempts = []

    def unavailable_wmi():
        wmi_attempts.append("powershell")
        return [], "Libre Hardware Monitor indisponível"

    session = LhmSession(discover=lambda: query_lhm(
        bridge_query=lambda: ([], ""), rest_query=lambda: ([], ""),
        wmi_query=unavailable_wmi, lhm_installed=lambda: False,
    ))

    for _ in range(4):
        session.snapshot()

    assert wmi_attempts == ["powershell"]


def test_unavailable_sensor_state_remains_until_a_new_session_is_created():
    responses = iter([
        ([], "Libre Hardware Monitor indisponível"),
        ([{"name": "NVMe", "type": "Temperature", "value": 40}], "Libre Hardware Monitor (WMI)"),
    ])
    discover = lambda: next(responses)

    first_run = LhmSession(discover=discover)
    assert first_run.snapshot()[1] == "Libre Hardware Monitor indisponível"
    assert first_run.snapshot()[1] == "Libre Hardware Monitor indisponível"

    restarted_run = LhmSession(discover=discover)
    assert restarted_run.snapshot()[1] == "Libre Hardware Monitor (WMI)"


def test_available_rest_source_is_polled_without_wmi_or_blocking_the_ui_path():
    clock = [0.0]
    rest_calls = []

    def rest_snapshot():
        rest_calls.append(clock[0])
        return ([{"name": "NVMe", "type": "Temperature", "value": 41}], "Libre Hardware Monitor (REST local)")

    session = LhmSession(
        discover=rest_snapshot, rest_query=rest_snapshot,
        clock=lambda: clock[0], rest_interval=5.0,
    )

    assert session.snapshot()[0][0]["value"] == 41
    clock[0] = 5.0
    assert session.snapshot()[0][0]["value"] == 41
    assert rest_calls == [0.0, 5.0]

from pathlib import Path

from sensor_bridge import bridge_executable, parse_bridge_payload, query_sensor_bridge


def test_bridge_payload_keeps_only_declared_sensor_fields():
    sensors = parse_bridge_payload('{"version":1,"sensors":[{"name":"CPU Package","type":"Temperature","value":52.5,"parent":"CPU","private":"ignored"}]}')
    assert sensors == [{"name": "CPU Package", "type": "Temperature", "value": 52.5, "parent": "CPU"}]


def test_bridge_payload_rejects_unknown_contract():
    try:
        parse_bridge_payload('{"version":2,"sensors":[]}')
    except ValueError:
        pass
    else:
        raise AssertionError("expected invalid bridge payload")


def test_bridge_reports_not_packaged_without_executable(tmp_path: Path):
    assert bridge_executable(tmp_path) is None
    assert query_sensor_bridge(executable=tmp_path / "missing.exe") == ([], "SensorBridge interno indisponível")

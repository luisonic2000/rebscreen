from types import SimpleNamespace
from network_telemetry import NetworkRates


def sample(received, sent): return SimpleNamespace(bytes_recv=received, bytes_sent=sent)


def test_network_rates_use_delta_of_two_samples_for_active_interface():
    rates = NetworkRates(); stats={"Ethernet": SimpleNamespace(isup=True)}
    assert rates.read({"Ethernet": sample(100, 50)}, stats, 10) == (0.0, 0.0)
    assert rates.read({"Ethernet": sample(1124, 562)}, stats, 12) == (512.0, 256.0)


def test_network_rates_ignore_virtual_interface_and_handle_zero_traffic():
    rates = NetworkRates(); stats={"vEthernet": SimpleNamespace(isup=True), "Wi-Fi": SimpleNamespace(isup=True)}
    rates.read({"vEthernet": sample(9999,9999), "Wi-Fi": sample(10,20)}, stats, 1)
    assert rates.read({"vEthernet": sample(19999,19999), "Wi-Fi": sample(10,20)}, stats, 2) == (0.0, 0.0)


def test_network_rates_are_unavailable_without_active_physical_interface():
    assert NetworkRates().read({"Loopback": sample(1,1)}, {"Loopback": SimpleNamespace(isup=True)}, 1) == (None, None)

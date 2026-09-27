from hardware_status import explain_serial_error


def test_permission_error_explains_that_the_port_is_busy():
    message = explain_serial_error(PermissionError(13, "Acesso negado."))
    assert "ocupada" in message


def test_missing_port_has_a_concrete_recovery_message():
    assert "não está disponível" in explain_serial_error(OSError("could not open port 'COM9'"))

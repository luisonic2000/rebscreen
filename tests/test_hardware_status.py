from hardware_status import explain_serial_error


def test_permission_error_explains_that_the_port_is_busy():
    message = explain_serial_error(PermissionError(13, "Acesso negado."))
    assert "ocupada" in message


def test_missing_port_has_a_concrete_recovery_message():
    assert "não está disponível" in explain_serial_error(OSError("could not open port 'COM9'"))


def test_serial_errors_use_selected_language_and_the_actual_port():
    message = explain_serial_error(PermissionError(13, "Access is denied for COM9"), language="zh-CN")

    assert "COM9" in message
    assert "ocupada" not in message

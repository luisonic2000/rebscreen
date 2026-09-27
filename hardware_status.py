"""User-facing serial diagnostics that do not open or write to a device."""
from __future__ import annotations


def explain_serial_error(error: BaseException) -> str:
    message = str(error).lower()
    if "acesso negado" in message or "permissionerror" in message or "access is denied" in message:
        return "COM3 está ocupada por outro programa. Feche o software que usa a tela e tente novamente."
    if "could not open port" in message or "file not found" in message:
        return "A porta selecionada não está disponível. Confira o cabo e a porta COM."
    return f"Não foi possível acessar a porta: {error}"

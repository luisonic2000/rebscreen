"""Per-executable local instance coordination for Windows."""
from __future__ import annotations

import ctypes
import os
import socket
import sys
import threading
import zlib


def executable_identity(executable: str | None = None) -> str:
    value = executable or (sys.executable if getattr(sys, "frozen", False) else __file__)
    return os.path.normcase(os.path.abspath(value))


def ipc_port(identity: str) -> int:
    return 43000 + (zlib.crc32(identity.encode("utf-8")) % 1000)


class SingleInstance:
    def __init__(self, identity: str | None = None) -> None:
        self.identity = executable_identity(identity)
        self.port = ipc_port(self.identity)
        self.handle = None
        self.server = None

    def acquire(self) -> bool:
        if os.name != "nt":
            return True
        name = "Local\\Rebscreen-" + format(zlib.crc32(self.identity.encode("utf-8")), "08x")
        self.handle = ctypes.windll.kernel32.CreateMutexW(None, False, name)
        if ctypes.GetLastError() == 183:
            self.notify_existing()
            return False
        return True

    def notify_existing(self) -> None:
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=0.75) as client:
                client.sendall(b"show")
        except OSError:
            pass

    def listen(self, callback) -> None:
        def serve():
            try:
                self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.server.bind(("127.0.0.1", self.port)); self.server.listen(1)
                while self.server:
                    client, _ = self.server.accept()
                    with client:
                        if client.recv(16) == b"show": callback()
            except OSError:
                pass
        threading.Thread(target=serve, name="rebscreen-single-instance", daemon=True).start()

    def close(self) -> None:
        if self.server:
            self.server.close(); self.server = None
        if self.handle:
            ctypes.windll.kernel32.CloseHandle(self.handle); self.handle = None

#!/usr/bin/env python3
"""Test-only UNIX socket peer outside the Landlock domain."""

import socket
import threading
import time


def serve(sock: socket.socket) -> None:
    while True:
        try:
            conn, _ = sock.accept()
        except OSError:
            return
        conn.close()


path = "/tmp/llm-s6-path.sock"
try:
    import os
    os.unlink(path)
except FileNotFoundError:
    pass
path_socket = socket.socket(socket.AF_UNIX)
path_socket.bind(path)
path_socket.listen()
abstract_socket = socket.socket(socket.AF_UNIX)
abstract_socket.bind("\0llm-s6-abstract")
abstract_socket.listen()
threading.Thread(target=serve, args=(path_socket,), daemon=True).start()
threading.Thread(target=serve, args=(abstract_socket,), daemon=True).start()
print("ready", flush=True)
while True:
    time.sleep(60)

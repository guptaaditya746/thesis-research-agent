#!/usr/bin/env python3
"""Report Landlock escape checks without printing secret contents."""

from __future__ import annotations

import os
import socket
import sys


def report_file(label: str, path: str, count_bytes: bool = False) -> None:
    accessible = os.access(path, os.R_OK)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
    except OSError as exc:
        print(f"{label}: test-r={'readable' if accessible else 'denied'}; open=denied ({exc.__class__.__name__})")
        return
    try:
        size = 0
        if count_bytes:
            while True:
                part = os.read(fd, 65536)
                if not part:
                    break
                size += len(part)
            print(f"{label}: test-r={'readable' if accessible else 'denied'}; open=readable; bytes={size}")
        else:
            size = os.fstat(fd).st_size
            print(f"{label}: test-r={'readable' if accessible else 'denied'}; open=readable; bytes={size}")
    finally:
        os.close(fd)


for spec in sys.argv[1:]:
    label, raw_pid = spec.split("=", 1)
    try:
        os.kill(int(raw_pid), 0)
        print(f"kill-0 {label}: allowed")
    except PermissionError:
        print(f"kill-0 {label}: denied")
    except ProcessLookupError:
        print(f"kill-0 {label}: absent")

litellm_pid = next((int(s.split("=", 1)[1]) for s in sys.argv[1:] if s.startswith("litellm=")), None)
if litellm_pid is not None:
    report_file("proc-environ", f"/proc/{litellm_pid}/environ", count_bytes=True)

home = os.environ.get("HOME", "")
repo = "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent"
for label, path in (
    ("ssh-key", os.path.join(home, ".ssh/id_ed25519_webis_tunnel")),
    ("repo-env", os.path.join(repo, "related/final-final-llm-setup/.env")),
    ("git-credentials", os.path.join(home, ".git-credentials")),
):
    report_file(label, path)

print(f"SSH_AUTH_SOCK_count={int('SSH_AUTH_SOCK' in os.environ)}")
try:
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"udp-sendto={udp.sendto(b'x', ('1.1.1.1', 53))} bytes sent")
    udp.close()
except OSError as exc:
    print(f"udp-sendto=denied ({exc.__class__.__name__})")

for label, address in (("abstract", "\0llm-s6-abstract"), ("pathname", "/tmp/llm-s6-path.sock")):
    client = socket.socket(socket.AF_UNIX)
    try:
        client.connect(address)
        print(f"unix-{label}=allowed")
    except OSError as exc:
        print(f"unix-{label}=denied ({exc.__class__.__name__})")
    finally:
        client.close()

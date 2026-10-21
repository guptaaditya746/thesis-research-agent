from __future__ import annotations

import http.server
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "omen-tunnels"
LOADER = SourceFileLoader("omen_tunnels", str(SCRIPT))
SPEC = spec_from_loader("omen_tunnels", LOADER)
assert SPEC
tunnels = module_from_spec(SPEC)
SPEC.loader.exec_module(tunnels)


def test_harness_ui_routes_from_laptop_to_compute(monkeypatch):
    monkeypatch.setattr(tunnels, "GATEWAY_PORT_OFFSET", 1000)

    assert tunnels.forward_args("gateway", ["harness-ui"]) == [
        "-L", "127.0.0.1:25173:127.0.0.1:25173"
    ]
    assert tunnels.forward_args("compute", ["harness-ui"]) == [
        "-R", "127.0.0.1:25173:127.0.0.1:8080"
    ]
    assert tunnels.roles_for("laptop", ["harness-ui"]) == [
        ("gateway", tunnels.GATEWAY)
    ]


def test_harness_ui_uses_offset_gateway_port(monkeypatch):
    monkeypatch.setattr(tunnels, "GATEWAY_PORT_OFFSET", 0)

    assert tunnels.forward_args("compute", ["harness-ui"]) == [
        "-R", "127.0.0.1:24173:127.0.0.1:8080"
    ]


def test_all_includes_harness_ui():
    assert "harness-ui" in tunnels.selected_services(["all"])


# --- the failure modes of the harness-ui route (README, "Web app": troubleshooting) ---


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def fake_ssh(monkeypatch, tmp_path):
    """No ssh and no network: runtime dir in tmp_path, every ssh call recorded and reported as up."""
    calls = []
    monkeypatch.setattr(tunnels, "runtime_dir", lambda: tmp_path)

    def run(cmd, *args, **kwargs):
        calls.append(cmd)
        sock = Path(cmd[cmd.index("-S") + 1])
        if "-M" in cmd:  # the master leaves its control socket behind
            sock.touch()
        elif "exit" in cmd:
            sock.unlink(missing_ok=True)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(tunnels.subprocess, "run", run)
    monkeypatch.setattr(tunnels, "active", lambda sock, target: sock.exists())
    return calls


def _main(monkeypatch, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["omen-tunnels", *argv])
    return tunnels.main()


def test_compute_start_refuses_when_no_web_app_listens_here(monkeypatch, fake_ssh):
    monkeypatch.setattr(tunnels, "accepts", lambda port, *a, **k: False)
    with pytest.raises(RuntimeError) as err:
        _main(monkeypatch, "compute", "start", "harness-ui")
    message = str(err.value)
    assert "127.0.0.1:8080" in message and socket.gethostname() in message
    assert "srun --jobid $JOB --overlap" in message and "--no-check" in message
    assert fake_ssh == []  # no hop started


def test_compute_start_no_check_records_offset_and_prints_gateway_port(monkeypatch, fake_ssh, tmp_path, capsys):
    monkeypatch.setattr(tunnels, "GATEWAY_PORT_OFFSET", 1000)
    monkeypatch.setattr(tunnels, "accepts", lambda *a, **k: pytest.fail("--no-check must not probe"))
    assert _main(monkeypatch, "compute", "start", "harness-ui", "--no-check") == 0
    assert ["-R", "127.0.0.1:25173:127.0.0.1:8080"] == fake_ssh[0][fake_ssh[0].index("-R"):][:2]
    state = json.loads((tmp_path / "compute.json").read_text())
    assert state["gateway_port_offset"] == 1000
    out = capsys.readouterr().out
    assert "offset 1000" in out and "gateway port 25173 -> 127.0.0.1:8080" in out


def test_compute_start_checks_the_web_app_only_for_harness_ui(monkeypatch, fake_ssh):
    probed = []
    monkeypatch.setattr(tunnels, "accepts", lambda port, *a, **k: probed.append(port) or True)
    assert _main(monkeypatch, "compute", "start", "tracing") == 0
    assert probed == []
    assert _main(monkeypatch, "compute", "stop") == 0
    assert _main(monkeypatch, "compute", "start", "harness-ui") == 0
    assert probed == [8080]


def test_both_ends_print_the_same_gateway_port(monkeypatch):
    monkeypatch.setattr(tunnels, "GATEWAY_PORT_OFFSET", 1000)
    laptop = "\n".join(tunnels.ready_lines("laptop", ["harness-ui"]))
    compute = "\n".join(tunnels.ready_lines("compute", ["harness-ui"]))
    assert "http://127.0.0.1:25173" in laptop and "gateway port 25173" in laptop
    assert "gateway port 25173" in compute
    monkeypatch.setattr(tunnels, "GATEWAY_PORT_OFFSET", 0)
    assert "gateway port 24173" in "\n".join(tunnels.ready_lines("compute", ["harness-ui"]))


def test_start_refuses_running_tunnels_with_another_offset(monkeypatch, fake_ssh):
    monkeypatch.setattr(tunnels, "GATEWAY_PORT_OFFSET", 1000)
    assert _main(monkeypatch, "laptop", "start", "harness-ui") == 0
    monkeypatch.setattr(tunnels, "GATEWAY_PORT_OFFSET", 0)
    with pytest.raises(RuntimeError, match="offset 1000 are running; this command uses 0"):
        _main(monkeypatch, "laptop", "start", "harness-ui")


def test_status_prints_offset_and_warns_on_mismatch(monkeypatch, fake_ssh, capsys):
    monkeypatch.setattr(tunnels, "GATEWAY_PORT_OFFSET", 1000)
    assert _main(monkeypatch, "laptop", "start", "harness-ui") == 0
    capsys.readouterr()
    monkeypatch.setattr(tunnels, "GATEWAY_PORT_OFFSET", 0)
    assert _main(monkeypatch, "laptop", "status") == 0
    out = capsys.readouterr().out
    assert "Gateway port offset: 1000; gateway ports: harness-ui 25173" in out
    assert "Warning: started with offset 1000, this command uses 0" in out


def test_listener_ports_name_where_harness_ui_listens(monkeypatch):
    monkeypatch.setattr(tunnels, "GATEWAY_PORT_OFFSET", 1000)
    assert tunnels.listener_ports("gateway", ["harness-ui"]) == ["25173 on laptop"]
    assert tunnels.listener_ports("compute", ["harness-ui"]) == ["25173 on gateway"]


def test_accepts_a_loopback_listener():
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        assert tunnels.accepts(server.getsockname()[1])
    assert not tunnels.accepts(_free_port())


class _Server:
    """A loopback HTTP server: `routes` maps a path to (status, body); `close_silently` answers nothing."""

    def __init__(self, routes=None, close_silently=False):
        routes = routes or {}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                if close_silently:
                    self.close_connection = True
                    return
                status, body = routes.get(self.path, (404, "{}"))
                data = body.encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.httpd = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]

    def __enter__(self):
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()


def test_check_reports_the_guards_400_body(capsys):
    detail = json.dumps({"detail": "Host 'gw.example:25173' is not served"})
    with _Server({"/": (400, detail), "/api/health": (400, detail)}) as server:
        assert tunnels.check_ui(server.port, timeout=5) == 1
    out = capsys.readouterr().out
    assert f"http://127.0.0.1:{server.port}/: HTTP 400" in out
    assert "guard refused it" in out and "is not served" in out


def test_check_passes_when_the_web_app_answers(capsys):
    with _Server({"/": (200, "<html></html>"), "/api/health": (200, '{"ok": true}')}) as server:
        assert tunnels.check_ui(server.port, timeout=5) == 0
    assert "the web app answers" in capsys.readouterr().out


def test_check_flags_another_server_on_the_port(capsys):
    with _Server({"/": (200, "<html>static</html>")}) as server:
        assert tunnels.check_ui(server.port, timeout=5) == 1
    assert "probably not 'webapp serve'" in capsys.readouterr().out


def test_check_reports_refused_and_silent_ends(capsys):
    assert tunnels.check_ui(_free_port(), timeout=5) == 1
    assert "connection refused" in capsys.readouterr().out
    with _Server(close_silently=True) as server:
        assert tunnels.check_ui(server.port, timeout=5) == 1
    assert "closed without an answer" in capsys.readouterr().out


@pytest.mark.skipif(os.name == "nt" or not shutil.which("python3"), reason="the wrapper is a POSIX sh script")
def test_external_wrapper_runs_the_sibling_script_with_offset(tmp_path):
    stale = tmp_path / "omen-tunnels"
    stale.write_text("#!/bin/sh\necho stale\n")
    stale.chmod(0o755)
    env = {**os.environ, "PATH": f"{tmp_path}{os.pathsep}{os.environ.get('PATH', '')}"}
    out = subprocess.run(["sh", str(SCRIPT.parent / "omen-tunnels-external"), "list"], env=env,
                         capture_output=True, text=True, check=True).stdout
    assert "stale" not in out and "25173" in out

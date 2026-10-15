from __future__ import annotations

from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path


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

"""`evqa doctor` with fake checks, the `paper write` freeze guard and the `eval --domain` check. No network."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from evqa import cli, doctor, paperwriter, paths


# ---------- doctor ----------

def test_doctor_gateway_ok_and_down(monkeypatch):
    monkeypatch.setenv("LITELLM_BASE_URL", "http://gw:9/v1/")
    monkeypatch.setenv("LITELLM_MASTER_KEY", "k")
    seen = []
    assert doctor.check_gateway(get=lambda u, k, t: seen.append((u, k)) or 200)[1] == "ok"
    assert seen == [("http://gw:9/v1/models", "k")]

    def down(*_):
        raise OSError("refused")
    assert doctor.check_gateway(get=down)[1] == "FAIL"
    monkeypatch.delenv("LITELLM_MASTER_KEY")
    assert doctor.check_gateway(get=lambda *_: 200)[1] == "FAIL"


def test_doctor_claude_slurm_disk_git(monkeypatch):
    assert doctor.check_claude(run=lambda m, t: '{"is_error": false, "result": "ok"}')[1] == "ok"
    assert doctor.check_claude(run=lambda m, t: '{"is_error": true, "result": "no login"}')[1] == "FAIL"
    assert doctor.check_claude(run=lambda m, t: "not json")[1] == "FAIL"
    assert doctor.slurm_hours("1-02:30:00") == 26.5 and doctor.slurm_hours("45:00") == 0.75
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)
    assert doctor.check_slurm(2, squeue=lambda j: "9:00:00") is None
    monkeypatch.setenv("SLURM_JOB_ID", "77")
    assert doctor.check_slurm(2, squeue=lambda j: "1:10:00")[1] == "warn"
    assert doctor.check_slurm(2, squeue=lambda j: "3:00:00")[1] == "ok"
    assert doctor.check_disk(Path("/nonexistent/runs"), free=lambda p: 10**9)[1] == "warn"
    assert doctor.check_disk(Path("/"), free=lambda p: 5 * 10**9)[1] == "ok"
    assert doctor.check_git(status=lambda: " M a.py\n")[1] == "warn"
    assert doctor.check_git(status=lambda: "")[1] == "ok"


def test_doctor_picks_backends_from_config_and_exits_1_on_fail(tmp_path, capsys):
    cfg = tmp_path / "c.yaml"
    cfg.write_text(yaml.safe_dump({"llm": {"backend": "qwen"}, "steps": {"spec": {"backend": "claude",
                                                                                   "model": "claude-x"}}}))
    assert doctor.backends_of(cfg) == {"qwen", "claude"} and doctor.backends_of(None) == {"qwen"}
    calls = []
    fake = {k: (lambda k=k: calls.append(k) or (k, "ok", "")) for k in ("gateway", "claude", "slurm", "disk", "git")}
    a = cli.argparse.Namespace(config=None, backend="claude", claude=False, min_hours=2.0)
    assert doctor.main(a, checks=fake) == 0 and calls == ["claude", "slurm", "disk", "git"]
    fake["git"] = lambda: ("git", "warn", "dirty")
    fake["gateway"] = lambda: ("gateway", "FAIL", "down")
    a.backend = "qwen"
    assert doctor.main(a, checks=fake) == 1
    out = capsys.readouterr().out
    assert "FAIL  gateway" in out and "warn  git" in out


# ---------- paper write guard ----------

def _no_write(monkeypatch):
    called = []
    monkeypatch.setattr(paperwriter, "write_domain", lambda *a, **k: called.append(a) or [])
    return called


def test_paper_write_refuses_frozen_domain(monkeypatch, capsys):
    called = _no_write(monkeypatch)
    for d in ("medical", "medical_holdout"):
        assert (paths.domain_dir(d) / "FROZEN").is_file()
        assert cli.main(["paper", "write", d]) == 1
    assert called == [] and "--force" in capsys.readouterr().err
    assert cli.main(["paper", "write", "medical", "--force"]) == 0 and len(called) == 1


def test_paper_write_refuses_tracked_paper(tmp_path, monkeypatch):
    called = _no_write(monkeypatch)
    (tmp_path / "seed" / "dom" / "papers" / "P1").mkdir(parents=True)
    out = tmp_path / "dataset" / "dom" / "P1" / "paper.md"
    monkeypatch.setattr(cli, "domain_dir", lambda d: tmp_path / "seed" / d)
    monkeypatch.setattr(paths, "paper_file", lambda d, p: tmp_path / "dataset" / d / p / "paper.md")
    monkeypatch.setattr(cli, "_tracked", lambda ps: list(ps))
    assert cli.main(["paper", "write", "dom"]) == 0            # no paper.md yet: nothing to protect
    out.parent.mkdir(parents=True)
    out.write_text("x")
    assert cli.main(["paper", "write", "dom"]) == 1            # exists and tracked
    monkeypatch.setattr(cli, "_tracked", lambda ps: [])
    assert cli.main(["paper", "write", "dom"]) == 0            # exists, untracked (a fresh draft)
    assert len(called) == 2


# ---------- eval --domain ----------

def test_eval_domain_comes_from_config(tmp_path, monkeypatch):
    from evqa.eval import prism
    got = []
    monkeypatch.setattr(prism, "score_run", lambda run_dir, domain: got.append(domain) or {"totals": {}})
    (tmp_path / "config.yaml").write_text(yaml.safe_dump({"domain": "medical_holdout"}))
    assert cli.main(["eval", str(tmp_path)]) == 0
    assert cli.main(["eval", str(tmp_path), "--domain", "medical_holdout"]) == 0
    with pytest.raises(SystemExit, match="disagrees"):
        cli.main(["eval", str(tmp_path), "--domain", "medical"])
    assert got == ["medical_holdout", "medical_holdout"]
    with pytest.raises(SystemExit, match="pass --domain"):
        cli.main(["eval", str(tmp_path / "nope")])

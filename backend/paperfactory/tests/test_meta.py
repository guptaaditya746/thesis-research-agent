"""Meta files (#8): outputs remember what they were made from; restarts redo outdated steps and say why."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from paperfactory import cli, config, meta, repair
from paperfactory.tests.test_offline import PILOT


def law(tmp_path: Path, **kw) -> config.Settings:
    (tmp_path / "w.json").write_text(json.dumps(PILOT))
    return config.Settings("law", "argument", papers=3, out=str(tmp_path / "run"),
                           world_file=str(tmp_path / "w.json"), slot_dir=str(tmp_path / "slots"), leak_trials=0, **kw)


def test_world_is_made_again_when_its_inputs_change(tmp_path: Path, capsys) -> None:
    s = law(tmp_path)
    cli.run(s, ["world"])
    m = meta.read(s.out_dir / "world.json")
    assert m["inputs"] and m["record"]["git"] and m["output"]
    cli.run(s, ["world"])
    assert "settings changed" not in capsys.readouterr().out                # same inputs: kept
    w = dict(PILOT, papers={k: dict(v, thesis=v["thesis"] + " (v2)") for k, v in PILOT["papers"].items()})
    (tmp_path / "w.json").write_text(json.dumps(w))
    cli.run(s, ["world"])
    out = capsys.readouterr().out
    assert "settings changed (world_file)" in out
    assert (s.out_dir / "world.json.stale-1").is_file() and (s.out_dir / "world.meta.json.stale-1").is_file()
    assert "(v2)" in (s.out_dir / "world.json").read_text()


def test_output_without_meta_stops_the_run_unless_allow_mixed(tmp_path: Path) -> None:
    s = law(tmp_path)
    cli.run(s, ["world"])
    meta.path_of(s.out_dir / "world.json").unlink()
    with pytest.raises(meta.MixedSettings, match="no meta file"):
        cli.run(s, ["world"])
    cli.run(s, ["world"], allow_mixed=True)
    assert not list(s.out_dir.glob("*.stale-*"))


def test_paper_written_then_checked(tmp_path: Path) -> None:
    p = tmp_path / "work" / "P1" / "paper.md"
    p.parent.mkdir(parents=True)
    p.write_text("as written")
    wi, ci = {"writer": "a"}, {"verifier": "v"}
    meta.write_done(p, wi)
    assert not meta.write_stale(p, wi, False, "w")
    assert meta.write_stale(p, {"writer": "b"}, False, "w")
    assert meta.check_state(p, ci, False, "c") == ("todo", [])
    # the check step: raw copy, repaired paper, repairs log; a stop before check_done must not redo the writing
    (p.parent / "paper.raw.md").write_text("as written")
    p.write_text("repaired")
    (p.parent / "paper.repairs.json").write_text("{}")
    assert not meta.write_stale(p, wi, False, "w")
    assert meta.check_state(p, ci, False, "c")[0] == "redo"                 # paper.md changed, check not recorded
    meta.check_done(p, ci)
    assert meta.check_state(p, ci, False, "c") == ("done", [])
    assert meta.check_state(p, {"verifier": "w"}, False, "c") == ("redo", ["verifier"])
    assert not meta.write_stale(p, wi, False, "w")                          # check_done kept the write part


def test_check_step_restarts_from_the_paper_as_written(tmp_path: Path, monkeypatch) -> None:
    s = law(tmp_path)
    cli.run(s, ["world", "seed", "materials"])
    pid = next(iter(PILOT["papers"]))
    work = s.out_dir / "work" / pid
    work.mkdir(parents=True)
    (work / "paper.md").write_text("as written")
    template = s.out_dir / "template_argument_6p"
    for p in PILOT["papers"]:
        if p != pid:
            continue
        meta.write_done(work / "paper.md", cli.write_inputs(s, pid, template))
    seen = []

    def fake_repair(self, p, redo):
        seen.append((p, (work / "paper.md").read_text()))
        (work / "paper.raw.md").write_text((work / "paper.md").read_text())
        (work / "paper.md").write_text(f"repaired {len(seen)}")
        (work / "paper.repairs.json").write_text(json.dumps({"status": "repaired"}))
        return {"pid": p, "status": "repaired"}
    monkeypatch.setattr(repair.Checker, "repair_paper", fake_repair)
    cli.run(s, ["check"])
    cli.run(s, ["check"])
    assert len(seen) == 1                                                   # same settings: not checked again
    s2 = law(tmp_path, models={"verifier": "claude-other", "default": "claude-haiku-5-5"})
    cli.run(s2, ["check"])
    assert seen[-1] == (pid, "as written")                                  # restarted from paper.raw.md
    assert (work / "paper.repairs.json.stale-1").is_file()


def test_papers_with_different_settings_are_not_mixed(tmp_path: Path) -> None:
    a = {"inputs": {"writer": "x"}, "check": {"world": "1"}}
    b = {"inputs": {"writer": "y"}, "check": {"world": "1"}}
    keys = {"inputs": ["writer"], "check": ["world"]}
    assert meta.same_settings({"P1": a, "P2": dict(a)}, keys, False, "eval") == []
    with pytest.raises(meta.MixedSettings, match="2 different settings"):
        meta.same_settings({"P1": a, "P2": b}, keys, False, "eval")
    with pytest.raises(meta.MixedSettings, match="no meta"):
        meta.same_settings({"P1": a, "P2": None}, keys, False, "eval")
    assert len(meta.same_settings({"P1": a, "P2": b, "P3": None}, keys, True, "eval")) == 2


def test_check_redo_keeps_the_writers_meta(tmp_path: Path) -> None:
    """Review finding 1: setting paper.repairs.json aside must not take paper.meta.json along (paid rewrite)."""
    work = tmp_path / "work" / "P1"
    p = work / "paper.md"
    work.mkdir(parents=True)
    p.write_text("as written")
    meta.write_done(p, {"writer": "a"})
    (work / "paper.raw.md").write_text("as written")
    p.write_text("repaired")
    (work / "paper.repairs.json").write_text("{}")
    meta.check_done(p, {"world": 1})
    assert meta.check_state(p, {"world": 2}, False, "c")[0] == "redo"
    meta.set_aside(work / "paper.repairs.json")
    assert (work / "paper.meta.json").is_file() and not list(work.glob("paper.meta.json.stale-*"))
    p.write_text("as written")
    (work / "paper.repairs.json").write_text("{}")
    meta.check_done(p, {"world": 2})
    assert not meta.write_stale(p, {"writer": "a"}, False, "w")
    assert meta.read(p)["inputs"]                                  # eval's same_settings still sees the writer part


def test_each_paper_gets_its_meta_as_soon_as_it_is_written(tmp_path: Path, monkeypatch) -> None:
    """Review finding 2: a run stopped in the middle of the write step keeps the papers already written."""
    from paperfactory import write
    s = law(tmp_path)
    cli.run(s, ["world", "seed", "materials"])
    first, *rest = list(PILOT["papers"])

    def fake_write(s_, pid, template, attempt=1):
        if pid != first:
            raise KeyboardInterrupt                                     # the run stops here
        p = s_.out_dir / "work" / pid / "paper.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("written")
        return {"pid": pid, "status": "ok"}
    monkeypatch.setattr(write, "write_one", fake_write)
    monkeypatch.setattr(write, "pmap_papers", lambda fn, pids: [fn(p) for p in pids])
    with pytest.raises(KeyboardInterrupt):
        cli.run(s, ["write"])
    paper = s.out_dir / "work" / first / "paper.md"
    assert meta.read(paper)["inputs"]
    assert not meta.write_stale(paper, cli.write_inputs(s, first, s.out_dir / "template_argument_6p"), False, "w")


def test_a_kept_legacy_paper_is_not_rewritten_after_its_check(tmp_path: Path) -> None:
    """Review finding 2b: --allow-mixed keeps a paper without meta; its check meta must not make it look changed."""
    work = tmp_path / "work" / "P1"
    p = work / "paper.md"
    work.mkdir(parents=True)
    p.write_text("legacy")
    assert not meta.write_stale(p, {"writer": "a"}, True, "w")
    (work / "paper.raw.md").write_text("legacy")
    (work / "paper.repairs.json").write_text("{}")
    meta.check_done(p, {"world": 1})
    assert not meta.write_stale(p, {"writer": "a"}, True, "w")              # still legacy: kept, not rewritten
    with pytest.raises(meta.MixedSettings):
        meta.write_stale(p, {"writer": "a"}, False, "w")                    # and without the flag: a clear stop

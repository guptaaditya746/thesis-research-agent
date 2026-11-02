"""`freeze`: a pack is frozen only when it loads, passes `pack check`, has a provenance entry for each of its files
and its words were not written from the recipe; FROZEN.json records the hashes and the tag command is printed,
never run."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from evidence.pack import load_pack
from jsonio import sha256_hex
from packbuilder.freeze import freeze

FIXTURE = Path(__file__).resolve().parents[2] / "evidence" / "tests" / "fixtures" / "drugtoy"


def frozen_ready_pack(tmp_path: Path, words_files_read: list[str] | None = None,
                      drop: str | None = None) -> Path:
    """A copy of the drugtoy fixture pack (pack, words, recipe, questions, protocols) whose provenance.json has the
    `pack`, `words` and `generator` entries freeze asks for; `drop` leaves one of them out."""
    pack = tmp_path / "drugtoy"
    shutil.copytree(FIXTURE, pack)
    prov: dict[str, Any] = {
        "source": "test",
        "pack": {"by": "packbuilder propose"},
        "words": {"by": "packbuilder propose",
                  "files_read": words_files_read or ["manifest.json", "papers/T001.md"]},
        "generator": {"source": "written by hand for the tests"},
    }
    prov.pop(drop, None)
    (pack / "provenance.json").write_text(json.dumps(prov, indent=2), encoding="utf-8")
    return pack


def no_git(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Record any subprocess start: freeze must not run git (it prints the tag command)."""
    started: list[Any] = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: started.append(a) or (_ for _ in ()).throw(
        AssertionError("freeze started a process")))
    return started


def test_freeze_refuses_words_written_from_generator(tmp_path: Path) -> None:
    pack = frozen_ready_pack(tmp_path, words_files_read=["generator.yaml"])
    with pytest.raises(ValueError, match="generator.yaml"):
        freeze(pack)
    assert not (pack / "FROZEN.json").exists()


def test_freeze_records_hashes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    started = no_git(monkeypatch)
    pack = frozen_ready_pack(tmp_path)
    out = freeze(pack)
    assert set(out["files"]) >= {"pack.yaml", "words.yaml", "provenance.json"}
    assert {"generator.yaml", "questions.yaml", "protocols/drugtoy-response.yaml"} <= set(out["files"])
    lf = (pack / "provenance.json").read_bytes().replace(b"\r\n", b"\n")       # line ends as LF, as Pack.sha256
    assert out["files"]["provenance.json"] == sha256_hex(lf)
    assert out["pack_sha256"] == load_pack("drugtoy", root=tmp_path).sha256
    assert out["recipe_sha256"] == sha256_hex((pack / "generator.yaml").read_bytes().replace(b"\r\n", b"\n"))
    assert json.loads((pack / "FROZEN.json").read_text(encoding="utf-8")) == out
    assert "git tag ev4-pack-drugtoy-v1" in capsys.readouterr().out
    assert started == []


def test_freeze_needs_a_provenance_entry_for_each_file(tmp_path: Path) -> None:
    for key, file in (("words", "words.yaml"), ("pack", "pack.yaml"), ("generator", "generator.yaml")):
        with pytest.raises(ValueError, match=f"no provenance entry for {file}"):
            freeze(frozen_ready_pack(tmp_path / key, drop=key))


def test_freeze_reads_the_legacy_files_entries(tmp_path: Path) -> None:
    pack = frozen_ready_pack(tmp_path)
    prov = json.loads((pack / "provenance.json").read_text(encoding="utf-8"))
    del prov["pack"], prov["words"]
    prov["files"] = {"pack.yaml": "by hand", "words.yaml": "by hand"}
    (pack / "provenance.json").write_text(json.dumps(prov), encoding="utf-8")
    assert freeze(pack)["files"]["pack.yaml"]


def test_freeze_runs_pack_check(tmp_path: Path) -> None:
    pack = frozen_ready_pack(tmp_path)
    (pack / "protocols" / "broken.yaml").write_text("id: broken\ndomain: drugtoy\n", encoding="utf-8")
    with pytest.raises(ValueError, match="broken.yaml"):
        freeze(pack)


def test_a_frozen_pack_is_not_frozen_again_with_other_files(tmp_path: Path) -> None:
    pack = frozen_ready_pack(tmp_path)
    first = freeze(pack)
    assert freeze(pack) == first                          # the same files: nothing changes
    (pack / "words.yaml").write_text((pack / "words.yaml").read_text(encoding="utf-8") + "\n# edited\n",
                                     encoding="utf-8")
    with pytest.raises(ValueError, match="already frozen"):
        freeze(pack)


def test_freeze_command(tmp_path: Path, capsys) -> None:
    from packbuilder.cli import main
    assert main(["freeze", str(frozen_ready_pack(tmp_path / "ok"))]) == 0
    assert "git tag ev4-pack-drugtoy-v1" in capsys.readouterr().out
    assert main(["freeze", str(frozen_ready_pack(tmp_path / "bad", words_files_read=["../generator.yaml"]))]) == 2
    assert "generator.yaml" in capsys.readouterr().err

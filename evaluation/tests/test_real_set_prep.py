"""scripts/real-set-prep.py tune-examples: labels only, no model; `evidence tune` accepts the file (tiny fixtures)."""
from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from evidence.steps import tune as T
from evaluation.wholerun import tune_split

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(__file__).resolve().parent / "data"
spec = importlib.util.spec_from_file_location("real_set_prep", ROOT / "scripts" / "real-set-prep.py")
prep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prep)

TEXT = "We test YSZ and GDC electrolytes.\n\nThe conductivity of YSZ is 0.12 S/cm at 800 C.\n\nSamples were 3 mm thick."


def sofc_set(tmp_path: Path) -> Path:
    s = tmp_path / "sofc"
    s.mkdir()
    papers = [{"id": f"p{i}", "text": TEXT + f" Paper number {i}.",
               "values": [{"value": 0.12, "unit": "S/cm", "material": "YSZ", "measure": "conductivity"}],
               "experiments": [{"id": "e1", "slots": {"material": "YSZ"}}, {"id": "e2", "slots": {"material": "GDC"}}]}
              for i in range(1, 6)]
    (s / "sofc.json").write_text(json.dumps({"papers": papers}), encoding="utf-8")
    prep.sofc_corpus(s)
    tune_split([f"p{i}" for i in range(1, 6)], 0.4, 0, s / "corpus" / "tune_split.json")
    return s


def test_sofc_examples_from_labels(tmp_path, capsys):
    s = sofc_set(tmp_path)
    out = prep.tune_examples(s)
    assert out == s / "corpus" / "tune_examples.json"
    rows = json.loads(out.read_text(encoding="utf-8"))["examples"]
    exp = [r for r in rows if r["step"] == "map_experiments"]
    assert len(exp) == 5 and exp[0]["gold"]["n"] == 2 and exp[0]["inputs"]["paper"].startswith(TEXT)
    rc = [r for r in rows if r["step"] == "recheck"]
    pos = [r for r in rc if r["gold"]["keep"] == [True]]
    neg = [r for r in rc if r["gold"]["keep"] == [False]]
    assert pos and neg and len(neg) <= len(pos)
    assert "0.12" in pos[0]["inputs"]["paragraph"] and "YSZ" in pos[0]["inputs"]["paragraph"]
    assert all("0.12" not in r["inputs"]["paragraph"] for r in neg)
    assert "no examples for claims.read_claim" in capsys.readouterr().out      # SOFC has no claim labels


def test_tune_accepts_the_file_for_each_real_step(tmp_path):
    s = sofc_set(tmp_path)
    prep.tune_examples(s)
    d = s / "corpus"
    for step in ("recheck", "map_experiments"):
        train = T.examples_of(T.SPECS[step], T.sources(step, [d], "train"))
        test = T.examples_of(T.SPECS[step], T.sources(step, [d], "test"))
        assert train and test, step
        T.check_disjoint(T.sources(step, [d], "train"), T.sources(step, [d], "test"))


def test_cochrane_has_no_sentence_labels(tmp_path, capsys):
    s = tmp_path / "cf"
    shutil.copytree(DATA / "cochrane_tiny", s)
    assert prep.tune_examples(s) is None
    out = capsys.readouterr().out
    for step in T.REAL_STEPS:
        assert f"no examples for {step}" in out
    assert not (s / "corpus" / "tune_examples.json").exists()


def test_unknown_set_folder_refused(tmp_path):
    with pytest.raises(SystemExit):
        prep.tune_examples(tmp_path)

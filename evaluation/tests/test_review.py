"""review.summarise over a synth/review.py sheet."""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from evaluation import cli, review
from synth.review import COLUMNS


def sheet(path: Path, rows: list[dict[str, str]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({**{c: "" for c in COLUMNS}, **r})
    return path


def row(fact: str, present: str = "yes", states: str = "yes", unamb: str = "yes", notes: str = "") -> dict[str, str]:
    return {"paper": "S001", "fact": fact, "present": present, "states_truth": states, "unambiguous": unamb,
            "notes": notes}


def test_summarise_counts_and_lists_a_problem(tmp_path: Path) -> None:
    csv_path = sheet(tmp_path / "r.csv", [row("S001.m1"), row("S001.m2", states="no", notes="wrong number"),
                                          row("S001.m3", present="Y", unamb="YES")])
    got = review.summarise(csv_path)
    assert got == {"rows": 3, "reviewed": 3, "present": 3, "states_truth": 2, "unambiguous": 3,
                   "problems": [{"paper": "S001", "fact": "S001.m2", "check": "states_truth", "notes": "wrong number"}]}


def test_an_empty_sheet_is_unreviewed(tmp_path: Path) -> None:
    got = review.summarise(sheet(tmp_path / "r.csv", [row("S001.m1", "", "", ""), row("S001.m2", "yes", "", "")]))
    assert (got["rows"], got["reviewed"], got["present"], got["problems"]) == (2, 0, 1, [])


def test_a_value_that_is_not_a_tick_names_the_row(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"row 3.*S001\.m2.*states_truth.*'maybe'"):
        review.summarise(sheet(tmp_path / "r.csv", [row("S001.m1"), row("S001.m2", states="maybe")]))


def test_cli_review_prints_the_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = sheet(tmp_path / "r.csv", [row("S001.m1", states="no")])
    assert cli.main(["review", "--csv", str(path)]) == 0
    out = capsys.readouterr().out
    assert "reviewed: 1" in out and "S001.m1" in out

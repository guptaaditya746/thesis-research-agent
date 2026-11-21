"""L0 (evqa/eval/dataset.py) on a hand-written correct P-med-01 paper: every fact found in its planned place, and
numbers changed on purpose are caught (plan target: at least 95%)."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from evqa.eval import dataset
from evqa.seed.brief import paper_facts

PAPER = (Path(__file__).parent / "fixtures" / "P-med-01" / "paper.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def facts() -> list[dict[str, Any]]:
    return paper_facts("medical")["P-med-01"]["facts"]


@pytest.fixture(scope="module")
def good(facts: list[dict[str, Any]]) -> dict[str, Any]:
    return dataset.check_text(PAPER, facts)


def test_correct_paper_has_every_fact_in_place(good: dict[str, Any]) -> None:
    assert good["summary"]["facts"] == 18
    assert good["summary"]["found"] == good["summary"]["in_planned_place"] == 18
    assert good["extra"] == []
    for f in good["facts"]:
        for s in f["spans"]:
            assert s["raw"].lstrip("−-") == f["value"].lstrip("-")   # the span really is the value as written
            assert not s["ambiguous"]
    kinds = {i["kind"] for i in good["ignored"]}
    assert {"year", "count", "dose", "time", "p-value"} <= kinds


def test_shared_values_go_to_the_right_row(good: dict[str, Any]) -> None:
    # R-med-01-10 (20 mg, week 24) and -11 (40 mg, week 12) are both -1.2 kg: each gets its own table cell
    spans = {f["id"]: f["spans"] for f in good["facts"]}
    assert spans["R-med-01-10"][0]["start"] != spans["R-med-01-11"][0]["start"]


def test_extra_numbers_and_near_misses(facts: list[dict[str, Any]]) -> None:
    text = PAPER.replace("Weight fell with every dose.", "Weight fell by 2.4 kg (95% CI 1.9 to 2.9) at most.")
    r = dataset.check_text(text, facts)
    assert [e["raw"] for e in r["extra"]] == ["2.4", "1.9 to 2.9"]
    assert any(i["kind"] == "CI level" for i in r["ignored"])
    # % instead of percentage points, and a lost minus sign, are near misses, not matches
    text = PAPER.replace("0.57 percentage points", "0.57%").replace("| −0.46 |", "| 0.46 |")
    r = {f["id"]: f for f in dataset.check_text(text, facts)["facts"]}
    assert r["R-med-01-02"]["status"] == "missing" and "percent" in r["R-med-01-02"]["near"][0]["why"]
    assert r["R-med-01-01"]["status"] == "missing" and r["R-med-01-01"]["near"][0]["why"] == "same number, other sign"


def test_placement(facts: list[dict[str, Any]]) -> None:
    # a text fact written only in the table, and a table fact written only in a sentence
    text = (PAPER.replace("| 10 mg | 24 | see text |", "| 10 mg | 24 | −0.57 |")
            .replace("by 0.57 percentage points with 10 mg, ", "")
            .replace("| 10 mg | 12 | −0.46 |", "| 10 mg | 12 | see text |")
            .replace("Weight fell with every dose.", "At week 12, 10 mg lowered HbA1c by 0.46 percentage points."))
    r = {f["id"]: f for f in dataset.check_text(text, facts)["facts"]}
    for rid in ("R-med-01-01", "R-med-01-02"):
        assert r[rid]["status"] == "found" and not r[rid]["in_planned_place"], rid
    assert r["R-med-01-01"]["spans"][0]["where"] == "text" and r["R-med-01-02"]["spans"][0]["where"] == "table"


def _write(d: Decimal, decimals: int, raw: str) -> str:
    """A number written the way the paper wrote the original: unicode minus, or no sign when a word gives it."""
    q = abs(d).quantize(Decimal(1).scaleb(-decimals))
    if raw[0] in "−-+":
        return ("−" if d < 0 else "") + str(q)
    return str(q) if d < 0 else "+" + str(q)   # 'lowered by X': a positive value needs an explicit '+'


def mutations(fact: dict[str, Any], others: list[dict[str, Any]], raw: str) -> dict[str, str]:
    v = Decimal(fact["value"])
    dec = max(0, -v.as_tuple().exponent)   # type: ignore[operator]
    step = Decimal(1).scaleb(-dec)
    same_unit = sorted({Decimal(o["value"]) for o in others if o["unit"] == fact["unit"]} - {v},
                       key=lambda o: abs(o - v))
    out = {"+1 last digit": v + step, "-1 last digit": v - step, "+3 last digits": v + 3 * step,
           "sign flipped": -v, "decimal point moved": v * 10}
    if same_unit:
        out["swapped with nearest other value"] = same_unit[0]
    return {k: _write(x, dec, raw) for k, x in out.items()}


def test_mutations_are_caught(facts: list[dict[str, Any]], good: dict[str, Any]) -> None:
    """Change each seed value everywhere the paper wrote it; L0 must then report that fact missing."""
    caught, missed = 0, []
    for f in good["facts"]:
        seed = next(x for x in facts if x["id"] == f["id"])
        raw = f["spans"][0]["raw"]
        for kind, new in mutations(seed, facts, raw).items():
            text = PAPER
            for s in sorted(f["spans"], key=lambda s: -s["start"]):
                text = text[:s["start"]] + new + text[s["end"]:]
            r = {x["id"]: x for x in dataset.check_text(text, facts)["facts"]}
            if r[f["id"]]["status"] == "missing":
                caught += 1
            else:
                missed.append((f["id"], kind, new))
    total = caught + len(missed)
    print(f"L0 mutation catch rate: {caught}/{total} = {caught / total:.1%}; missed: {missed}")
    assert total >= 100
    assert caught / total >= 0.95, missed


def test_check_writes_to_the_seed_folder_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(dataset, "domain_dir", lambda d: tmp_path / "seed" / d)
    r = dataset.check("medical", "P-med-01", text=PAPER)
    written = tmp_path / "seed" / "medical" / "l0" / "P-med-01.json"
    assert written.is_file() and r["summary"]["found"] == 18 and len(r["paper_sha256"]) == 64


def test_lists_of_weeks_and_table_numbers_are_ignored(facts) -> None:
    text = "Each measure was taken at weeks 4, 8, 12, 26 and 52. Results are in Tables 1 and 2.\n"
    r = dataset.check_text(text, facts)
    assert r["extra"] == [] and {x["kind"] for x in r["ignored"]} <= {"time", "label"}


def test_name_check_of_code_only_and_both_papers() -> None:
    names = {"quelmastin": {"written": "code", "code": "QLM-331"}}
    assert dataset.check_names("QLM-331 lowered HbA1c.", names) == []
    assert dataset.check_names("Quelmastin (QLM-331) lowered HbA1c.", names)
    both = {"quendarin": {"written": "both", "code": "QND-631"}}
    assert dataset.check_names("Quendarin (QND-631) and later quendarin.", both) == []
    assert dataset.check_names("QND-631 only.", both)


def test_header_with_two_units_lets_the_row_label_decide() -> None:
    assert dataset._header_unit("Mean difference (percentage points for HbA1c; kg for body weight)") is None
    assert dataset._header_unit("HbA1c change (percentage points)") is not None

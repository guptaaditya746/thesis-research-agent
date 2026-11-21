"""evqa/norm.py: reading values as papers write them, and the seed comparison rule (plan, "Value matching")."""
from __future__ import annotations

from decimal import Decimal

import pytest

from evqa import norm
from evqa.norm import PERCENT, PP, Verdict, find_values, normalize_value, same, seed_value

KG = "http://qudt.org/vocab/unit/KiloGM"
G = "http://qudt.org/vocab/unit/GM"
MG = "http://qudt.org/vocab/unit/MilliGM"
MMOL = "http://qudt.org/vocab/unit/MilliMOL-PER-L"
MGDL = "http://qudt.org/vocab/unit/MilliGM-PER-DeciL"
WK = "http://qudt.org/vocab/unit/WK"


@pytest.mark.parametrize(("text", "value", "unit", "decimals", "basis"), [
    ("−1.1", "-1.1", None, 1, "level"),
    ("-1.10", "-1.10", None, 2, "level"),
    ("– 0.5", "0.5", None, 1, "level"),              # a dash with a space after is no minus sign
    ("–0.5", "-0.5", None, 1, "level"),                   # en dash right before a digit is one
    ("+0.5 kg", "0.5", KG, 1, "level"),
    ("1.1 percentage points lower", "-1.1", PP, 1, "change"),
    ("reduced by 1.1", "-1.1", None, 1, "change"),
    ("HbA1c fell by 0.78 pp", "-0.78", PP, 2, "change"),
    ("a reduction in HbA1c of 0.57 percentage points", "-0.57", PP, 2, "change"),
    ("a 1.2 kg loss", "-1.2", KG, 1, "change"),
    ("weight increased by 0.5 kg", "0.5", KG, 1, "change"),
    ("reduced by −0.8", "-0.8", None, 1, "change"),       # an explicit sign wins over the word
    ("1,234.5 mg", "1234.5", MG, 1, "level"),
    ("0.78%", "0.78", PERCENT, 2, "level"),
    ("0.78 per cent", "0.78", PERCENT, 2, "level"),
    ("-0.78 percentage-points", "-0.78", PP, 2, "level"),
    ("6.5 mmol/L", "6.5", MMOL, 1, "level"),
    ("110 mg/dL", "110", MGDL, 0, "level"),
    ("24-week", "24", WK, 0, "level"),
    ("10mg", "10", MG, 0, "level"),
])
def test_normalize_single_values(text: str, value: str, unit: str | None, decimals: int, basis: str) -> None:
    v = normalize_value(text)
    assert v is not None
    assert (v.value, v.unit, v.decimals, v.sign_basis) == (Decimal(value), unit, decimals, basis)
    assert v.raw == text.strip()


@pytest.mark.parametrize(("text", "low", "high", "unit"), [
    ("0.6 to 0.9", "0.6", "0.9", None),
    ("0.6–0.9 kg", "0.6", "0.9", KG),
    ("0.6-0.9", "0.6", "0.9", None),
    ("-0.95 to -0.61 percentage points", "-0.95", "-0.61", PP),
    ("reduced by 0.6 to 0.9 kg", "-0.9", "-0.6", KG),
])
def test_ranges(text: str, low: str, high: str, unit: str | None) -> None:
    v = normalize_value(text)
    assert v is not None and v.is_range and v.value is None
    assert (v.low, v.high, v.unit) == (Decimal(low), Decimal(high), unit)


def test_from_to_is_two_levels_not_a_range() -> None:
    vals = [f.value for f in find_values("HbA1c fell from 8.1% to 7.3%")]
    assert [(v.value, v.sign_basis) for v in vals] == [(Decimal("8.1"), "level"), (Decimal("7.3"), "level")]


def test_digits_inside_names_are_not_numbers() -> None:
    assert [f.value.raw for f in find_values("HbA1c in P-med-01 with BRN-233 (type 2)")] == ["2"]


def test_list_shares_unit_and_direction() -> None:
    text = "Brenoxalin 40 mg lowered HbA1c by 0.57, 0.78 and 0.91 percentage points; weight rose by 0.5 kg."
    got = [(str(f.value.value), f.value.unit) for f in find_values(text)]
    assert got == [("40", MG), ("-0.57", PP), ("-0.78", PP), ("-0.91", PP), ("0.5", KG)]


def test_elided_verb_after_by_keeps_the_direction() -> None:
    text = "HbA1c fell by 0.57 pp with 10 mg, by 0.78 pp with 20 mg\nand by 0.91 pp with 40 mg."
    assert [str(f.value.value) for f in find_values(text) if f.value.unit == PP] == ["-0.57", "-0.78", "-0.91"]
    # a new sentence forgets it
    assert str(find_values("HbA1c fell by 0.5 pp. The change by 0.7 pp was small.")[1].value.value) == "0.7"


def test_a_dose_before_a_verb_is_not_flipped() -> None:
    assert find_values("Brenoxalin 40 mg reduced HbA1c")[0].value.value == Decimal(40)


def test_default_unit_and_unit_in_headers() -> None:
    assert normalize_value("−0.46", unit=PP).unit == PP
    assert norm.unit_in("HbA1c change (percentage points)") == PP
    assert norm.unit_in("Body weight change, kg") == KG
    assert norm.unit_in("Dose") is None
    assert norm.unit_in("Week") == WK
    assert normalize_value("no number here") is None


@pytest.mark.parametrize(("paper", "seed", "seed_unit", "verdict"), [
    ("-1.1 pp", "-1.10", PP, Verdict.SAME),              # trailing zero
    ("-1.10 pp", "-1.1", PP, Verdict.SAME),
    ("−1.1 percentage points", "-1.12", PP, Verdict.SAME),   # paper rounded to 1 decimal: half of 0.1 allowed
    ("-1.1 pp", "-1.16", PP, Verdict.DIFFERENT),
    ("-1.10 pp", "-1.12", PP, Verdict.DIFFERENT),        # 2 decimals printed: only 0.005 allowed
    ("reduced by 1.1 percentage points", "-1.1", PP, Verdict.SAME),
    ("1.1 percentage points", "-1.1", PP, Verdict.DIFFERENT),
    ("-0.78%", "-0.78", PP, Verdict.DIFFERENT),          # percent is not percentage points
    ("-0.78 pp", "-0.78", PERCENT, Verdict.DIFFERENT),
    ("1.2 g", "1200", MG, Verdict.SAME),                 # unit conversion with QUDT multipliers
    ("1200 mg", "1.2", G, Verdict.SAME),
    ("0.0012 kg", "1200", MG, Verdict.SAME),
    ("1.3 g", "1200", MG, Verdict.DIFFERENT),
    ("-1.2 kg", "-1200", G, Verdict.SAME),
    ("110 mg/dL", "6.1", MMOL, Verdict.CANT_COMPARE),    # glucose needs a molar mass: different kind of unit
    ("1.2 kg", "1.2", MMOL, Verdict.CANT_COMPARE),
    ("1.2", "1.2", KG, Verdict.CANT_COMPARE),            # no unit in the paper
])
def test_same(paper: str, seed: str, seed_unit: str, verdict: Verdict) -> None:
    v = normalize_value(paper)
    assert v is not None
    m = same(v, seed_value(seed, seed_unit))
    assert m.verdict is verdict, m.reason


def test_ranges_compare_bound_by_bound() -> None:
    seed = normalize_value("0.60 to 0.90 kg")
    assert seed is not None
    assert same(normalize_value("0.6 to 0.9 kg"), seed).verdict is Verdict.SAME   # type: ignore[arg-type]
    assert same(normalize_value("0.6 to 1.0 kg"), seed).verdict is Verdict.DIFFERENT   # type: ignore[arg-type]
    assert same(normalize_value("600-900 g"), seed).verdict is Verdict.SAME   # type: ignore[arg-type]
    m = same(normalize_value("0.75 kg"), seed)   # type: ignore[arg-type]
    assert m.verdict is Verdict.CANT_COMPARE and "range" in m.reason


def test_unknown_unit_cant_compare() -> None:
    v = norm.Value(Decimal("1"), "http://example.org/unit/Foo", 0)
    assert same(v, seed_value("1", KG)).verdict is Verdict.CANT_COMPARE


def test_seed_value_keeps_printed_decimals() -> None:
    v = seed_value("-0.90", PP)
    assert (v.decimals, v.sign_basis, v.as_json()["value"]) == (2, "change", "-0.90")


def test_units_file_has_qudt_iris_and_factors() -> None:
    u = norm.units()
    assert u[MG]["multiplier"] == "0.000001" and u[KG]["multiplier"] == "1.0"
    assert u[PP]["dimension"] != u[PERCENT]["dimension"]
    assert norm.factor(G, MG) == Decimal(1000)

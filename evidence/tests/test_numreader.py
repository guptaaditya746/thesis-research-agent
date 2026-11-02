"""numreader.read_numbers (D35: one general number reader for every topic): each written form of a number ("0.68",
"82.5%", "41 of 120", "41/120", "0.61 ± 0.03", "between 0.4 and 0.6") gives one span with its value as a fraction
where it is one; broken counts are skipped. number_measurement reads through it, so a count result in a drug trial
("41 of 120 patients") is a measurement of a fraction metric and an enrolment count is not."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from evidence import contract
from evidence.extractors.numreader import read_numbers

from .conftest import regex_run

HERE = Path(__file__).resolve().parent
DRUG_TOY_DOMAINS = HERE / "fixtures"   # the pack folder is fixtures/drugtoy (a pack root may hold other folders)
DRUG_TOY_PROTOCOL = DRUG_TOY_DOMAINS / "drugtoy" / "protocols" / "drugtoy-response.yaml"


@pytest.fixture(autouse=True)
def _registry():
    """Each test leaves the type registry as it found it (the drugtoy pack registers arm, outcome, result)."""
    before = dict(contract.ITEM_PREFIX)
    yield
    contract.ITEM_PREFIX.clear()
    contract.ITEM_PREFIX.update(before)


def measurements(sentences: list[str], tmp: Path, protocol: Path) -> list[SimpleNamespace]:
    """The measured-value items of a regex-only run over one paper per sentence, in document order."""
    docs = {f"P{n}": f"# Trial {n}\n\n{text}\n" for n, text in enumerate(sentences, 1)}
    _, items = regex_run(docs, tmp, protocol, domains=DRUG_TOY_DOMAINS)
    found = [i for i in items.values() if i["evidence_type"] == "result"]
    found.sort(key=lambda i: (i["spans"][0]["selector"]["file"], i["spans"][0]["selector"]["start"]))
    return [SimpleNamespace(fields=i["fields"], spans=i["spans"]) for i in found]


@pytest.mark.parametrize("text,value,form", [
    ("accuracy of 0.68", 0.68, "plain"),
    ("reached 82.5%", 0.825, "percent"),
    ("41 of 120 patients", 41 / 120, "k_of_n"),
    ("41/120 responded", 41 / 120, "fraction"),
    ("0.61 ± 0.03", 0.61, "plus_minus"),
    ("between 0.4 and 0.6", 0.4, "range"),
])
def test_reads_each_form(text, value, form):
    (n,) = [s for s in read_numbers(text) if s.form == form]
    assert n.value == pytest.approx(value)


def test_spans_and_parts_are_offsets_into_the_original_text():
    text = "We saw 41 out of 1,200 patients and ８２．５％ elsewhere."
    spans = read_numbers(text)
    (k,) = [s for s in spans if s.form == "k_of_n"]
    assert text[k.start:k.end] == k.raw == "41 out of 1,200"
    assert [text[a:b] for a, b in k.parts] == ["41", "1,200"]
    (p,) = [s for s in spans if s.form == "percent"]   # NFKC: full-width digits read, offsets of the original
    assert p.raw == "８２．５％" and p.value == pytest.approx(0.825)


def test_compound_forms_take_their_numbers():
    assert [s.form for s in read_numbers("41 of 120 and 0.61 ± 0.03 and 3/4")] == ["k_of_n", "plus_minus", "fraction"]


def test_impossible_counts_are_skipped():
    assert [s for s in read_numbers("0 of 0 and 45 of 30 and of 120") if s.form == "k_of_n"] == []


def test_count_result_becomes_a_measurement(tmp_path):
    items = measurements(["Zelvora: 41 of 120 patients reached response rate."], tmp_path, DRUG_TOY_PROTOCOL)
    assert items[0].fields["value"] == pytest.approx(0.3417, abs=1e-4) and items[0].fields["form"] == "k_of_n"
    exact = {s["role"]: s["selector"]["exact"] for s in items[0].spans}
    assert exact["value"] == "41" and exact["value_total"] == "120"


def test_enrolment_count_is_not_a_measurement(tmp_path):
    assert measurements(["We enrolled 120 patients."], tmp_path, DRUG_TOY_PROTOCOL) == []
    # with an arm and the metric in the sentence, a bare count is still not a value
    assert measurements(["The Zelvora arm enrolled 120 patients to measure the response rate."], tmp_path / "b",
                        DRUG_TOY_PROTOCOL) == []


def test_share_of_patients_is_a_measurement(tmp_path):
    (item,) = measurements(["The response rate was 34% of patients for Zelvora."], tmp_path, DRUG_TOY_PROTOCOL)
    assert item.fields["value"] == pytest.approx(0.34) and item.fields["form"] == "percent"


def test_superscripts_and_fractions_are_not_folded_into_numbers():
    # only full- and half-width forms are NFKC-folded: a footnote mark or a vulgar fraction is no digit
    assert [(s.form, s.value) for s in read_numbers("accuracy of 0.68¹ on X")] == [("plain", 0.68)]
    assert [(s.form, s.value) for s in read_numbers("reached 71.2%²")] == [("percent", 0.712)]
    assert read_numbers("about ½ of them") == []
    (wide,) = read_numbers("accuracy of ０．６８")
    assert (wide.form, wide.value, wide.raw) == ("plain", 0.68, "０．６８")


def test_a_footnote_mark_glues_the_number_out_of_a_measurement(tmp_path):
    assert measurements(["Zelvora reached a response rate of 0.68¹."], tmp_path, DRUG_TOY_PROTOCOL) == []
    (item,) = measurements(["Zelvora reached a response rate of 0.68."], tmp_path / "b", DRUG_TOY_PROTOCOL)
    assert item.fields["value"] == 0.68


def test_the_number_of_a_code_name_is_not_read():
    """A drug's code name ("ZV-217", plan 2 Task 5 name variants) is a name, not a value; ranges still read."""
    assert [n.raw for n in read_numbers("In adults, 41 of 120 patients on ZV-217 responded.")] == ["41 of 120"]
    assert [(n.raw, n.form) for n in read_numbers("between 0.4-0.6 and -0.2")] == [("0.4-0.6", "range"), ("0.2", "plain")]

"""The arXiv edit test and the hand-check sheets (spec 6.12 item 3, 6.15): an edit changes one paper of a corpus,
and the check asks whether the right item, its links and the answer follow the text. The runs here are scripted (no
network, no model): the paper's system "System R" is read by the scripted llm_condition and its value by the scripted
llm_measurement (both read the paper text, so they follow an edit); the closed-book control is the regex's."""
from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from typing import Any

import pytest

from evaluation import cli
from evaluation.realpapers.edits import Edit, EditError, apply, check, load_edits, summary
from evaluation.realpapers.sheet import COLUMNS, sheet, summarise, write_sheet
from evidence import engine
from evidence.contract import Item, Span
from evidence.rundir import ANSWER_FILE, EVIDENCE_FILE, PROTOCOL_FILE, Corpus, write_lines
from evidence.tests.conftest import (PROTOCOL, context_id, corpus_of, paper_text, provider_of, scripted,
                                     screen_yes)

TEXT = ("# Retrieval for questions\n\n## Results\n\nSystem R reaches an answer accuracy of 0.71 on Natural Questions, "
        "compared with 0.62 for the closed-book model.\n")
OTHER = ("# Another study\n\n## Results\n\nThe retrieval-augmented model reaches an answer accuracy of 80%, compared "
         "with 70% for the closed-book model.\n")
EDIT = Edit(id="e1", paper="p1", kind="number", find="0.71", replace="0.31")
EDIT2 = Edit(id="e2", paper="p1", kind="name", find="System R", replace="System Q")
SYSTEM = re.compile(r"System [A-Z]")
VALUE = re.compile(r"System [A-Z] reaches an answer accuracy of (\d\.\d+)")


@pytest.fixture(autouse=True)
def code_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sealed runs name commit `test` (no `git rev-parse` per run; F54)."""
    monkeypatch.setenv("EVIDENCE_CODE_COMMIT", "test")


def corpus_with(text: str, root: Path | None = None) -> Path:
    """A corpus of p1 (`text`) and p2 (OTHER), under `root` (default: a fresh temporary folder)."""
    if root is None:
        import tempfile
        root = Path(tempfile.mkdtemp()) / "corpus"
    return corpus_of(root, {"p1": text, "p2": OTHER})


def script(kind: str, doc: str, prompt: str) -> dict[str, Any]:
    """The scripted reader: the paper's "System X" as a rag condition, and its value linked to it."""
    if kind == "screen":
        return screen_yes(prompt)
    if kind == "retry":
        return {"quotes": []}
    text = paper_text(prompt)
    name, value = SYSTEM.search(text), VALUE.search(text)
    if kind == "condition" and name:
        return {"items": [{"fields": {"label": name.group(0), "role": "rag"},
                           "quotes": {"condition_label": name.group(0)}}]}
    if kind == "measurement" and name and value:
        try:
            cond, metric = context_id(prompt, name.group(0)), context_id(prompt, '"factual_accuracy"')
        except AssertionError:       # the context holds no such condition (a part of the paper without it)
            return {"items": []}
        return {"items": [{"fields": {"value": float(value.group(1)), "dataset": None, "form": None},
                           "links": {"condition": cond, "metric": metric},
                           "quotes": {"value": value.group(1), "condition_label": name.group(0),
                                      "metric_label": None, "value_total": None}}]}
    return {"items": []}


def scripted_run(corpus: Path, out: Path, run_id: str = "run") -> Path:
    return engine.run(PROTOCOL, corpus, out, provider=provider_of(scripted(script, [])), model="scripted-alias",
                      strategy="all", workers=1, run_id=run_id)


def run_pair(tmp: Path, edit: Edit) -> tuple[Path, Path]:
    """(original run, edited run) of the scripted reader over corpus_with(TEXT) and its edit `edit`."""
    corpus = corpus_with(TEXT, tmp / "corpus")
    edited = apply(corpus, edit, tmp / "edited")
    return scripted_run(corpus, tmp / "runs-original"), scripted_run(edited, tmp / "runs-edited", edit.id)


# --- apply --------------------------------------------------------------------------------------------------


def test_find_must_occur_once(tmp_path: Path) -> None:
    with pytest.raises(EditError, match="e1.*2 times"):
        apply(corpus_with("0.71 and 0.71"), Edit(id="e1", paper="p1", kind="number", find="0.71", replace="0.31"),
              tmp_path)
    with pytest.raises(EditError, match="e1.*0 times"):
        apply(corpus_with("no number"), EDIT, tmp_path)
    with pytest.raises(EditError, match="e1.*no paper 'p9'"):
        apply(corpus_with(TEXT), EDIT.model_copy(update={"paper": "p9"}), tmp_path)


def test_apply_changes_only_that_paper_and_its_sha(tmp_path: Path) -> None:
    corpus = corpus_with(TEXT, tmp_path / "corpus")
    edited = apply(corpus, EDIT, tmp_path / "edited")
    assert edited == tmp_path / "edited" / "e1"
    assert (edited / "papers/p1.md").read_text(encoding="utf-8") == TEXT.replace("0.71", "0.31")
    assert (edited / "papers/p2.md").read_bytes() == (corpus / "papers/p2.md").read_bytes()
    before, after = Corpus(corpus), Corpus(edited)
    assert [p.id for p in after.papers] == ["p1", "p2"]
    assert after.papers[0].sha256 != before.papers[0].sha256 and after.papers[1].sha256 == before.papers[1].sha256
    assert after.text(after.papers[0]) == TEXT.replace("0.71", "0.31")   # the manifest's sha256 matches the text
    assert (corpus / "papers/p1.md").read_text(encoding="utf-8") == TEXT      # the original is untouched
    assert json.loads((edited / "edit.json").read_text(encoding="utf-8"))["id"] == "e1"


def test_load_edits_refuses_a_limitation_with_a_replacement_and_a_repeated_id(tmp_path: Path) -> None:
    path = tmp_path / "edits.yaml"
    path.write_text("edits:\n- {id: e1, paper: p1, kind: number, find: '0.71', replace: '0.31'}\n"
                    "- {id: e2, paper: p1, kind: name, find: System R, replace: System Q}\n", encoding="utf-8")
    assert load_edits(path) == [EDIT, EDIT2]
    path.write_text("edits:\n- {id: e3, paper: p1, kind: limitation, find: We did not test X., replace: other}\n",
                    encoding="utf-8")
    with pytest.raises(ValueError, match="limitation"):
        load_edits(path)
    path.write_text("edits:\n- {id: e1, paper: p1, kind: number, find: '0.71', replace: '0.31'}\n"
                    "- {id: e1, paper: p2, kind: number, find: '80', replace: '60'}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="e1"):
        load_edits(path)


# --- check: number and name ---------------------------------------------------------------------------------


def test_number_edit_carries_through(tmp_path: Path) -> None:
    orig, edited = run_pair(tmp_path, Edit(id="e1", paper="p1", kind="number", find="0.71", replace="0.31"))
    assert check(orig, edited, EDIT) == {"item": True, "link": True, "answer": True}


def test_an_edit_the_run_did_not_follow_fails_every_part(tmp_path: Path) -> None:
    """The original run checked against itself: no item has the new value, no answer changed."""
    orig, _ = run_pair(tmp_path, EDIT)
    assert check(orig, orig, EDIT) == {"item": False, "link": False, "answer": False}
    assert check(orig, orig, EDIT2) == {"item": False, "link": False, "answer": False}


def test_name_swap_moves_the_links(tmp_path: Path) -> None:
    orig, edited = run_pair(tmp_path, Edit(id="e2", paper="p1", kind="name", find="System R", replace="System Q"))
    assert check(orig, edited, EDIT2)["link"]
    assert check(orig, edited, EDIT2) == {"item": True, "link": True, "answer": True}


def test_a_value_the_answer_does_not_use_leaves_the_answer_unchanged(tmp_path: Path) -> None:
    """Editing the other paper's control value (70% -> 75%) changes p2's study; p1's entry stays as it was, so an edit
    of p1 checked against that run reports no answer change."""
    corpus = corpus_with(TEXT, tmp_path / "corpus")
    other = Edit(id="e5", paper="p2", kind="number", find="70%", replace="75%")
    orig = scripted_run(corpus, tmp_path / "runs-original")
    edited = scripted_run(apply(corpus, other, tmp_path / "edited"), tmp_path / "runs-edited", "e5")
    assert check(orig, edited, other) == {"item": True, "link": True, "answer": True}
    assert check(orig, edited, EDIT)["answer"] is False


# --- check: limitation (plan 2's answer shape; hand-made runs, no rag limitations protocol yet, F25) ----------


LIMITED = ("# A study\n\n## Discussion\n\nSystem R was tested on English only. The sample is small. "
           "We used one seed.\n")
CUT = "The sample is small. "


def selector(text: str, file: str, start: int, end: int) -> dict[str, Any]:
    return {"file": file, "start": start, "end": end, "exact": text[start:end],
            "prefix": text[max(0, start - 32):start], "suffix": text[end:end + 32]}


def limitation_run(root: Path, text: str, sentences: list[str], linked: bool = False) -> Path:
    """A run directory in plan 2's limitations shape: one item per sentence (author_claim stands in for the
    limitation type, which the rag pack lacks), each listed in an answer entry; `linked`: a second item links to
    the first limitation."""
    root.mkdir(parents=True)
    (root / PROTOCOL_FILE).write_bytes(PROTOCOL.read_bytes())
    file = "papers/p1.md"
    items = []
    for s in sentences:
        at = text.index(s)
        items.append(Item.build("author_claim", {"direction": "no_effect", "quote": s},
                                [Span(role="claim", selector=selector(text, file, at, at + len(s)))]))
    if linked:
        items.append(Item.build("condition", {"label": "System R", "role": "rag"},
                                [Span(role="condition_label", selector=selector(text, file, text.index("System R"),
                                                                                text.index("System R") + 8))],
                                links={"limitation": items[0].item_id}))
    write_lines(root / EVIDENCE_FILE, [i.model_dump(mode="json") for i in items])
    entries = [{"thing": "System R", "category": "scope", "papers": ["p1"], "items": [i.item_id]}
               for i in items if i.evidence_type == "author_claim"]
    (root / ANSWER_FILE).write_text(json.dumps({"kind": "limitations", "entries": entries}), encoding="utf-8")
    return root


def test_limitation_edit_removes_the_item_and_one_from_the_count(tmp_path: Path) -> None:
    edit = Edit(id="e3", paper="p1", kind="limitation", find=CUT, replace="")
    after = LIMITED.replace(CUT, "")
    all3 = ["System R was tested on English only.", "The sample is small.", "We used one seed."]
    orig = limitation_run(tmp_path / "orig", LIMITED, all3)
    edited = limitation_run(tmp_path / "edited", after, [all3[0], all3[2]])
    assert check(orig, edited, edit) == {"item": True, "link": True, "answer": True}
    kept = limitation_run(tmp_path / "kept", LIMITED, all3)   # a run that still lists the deleted sentence
    assert check(orig, kept, edit) == {"item": False, "link": True, "answer": False}


def test_limitation_link_fails_when_an_item_still_links_to_the_deleted_one(tmp_path: Path) -> None:
    edit = Edit(id="e4", paper="p1", kind="limitation", find="System R was tested on English only. ", replace="")
    first = "System R was tested on English only."
    after = LIMITED.replace(edit.find, "")
    orig = limitation_run(tmp_path / "orig", LIMITED, [first, "The sample is small."], linked=True)
    stale = limitation_run(tmp_path / "edited", LIMITED, [first], linked=True)   # still links to it
    assert check(orig, stale, edit)["link"] is False
    fixed = limitation_run(tmp_path / "fixed", after, ["The sample is small."])
    assert check(orig, fixed, edit)["link"] is True


def test_summary_shares_per_part_and_over_all_three() -> None:
    results = {"e1": {"item": True, "link": True, "answer": True},
               "e2": {"item": True, "link": False, "answer": True}}
    kinds = {"e1": "number", "e2": "name"}
    s = summary(results, kinds)
    assert s["carried"] == {"item": 1.0, "link": 0.5, "answer": 1.0, "all": 0.5}
    assert s["by_kind"]["name"] == {"edits": 1, "item": 1.0, "link": 0.0, "answer": 1.0, "all": 0.0}
    results["e3"] = {"item": None, "link": None, "answer": None}           # not testable: left out of every share
    results["e4"] = {"item": True, "link": None, "answer": False}          # link not testable: out of link and all
    s = summary(results, {**kinds, "e3": "number", "e4": "name"})
    assert s["carried"] == {"item": 1.0, "link": 0.5, "answer": 2 / 3, "all": 0.5}


# --- fix round 1: number spot, recorded offset, scale, not testable ------------------------------------------


def test_a_number_edit_holds_one_number_with_the_same_context() -> None:
    for find, replace, why in (("0.71 and 0.62", "0.31 and 0.62", "exactly one number"),
                               ("accuracy", "precision", "exactly one number"),
                               ("accuracy of 0.71", "recall of 0.31", "the number only"),
                               ("0.71", "0.71", "changes nothing")):
        with pytest.raises(ValueError, match=why):
            Edit(id="x", paper="p1", kind="number", find=find, replace=replace)
    with pytest.raises(ValueError, match="changes nothing"):
        Edit(id="x", paper="p1", kind="name", find="System R", replace="System R")


def test_context_words_in_find_do_not_widen_the_spot(tmp_path: Path) -> None:
    edit = Edit(id="e6", paper="p1", kind="number", find="accuracy of 0.71", replace="accuracy of 0.31")
    orig, edited = run_pair(tmp_path, edit)
    assert check(orig, edited, edit) == {"item": True, "link": True, "answer": True}


def test_apply_records_the_offset_and_check_uses_it(tmp_path: Path) -> None:
    orig, edited = run_pair(tmp_path, EDIT)
    record = json.loads((tmp_path / "edited" / "e1" / "edit.json").read_text(encoding="utf-8"))
    assert record["at"] == TEXT.index("0.71")
    assert check(orig, edited, EDIT, at=record["at"]) == {"item": True, "link": True, "answer": True}
    assert check(orig, edited, EDIT, at=0) == {"item": None, "link": None, "answer": None}   # nothing read there


NUMBERS = "# A study\n\n## Results\n\nSystem R reaches 71.0 here. We used 5 seeds.\n"


def hand_run(root: Path, text: str, items: list[tuple[str, dict[str, Any], str]],
             answer: dict[str, Any] | None = None) -> Path:
    """A run directory of paper p1 holding `items` (type, fields, the text its one span covers) and `answer`."""
    root.mkdir(parents=True)
    (root / PROTOCOL_FILE).write_bytes(PROTOCOL.read_bytes())
    built = []
    for etype, fields, quote in items:
        at = text.index(quote)
        built.append(Item.build(etype, fields, [Span(role="value", selector=selector(text, "papers/p1.md", at,
                                                                                      at + len(quote)))]))
    write_lines(root / EVIDENCE_FILE, [i.model_dump(mode="json") for i in built])
    (root / ANSWER_FILE).write_text(json.dumps(answer or {}), encoding="utf-8")
    return root


def test_the_new_value_must_have_the_original_scale(tmp_path: Path) -> None:
    """71.0 read as 0.71 (a % column): the edited item must hold 0.31, not 31.0."""
    edit = Edit(id="e7", paper="p1", kind="number", find="71.0", replace="31.0")
    after = NUMBERS.replace("71.0", "31.0")
    orig = hand_run(tmp_path / "orig", NUMBERS, [("measurement", {"value": 0.71, "dataset": None}, "71.0")])
    scaled = hand_run(tmp_path / "scaled", after, [("measurement", {"value": 0.31, "dataset": None}, "31.0")])
    raw = hand_run(tmp_path / "raw", after, [("measurement", {"value": 31.0, "dataset": None}, "31.0")])
    assert check(orig, scaled, edit)["item"] is True
    assert check(orig, raw, edit)["item"] is False


def test_an_unread_spot_and_an_unlinked_name_are_not_testable(tmp_path: Path) -> None:
    unread = Edit(id="e8", paper="p1", kind="number", find="5 seeds", replace="7 seeds")
    orig = hand_run(tmp_path / "orig", NUMBERS, [("measurement", {"value": 0.71, "dataset": None}, "71.0"),
                                                 ("condition", {"label": "System R", "role": "rag"}, "System R")])
    after = NUMBERS.replace("System R", "System Q")
    swapped = hand_run(tmp_path / "swapped", after, [("condition", {"label": "System Q", "role": "rag"}, "System Q")],
                       {"studies": [{"document": "p1", "winner": "System Q"}]})
    assert check(orig, swapped, unread) == {"item": None, "link": None, "answer": None}
    assert check(orig, swapped, EDIT2) == {"item": True, "link": None, "answer": True}   # nothing linked to System R
    both = hand_run(tmp_path / "both", after, [("condition", {"label": "System Q", "role": "rag"}, "System Q")],
                    {"studies": [{"document": "p1", "winner": "System Q", "loser": "System R"}]})
    assert check(orig, both, EDIT2)["answer"] is False                                  # still names System R


def test_report_lists_not_testable_edits_apart(tmp_path: Path) -> None:
    from evaluation.realpapers.edits import report
    edit = Edit(id="e7", paper="p1", kind="number", find="71.0", replace="31.0")
    unread = Edit(id="e8", paper="p1", kind="number", find="5 seeds", replace="7 seeds")
    orig = hand_run(tmp_path / "orig", NUMBERS, [("measurement", {"value": 0.71, "dataset": None}, "71.0")])
    for e, text in ((edit, NUMBERS.replace("71.0", "31.0")), (unread, NUMBERS.replace("5 seeds", "7 seeds"))):
        run = hand_run(tmp_path / "runs" / e.id, text, [("measurement", {"value": 0.31, "dataset": None}, "31.0")]
                       if e is edit else [])
        (run / "run.json").write_text('{"run_id": "x"}', encoding="utf-8")   # a complete run
    real = report(orig, tmp_path / "runs", [edit, unread])
    assert real["not_testable"] == {"e8": ["item", "link", "answer"]} and real["not_testable_edits"] == 1
    assert real["carried"]["item"] == 1.0 and real["by_edit"]["e8"]["item"] is None


# --- sheets -------------------------------------------------------------------------------------------------


def sentence_paper(n: int) -> str:
    return "# Paper\n\n" + " ".join(f"Sentence {k} says System {k} scores {k}." for k in range(n)) + "\n"


def sheet_run(tmp: Path, papers: int = 3, per_paper: int = 60) -> tuple[Path, Path]:
    """(run, corpus): `papers` papers of `per_paper` sentences, one condition item per sentence (its name)."""
    texts = {f"q{p}": sentence_paper(per_paper) for p in range(1, papers + 1)}
    corpus = corpus_of(tmp / "corpus", texts)
    run = tmp / "run"
    run.mkdir()
    (run / PROTOCOL_FILE).write_bytes(PROTOCOL.read_bytes())
    items = []
    for doc, text in texts.items():
        for k in range(per_paper):
            name = f"System {k}"
            at = text.index(name + " scores")
            items.append(Item.build("condition", {"label": name, "role": "rag"},
                                    [Span(role="condition_label",
                                          selector=selector(text, f"papers/{doc}.md", at, at + len(name)))]))
    write_lines(run / EVIDENCE_FILE, [i.model_dump(mode="json") for i in items])
    return run, corpus


def sheet_rows(tmp: Path, sample: int, seed: int) -> list[dict[str, str]]:
    if not (tmp / "run").exists():
        sheet_run(tmp)
    return sheet(tmp / "run", tmp / "corpus", sample=sample, seed=seed)


def test_sample_is_reproducible(tmp_path: Path) -> None:
    assert sheet_rows(tmp_path, sample=100, seed=0) == sheet_rows(tmp_path, sample=100, seed=0)
    assert len(sheet_rows(tmp_path, sample=100, seed=0)) == 100
    assert sheet_rows(tmp_path, sample=100, seed=1) != sheet_rows(tmp_path, sample=100, seed=0)


def test_sheet_rows_hold_the_item_and_its_sentence(tmp_path: Path) -> None:
    run, corpus = sheet_run(tmp_path, papers=3, per_paper=4)
    rows = sheet(run, corpus, papers=2)
    assert [r["paper"] for r in rows] == ["q1"] * 4 + ["q2"] * 4            # every item of the first 2 papers
    assert list(rows[0]) == list(COLUMNS)
    assert rows[1]["sentence"] == "Sentence 1 says System 1 scores 1."      # cut at the sentence ends
    assert rows[1]["type"] == "condition" and json.loads(rows[1]["fields"])["label"] == "System 1"
    assert rows[1]["right_or_wrong"] == "" and rows[1]["note"] == ""
    with pytest.raises(ValueError, match="sample or papers"):
        sheet(run, corpus)


def csv_rows(right: int, wrong: int, blank: int = 0) -> Path:
    import tempfile
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    for n, mark in enumerate(["right"] * right + ["wrong"] * wrong + [""] * blank):
        writer.writerow({c: "" for c in COLUMNS} | {"item_id": f"c-{n}", "right_or_wrong": mark})
    path = Path(tempfile.mkdtemp()) / "sheet.csv"
    path.write_bytes(buf.getvalue().encode("utf-8-sig"))
    return path


def test_wilson_interval() -> None:
    s = summarise(csv_rows(right=80, wrong=20))
    assert s["precision"] == 0.8 and s["wilson95"] == pytest.approx([0.7112, 0.8666], abs=1e-3)


def test_blank_rows_are_not_counted_and_a_bad_cell_is_named(tmp_path: Path) -> None:
    s = summarise(csv_rows(right=3, wrong=1, blank=5))
    assert (s["n"], s["right"], s["precision"]) == (4, 3, 0.75)
    assert summarise(csv_rows(right=0, wrong=0, blank=2)) == {"n": 0, "right": 0, "precision": None,
                                                              "wilson95": None}
    bad = tmp_path / "bad.csv"
    bad.write_text(",".join(COLUMNS) + "\nc-1,p1,condition,{},s,maybe,\n", encoding="utf-8")
    with pytest.raises(ValueError, match="row 2.*maybe"):
        summarise(bad)


# --- command line -------------------------------------------------------------------------------------------


def test_cli_apply_check_sheet_and_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    corpus = corpus_with(TEXT, tmp_path / "corpus")
    edits = tmp_path / "edits.yaml"
    edits.write_text("edits:\n- {id: e1, paper: p1, kind: number, find: '0.71', replace: '0.31'}\n"
                     "- {id: e2, paper: p1, kind: name, find: System R, replace: System Q}\n", encoding="utf-8")
    assert cli.main(["edits", "apply", "--corpus", str(corpus), "--edits", str(edits),
                     "--out", str(tmp_path / "edited")]) == 0
    orig = scripted_run(corpus, tmp_path / "runs-original")
    for e in ("e1", "e2"):
        scripted_run(tmp_path / "edited" / e, tmp_path / "runs", e)
    assert cli.main(["edits", "check", "--original", str(orig), "--runs", str(tmp_path / "runs"),
                     "--edits", str(edits), "--corpora", str(tmp_path / "edited"),
                     "--out", str(tmp_path / "report")]) == 0
    real = json.loads((tmp_path / "report" / "real.json").read_text(encoding="utf-8"))
    assert real["carried"] == {"item": 1.0, "link": 1.0, "answer": 1.0, "all": 1.0} and real["missing"] == []
    assert (tmp_path / "report" / "real.md").read_text(encoding="utf-8").startswith("# real-paper check: arXiv edit")

    out = tmp_path / "sheet.csv"
    assert cli.main(["sheet", "--run", str(orig), "--corpus", str(corpus), "--papers", "5", "--out", str(out)]) == 0
    rows = list(csv.DictReader(io.StringIO(out.read_bytes().decode("utf-8-sig"))))
    assert {r["paper"] for r in rows} == {"p1", "p2"}
    for r in rows:   # the hand-checker marks every row right but the first
        r["right_or_wrong"] = "right"
    rows[0]["right_or_wrong"] = "wrong"
    write_sheet(rows, out)
    capsys.readouterr()
    assert cli.main(["sheet-summary", str(out), "--out", str(tmp_path / "demo")]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert (printed["n"], printed["right"]) == (len(rows), len(rows) - 1)
    md = (tmp_path / "demo" / "real.md").read_text(encoding="utf-8")
    assert "demonstration, not an evaluation" in md.splitlines()[0]

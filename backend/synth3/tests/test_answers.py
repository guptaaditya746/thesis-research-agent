"""synth3.answers: answers in one shape, from engine run folders and the baseline, and the `collect` command."""
import json
from pathlib import Path

import pytest

from evidence.contract import Item, Span
from jsonio import canonical
from synth3.answers import (MAX_TEXT, AnswerRecord, answer_path, answer_text, cited_papers, from_engine_run,
                            from_rag_answer, item_id, load_answer, load_answers, save_answer)
from synth3.cli import main
from synth3.sheetfacts import load_folder
from synth3.tests.conftest import q

FIX = Path(__file__).parent / "fixtures" / "questions"


def fake_run(run: Path, folder, answer: dict, spans: list[tuple[str, int, int]]) -> Path:
    """An engine run folder: answer.json, run.json (corpus_id top-level) and one measurement item per span."""
    run.mkdir(parents=True, exist_ok=True)
    (run / "answer.json").write_text(json.dumps(answer), encoding="utf-8")
    (run / "run.json").write_text(json.dumps({"corpus_id": folder.corpus_id}), encoding="utf-8")
    rows = []
    for paper, start, end in spans:
        text = (folder.path / "papers" / f"{paper}.md").read_text(encoding="utf-8")
        selector = {"file": f"papers/{paper}.md", "start": start, "end": end, "exact": text[start:end]}
        item = Item.build("measurement", {"n": start}, [Span(role="value", selector=selector)])
        rows.append(item.model_dump_json())
    (run / "evidence.jsonl").write_text("".join(r + "\n" for r in rows), encoding="utf-8")
    return run


def test_engine_run_becomes_a_record(folder, tmp_path):
    f = load_folder(folder); text = (folder / "papers" / "S001.md").read_text(encoding="utf-8")
    run = fake_run(tmp_path / "run", f, {"label": "supported", "studies": [{"document": "S001"}]},
                   [("S001", 100, 120), ("S002", 50, 60)])
    rec = from_engine_run(run, f, q("Q?"))
    assert [x.paper for x in rec.facts] == ["S001", "S002"] and rec.facts[0].quote == text[100:120]
    assert '"label":"supported"' in rec.text and rec.cited == ["S001"] and not rec.text_cut
    assert rec.system == "engine" and rec.domain == "demo" and rec.seed == 1


def test_a_model_written_answer_is_used_as_text(folder, tmp_path):
    f = load_folder(folder)
    run = fake_run(tmp_path / "run", f, {"answer_text": "Targeted therapy helps (S003).", "label": "x"}, [])
    assert from_engine_run(run, f, q("Q?")).text == "Targeted therapy helps (S003)."


def test_a_fixed_kind_answer_never_names_its_system():
    text, _ = answer_text({"system": "evidence-engine", "kind": "best", "winner": "Method K", "protocol": "p.yaml",
                           "question_id": "q1", "studies": [{"document": "S001", "system": "evidence-engine"}],
                           "model_call": {"model": "orch-model"}})
    assert "evidence-engine" not in text and "orch-model" not in text and "p.yaml" not in text
    assert '"winner":"Method K"' in text


def test_hidden_keys_go_at_any_depth():
    text, _ = answer_text({"kind": "best", "detail": {"system": "evidence-engine", "rows": [
        {"corpus_id": "c", "system": "evidence-engine", "keep": 1, "extract_call": {"m": "orch-model"}}]}})
    assert "evidence-engine" not in text and "orch-model" not in text and '"corpus_id"' not in text
    assert text == canonical({"kind": "best", "detail": {"rows": [{"keep": 1}]}})


def test_long_text_is_cut_and_flagged():
    text, cut = answer_text({"answer_text": "a" * (MAX_TEXT + 5)})
    assert cut and len(text) <= MAX_TEXT + 40
    assert answer_text({"answer_text": "short"}) == ("short", False)


def test_cited_papers_keeps_known_ids_in_first_seen_order():
    assert cited_papers("S003 and S001, then S003, S999 and XS002", ["S001", "S002", "S003"]) == ["S003", "S001"]


def test_a_run_on_another_corpus_is_refused(folder, tmp_path):
    f = load_folder(folder); run = fake_run(tmp_path / "run", f, {"label": "x"}, [])
    (run / "run.json").write_text(json.dumps({"corpus_id": "other"}), encoding="utf-8")
    with pytest.raises(ValueError, match="corpus"):
        from_engine_run(run, f, q("Q?"))


def test_a_run_without_an_answer_is_refused(folder, tmp_path):
    f = load_folder(folder); run = fake_run(tmp_path / "run", f, {"label": "x"}, [])
    (run / "answer.json").unlink()
    with pytest.raises(ValueError, match="answer.json"):
        from_engine_run(run, f, q("Q?"))


def test_an_item_of_a_paper_the_folder_lacks_is_refused(folder, tmp_path):
    f = load_folder(folder); run = fake_run(tmp_path / "run", f, {"label": "x"}, [("S001", 1, 5)])
    row = json.loads((run / "evidence.jsonl").read_text(encoding="utf-8"))
    row["spans"][0]["selector"]["file"] = "papers/S999.md"
    (run / "evidence.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="S999"):
        from_engine_run(run, f, q("Q?"))


def test_rag_answer_keeps_the_cited_passages(folder):
    f = load_folder(folder); text = (folder / "papers" / "S002.md").read_text(encoding="utf-8")
    rec = from_rag_answer({"answer_text": "See S002.", "citations": [{"document": "S002", "start": 10, "end": 90}]},
                          f, q("Q?"), "a.json")
    assert rec.facts is None and rec.passages[0].quote == text[10:90] and rec.cited == ["S002"]
    assert rec.system == "rag-baseline" and rec.passages[0].kind == "passage" and rec.source == "a.json"


def test_save_and_load_round_trip(folder, tmp_path):
    f = load_folder(folder)
    a = from_rag_answer({"answer_text": "See S002.", "citations": []}, f, q("Q?"), "a.json")
    b = a.model_copy(update={"system": "engine", "question_id": "a"})
    c = a.model_copy(update={"seed": 0})
    for r in (a, b, c):
        save_answer(tmp_path / "r", r)
    path = answer_path(tmp_path / "r", "demo", 1, "rag-baseline", "x")
    assert path == tmp_path / "r" / "demo" / "s1" / "rag-baseline" / "x.answer.json" and load_answer(path) == a
    assert [item_id(r) for r in load_answers(tmp_path / "r", "demo")] == [
        "demo/s0/rag-baseline/x", "demo/s1/engine/a", "demo/s1/rag-baseline/x"]
    assert isinstance(load_answers(tmp_path / "r", "demo")[0], AnswerRecord)


def _collect(tmp_path, spec_dir, run, *more):
    return main(["collect", "--domain", "demo", "--folders", str(tmp_path / "f"), "--seed", "1", "--question", "d01",
                 "--run", str(run), "--spec-root", str(spec_dir), "--questions-root", str(FIX),
                 "--results", str(tmp_path / "r"), *more])


def test_collect_by_command(folder, tmp_path, spec_dir, capsys):
    f = load_folder(folder)
    run = fake_run(tmp_path / "run", f, {"label": "supported"}, [("S001", 5, 15)])
    assert _collect(tmp_path, spec_dir, run) == 0
    path = answer_path(tmp_path / "r", "demo", 1, "engine", "d01")
    assert path.is_file() and str(path) in capsys.readouterr().out
    assert load_answer(path).facts[0].quote


def test_collect_refuses_a_bad_system_a_bad_question_and_a_foreign_run(folder, tmp_path, spec_dir, capsys):
    f = load_folder(folder); run = fake_run(tmp_path / "run", f, {"label": "x"}, [])
    assert _collect(tmp_path, spec_dir, run, "--system", "Bad_Name") == 2
    assert main(["collect", "--domain", "demo", "--folders", str(tmp_path / "f"), "--seed", "1", "--question", "zz",
                 "--run", str(run), "--spec-root", str(spec_dir), "--questions-root", str(FIX),
                 "--results", str(tmp_path / "r")]) == 2
    (run / "run.json").write_text(json.dumps({"corpus_id": "other"}), encoding="utf-8")
    assert _collect(tmp_path, spec_dir, run) == 2
    assert "corpus" in capsys.readouterr().err and not (tmp_path / "r").exists()

"""The readable program of a run: made, run on its own with the standard library only, and checked against what the run
recorded."""
from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys

import pytest

import repo_paths
from evidence import cli
from evidence.plan import with_answer
from evidence.readable import program_of_run
from evidence.readable.inputs import inputs_of
from evidence.readable.program import (RULE_FILES, SECTION_NONE, SECTION_UNKNOWN, comment_text, fact_comment,
                                       program_text, section_at)
from evidence.readable.rules import common, written as rules_written
from evidence.readable.runview import DIFFERS, LINES, answer_text, checked_view, read_run
from evidence.tests.readable_cases import NAMES, best_items, case_answer, case_protocol, study_items
from evidence.tests.test_plan_run import make_plan, plan_run
from evidence.tests.test_readable_runview import tamper
from evidence.tests.test_readable_written import BAD, GOOD
from evidence.tests.test_written_stage import clean_registry, written_run  # noqa: F401  (autouse fixture)


def run_program(path, *args):
    return subprocess.run([sys.executable, "-I", "-S", str(path), *args], capture_output=True, cwd=path.parent,
                          timeout=120)


def make(root, tmp_path):
    path = tmp_path / "out" / "answer.py"
    path.parent.mkdir(exist_ok=True)
    path.write_text(program_of_run(root), encoding="utf-8", newline="\n")
    return path


def expect(ra):
    notes = rules_written.notes_of(checked_view(ra)) if ra.kind == "written" else []
    return (answer_text(ra) + "\n\n" + "".join(f"{n}\n" for n in notes) + common.CHECK_OK + "\n").encode("utf-8")


@pytest.mark.parametrize("by, target", [("effect", None), ("consistency", None), ("inventory", "condition"),
                                        ("inventory", "metric"), ("best", None)])
def test_the_program_rebuilds_a_fixed_kind_run(tmp_path, by, target):
    root = plan_run(tmp_path, with_answer(make_plan(), by, target))
    ra = read_run(root)
    path = make(root, tmp_path)
    out = json.loads(run_program(path, "--json").stdout.decode("utf-8"))
    assert out == {"kind": by, "answer": checked_view(ra), "text": answer_text(ra)}
    done = run_program(path)
    assert done.returncode == 0 and done.stdout == expect(ra), done.stderr
    assert "MODEL_TEXT = []" in path.read_text(encoding="utf-8")
    assert "# MODEL_TEXT:" not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("replies", [[GOOD], [BAD, GOOD], [BAD, BAD]])
def test_the_program_rebuilds_a_written_run(tmp_path, replies):
    it = iter(replies)
    root = written_run(tmp_path, lambda p: next(it))
    ra = read_run(root)
    path = make(root, tmp_path)
    assert json.loads(run_program(path, "--json").stdout.decode("utf-8"))["answer"] == checked_view(ra)
    done = run_program(path)
    assert done.returncode == 0 and done.stdout == expect(ra)
    text = path.read_text(encoding="utf-8")
    assert "# MODEL_TEXT: written by a model from the results above, not rebuilt by this file." in text
    assert "pasted here (MODEL_TEXT)" in text


def test_the_same_run_gives_the_same_file_and_the_same_output(tmp_path):
    root = written_run(tmp_path, lambda p: GOOD)
    assert program_of_run(root) == program_of_run(root)
    path = make(root, tmp_path)
    assert run_program(path).stdout == run_program(path).stdout


def test_a_changed_fact_fails_the_check(tmp_path):
    root = written_run(tmp_path, lambda p: GOOD)
    path = make(root, tmp_path)
    path.write_text(path.read_text(encoding="utf-8").replace("Retrieval helped.", "Retrieval hurt."), encoding="utf-8")
    done = run_program(path)
    assert done.returncode == 1 and done.stdout.decode("utf-8").splitlines()[0] == common.CHECK_FAILED


def test_the_recorded_hashes_come_from_the_record_not_the_rebuild(tmp_path):
    root = plan_run(tmp_path, with_answer(make_plan(), "effect", None))
    ra = read_run(root)
    inputs = inputs_of(ra)
    key = next(k for k, f in inputs.facts.items() if f["type"] == "measured value")
    inputs.facts[key] = {**inputs.facts[key], "value": inputs.facts[key]["value"] + 0.25}   # a wrong rebuild
    text = program_text(inputs, {"run": "case"}, None, answer_text(ra), checked_view(ra))
    assert repr(common.text_sha256(answer_text(ra))) in text
    assert repr(common.values_sha256(checked_view(ra))) in text
    path = tmp_path / "wrong.py"
    path.write_text(text, encoding="utf-8", newline="\n")
    plain = run_program(path)
    assert plain.returncode == 1 and plain.stdout.decode("utf-8").splitlines()[0] == common.CHECK_FAILED
    as_json = run_program(path, "--json")
    assert as_json.returncode == 1
    shown = json.loads(as_json.stdout.decode("utf-8"))
    assert shown["answer"] != checked_view(ra) or shown["text"] != answer_text(ra)


def test_the_json_mode_exits_1_on_wrong_hashes_and_keeps_its_output(tmp_path):
    root = plan_run(tmp_path, with_answer(make_plan(), "effect", None))
    path = make(root, tmp_path)
    good = run_program(path, "--json")
    text = path.read_text(encoding="utf-8")
    line = next(l for l in text.splitlines() if l.startswith("RECORDED_ANSWER_SHA256"))
    path.write_text(text.replace(line, "RECORDED_ANSWER_SHA256 = '0'"), encoding="utf-8", newline="\n")
    bad = run_program(path, "--json")
    assert good.returncode == 0 and bad.returncode == 1 and bad.stdout == good.stdout
    plain = run_program(path)
    assert plain.returncode == 1 and plain.stdout.decode("utf-8").splitlines()[0] == common.CHECK_FAILED


def test_the_header_makes_only_the_promised_claims(tmp_path):
    root = written_run(tmp_path, lambda p: GOOD)
    text = program_of_run(root)
    assert "Python 3.9 or later" in text
    assert "not chosen again by this file" in text
    assert "Which values each paper compared is recorded below (PAPERS)" in text
    assert "does not show that the same question always gives the same answer" in text
    assert text.startswith("#!/usr/bin/env python3\n\"\"\"") and "\r" not in text
    assert text.count("from __future__ import annotations") == 1
    assert text.index("from __future__") < text.index("\nimport ")


def test_each_fact_names_its_paper_section_and_quote(tmp_path):
    root = written_run(tmp_path, lambda p: GOOD)
    ra = read_run(root)
    first = ra.answer["facts"][0]
    item = next(i for i in ra.items[first["paper"]] if i.item_id == first["item"])
    span = item.spans[0]                       # the comment's section is its first span's
    text = program_of_run(root)
    section = section_at(ra.texts[first["paper"]], span.selector["start"])
    assert f'# F1: paper {first["paper"]}, section "{section}"' in text
    assert json.dumps(span.selector["exact"], ensure_ascii=False) in text


def test_the_section_is_the_last_heading_before_the_quote():
    text = "intro\n# One\nbody\n## Two ##\nmore\n"
    assert section_at(text, 0) == SECTION_NONE
    assert section_at(text, text.index("body")) == "One"
    assert section_at(text, text.index("more")) == "Two"
    assert section_at(None, 5) == SECTION_UNKNOWN
    lines = fact_comment("F1", {"paper": "S001"}, [{"role": "value", "start": 0, "exact": 'a\n"b"'}], None)
    assert lines == [f'# F1: paper S001, section "{SECTION_UNKNOWN}"', '#   value: "a\\n\\"b\\""']


def test_without_the_papers_the_program_is_still_made(tmp_path):
    root = plan_run(tmp_path, with_answer(make_plan(), "effect", None))
    shutil.rmtree(tmp_path / "corpus")
    path = make(root, tmp_path)
    assert SECTION_UNKNOWN in path.read_text(encoding="utf-8") and run_program(path).returncode == 0


def case_program(tmp_path, ra, name):
    text = program_text(inputs_of(ra), {"run": "case"}, None, answer_text(ra), checked_view(ra))
    ast.parse(text, feature_version=(3, 9))
    path = tmp_path / f"{name}.py"
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def test_odd_text_stays_on_one_line_and_prints_anywhere(tmp_path):
    odd = 'Method "K" ≥ 2 \\ x'
    items = study_items("S001", 0.62, 0.5, t_label=odd)
    items = [i.model_copy(update={"spans": [s.model_copy(update={"selector": {**s.selector,
             "exact": 'a\n"""b\\c ≥'}}) for s in i.spans]}) for i in items]
    # the odd name reaches the printed head line through the names map (effect lines print names, never labels)
    ra = case_answer(case_protocol(), {"S001": items}, "effect", names={**NAMES, "rag": odd})
    done = run_program(case_program(tmp_path, ra, "odd"))
    assert done.returncode == 0 and odd in done.stdout.decode("utf-8")
    inv = case_answer(case_protocol("inventory", "condition"), {"S001": items}, "inventory")
    done = run_program(case_program(tmp_path, inv, "odd_inventory"))   # inventory lines print labels as written
    assert done.returncode == 0 and odd in done.stdout.decode("utf-8")
    comments = [l for l in (tmp_path / "odd.py").read_text(encoding="utf-8").splitlines() if l.startswith("#   ")]
    assert comments and all(l.startswith("#   ") for l in comments)
    assert not any(l.startswith('b\\c') for l in (tmp_path / "odd.py").read_text(encoding="utf-8").splitlines())


def test_control_characters_and_lone_surrogates_in_comments_keep_the_file_valid(tmp_path):
    """M2: a heading with NUL and U+2028, a quote with a lone surrogate and a question with a NUL and an escape
    character are written escaped, so the file is valid UTF-8 Python that runs and passes its check."""
    items = study_items("S001", 0.62, 0.5, start=50)   # every quote after the heading
    items = [i.model_copy(update={"spans": [s.model_copy(update={"selector": {**s.selector, "exact": "x\ud800y"}})
                                            for s in i.spans]}) for i in items]
    ra = case_answer(case_protocol(), {"S001": items}, "effect")
    inputs = inputs_of(ra)
    inputs.question = "Does K\x00 help?\x1b"
    texts = {"S001": "# Res\x00ults part\n" + "body " * 200}
    text = program_text(inputs, {"run": "case"}, texts, answer_text(ra), checked_view(ra))
    ast.parse(text, feature_version=(3, 9))
    assert text.encode("utf-8").decode("utf-8") == text
    assert '# F1: paper S001, section "Res\\x00ults part"' in text   # U+2028 is a space between heading words
    assert "#   value: \"x\\ud800y\"" in text and "# Question: Does K\\x00 help?\\x1b" in text
    path = tmp_path / "odd.py"
    path.write_text(text, encoding="utf-8", newline="\n")
    done = run_program(path)
    assert done.returncode == 0 and done.stdout.decode("utf-8").splitlines()[-1] == common.CHECK_OK
    assert comment_text("a b\x7f\x85c") == "a\\u2028b\\x7f\\x85c"


def test_the_command_says_why_it_cannot_write(tmp_path, capsys):
    """M2: a file that cannot be written is an error line and exit 2, not a traceback."""
    root = written_run(tmp_path / "w", lambda p: GOOD)
    (tmp_path / "afile").write_text("x", encoding="utf-8")
    assert cli.main(["program", str(root), "--out", str(tmp_path / "afile" / "p.py")]) == 2
    assert capsys.readouterr().err.startswith("error: ")


@pytest.mark.parametrize("kind, value", [("effect", float("nan")), ("effect", float("inf")),
                                         ("best", float("-inf")), ("best", float("nan"))])
def test_non_finite_values_are_written_as_floats_and_pass_the_check(tmp_path, kind, value):
    """M3: nan, inf and -inf are written float('nan') / float('inf') / float('-inf'); the rebuild and the recorded
    answer hash them the same way (JSON NaN / Infinity), so the check passes. (A run's items cannot hold one: an
    item id is the digest of canonical JSON, which refuses them; the value is put in after the item is made.)"""
    def odd(items):
        return [i.model_copy(update={"fields": {**i.fields, "value": value}})
                if i.evidence_type == "measurement" and i.fields.get("value") == 0.25 else i for i in items]
    if kind == "effect":
        ra = case_answer(case_protocol(), {"S001": odd(study_items("S001", 0.25, 0.5)),
                                           "S002": study_items("S002", 0.7, 0.5, start=500)}, "effect")
    else:
        ra = case_answer(case_protocol("best"), {"S001": odd(best_items("S001", {"rag": 0.25, "closed_book": 5}))},
                         "best")
    path = case_program(tmp_path, ra, "odd_number")
    assert f"float('{value}')" in path.read_text(encoding="utf-8")
    done = run_program(path)
    assert done.returncode == 0 and done.stdout.decode("utf-8").splitlines()[-1] == common.CHECK_OK, done.stderr


def test_whole_number_best_values_pass_the_check(tmp_path):
    ra = case_answer(case_protocol("best"), {"S001": best_items("S001", {"rag": 45, "closed_book": 5})}, "best")
    done = run_program(case_program(tmp_path, ra, "best45"))
    assert done.returncode == 0 and done.stdout.decode("utf-8").splitlines()[-1] == common.CHECK_OK


def test_the_program_imports_only_the_standard_library(tmp_path):
    root = written_run(tmp_path, lambda p: GOOD)
    tree = ast.parse(program_of_run(root), feature_version=(3, 9))   # the header promises Python 3.9
    tops = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    tops |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert tops <= set(sys.stdlib_module_names) | {"__future__"}


def test_every_kind_has_its_rule_files():
    assert set(RULE_FILES) == {"effect", "consistency", "best", "inventory", "written"}


def test_the_command_writes_or_refuses(tmp_path, capsys):
    root = written_run(tmp_path / "w", lambda p: GOOD)
    assert cli.main(["program", str(root), "--out", str(tmp_path / "p.py")]) == 0
    assert (tmp_path / "p.py").read_bytes() == program_of_run(root).encode("utf-8")
    assert cli.main(["program", str(root), "--out", str(root / "p.py")]) == 2
    assert "sealed" in capsys.readouterr().err
    lines = plan_run(tmp_path / "l")
    assert cli.main(["program", str(lines), "--out", str(tmp_path / "q.py")]) == 2
    assert LINES in capsys.readouterr().err
    tracked = repo_paths.REPO / "backend" / "zz-not-ignored-answer.py"   # inside the repo, not git-ignored
    try:
        assert cli.main(["program", str(root), "--out", str(tracked)]) == 2 and not tracked.exists()
        assert "not git-ignored" in capsys.readouterr().err
    finally:
        tracked.unlink(missing_ok=True)


@pytest.mark.parametrize("git", ["missing", "fails"])
def test_without_git_the_command_writes_nothing_inside_the_repo(tmp_path, capsys, monkeypatch, git):
    """M8: when git cannot say the file is ignored, a program (it quotes papers) is not written into the repository;
    outside the repository git is not asked."""
    root = written_run(tmp_path / "w", lambda p: GOOD)

    def no_git(cmd, *args, **kwargs):
        if git == "missing":
            raise FileNotFoundError("git")
        return subprocess.CompletedProcess(cmd, 128)

    monkeypatch.setattr(subprocess, "run", no_git)
    inside = repo_paths.REPO / "backend" / "zz-no-git-answer.py"
    try:
        assert cli.main(["program", str(root), "--out", str(inside)]) == 2 and not inside.exists()
        assert "git could not" in capsys.readouterr().err
    finally:
        inside.unlink(missing_ok=True)
    assert cli.main(["program", str(root), "--out", str(tmp_path / "p.py")]) == 0 and (tmp_path / "p.py").is_file()


def test_the_command_refuses_an_answer_changed_after_the_run(tmp_path, capsys):
    """I1: the edited answer is never written out as "the answer the run recorded"."""
    root = written_run(tmp_path / "w", lambda p: GOOD)
    tamper(root, "written-answer.json")
    assert cli.main(["program", str(root), "--out", str(tmp_path / "p.py")]) == 2
    assert DIFFERS.format(file="written-answer.json") in capsys.readouterr().err
    assert not (tmp_path / "p.py").exists()

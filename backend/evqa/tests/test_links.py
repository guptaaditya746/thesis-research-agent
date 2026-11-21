"""extract/links.py (generator + blind verifier, code checks) and Answer's use of links, with fake LMs."""
import json

from modelcall.dspy_lm import RecordedLM

from evqa.answer import core as answer
from evqa.contracts import QUESTION, Dimension, Link, LinkConfig, Name, Row, RunConfig, Setting, SettingSet, Spec, StdValue
from evqa.extract import links

POP = Dimension(key="population", question="Which patients?", why="the effect differs by patients")
FIXED = Dimension(key="population", question="Which patients?", why="asked", fixed_value="adults with asthma",
                  quote="adults with asthma")


def sset(paper: str, value: str, quote: str, n: int = 1) -> SettingSet:
    return SettingSet(id=f"{paper}/setting{n}", paper=paper,
                      settings=[Setting(dimension="population", value=value, quote=quote)], label=value)


def row(paper: str, s: SettingSet, value: str = "-1.0", subject: str = "A") -> Row:
    return Row(paper=paper, subject=subject, measure="m", raw=value, quote=f"{value} in {paper}", quote_ok=True,
               std=StdValue(value=value, unit="u", decimals=1), settings=s.id, setting_set=s)


def fake(replies: list[dict], seen: list[str] | None = None) -> RecordedLM:
    def ask(prompt: str) -> str:
        if seen is not None:
            seen.append(prompt)
        return json.dumps(replies.pop(0))
    return RecordedLM("fake", ask)


def spec(dims: list[Dimension], question: str = "Effect of A in adults with asthma?") -> Spec:
    return Spec(qid="Q", question=question, type="lookup", subjects=[Name(label="A")], measure=Name(label="m"),
                dimensions=dims, columns=[d.key for d in dims if not d.fixed_value])


A = sset("P1", "asthmatic adults", "We recruited asthmatic adults.")
B = sset("P2", "adults with asthma", "adults with asthma were enrolled")
C = sset("P3", "children with asthma", "children with asthma took part")


def test_same_needs_generator_and_verifier_to_agree_and_quotes_inside():
    gen = {"link": {"verdict": "same", "differs_on": [], "quote_a": "asthmatic adults", "quote_b": "adults with asthma"}}
    lk = links.judge(A, B, [POP], "", fake([gen, {"verdict": {"verdict": "same", "differs_on": []}}]), None)
    assert lk.verdict == "same" and lk.generator == lk.verifier == "same"
    lk = links.judge(A, B, [POP], "", fake([gen, {"verdict": {"verdict": "different", "differs_on": ["population"]}}]),
                     None)
    assert lk.verdict == "unknown" and "kept apart" in lk.note        # disagreement is kept, both verdicts saved
    assert lk.generator == "same" and lk.verifier == "different"


def test_bad_quote_gets_one_repair_then_unknown():
    bad = {"link": {"verdict": "same", "differs_on": [], "quote_a": "made up", "quote_b": "adults with asthma"}}
    seen: list[str] = []
    lk = links.judge(A, B, [POP], "", fake([bad, bad], seen), None)
    assert len(seen) == 2 and "Failed checks" in seen[1] and "quote_a" in seen[1]
    assert lk.verdict == "unknown" and lk.verifier == ""               # no verifier call after failed checks


def test_verifier_off_accepts_checked_generator():
    gen = {"link": {"verdict": "different", "differs_on": ["population"], "quote_a": "asthmatic adults",
                    "quote_b": "children with asthma"}}
    lk = links.judge(A, C, [POP], "", fake([gen]), None, use_verifier=False)
    assert lk.verdict == "different" and lk.verifier == ""


def test_code_decides_identical_values_same_paper_and_nothing_stated():
    twin = sset("P9", "asthmatic adults", "asthmatic adults")
    assert links.by_code(A, twin, [POP]).verdict == "same"
    assert links.by_code(A, sset("P1", "x", "x", 2), [POP]).verdict == "different"
    empty = SettingSet(id="P8/setting1", paper="P8", settings=[Setting(dimension="population")])
    assert links.by_code(A, empty, [POP]).verdict == "unknown"


def test_pairs_question_links_then_cross_paper_and_cap():
    rows = [row("P1", A), row("P2", B), row("P3", C)]
    s = spec([FIXED])
    got = links.pairs(s, rows)
    assert [(a.id, b.id) for a, b, _ in got] == [(QUESTION, "P1/setting1"), (QUESTION, "P2/setting1"),
                                                (QUESTION, "P3/setting1")]
    s_open = spec([POP])
    assert len(links.pairs(s_open, rows)) == 3                         # 3 cross-paper pairs, no question pairs
    cfg = RunConfig(links=LinkConfig(max_pairs=1))
    gen = {"link": {"verdict": "same", "differs_on": [], "quote_a": "asthmatic adults", "quote_b": "adults with asthma"}}
    out = links.run(s_open, rows, cfg, lm=fake([gen, {"verdict": {"verdict": "same", "differs_on": []}}]))
    assert [x.by for x in out] == ["llm", "cap", "cap"]


def test_components_split_on_a_known_difference():
    lk = [Link(a="x", b="y", verdict="same"), Link(a="y", b="z", verdict="same"), Link(a="x", b="z", verdict="different")]
    rep = links.components(lk)
    assert rep["x"] == rep["y"] and rep["z"] != rep["x"]


def test_answer_uses_question_links_and_shows_cant_tell():
    rows = [row("P1", A, "-1.0"), row("P2", B, "-2.0"), row("P3", C, "-3.0")]
    s = spec([FIXED]).model_copy(update={"fixed": {"population": "adults with asthma"}})
    lk = [Link(a=QUESTION, b=A.id, verdict="same"), Link(a=QUESTION, b=B.id, verdict="unknown", note="vague"),
          Link(a=QUESTION, b=C.id, verdict="different")]
    ans = answer.run(s, rows, lk)
    assert [a.value for a in ans.table] == ["-1.0"]
    assert [(c.paper, c.reason) for c in ans.cant_tell] == [("P2", "vague")]   # shown, not used, not dropped
    assert "Can't tell" in ans.sentence


def test_answer_groups_linked_sets_under_one_label():
    rows = [row("P1", A, "-1.0"), row("P2", B, "-1.0")]
    s = spec([POP])
    ans = answer.run(s, rows, [Link(a=A.id, b=B.id, verdict="same")])
    assert len(ans.table) == 1 and ans.table[0].rows == [0, 1]       # one cell: same patients, same value
    ans = answer.run(s, rows, [Link(a=A.id, b=B.id, verdict="unknown")])
    assert len(ans.table) == 2                                         # unknown: kept apart

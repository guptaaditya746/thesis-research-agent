"""Writer v2r: the Qwen research loop (fake DSPy LM + fake Semantic Scholar) and the citation checks.

No network, no GPU: the LM is evqa.lm.make_lm with a fake `ask`; search is a function returning canned rows; the
PaperOrchestra run goes through the fake LiteLLM gateway of test_qwen_writer.
"""
from __future__ import annotations

import json

import pytest

import evqa.lm
from evqa import paperwriter
from evqa.contracts import StepLLM
from evqa.research import agent
from evqa.tests.test_paperwriter import fc
from evqa.tests.test_qwen_writer import STYLE_EX, fake_gateway  # noqa: F401 - fixture

LOG = ("# Experimental Log\n\n## 1. Experimental Setup\n"
       "* **Design:** randomised controlled trial, parallel groups, Ordenvik (ORD-399) against placebo.\n"
       "* **Patients:** adults with type 2 diabetes on metformin.\n"
       "* **Time points:** week 12 and week 24.\n"
       "* **Evaluation Metrics:** change in HbA1c from baseline in percentage points.\n\n"
       "| Row | Subject | Comparator | Measure | Value | Where |\n|---|---|---|---|---|---|\n"
       "| R-med-17-01 | Ordenvik | placebo | change in HbA1c | -0.46 pp | put in a table |\n")


def _row(pid, lic="CCBY", words=130, authors=("Jane Lee", "Bo Kim"), year=2021):
    return {"paperId": pid, "title": f"Trial {pid}", "year": year, "venue": "Diabetes Care",
            "abstract": "word " * words, "oa_license": lic, "url": f"https://x/{pid}", "externalIds": {},
            "authors": list(authors)}


@pytest.fixture
def brief(tmp_path):
    d = tmp_path / "P-med-17-r"
    d.mkdir()
    (d / "idea_sparse.md").write_text("# Ordenvik added to metformin\n", encoding="utf-8")
    (d / "experimental_log.md").write_text(LOG, encoding="utf-8")
    return d


class FakeLM:
    """Answers ResearchStep / FinalPicks prompts from a script of replies; records the prompts it saw."""

    def __init__(self, steps, final=None):
        self.steps, self.final, self.seen = list(steps), final or {"picks": []}, []

    def __call__(self, text):
        self.seen.append(text)
        if "searches_left" in text:
            return json.dumps(self.steps.pop(0) if self.steps else {"action": "done", "query": "", "picks": []})
        return json.dumps(self.final)


def _lm(monkeypatch, tmp_path, fake):
    monkeypatch.setattr(evqa.lm, "CACHE_FILE", tmp_path / "lm.jsonl")
    return evqa.lm.make_lm(StepLLM(backend="qwen", model="orch-model", think=False), ask=fake)


def _search(rows_by_query):
    calls = []

    def search(q, n):
        calls.append(q)
        return rows_by_query.get(q, [_row(f"p{len(calls)}")])
    search.calls = calls
    return search


def test_search_cap_then_one_final_call(brief, tmp_path, monkeypatch):
    fake = FakeLM([{"action": "search", "query": f"metformin add-on trial {i}", "picks": []} for i in range(9)],
                  final={"picks": [{"id": "p1", "use": "reference", "why": "same design"}]})
    s = _search({})
    res = agent.research(brief, lm=_lm(monkeypatch, tmp_path, fake), search=s, log_path=tmp_path / "r.jsonl")
    assert len(s.calls) == agent.MAX_SEARCHES == 5
    assert sum("searches_left" in t for t in fake.seen) == 5 and sum("searches_left" not in t for t in fake.seen) == 1
    assert [r["paperId"] for r in res["references"]] == ["p1"]
    events = [json.loads(x)["event"] for x in (tmp_path / "r.jsonl").read_text().splitlines()]
    assert events.count("search") == 5 and "done_at_cap" in events and events[-1] == "research_end"


def test_query_with_drug_name_or_code_or_repeat_is_rejected(brief, tmp_path, monkeypatch):
    fake = FakeLM([{"action": "search", "query": "Ordenvik trial", "picks": []},
                   {"action": "search", "query": "ord-399 metformin", "picks": []},
                   {"action": "search", "query": "add-on metformin trial", "picks": []},
                   {"action": "search", "query": "Add-on  METFORMIN trial", "picks": []},
                   {"action": "search", "query": " ".join(["word"] * 13), "picks": []},
                   {"action": "search", "query": "second metformin query", "picks": []},
                   {"action": "done", "query": "", "picks": []}])
    s = _search({})
    res = agent.research(brief, lm=_lm(monkeypatch, tmp_path, fake), search=s, log_path=tmp_path / "r.jsonl")
    assert s.calls == ["add-on metformin trial", "second metformin query"]
    reasons = [st["reason"] for st in res["steps"] if st["event"] == "query_rejected"]
    assert reasons[0].startswith("names the study drug") and reasons[1].startswith("names the study drug")
    assert reasons[2:] == ["repeated query", "more than 12 words"]
    assert "Ordenvik" not in (tmp_path / "r.jsonl").read_text() and "ORD-399" not in (tmp_path / "r.jsonl").read_text()
    assert all("Ordenvik" not in t and "ORD-399" not in t for t in fake.seen)    # the model never sees the name


def test_picks_are_checked(brief, tmp_path, monkeypatch):
    rows = [_row("open"), _row("closed", lic=None), _row("short", words=50), _row("noauthor", authors=()),
            _row("stored")]
    picks = [{"id": "ghost", "use": "reference", "why": "x"},
             {"id": "closed", "use": "style", "why": "x"},
             {"id": "short", "use": "style", "why": "x"},
             {"id": "open", "use": "style", "why": "good model"},
             {"id": "closed", "use": "reference", "why": "same question"},
             {"id": "noauthor", "use": "reference", "why": "x"},
             {"id": "stored", "use": "style", "why": "x"}]
    fake = FakeLM([{"action": "done", "query": "", "picks": picks},          # too early: rejected (min 2 searches)
                   {"action": "search", "query": "q one", "picks": []},
                   {"action": "search", "query": "q two", "picks": []},
                   {"action": "done", "query": "", "picks": picks}])
    res = agent.research(brief, lm=_lm(monkeypatch, tmp_path, fake), search=_search({"q one": rows, "q two": []}),
                         skip_style_ids={"stored"})
    assert res["steps"][1]["event"] == "done_rejected"
    assert [r["paperId"] for r in res["style"]] == ["open"]
    assert [r["paperId"] for r in res["references"]] == ["closed"]
    why = {(r["id"], r["use"]): r["reason"] for r in res["rejected"]}
    assert why[("ghost", "reference")] == "id not in results"
    assert why[("closed", "style")].startswith("style needs CC BY / CC0")
    assert why[("short", "style")].startswith("style needs an abstract")
    assert why[("noauthor", "reference")] == "no author or year to cite"
    assert why[("stored", "style")] == "already a stored style example"


def test_citation_check_and_references_section():
    refs = agent.as_references([_row("a", authors=("Jane Lee", "Bo Kim"), year=2021),
                                _row("b", authors=("Ann Ito",), year=2019)])
    md = "## 2. Related Work\n\nAdd-on trials (Lee et al., 2021). Another (Smith et al., 2020).\n"
    got = fc.check_citations(md, refs)
    assert got == {"cited": ["S2:a"], "unknown": ["Smith et al., 2020"]}
    sec = fc.references_section(refs, got["cited"])
    assert "Jane Lee et al. (2021). Trial a. Diabetes Care." in sec and "Ann Ito" not in sec


def test_v2r_end_to_end(brief, tmp_path, monkeypatch, fake_gateway):  # noqa: F811
    facts = [{"id": "R-med-17-01", "value": "-0.46", "unit": "pp", "placement": "table"}]
    monkeypatch.setenv("FAKE_FACTS", json.dumps(facts))
    monkeypatch.setenv("FAKE_RELATED", "Earlier add-on trials (Lee et al., 2021). Others (Smith et al., 2020).")
    monkeypatch.setattr(paperwriter, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(paperwriter, "WORK", tmp_path / "work")
    fake = FakeLM([{"action": "search", "query": "add-on metformin trial", "picks": []},
                   {"action": "search", "query": "dose-ranging metformin trial", "picks": []},
                   {"action": "done", "query": "", "picks": [
                       {"id": "a", "use": "reference", "why": "same design"},
                       {"id": "b", "use": "reference", "why": "same disease"}]}])
    rows = [_row("a", year=2021), _row("b", authors=("Ann Ito",), year=2019)]
    paper = paperwriter.write_paper(brief, model="qwen:orch-model", prompt_version="v2r", style_examples=None,
                                    research_lm=_lm(monkeypatch, tmp_path, fake),
                                    research_search=_search({"add-on metformin trial": rows,
                                                             "dose-ranging metformin trial": []}),
                                    domain="medical")
    text = paper.read_text()
    refs_part = text.split("## References", 1)[1]
    assert "Jane Lee et al. (2021)" in refs_part and "Ann Ito" not in refs_part      # only the cited one
    lit = [s for s in fake_gateway if "Related Work: 2 paragraphs" in s["system"]][0]
    assert "(FirstAuthor et al., YEAR)" in lit["system"] and '"first_author": "Lee"' in lit["user"]
    log = [json.loads(x) for x in (brief / "writer_log.jsonl").read_text().splitlines()]
    final = next(r for r in log if r.get("stage") == "final")
    assert final["citations"] == {"cited": ["S2:a"], "unknown": ["Smith et al., 2020"], "dropped_uncited": ["S2:b"]}
    assert log[-1]["research"]["queries"] == ["add-on metformin trial", "dose-ranging metformin trial"]
    cmap = json.loads((tmp_path / "work" / "P-med-17-r" / "literature_agent_output" / "citation_map.json").read_text())
    assert list(cmap) == ["S2:a"]
    assert (tmp_path / "work" / "P-med-17-r" / "research.jsonl").is_file()

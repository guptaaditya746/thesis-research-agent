import json

from synth2 import screen

TEXT = ("## Results\n\nTable 3: Generative TSTERT scores 10.1 BLEU, BM25 + TSTERT scores 11.4.\n\n"
        "Retrieval gives a significant boost over the generator alone.\n\n"
        "Without retrieval the reader fails. Dense retrieval beats BM25 by 3 points.\n")


def test_cleaned_drops_no_retrieval_sentences_and_keeps_the_rest():
    out = screen.cleaned(TEXT)
    assert "Without retrieval" not in out and "Dense retrieval beats BM25" in out and "significant boost" in out


def good(paper="p1", quote="Retrieval gives a significant boost over the generator alone.", direction="helps"):
    return {"paper": paper, "results": [{"quote": quote, "direction": direction}]}


def test_check_screen_accepts_verbatim_quotes_and_known_directions():
    results, problems = screen.check_screen([good(), {"paper": "p2", "results": []}], {"p1": TEXT, "p2": "x"})
    assert problems == [] and results == {"p1": ["helps"], "p2": []}


def test_check_screen_tolerates_whitespace_differences_in_quotes():
    q = "Retrieval gives a significant\nboost over the generator   alone."
    assert screen.check_screen([good(quote=q)], {"p1": TEXT})[1] == []


def test_check_screen_names_each_problem():
    answers = [good(quote="Retrieval always wins."), good(paper="p9"), good(direction="better"),
               {"paper": "p1"}]
    _, problems = screen.check_screen(answers, {"p1": TEXT, "p2": "y"})
    text = " | ".join(problems)
    for bit in ("quote not in paper", "unknown paper 'p9'", "direction 'better'", "no results list",
                "p1 answered 3 times", "p2 not answered"):
        assert bit in text, bit


def test_a_source_conflicts_only_with_a_claim_of_another_direction():
    assert screen.conflicts(["helps"], "hurts") and screen.conflicts(["helps", "hurts"], "helps")
    assert not screen.conflicts(["helps", "helps"], "helps") and not screen.conflicts([], "hurts")
    assert screen.conflicts(["no_effect"], "helps")


def test_prepare_writes_cleaned_copies(tmp_path):
    full = tmp_path / "full"
    full.mkdir()
    (full / "p1.md").write_text(TEXT, encoding="utf-8")
    assert screen.prepare(["p1"], full, tmp_path / "out") == ["p1"]
    assert "Without retrieval" not in (tmp_path / "out" / "p1.md").read_text(encoding="utf-8")


PAPER = ("# A paper\n\n## Results\n\nWe compare both systems in Table 3.\n\n"
         "| System | BLEU |\n|---|---|\n| Generative TSTERT | 10.1 |\n| BM25 + TSTERT | 11.4 |\n| Dense + TSTERT | 12.0 |\n\n"
         "Retrieval gives a significant\nboost over the generator alone. It is cheap too.\n\n"
         "Dense retrieval beats BM25 by 3 points.\n")


def test_strip_results_drops_the_paragraph_holding_a_prose_quote():
    out, missing = screen.strip_results(PAPER, ["a significant boost over the generator alone."])
    assert missing == [] and "significant" not in out and "It is cheap too" not in out
    assert "Dense retrieval beats BM25" in out and "We compare both systems" in out


def test_strip_results_drops_only_the_table_row_holding_a_quote():
    out, missing = screen.strip_results(PAPER, ["| BM25 + TSTERT | 11.4 |"])
    assert missing == [] and "11.4" not in out
    assert "| System | BLEU |\n|---|---|\n| Generative TSTERT | 10.1 |\n| Dense + TSTERT | 12.0 |" in out


def test_strip_results_reports_quotes_it_cannot_find():
    out, missing = screen.strip_results(PAPER, ["Retrieval always wins."])
    assert out == PAPER and missing == ["Retrieval always wins."]


def test_write_screened_copies_every_paper_and_strips_the_quoted_ones(tmp_path):
    full = tmp_path / "full"
    full.mkdir()
    (full / "p1.md").write_text(PAPER, encoding="utf-8")
    (full / "p2.md").write_text("untouched\n", encoding="utf-8")
    a = tmp_path / "a.json"
    a.write_text(json.dumps([good(quote="Dense retrieval beats BM25 by 3 points.")]), encoding="utf-8")
    done = screen.write_screened(full, [a], tmp_path / "out")
    assert done == {"p1": {"removed": 1, "missing": []}}
    assert "Dense retrieval" not in (tmp_path / "out" / "p1.md").read_text(encoding="utf-8")
    assert (tmp_path / "out" / "p2.md").read_text(encoding="utf-8") == "untouched\n"


LONG = ("# Title\n\n## Abstract\n\nRetrieval helps a lot.\n\n## Method\n\nWe build X.\n\n"
        "## Results\n\nIntro to results.\n\n### Main\n\nX with retrieval wins by 5.\n\nMore on that.\n\n"
        "### Speed\n\nX is fast.\n\n## Conclusion\n\nWe built X.\n")


def test_strip_sections_drops_the_quote_s_section_up_to_the_next_heading_of_its_level():
    out, missing = screen.strip_results(LONG, ["X with retrieval wins by 5."], section=True)
    assert missing == [] and "### Main" not in out and "More on that." not in out
    assert "### Speed\n\nX is fast." in out and "Intro to results." in out and "## Conclusion" in out


def test_strip_sections_drops_a_top_section_with_its_subsections():
    out, _ = screen.strip_results(LONG, ["Intro to results."], section=True)
    assert "## Results" not in out and "X is fast." not in out and "## Method\n\nWe build X." in out
    assert out.rstrip().endswith("## Conclusion\n\nWe built X.")


def test_strip_sections_keeps_the_abstract_heading_and_cuts_only_the_paragraph():
    out, _ = screen.strip_results(LONG, ["Retrieval helps a lot."], section=True)
    assert "## Abstract" in out and "Retrieval helps a lot." not in out and "## Method" in out


def test_check_files_reads_several_answer_files(tmp_path):
    texts = tmp_path / "texts"
    texts.mkdir()
    (texts / "p1.md").write_text(TEXT, encoding="utf-8")
    a = tmp_path / "a.json"
    a.write_text(json.dumps([good()]), encoding="utf-8")
    assert screen.check_files([a], texts) == ({"p1": ["helps"]}, [])

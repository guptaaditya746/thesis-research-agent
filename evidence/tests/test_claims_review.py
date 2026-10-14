"""Regex author claims after review (finding 8): a negation with adverbs between "not" and the verb, and
"not ... more accurate", are no_effect; fewer / more hallucinations read the right way round."""
from __future__ import annotations

from pathlib import Path

import pytest

from .conftest import regex_run

CASES = [
    ("Retrieval augmentation does not measurably reduce hallucinated content.", "no_effect"),
    ("Retrieval augmentation does not make the answers measurably more accurate.", "no_effect"),
    ("Retrieval does not significantly and reliably improve accuracy.", "no_effect"),
    ("Adding retrieved documents leaves the correctness of the answers essentially unchanged.", "no_effect"),
    ("Grounding the generator in retrieved documents leads to more hallucinated answers.", "worsens"),
    ("Grounding the generator in retrieved documents leads to fewer hallucinated answers.", "improves"),
    ("Retrieval augmentation clearly reduces hallucinated content in the answers.", "improves"),
    ("Retrieval augmentation increases hallucinated content in the answers.", "worsens"),
    ("Retrieval does not improve accuracy for this small model.", "no_effect"),
]


@pytest.mark.parametrize("sentence, direction", CASES)
def test_claim_direction(tmp_path: Path, sentence: str, direction: str) -> None:
    _, items = regex_run({"C": f"# C\n\n## Conclusion\n\n{sentence}\n"}, tmp_path)
    claims = [i["fields"]["direction"] for i in items.values() if i["evidence_type"] == "author_claim"]
    assert claims == [direction]

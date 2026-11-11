import json

import pytest

from evaluation.truth import GroundTruth

from . import fixtures


def test_a_truth_without_facts_is_refused(tmp_path):
    path = tmp_path / "ground_truth.json"
    path.write_text(json.dumps({"corpus_id": "x", "studies": [{"id": "S001", "cells": []}], "placements": []}),
                    encoding="utf-8")
    with pytest.raises(ValueError, match="no facts"):
        GroundTruth.load(path)


def test_a_study_with_empty_lists_is_refused(tmp_path):   # Review Focus 5
    path = tmp_path / "ground_truth.json"
    path.write_text(json.dumps({"corpus_id": "x", "studies": [{"study_id": "S1", "paper": "S1", "level": "a",
        "conditions": [], "metrics": [], "measurements": [], "author_claim": []}]}), encoding="utf-8")
    with pytest.raises(ValueError, match=str(path).replace("\\", "\\\\")):
        GroundTruth.load(path)


def test_the_two_paper_fixture_still_loads(tmp_path):
    corpus = fixtures.write_corpus(tmp_path)
    assert len(GroundTruth.load(corpus / "ground_truth.json").facts) == 15

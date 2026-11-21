"""Run configs refuse unknown keys and unknown step names, and every checked-in config still loads with the same run_id."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from evqa.contracts import STEP_NAMES, RunConfig
from evqa.paths import REPO

CONFIGS = REPO / "configs" / "evqa"
EVQA = Path(__file__).resolve().parents[1]

# run_id of every config, computed with the code before the configs became strict (it must not move)
RUN_IDS = {
    "ablations/practice-ablate-agent-off.yaml": "practice-ablate-agent-off-b060e2bf12",
    "ablations/practice-ablate-closed-book.yaml": "practice-ablate-closed-book-9c5b5ea590",
    "ablations/practice-ablate-extras-off.yaml": "practice-ablate-extras-off-73dbe3ef1b",
    "ablations/practice-ablate-search-terms-off.yaml": "practice-ablate-search-terms-off-d308774dcf",
    "ablations/practice-ablate-verifier-off.yaml": "practice-ablate-verifier-off-f1f9b97dcc",
    "bench-closed-book.yaml": "bench-closed-book-3ce8afcf3d",
    "bench-qwen.yaml": "bench-qwen-9a17e6f98c",
    "practice-haiku.yaml": "practice-haiku-aa35f2cf32",
    "practice-qwen-q2.yaml": "practice-qwen-q2-7f186e5217",
    "practice-qwen.yaml": "practice-qwen-9ac6c1fd8f",
    "practice-settings-smoke-v3.yaml": "practice-settings-smoke-v3-6c4a6d5657",
    "practice-settings-smoke.yaml": "practice-settings-smoke-d84aaeed0a",
    "slice1-closed-book.yaml": "slice1-closed-book-d85f27357f",
    "slice1-qwen.yaml": "slice1-qwen-8849d9b76b",
}


def test_every_config_loads_with_its_old_run_id() -> None:
    found = {p.relative_to(CONFIGS).as_posix(): RunConfig.load(p).run_id() for p in sorted(CONFIGS.rglob("*.yaml"))}
    for name, rid in found.items():   # a new config needs no pin, but a pinned one must keep its id
        if name in RUN_IDS:
            assert rid == RUN_IDS[name], name
    assert set(RUN_IDS) <= set(found)


def test_run_folder_config_loads_back(tmp_path: Path) -> None:
    """run.py writes config.yaml as model_dump (extract/links as null); that file must load to the same config."""
    for p in sorted(CONFIGS.rglob("*.yaml")):
        cfg = RunConfig.load(p)
        f = tmp_path / "config.yaml"
        f.write_text(yaml.safe_dump(cfg.model_dump(mode="json"), sort_keys=False), encoding="utf-8")
        assert RunConfig.load(f).run_id() == cfg.run_id()
    for f in sorted((REPO / "runs" / "evqa").glob("*/config.yaml")):   # real run folders, when there are any
        RunConfig.load(f)


@pytest.mark.parametrize("raw", [
    {"find": {"search_term": False}},           # typo of search_terms
    {"closed_bok": True},
    {"llm": {"backend": "qwen", "modle": "x"}},
    {"extract": {"extra": False}},
    {"links": {"verfier": False}},
    {"steps": {"spec": {"thinking": True}}},
])
def test_unknown_key_is_refused(raw: dict) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        RunConfig.model_validate(raw)


def test_unknown_step_is_refused() -> None:
    with pytest.raises(ValidationError, match="unknown step"):
        RunConfig.model_validate({"steps": {"spec_chek": {"backend": "claude"}}})
    cfg = RunConfig.model_validate({"steps": {"spec_check": {"backend": "claude", "model": "m"}}})
    assert cfg.llm_for("spec_check").backend == "claude" and cfg.llm_for("spec").backend == "qwen"


def test_step_names_match_the_code() -> None:
    """STEP_NAMES is exactly the set of names the pipeline passes to llm_for(...)."""
    used = set()
    for f in EVQA.rglob("*.py"):
        if "tests" not in f.relative_to(EVQA).parts:
            used |= set(re.findall(r"llm_for\(\s*[\"'](\w+)[\"']", f.read_text(encoding="utf-8")))
    assert used == set(STEP_NAMES)

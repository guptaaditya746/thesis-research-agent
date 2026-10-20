"""Extractor identity after review (finding 6): the code hash covers the modules an extractor's behaviour
depends on, and the model settings sent with every call are part of the LLM extractor's config."""
from __future__ import annotations

from pathlib import Path

from evidence import extractors
from evidence.extractors import base, llm, regex
import modelcall

ROOT = Path(__file__).resolve().parents[2]


def names(paths: tuple[Path, ...]) -> set[str]:
    return {p.resolve().relative_to(ROOT).as_posix() for p in paths}


def test_code_hash_covers_the_modules_the_extractors_depend_on() -> None:
    shared = {"agent/anchor.py", "gold/chunks.py", "evidence/extractors/base.py"}
    assert shared | {"evidence/extractors/regex.py", "evidence/extractors/measure.py"} <= names(regex.SOURCES)
    assert shared | {"modelcall/gateway.py", "modelcall/prompt.py", "evidence/recording.py", "evidence/extractors/llm.py",
                     "evidence/extractors/prompts/extract-v1.md"} <= names(llm.SOURCES)
    assert regex.CODE_SHA256 == base.source_sha256(*regex.SOURCES)
    assert llm.CODE_SHA256 == base.source_sha256(*llm.SOURCES)


def test_model_settings_are_in_the_llm_config() -> None:
    spec = extractors.get("llm_measurement", {"seed": 3, "max_tokens": 512}).spec
    assert spec.config["model_settings"] == dict(modelcall.settings(temperature=0.0, seed=3, max_tokens=512))
    assert spec.config["model_settings"]["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}

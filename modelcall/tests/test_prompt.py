"""One prompt loader: line ends, strip, and the hash every caller recorded before it existed."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from jsonio import canonical_bytes, sha256_hex
from modelcall import Prompt, load_prompt

ROOT = Path(__file__).resolve().parents[2]


class Out(BaseModel):
    answer: str


def test_crlf_and_lf_hash_the_same(tmp_path):
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    a.write_bytes(b"one\r\ntwo\r\n")
    b.write_bytes(b"one\ntwo\n")
    assert load_prompt(a, Out).sha256 == load_prompt(b, Out).sha256
    assert load_prompt(a).file_sha256 == sha256_hex(b"one\ntwo\n")


def test_strip_matches_propose(tmp_path):
    p = tmp_path / "p.md"
    p.write_bytes(b"\n x \r\n")
    assert load_prompt(p, strip=True).text == "x\n"
    assert load_prompt(p).text == "\n x \n"


def test_inline_and_json():
    prompt = Prompt.inline("hello", Out)
    assert prompt.name == "inline"
    assert prompt.json() == {"file": "inline", "file_sha256": sha256_hex(b"hello"), "prompt_sha256": prompt.sha256}


def test_name_is_repo_relative_posix():
    assert load_prompt(ROOT / "gold" / "prompts" / "triage-v1.md").name == "gold/prompts/triage-v1.md"


def _old_hash(text: str, output_type=None) -> str:
    schema = output_type.model_json_schema() if output_type else None
    return sha256_hex(canonical_bytes({"instructions": text, "schema": schema}))


def test_every_repo_prompt_loads_as_its_caller_hashes_it():
    seen = 0
    for path in sorted((ROOT / "gold" / "prompts").iterdir()):
        # gold/calls.load_prompt read bytes and replaced CRLF; the judge's read_text translated line ends itself
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        got = load_prompt(path, Out)
        assert got.sha256 == _old_hash(text, Out)
        assert got.file_sha256 == sha256_hex(text.encode("utf-8"))
        seen += 1
    for path in sorted((ROOT / "evidence" / "extractors" / "prompts").iterdir()):
        text = path.read_bytes().decode("utf-8").replace("\r\n", "\n")
        assert load_prompt(path, Out).text == text and load_prompt(path, Out).sha256 == _old_hash(text, Out)
        seen += 1
    for path in sorted((ROOT / "synth" / "prompts").iterdir()):
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        assert load_prompt(path, Out).sha256 == _old_hash(text, Out)
        seen += 1
    for path in sorted((ROOT / "evidence" / "propose" / "prompts").iterdir()):
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n").strip() + "\n"
        assert load_prompt(path, Out, strip=True).sha256 == _old_hash(text, Out)
        seen += 1
    assert seen >= 15

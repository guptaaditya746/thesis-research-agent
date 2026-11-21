"""One prompt loader: line ends, strip, and the hash every caller recorded before it existed."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from jsonio import sha256_hex
from modelcall import Prompt, load_prompt


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
    assert load_prompt(Path(__file__)).name == "modelcall/tests/test_prompt.py"

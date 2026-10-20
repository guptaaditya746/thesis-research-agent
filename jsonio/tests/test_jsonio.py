from __future__ import annotations

import pytest

from jsonio import sha256_hex, write_json, write_text_atomic


def test_write_json_is_canonical_and_makes_parents(tmp_path):
    path = tmp_path / "a" / "b.json"
    digest = write_json(path, {"b": 1, "a": "é"})
    assert digest == sha256_hex(b'{"a":"\xc3\xa9","b":1}\n')
    assert path.read_bytes() == b'{"a":"\xc3\xa9","b":1}\n'


def test_write_json_atomic_leaves_no_temp_file_on_error(tmp_path):
    from jsonio import write_json_atomic
    with pytest.raises(TypeError):
        write_json_atomic(tmp_path / "x.json", {1j})
    assert list(tmp_path.iterdir()) == []


def test_write_text_atomic_writes_lf(tmp_path):
    path = tmp_path / "t.txt"
    write_text_atomic(path, "a\nb\n")
    assert path.read_bytes() == b"a\nb\n"

"""JsonlCache: the key line a reader scans for, and `items`."""
from __future__ import annotations

from modelcall import KEY_LINE, JsonlCache


def test_key_line_matches_put(tmp_path):
    path = tmp_path / "c.jsonl"
    JsonlCache(path).put("k", {"a": 1})
    line = path.read_bytes().splitlines()[0]
    match = KEY_LINE.match(line)
    assert match and match.group(1) == b"k"


def test_items_last_line_wins(tmp_path):
    path = tmp_path / "c.jsonl"
    cache = JsonlCache(path)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("a", 3)
    assert dict(cache.items()) == {"a": 3, "b": 2}
    assert dict(JsonlCache(path).items()) == {"a": 3, "b": 2}

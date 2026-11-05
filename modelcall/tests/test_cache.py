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


def _writer(path: str, tag: str, n: int) -> None:
    from modelcall.cache import JsonlCache
    cache = JsonlCache(path)
    for i in range(n):
        cache.put(f"{tag}-{i}", {"text": tag * (1000 + 997 * i % 60000)})   # 1-64 KB lines


def test_two_processes_append_to_one_cache_and_see_each_other(tmp_path) -> None:
    """Parallel question runs share a cache: no torn line, and a miss reads what the other process wrote."""
    import multiprocessing

    from modelcall.cache import JsonlCache
    path = str(tmp_path / "shared.jsonl")
    reader = JsonlCache(path)                          # opened before either writer: it must catch up on a miss
    ctx = multiprocessing.get_context("spawn")
    procs = [ctx.Process(target=_writer, args=(path, tag, 60)) for tag in ("a", "b")]
    for p in procs:
        p.start()
    for p in procs:
        p.join(120)
        assert p.exitcode == 0
    again = JsonlCache(path)
    assert again.skipped == 0 and len(dict(again.items())) == 120
    assert reader.get("a-59") is not None and reader.get("b-0") is not None and reader.skipped == 0

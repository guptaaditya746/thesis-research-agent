import json

import pytest

from synth3.pool import folder_sources, split_pool
from synth3.tests.conftest import make_pool


def test_split_is_seeded_disjoint_and_never_overwritten(tmp_path, REAL):
    pool = make_pool(tmp_path / "p", 20, REAL)
    s = split_pool(pool, REAL)
    assert len(s["test"]) == REAL.n_test and not set(s["test"]) & set(s["sources"])
    with pytest.raises(ValueError, match="refusing to overwrite"):
        split_pool(pool, REAL)


def test_same_pool_same_split(tmp_path, REAL):
    a = split_pool(make_pool(tmp_path / "a", 20, REAL), REAL)
    b = split_pool(make_pool(tmp_path / "b", 20, REAL), REAL)
    assert a["test"] == b["test"]


def test_test_papers_are_cut_into_pieces(tmp_path, REAL):
    pool = make_pool(tmp_path / "p", 20, REAL); s = split_pool(pool, REAL)
    index = json.loads((pool / "pieces" / "index.json").read_text())
    assert index and {x["paper"] for x in index} <= set(s["test"])


def test_big_pool_gives_disjoint_folders():
    order = [f"P{i:03d}" for i in range(200)]
    blocks = [folder_sources(order, s, 40)[:40] for s in range(1, 6)]
    assert all(len(set(b)) == 40 for b in blocks) and len(set().union(*blocks)) == 200


def test_small_pool_repeats_across_folders_never_within():
    order = [f"P{i:03d}" for i in range(60)]
    assert all(len(set(folder_sources(order, s, 40)[:40])) == 40 for s in range(1, 6))
    with pytest.raises(ValueError, match="needs at least 40"):
        folder_sources(order[:30], 1, 40)


def test_too_small_pool_and_missing_split(tmp_path, REAL):
    from synth3.pool import load_split, source_order
    pool = make_pool(tmp_path / "p", REAL.n_test, REAL)
    with pytest.raises(ValueError, match="at least"):
        split_pool(pool, REAL)
    with pytest.raises(ValueError, match="run synth3 pool-split first"):
        load_split(pool)
    pool2 = make_pool(tmp_path / "q", 20, REAL)
    s = split_pool(pool2, REAL)
    o = source_order(load_split(pool2), REAL.domain)
    assert sorted(o) == sorted(s["sources"])


def _tight(REAL):
    return REAL.model_copy(update={"exclude_title": "trial"})


def _repeat(pool, pid, rs):
    from synth3.pmc import PoolPaper
    from synth3.pool import add_paper
    from synth3.tests.conftest import fake_paper
    i = int(pid[1:])
    return add_paper(pool, PoolPaper(id=pid, title=f"HOPE-{i} trial", year=2015, journal="J", license="CC-BY",
                                     article_type="research-article", text=fake_paper(i)), rs)


def test_after_the_split_a_paper_it_uses_is_never_removed_by_a_new_config(tmp_path, REAL):
    from synth3.pool import load_split
    pool = make_pool(tmp_path / "p", 20, REAL); split_pool(pool, REAL)
    pid = load_split(pool)["sources"][0]
    with pytest.raises(ValueError, match="split.json lists it"):
        _repeat(pool, pid, _tight(REAL))
    assert (pool / "full" / f"{pid}.md").is_file()


def test_a_paper_the_split_does_not_use_may_still_be_removed(tmp_path, REAL):
    pool = make_pool(tmp_path / "p", 20, REAL); split_pool(pool, REAL)
    out = _repeat(pool, "P999", _tight(REAL))
    assert not out["kept"]


def test_build_real_names_a_missing_source_file(tmp_path, SPEC, REAL, pool):
    from synth3.pool import load_split
    from synth3.realcorpus import build_real_folder
    from synth3.tests.conftest import approved
    (pool / "full" / f"{load_split(pool)['sources'][0]}.md").unlink()
    with pytest.raises(ValueError, match="pool-fetch"):
        build_real_folder(tmp_path / "r", SPEC, approved(SPEC, 1), 40, "table", REAL, pool)

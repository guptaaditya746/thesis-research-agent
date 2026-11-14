import random

import pytest

pytest.importorskip("sklearn")
import numpy as np  # noqa: E402

from synth2 import realism  # noqa: E402

REAL_WORDS = "we show that the model improves however thus such while results were same our data sets".split()
SYN_WORDS = "the system gets better accuracy table row noise level reading shows study cells count".split()
VIEWS = ["1 full words", "2 masked words", "3 function words", "4 surface only"]


def paper(rnd, words, title):
    paras = [" ".join(rnd.choice(words) for _ in range(60)) + "." for _ in range(4)]
    return f"# {title}\n\n## Abstract\n\n" + "\n\n".join(paras) + "\n"


@pytest.fixture
def toy(tmp_path):
    rnd = random.Random(0)
    real = tmp_path / "real"
    real.mkdir()
    for i in range(10):
        (real / f"{i:03d}_p1.md").write_text(paper(rnd, REAL_WORDS, f"Real {i}"), encoding="utf-8")
    syn = tmp_path / "syn" / "papers"
    syn.mkdir(parents=True)
    for i in range(10):
        (syn / f"S{i:03d}.md").write_text(paper(rnd, SYN_WORDS, f"Syn {i}") + "\nLee et al. (2021)\n",
                                          encoding="utf-8")
    return real, tmp_path / "syn"


def test_c2st_returns_an_auc_for_each_of_the_five_views(toy):
    seen = []
    out = realism.c2st(*toy, log=seen.append)
    assert out["real"] == 10 and out["synthetic"] == 10
    assert list(out["auc"]) == VIEWS + ["5 masked + surface"]
    assert all(0.0 <= v <= 1.0 for v in out["auc"].values())
    assert out["auc"]["1 full words"] == 1.0            # the two toy vocabularies do not overlap
    assert len(seen) == 4
    assert set(out["cues masked words"]) == {"real", "synthetic"}
    assert len(out["surface strongest (+ = real)"]) == 8


def test_c2st_is_repeatable(toy):
    assert realism.c2st(*toy) == realism.c2st(*toy)


def test_synthetic_finds_a_grid_and_drops_label_lines(toy, tmp_path):
    texts, groups = realism.synthetic(toy[1])
    assert len(texts) == 10 and groups[0] == "syn-S000"
    assert not any("Lee et al." in t for t in texts)          # the author-label line is removed
    grid = tmp_path / "grid"
    (grid / "c" / "s0" / "base" / "papers").mkdir(parents=True)
    (grid / "c" / "s0" / "base" / "papers" / "S001.md").write_text("x", encoding="utf-8")
    assert len(realism.synthetic(grid)[0]) == 1


def test_masking_and_normalising():
    masked = realism.mask("Lee et al. (2021) report 12.5 percent on NQ with TriviaQA [3].")
    assert "NUM" in masked and "ACRO" in masked                # citation words are masked too (CITE turns into ACRO)
    assert not any(w in masked for w in ("12.5", "2021", "Lee", "TriviaQA", "NQ", "[3]"))
    assert "percent" in masked                               # ordinary words stay
    assert realism.normalize("**bold** `code`\n- item\n1. step") == "bold code\nitem\nstep"


def test_surface_has_22_counts_and_gap_surface_adds_ten_rates():
    text = "# T\n\nWe show, however, a result (once) 50%.\n\n| a | b |\n"
    assert len(realism.surface(text)) == 22
    assert len(realism.gap_surface(text)) == 32
    assert all(np.isfinite(realism.surface(text)))


def test_style_gap_is_zero_for_the_same_set_and_positive_otherwise(toy):
    real, syn = toy
    out = realism.style_gap(real, {"same": real, "syn": syn})
    assert out["same"]["mean |gap|"] == 0.0
    assert out["syn"]["mean |gap|"] > 0.0 and len(out["syn"]["biggest"]) == 8

import re

from synth3.pool import load_split
from synth3.realcorpus import build_real_folder
from synth3.realism import domain_mask, realism_report
from synth3.tests.conftest import approved


def test_mask_hides_drug_arm_control_and_setting_names(SPEC, REAL):
    out = domain_mask("lisinopril beat brelopril, placebo and usual care, and Targeted therapy at the "
                      "Coastal health service", REAL, SPEC)
    assert not re.search(r"(?i)pril|placebo|usual care|Targeted therapy|Coastal", out)
    assert out.count("ARMNAME") == 5 and "SITE" in out


def test_report_feeds_both_sides_raw_and_masked(tmp_path, SPEC, REAL, pool):
    build_real_folder(tmp_path / "r", SPEC, approved(SPEC, 1), 40, "table", REAL, pool)
    calls = []
    def fake(real_dir, syn_root, log=None):
        calls.append((sorted(p.name for p in real_dir.glob("*_p*.md")),
                      sorted(p.name for p in (syn_root / "papers").glob("S*_p*.md")),
                      " ".join(p.read_text(encoding="utf-8") for p in (syn_root / "papers").glob("*.md"))))
        return {"auc": {}}
    out = realism_report(tmp_path / "r", pool, REAL, SPEC, tmp_path / "w", c2st=fake, style_gap=lambda *a: {})
    assert len(calls) == 2 and calls[0][0] and calls[0][1]
    assert {n.split("_p")[0] for n in calls[0][0]} <= set(load_split(pool)["test"])
    labels = [a.label for a in SPEC.arms]
    assert any(l in calls[0][2] for l in labels) and not any(l in calls[1][2] for l in labels)
    assert set(out) == {"pieces", "raw", "masked", "style gap", "synth2 template v2"}

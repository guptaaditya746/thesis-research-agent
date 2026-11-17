"""Does a built real folder read like the pool's real papers? synth2's classifier on raw and masked copies."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from synth3.pool import load_split
from synth3.realspec import RealSpec
from synth3.rename import lower_names
from synth3.spec import DomainSpec

# synth2's own numbers for its template v2 papers, for comparison
SYNTH2_TEMPLATE_V2 = {
    "auc": {"1 full words": 0.913, "2 masked words": 0.742, "3 function words": 0.572,
            "4 surface only": 0.575, "5 masked + surface": 0.606},
    "style gap": 0.12,
}


def domain_mask(text: str, rs: RealSpec, spec: DomainSpec) -> str:
    """Drug names, arm labels and control words become ` ARMNAME `; setting names become ` SITE `. Both sides then
    look the same on these words (the synthetic side has no control word, the real side does)."""
    sites = [re.escape(x.name) for x in spec.settings]
    arms = [re.escape(a.label) for a in spec.arms] + ([rs.control_words] if rs.control_words else [])
    if sites:
        text = re.sub(r"\b(?:" + "|".join(sites) + r")\b", " SITE ", text, flags=re.I)
    if arms:
        text = re.sub(r"\b(?:" + "|".join(arms) + r")\b", " ARMNAME ", text, flags=re.I)
    return lower_names(rs).sub(" ARMNAME ", text)


def _masked_copy(src: Path, dst: Path, rs: RealSpec, spec: DomainSpec) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for f in sorted(src.glob("*.md")):
        text = domain_mask(f.read_text(encoding="utf-8"), rs, spec)
        (dst / f.name).write_text(text, encoding="utf-8")


def realism_report(folder: Path, pool: Path, rs: RealSpec, spec: DomainSpec, work: Path,
                   c2st=None, style_gap=None) -> dict:
    if c2st is None or style_gap is None:
        from synth2 import realism   # scikit-learn is heavy; load it only when used
        c2st, style_gap = c2st or realism.c2st, style_gap or realism.style_gap
    from synth2.realpool import slice_papers
    test = set(load_split(pool)["test"])
    shutil.rmtree(work, ignore_errors=True)   # a rerun must never mix in old pieces
    raw_real, raw_syn = work / "raw" / "real", work / "raw" / "synthetic" / "papers"
    raw_real.mkdir(parents=True, exist_ok=True)
    for f in sorted((pool / "pieces").glob("*_p*.md")):
        if f.stem.split("_p")[0] in test:
            shutil.copy(f, raw_real / f.name)
    sliced = slice_papers(folder / "papers", raw_syn)
    _masked_copy(raw_real, work / "masked" / "real", rs, spec)
    _masked_copy(raw_syn, work / "masked" / "synthetic" / "papers", rs, spec)
    return {
        "pieces": {"real": len(list(raw_real.glob("*.md"))), "synthetic": sliced["pieces"]},
        "raw": c2st(raw_real, raw_syn.parent),
        "masked": c2st(work / "masked" / "real", work / "masked" / "synthetic"),
        "style gap": style_gap(raw_real, {"folder": raw_syn.parent}),
        "synth2 template v2": SYNTH2_TEMPLATE_V2,
    }

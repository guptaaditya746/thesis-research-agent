"""Prepare a real set for the whole-run commands (general-system runbook, section 5).

    real-set-prep.py sofc-corpus --src DIR            DIR/sofc.json -> DIR/corpus/manifest.json + papers/<id>.md
    real-set-prep.py cochrane-corpus --src DIR        DIR/release.json -> DIR/corpus/<plot id>/ (manifest.json, papers/)
    real-set-prep.py tune-split --corpus DIR [--seed 0] [--fraction 0.2]
                                                      every paper id under DIR (its manifest.json, or one per
                                                      sub-folder) -> DIR/tune_split.json (evaluation.wholerun.tune_split)

Offline; no model. tune_split.json is written once (it is refused when it exists): `evaluate wholerun` drops the
questions on held-out papers and `evidence tune` trains only on them."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from evaluation.realpapers import sofc
from evaluation.wholerun import TUNE_FILE, tune_split
from jsonio import sha256_hex


def sofc_corpus(src: Path) -> Path:
    out = src / "corpus"
    (out / "papers").mkdir(parents=True, exist_ok=True)
    papers = []
    for p in sofc._open(src):
        blob = str(p["text"]).encode("utf-8")
        (out / "papers" / f"{p['id']}.md").write_bytes(blob)
        papers.append({"id": str(p["id"]), "file": f"papers/{p['id']}.md", "sha256": sha256_hex(blob)})
    (out / "manifest.json").write_text(json.dumps({"corpus_id": "sofc", "papers": papers}, indent=1) + "\n",
                                       encoding="utf-8", newline="\n")
    print(sofc.left_out(src))
    return out


def paper_ids(corpus: Path) -> list[str]:
    manifests = [corpus / "manifest.json"] if (corpus / "manifest.json").is_file() else sorted(corpus.glob("*/manifest.json"))
    ids = sorted({p["id"] for m in manifests for p in json.loads(m.read_text(encoding="utf-8"))["papers"]})
    if not ids:
        raise SystemExit(f"real-set-prep: no manifest.json with papers under {corpus}")
    return ids


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="real-set-prep.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sofc-corpus")
    s.add_argument("--src", type=Path, required=True)
    c = sub.add_parser("cochrane-corpus")
    c.add_argument("--src", type=Path, required=True)
    t = sub.add_parser("tune-split")
    t.add_argument("--corpus", type=Path, required=True)
    t.add_argument("--seed", type=int, default=0)
    t.add_argument("--fraction", type=float, default=0.2)
    args = ap.parse_args(argv)
    if args.cmd == "sofc-corpus":
        print(f"wrote {sofc_corpus(args.src)}")
        return 0
    if args.cmd == "cochrane-corpus":
        from evaluation.realpapers import cochraneforest
        out = cochraneforest.to_corpus(args.src, args.src / "corpus")
        print(f"wrote {out}: " + json.loads((out / cochraneforest.SOURCE_FILE).read_text(encoding="utf-8"))["left_out_line"])
        return 0
    path = args.corpus / TUNE_FILE
    if path.exists():
        raise SystemExit(f"real-set-prep: {path} exists; it is written once (move it aside to redo)")
    split = tune_split(paper_ids(args.corpus), args.fraction, args.seed, path)
    print(f"wrote {path}: {len(split['papers'])} held out for tuning, {len(split['rest'])} rest")
    return 0


if __name__ == "__main__":
    sys.exit(main())

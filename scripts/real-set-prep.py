"""Prepare a real set for the whole-run commands (general-system runbook, section 5).

    real-set-prep.py sofc-corpus --src DIR            DIR/sofc.json -> DIR/corpus/manifest.json + papers/<id>.md
    real-set-prep.py cochrane-corpus --src DIR        DIR/release.json -> DIR/corpus/<plot id>/ (manifest.json, papers/)
    real-set-prep.py tune-split --corpus DIR [--seed 0] [--fraction 0.2]
                                                      every paper id under DIR (its manifest.json, or one per
                                                      sub-folder) -> DIR/tune_split.json (evaluation.wholerun.tune_split)

    real-set-prep.py tune-examples --set DIR [--out DIR/corpus]
                                                      the labels of DIR (sofc.json or release.json) -> OUT/tune_examples.json
                                                      (format in evidence/steps/tune.py); a step the labels give nothing for
                                                      prints "no examples for <step>" and is skipped

Offline; no model. tune_split.json is written once (it is refused when it exists): `evaluate wholerun` drops the
questions on held-out papers and `evidence tune` trains only on them."""
from __future__ import annotations

import argparse
import json
import re
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


def _number_in(paragraph: str, value: float) -> str | None:
    for form in dict.fromkeys((repr(float(value)), f"{value:g}")):
        if re.search(rf"(?<![\w.]){re.escape(form)}(?![\w]|\.\d)", paragraph):
            return form
    return None


def _find(material: str, number: str) -> str:
    """One find as the engine's recheck prompt shows it (evidence/extractors/recheck._describe): a regex find of a
    measured value, type `measurement`, fields {"dataset": <the name>, "value": <number>}, quote = the number."""
    fields = json.dumps({"dataset": material, "value": float(number)}, sort_keys=True, ensure_ascii=False)
    return f"1. measurement | {fields} | {number}"


def sofc_examples(src: Path) -> tuple[dict[str, list[dict]], str]:
    """From the SOFC labels only. map_experiments: the paper and its number of labelled experiments. recheck: a
    paragraph holding a labelled value (its number and its material) is a find to keep. A find to drop is a number of
    a paragraph with no labelled value; hard ones first (the paragraph names a labelled material of the paper, the
    number is not its value: right name, wrong number), easy ones (no material named) only to fill up to as many as
    the keeps. Returns (rows per step, a note with the hard/easy ratio)."""
    rows: dict[str, list[dict]] = {"map_experiments": [], "recheck": [], "claims.read_claim": []}
    keep, hard, easy = [], [], []
    number = r"(?<![\w.])\d+(?:\.\d+)?(?![\w]|\.\d)"

    def row(pid: str, para: str, material: str, num: str, keeps: bool) -> dict:
        return {"step": "recheck", "paper": pid, "inputs": {"paragraph": para, "items": [_find(material, num)]},
                "gold": {"keep": [keeps]}}

    for paper in sofc._open(src):
        text, pid = str(paper["text"]), str(paper["id"])
        n = len(paper.get("experiments", []))
        if n:
            rows["map_experiments"].append({"step": "map_experiments", "paper": pid, "inputs": {"paper": text},
                                            "gold": {"n": n, "text": text}})
        values = [v for v in paper.get("values", []) if v.get("material") and v.get("value") is not None]
        if not values:
            continue
        for para in (q for q in text.split("\n\n") if q.strip()):
            hit = next(((v, num) for v in values if str(v["material"]).casefold() in para.casefold()
                        and (num := _number_in(para, float(v["value"])))), None)
            if hit:
                keep.append(row(pid, para, str(hit[0]["material"]), hit[1], True))
            elif not any(_number_in(para, float(v["value"])) for v in values):
                tok = re.search(number, para)
                if not tok:
                    continue
                named = next((str(v["material"]) for v in values if str(v["material"]).casefold() in para.casefold()), None)
                if named:
                    hard.append(row(pid, para, named, tok.group(), False))
                else:
                    easy.append(row(pid, para, str(values[0]["material"]), tok.group(), False))
    drops = hard[:len(keep)]
    drops += easy[:max(0, len(keep) - len(drops))]
    rows["recheck"] = keep + drops
    easy_used = len(drops) - min(len(hard), len(keep))
    return rows, (f"recheck: {len(keep)} keep, {len(drops)} drop ({len(drops) - easy_used} hard: material named, wrong number; "
                  f"{easy_used} easy: no material named)")


def tune_examples(set_dir: Path, out_dir: Path | None = None) -> Path | None:
    """Write `<out_dir>/tune_examples.json` (default `<set_dir>/corpus`, next to tune_split.json) from the labels of a
    set folder; None (nothing written) when no real step has examples. Cochrane gives a direction per study and per
    review, no sentence, so it gives no claims.read_claim example (a sentence would have to be invented)."""
    from evidence.steps.tune import EXAMPLES_FILE, REAL_STEPS
    set_dir = Path(set_dir)
    if (set_dir / sofc.SOURCE_FILE).is_file():
        by_step, note = sofc_examples(set_dir)
        print(note)
    elif (set_dir / "release.json").is_file():
        by_step = {}
    else:       # SciLead, SciREX: no labels this script can use
        print(f"real-set-prep: no {sofc.SOURCE_FILE} or release.json in {set_dir}: no labels to build examples from", file=sys.stderr)
        by_step = {}
    rows = []
    for step in REAL_STEPS:
        got = by_step.get(step, [])
        if got:
            print(f"{step}: {len(got)} examples")
        else:
            print(f"no examples for {step}")
        rows += got
    if not rows:
        return None
    out = Path(out_dir) if out_dir is not None else set_dir / "corpus"
    out.mkdir(parents=True, exist_ok=True)
    path = out / EXAMPLES_FILE
    path.write_text(json.dumps({"examples": rows}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return path


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
    e = sub.add_parser("tune-examples")
    e.add_argument("--set", type=Path, required=True, dest="set_dir")
    e.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    if args.cmd == "tune-examples":
        path = tune_examples(args.set_dir, args.out)
        print(f"wrote {path}" if path else "wrote nothing: no real step has examples from these labels")
        return 0
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

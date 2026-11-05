"""Convert one original MeasEval split to the limited scalar evaluator layout.

Usage: python -m evaluation.realpapers.convert_measeval RELEASE.zip SPLIT OUTPUT.json
The output retains all source annotations and explicitly records excluded quantities.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
from pathlib import Path
from zipfile import ZipFile

_NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")


def convert(zip_path: Path, split: str) -> dict:
    if split not in {"train", "trial", "eval"}:
        raise ValueError("split must be train, trial or eval")
    papers = []
    with ZipFile(zip_path) as z:
        names = z.namelist()
        matches = [n for n in names if re.search(rf"(?:^|/)data/{split}/tsv/[^/]+\.tsv$", n)]
        if not matches:
            raise ValueError(f"no TSV files for split {split}")
        for name in sorted(matches):
            base = name.rsplit("/", 2)[0]
            doc_id = Path(name).stem
            text_dir = "txt" if split == "trial" else "text"
            text_name = f"{base}/{text_dir}/{doc_id}.txt"
            text = z.read(text_name).decode("utf-8")
            rows = list(csv.DictReader(io.StringIO(z.read(name).decode("utf-8-sig")), delimiter="\t"))
            for row in rows:
                row["other"] = json.loads(row["other"] or "{}")
                row["startOffset"] = int(row["startOffset"])
                row["endOffset"] = int(row["endOffset"])
                if row["docId"] != doc_id or text[row["startOffset"]:row["endOffset"]] != row["text"]:
                    raise ValueError(f"annotation does not match source text: {name} {row['annotId']}")
            quantities, excluded = [], []
            for q in (r for r in rows if r["annotType"] == "Quantity"):
                raw, other = q["text"].strip(), q["other"]
                group = [r for r in rows if r["annotSet"] == q["annotSet"]]
                unit = other.get("unit")
                match = _NUMBER.match(raw)
                remainder = raw[match.end():].strip() if match else raw
                # A single, exact number followed by its documented unit only.
                if not match or remainder != (unit or "") or other.get("mods", []) not in ([], ["IsCount"]):
                    excluded.append({"annotation_id": q["annotId"], "text": q["text"], "reason": "not an unambiguous scalar"})
                    continue
                value = float(match.group())
                if not math.isfinite(value):
                    raise ValueError(f"nonfinite quantity in {name}")
                props = {r["annotId"] for r in group if r["annotType"] == "MeasuredProperty" and r["other"].get("HasQuantity") == q["annotId"]}
                entities = [r["text"] for r in group if r["annotType"] == "MeasuredEntity" and (r["other"].get("HasQuantity") == q["annotId"] or r["other"].get("HasProperty") in props)]
                quantities.append({"value": value, "unit": unit, "entity": entities[0] if len(entities) == 1 else None, "annotation_id": q["annotId"], "text": q["text"], "start_offset": q["startOffset"], "end_offset": q["endOffset"]})
            papers.append({"id": doc_id, "text": text, "quantities": quantities, "source_split": split, "source_tsv": name, "annotations": rows, "excluded_quantities": excluded})
    return {"papers": papers, "source_split": split, "conversion": "unambiguous scalar quantities only; excluded annotations retained"}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive", type=Path)
    p.add_argument("split", choices=("train", "trial", "eval"))
    p.add_argument("output", type=Path)
    args = p.parse_args()
    if args.output.exists():
        p.error("output already exists; choose a new path")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(convert(args.archive, args.split), f, ensure_ascii=False, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()

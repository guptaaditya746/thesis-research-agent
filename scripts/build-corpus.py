#!/usr/bin/env python3
"""Convert the frozen ACL/EMNLP PDF input once with Docling 2.110.0."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
import time
from importlib.metadata import version
from pathlib import Path

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def paper_ids(pdf_dir: Path, anthology_manifest: Path, samples_manifest: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    with anthology_manifest.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            mapping[row["filename"]] = row["anthology_id"].replace(".", "-")
    with samples_manifest.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            filename = row["filename"]
            if filename in {path.name for path in pdf_dir.glob("*.pdf")} and filename[:-4].isdigit():
                mapping[filename] = f"p{int(filename[:-4])}"
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    missing = [pdf.name for pdf in pdfs if pdf.name not in mapping]
    if missing:
        raise RuntimeError(f"PDFs lack paper IDs in the manifests: {missing}")
    ids = [mapping[pdf.name] for pdf in pdfs]
    if len(ids) != len(set(ids)):
        raise RuntimeError("paper ID mapping has duplicates")
    return mapping


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf-dir", type=Path, required=True)
    parser.add_argument("--anthology-manifest", type=Path, required=True)
    parser.add_argument("--samples-manifest", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--manifest-copy", type=Path, required=True)
    args = parser.parse_args()

    docling_version = version("docling")
    if docling_version != "2.110.0":
        raise SystemExit(f"expected Docling 2.110.0, found {docling_version}")
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    pdf_dir = args.pdf_dir.resolve()
    corpus = args.corpus.resolve()
    corpus.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if len(pdfs) != 337:
        raise SystemExit(f"expected 337 PDFs, found {len(pdfs)}")
    ids = paper_ids(pdf_dir, args.anthology_manifest, args.samples_manifest)
    options = PdfPipelineOptions(do_ocr=False, do_table_structure=True)
    converter = DocumentConverter(format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=options)
    })

    rows: list[dict[str, object]] = []
    for index, pdf in enumerate(pdfs, 1):
        paper_id = ids[pdf.name]
        markdown_path = corpus / f"{paper_id}.md"
        started = time.perf_counter()
        try:
            result = converter.convert(pdf)
            markdown = result.document.export_to_markdown()
            if len(markdown.encode("utf-8")) < 5000:
                raise ValueError(f"Markdown too small: {len(markdown.encode('utf-8'))} bytes")
            markdown_path.write_text(markdown, encoding="utf-8")
            row: dict[str, object] = {
                "id": paper_id,
                "source_pdf": str(pdf),
                "source_sha256": sha256(pdf),
                "markdown_sha256": sha256(markdown_path),
                "bytes": markdown_path.stat().st_size,
                "docling_version": docling_version,
                "conversion_seconds": round(time.perf_counter() - started, 3),
                "failure": None,
            }
        except Exception as exc:
            row = {
                "id": paper_id,
                "source_pdf": str(pdf),
                "source_sha256": sha256(pdf),
                "markdown_sha256": None,
                "bytes": 0,
                "docling_version": docling_version,
                "conversion_seconds": round(time.perf_counter() - started, 3),
                "failure": f"{type(exc).__name__}: {exc}",
            }
        rows.append(row)
        print(json.dumps({"index": index, **row}, ensure_ascii=False), flush=True)

    manifest = {
        "source": str(pdf_dir),
        "paper_count": len(pdfs),
        "converted_count": sum(row["failure"] is None for row in rows),
        "failure_count": sum(row["failure"] is not None for row in rows),
        "docling_version": docling_version,
        "do_ocr": False,
        "do_table_structure": True,
        "papers": rows,
    }
    manifest_path = corpus / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
    args.manifest_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(manifest_path, args.manifest_copy)
    print(json.dumps({"manifest": str(manifest_path), "copied_to": str(args.manifest_copy),
                      "converted": manifest["converted_count"],
                      "failures": manifest["failure_count"]}), flush=True)
    return 0 if manifest["failure_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

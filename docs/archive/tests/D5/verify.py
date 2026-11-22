from __future__ import annotations

import argparse
import hashlib
import json
import stat
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--manifest-copy", type=Path, required=True)
    parser.add_argument("--pdf-dir", type=Path, required=True)
    args = parser.parse_args()
    corpus = args.corpus.resolve()
    manifest_path = corpus / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    papers = manifest["papers"]
    assert manifest["paper_count"] == 337 and len(papers) == 337
    # User-approved exception: the scanned p38 PDF yielded only image markers
    # with the frozen no-OCR pipeline, so it is recorded and omitted.
    assert manifest["converted_count"] == 336 and manifest["failure_count"] == 1
    assert len({paper["id"] for paper in papers}) == 337
    failed = [paper for paper in papers if paper["failure"] is not None]
    assert len(failed) == 1 and failed[0]["id"] == "p38"
    assert {Path(paper["source_pdf"]).name for paper in papers} == {
        path.name for path in args.pdf_dir.glob("*.pdf")
    }
    for paper in papers:
        source = Path(paper["source_pdf"])
        markdown = corpus / f"{paper['id']}.md"
        assert source.is_file() and sha256(source) == paper["source_sha256"]
        if paper["failure"] is not None:
            assert paper["markdown_sha256"] is None and not markdown.exists()
            continue
        assert markdown.is_file() and markdown.stat().st_size == paper["bytes"]
        assert markdown.stat().st_size >= 5000
        assert sha256(markdown) == paper["markdown_sha256"]
    readonly_paths = [corpus, *corpus.rglob("*")]
    writable = [str(path) for path in readonly_paths
                if path.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)]
    assert not writable, f"writable corpus paths: {writable[:10]}"
    assert sha256(manifest_path) == sha256(args.manifest_copy)
    result = {
        "pass": True, "paper_count": len(papers), "converted_count": manifest["converted_count"],
        "failure_count": manifest["failure_count"], "hashes_verified": manifest["converted_count"],
        "ignored_failure_ids": [paper["id"] for paper in failed],
        "readonly_paths_verified": len(readonly_paths),
        "manifest_sha256": sha256(manifest_path), "corpus": str(corpus),
    }
    print(json.dumps(result, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# D5: Docling corpus conversion

- Input: all 337 PDFs in `final-final-frontend/corpus_acl_emnlp_2025_input` (the user-selected corpus only).
- Converter: Docling 2.110.0, OCR disabled, table structure enabled; output frozen at `/mnt/ceph/storage/data-tmp/2026/xepi3167/research-agent-corpus-docling-2.110.0`.
- Result: 336 PDFs yielded Markdown above the 5 KB minimum; 28,586,882 Markdown bytes total. All 336 source and output hashes verified; the manifest covers all 337 input PDFs. The tree has 338 verified paths and no write bits.
- Accepted exception: `p38` (source `38.pdf`) is an 18-page scanned paper. Without OCR, Docling returned 222 bytes of image markers. Per user direction it is excluded from the usable corpus; no OCR retry is included in the frozen corpus.
- The Slurm conversion took about 4 h 52 min wall time (sum of per-paper conversion times: 17,065 s). The batch step itself returned nonzero for the single rejected output; the explicit verifier passes with the one documented exclusion.
- Manifest SHA-256: `22e9471bbed7fa3e534cecef0d31e83950c88328ff8e7e7916a94b3fe4be9eb4`.

Verification command and result: `tests/D5/verify.py`; see `corpus/manifest.json` and `tests/D5/slurm-7140.out`.

# Deck for the meeting with Tim, 22 October 2026

`tim-2026-10-22.pptx` (13 slides, 16:9, speaker notes on every slide) follows study S005 of the EV1 LLM-written corpus through the system, then shows the benchmark, the EV1 evaluation and the 21 Oct repairs. Each slide is framed by Tim's 14 Oct messages; our own additions carry an "ours" tag.

Rebuild: `build_deck.py` (see its header) with a scratch venv that has python-pptx, matplotlib, networkx and pyyaml. `--prepare` runs the engine (regex only, no model), oracle and scorer offline on a copy of `tests/EV1/live-rerun/corpora/rag-llm-s1-mixed`. Images go to `img/`.

Data: every number and excerpt is read at build time from `tests/EV1/live-rerun/` (ground truth, LLM-written papers, fidelity, cascade and compare reports, run-summary) and from that offline run. The appendix image is a headless-Edge screenshot of `thesis_pipeline.html` (branch ev3/demo).

# Evaluation dashboard

Open `/evaluation_dashboard.html` on the existing pipeline-map server (laptop port 28099). The pipeline page links to it.

Rebuild the standalone HTML snapshot from the repository root:

```sh
python3 docs/dashboard/build.py
```

The generator uses the Python standard library. It embeds selected fields from `tests/EV2/scores/*/*/report.json` and corpus sizes from manifests. No server API, internet connection or model is required. Rebuild after adding score reports.

The size filter separates three-paper pilots from larger corpora. Missing reports are labelled Not evaluated, never assigned zero. Precision, recall and F1 are the evaluator's existing overall and evidence-type metrics, without recalculation or averaging. Correct study conclusions counts the synthesis report's correct study directions. Counterfactual corpora and answer-only baselines are excluded from extraction comparisons. CSV export covers the selected corpus and method.

Manual fidelity review CSVs are separate from engine extraction evaluation and are not presented as human approval.

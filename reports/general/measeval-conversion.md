# MeasEval conversion inspection

The original eval split contains 130 paragraph documents and 499 Quantity annotations. The converter maps 226 unambiguous literal scalar quantities into the current evaluator schema and retains the other 273 in `excluded_quantities`, together with all source annotations. This is a restricted subset, not a full-benchmark score. Every annotation offset and text was checked while loading the actual release. Dataset fields remain unverified.

Hand-checked against the original TSVs: `S0012821X12004384-1610` annotation `T1-1` is 2617.4 m linked directly to `brief peak`; list annotation `T1-2` is excluded. `S0012821X12004384-990` annotation `T1-2` is 39% linked via property `axis 1` to entity `total variance`; written number `two` is excluded. The output preserves the original row and all qualifiers and relationships for inspection.

The original eval split was selected explicitly and is not merged with train or trial. Output: `$EV/real/measeval/measeval.json`. The grouped-link version is byte-identical and is saved separately as `measeval-grouped.json`. Test: `uv run pytest evaluation/tests/test_convert_measeval.py -q` (1 passed).

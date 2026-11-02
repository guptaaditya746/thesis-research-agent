"""Real-paper checks (D42, spec 6.12): loaders and scorers for labelled real papers (SciREX, Yun et al., SciLead,
arXiv edits). Each writes `real.json` and `real.md` (common.write_real), reported as a "real-paper check" and never
mixed into a synthetic report.json. The gold of a real-paper set is read by its scorer only (D31)."""

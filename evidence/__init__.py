"""Executable research protocols: extractor contract, engine, evidence graph, deterministic synthesis."""
from . import evidence_types  # noqa: F401  (adds the `dataset` evidence type to the contract, see that module)
from . import records  # noqa: F401  (adds `experiment`, `claim`, `link`: a run of any kind loads without the engine)

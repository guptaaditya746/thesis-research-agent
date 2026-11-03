"""One ontology per field (computer science: CS-KG, medicine: MeSH, units everywhere: QUDT). Never hand-written for a
new field; a field without a tree runs with "reasoning off: no tree" (`fill.report`)."""
from .sources import fetch, load, ontology_hashes, other_names

__all__ = ["fetch", "load", "ontology_hashes", "other_names"]

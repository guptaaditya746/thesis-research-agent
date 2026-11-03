"""The ontology's names for each thing of the word list, kept apart from the LLM's names (`ontology_names`)."""
from __future__ import annotations

import rdflib

from evidence.names import clean
from evidence.plan import WordList

from .sources import other_names


def add_ontology_names(words: WordList, graph: rdflib.Graph | None) -> WordList:
    """Fill `ontology_names` per thing: the other names of the class whose label equals (after `names.clean`) one of
    the thing's names. A thing with no exact label match gets none. Names the word list already has are left out.
    No graph, or no match anywhere: the word list comes back unchanged."""
    if graph is None:
        return words
    added: dict[str, list[str]] = {k: list(v) for k, v in words.ontology_names.items()}
    for thing, names in words.things.items():
        known = {clean(n) for n in names} | {clean(n) for n in added.get(thing, [])}
        found: list[str] = []
        for name in names:
            for other in other_names(graph, name):
                if clean(other) not in known and other not in found:
                    found.append(other)
        if found:
            added[thing] = sorted(added.get(thing, []) + found)
    if added == words.ontology_names:
        return words
    return words.model_copy(update={"ontology_names": added})

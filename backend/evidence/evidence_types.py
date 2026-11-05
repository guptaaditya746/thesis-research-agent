"""The registry of evidence types beyond the contract's built-in ones (EV4: open evidence types).

A domain pack declares its evidence types, each with an item id prefix (pack.yaml `types`); `register` adds one to
the contract's registry (`contract.ITEM_PREFIX`), and from then on the contract's models take items of that type.
A name not registered is refused. `dataset` (prefix `d`, question-first step 2) is registered here when the
`evidence` package is imported (evidence/__init__.py), so the dataset extractors, which declare their type at
import, and old runs with dataset items load without a pack.
"""
from __future__ import annotations

import re

from . import contract

DATASET = "dataset"
PREFIX = "d"
# Other modules annotate evidence type names with this; validation happens in the contract (contract.EvidenceType)
# and against the pack's types (protocol.Protocol).
EvidenceType = str
PREFIX_PATTERN = re.compile(r"^[a-z]+$")   # item ids are `<prefix>-<hex>`; the LLM schema numbers rows `<prefix>1`


def register(name: str, prefix: str) -> None:
    """Register evidence type `name` with item id prefix `prefix`. Registering a type again with the same prefix
    does nothing; a prefix that belongs to another type, or another prefix for a registered type, raises
    ValueError (two types sharing a prefix would make their item ids look alike)."""
    if not PREFIX_PATTERN.match(prefix):
        raise ValueError(f"evidence type {name!r}: prefix {prefix!r} must be lowercase letters a-z")
    owner = next((t for t, p in contract.ITEM_PREFIX.items() if p == prefix), None)
    if owner == name:
        return
    if owner is not None:
        raise ValueError(f"evidence type {name!r}: prefix {prefix!r} already belongs to evidence type {owner!r}")
    held = contract.ITEM_PREFIX.get(name)
    if held is not None:
        raise ValueError(f"evidence type {name!r} already has prefix {held!r}, not {prefix!r}")
    contract.ITEM_PREFIX[name] = prefix


register(DATASET, PREFIX)

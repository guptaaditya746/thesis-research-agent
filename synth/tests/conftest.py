"""Shared fixtures of the synth tests."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from evidence import contract


@contextmanager
def kept_registry() -> Iterator[None]:
    """Leave the global evidence-type registry (`contract.ITEM_PREFIX`) as it was: loading a pack's protocol (the
    drugtoy one, for a drugtoy set) registers its types, and another test's pack may use the same type names with
    other prefixes."""
    before = dict(contract.ITEM_PREFIX)
    try:
        yield
    finally:
        contract.ITEM_PREFIX.clear()
        contract.ITEM_PREFIX.update(before)


@pytest.fixture(autouse=True)
def _registry() -> Iterator[None]:
    """Every synth test leaves the type registry as it found it (`kept_registry`)."""
    with kept_registry():
        yield

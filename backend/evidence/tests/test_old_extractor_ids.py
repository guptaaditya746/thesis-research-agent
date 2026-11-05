"""The contract still takes the items of old runs. The tests that rebuilt the EV2 runs' extractor ids are retired
(D36): the extractors now take their topic words from the domain pack, so their ids changed; old runs replay at
their own code tag (`ev3b-code`). test_pack_configs.py checks how pack words make an id."""
from __future__ import annotations

import pytest


def test_the_contract_still_takes_dataset_items() -> None:
    from evidence.contract import ExtractionResult, Item, Span
    span = Span(role="dataset_label", selector={"file": "p.md", "start": 0, "end": 4})
    item = Item.build("dataset", {"name": "TriviaCheck"}, [span])
    result = ExtractionResult(extractor_id="x", task_sha256="t", status="ok", items=(item.model_dump(),))
    assert item.item_id.startswith("d-") and result.items[0].evidence_type == "dataset"
    with pytest.raises(ValueError):
        Item(item_id="z-1", evidence_type="nonsense", fields={}, spans=(span,))

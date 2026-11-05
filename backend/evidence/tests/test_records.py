import pytest
from pydantic import ValidationError

from evidence.contract import Item, Span, digest
from evidence.records import ClaimRecord, Experiment, LinkRecord, item

SPAN = Span(role="claim", selector={"file": "p.md", "start": 0, "end": 5, "exact": "hello",
                                    "prefix": "", "suffix": "", "sha256": "x"})
EXP = Experiment(exp_id="e1", document="p", label="Exp 1", setting={"dataset": "NQ", "model": "gpt"}, span=SPAN)


def test_prefixes_registered_and_unique():
    from evidence.contract import ITEM_PREFIX
    import evidence.records  # registers
    assert ITEM_PREFIX["experiment"] == "x" and ITEM_PREFIX["claim"] == "cl" and ITEM_PREFIX["link"] == "ln"
    assert len(set(ITEM_PREFIX.values())) == len(ITEM_PREFIX)


def test_existing_prefixes_untouched():
    from evidence.contract import ITEM_PREFIX
    for name, p in {"condition": "c", "metric": "k", "measurement": "m", "author_claim": "a", "screen": "s",
                    "dataset": "d"}.items():
        assert ITEM_PREFIX[name] == p


def test_claim_strength_is_closed():
    with pytest.raises(ValidationError):
        ClaimRecord(subject="RAG", relation="raises", object="accuracy", setting={}, strength="maybe",
                    direction=None, span=SPAN)


def test_claim_direction_closed_and_group_default():
    with pytest.raises(ValidationError):
        ClaimRecord(subject="RAG", relation="raises", object=None, setting={}, strength="firm",
                    direction="up", span=SPAN)
    c = ClaimRecord(subject="RAG", relation="raises", object=None, setting={}, strength="hedged",
                    direction=None, span=SPAN)
    assert c.relation_group is None


def test_records_hash_stable():
    assert digest(EXP.model_dump(mode="json")) == digest(Experiment(**EXP.model_dump()).model_dump(mode="json"))


def test_item_converts_each_record():
    claim = ClaimRecord(subject="RAG", relation="raises", object="acc", setting={}, strength="firm",
                        direction="improves", span=SPAN)
    link = LinkRecord(subject_doc="p", relation="builds_on", object_ref="10.1/x", object_doc=None,
                      outside_set=True, span=SPAN)
    for rec, t, pre in [(EXP, "experiment", "x-"), (claim, "claim", "cl-"), (link, "link", "ln-")]:
        it = item(rec)
        assert isinstance(it, Item) and it.evidence_type == t and it.item_id.startswith(pre)
        assert it.spans == (SPAN,)
    assert item(EXP).item_id == item(EXP).item_id

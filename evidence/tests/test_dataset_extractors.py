"""The dataset extractors: regex_dataset finds benchmark-like names; llm_dataset is registered."""
from __future__ import annotations

from agent.anchor import Index, text_sha256
from evidence import protocol
from evidence.contract import DocumentRef, ExtractionTask, ProtocolRef
from evidence.extractors import get, names, regex

from .conftest import PROTOCOL, pack_words

PROTO = protocol.load(PROTOCOL)


class Ctx:
    def __init__(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text

    def index(self) -> Index:
        return Index(self._text)

    def context_items(self) -> list:
        return []

    def field_schema(self) -> dict:
        return {}


def run(text: str, config: dict | None = None):
    doc = DocumentRef(id="P", file="papers/P.md", sha256=text_sha256(text))
    task = ExtractionTask(protocol=ProtocolRef(id=PROTO.id, sha256=PROTO.sha256), evidence_type="metric",  # type: ignore[arg-type]
                          field_schema_sha256="x", document=doc)
    return get("regex_dataset", {**pack_words("regex_dataset", "dataset"), **(config or {})}).extract(task, Ctx(text))


def test_regex_dataset_finds_names() -> None:
    result = run("We test on TriviaCheck and LawFactQA. LawFactQA is hard.")
    assert sorted(i.fields["name"] for i in result.items) == ["LawFactQA", "TriviaCheck"]
    assert all(len(i.spans) == 1 and i.spans[0].role == "dataset_label" for i in result.items)
    assert len(result.items) == 2


def test_regex_dataset_ignores_plain_words() -> None:
    assert run("Question answering Results are shown. Question: Results?").items == ()


def test_regex_dataset_config_names() -> None:
    assert [i.fields["name"] for i in run("We use Natural Questions.", {"names": ["Natural Questions"]}).items] \
        == ["Natural Questions"]


def test_llm_dataset_registered() -> None:
    assert "llm_dataset" in names() and "regex_dataset" in names()


def test_existing_extractor_ids_unchanged() -> None:
    assert get("regex_metric").spec.code_sha256 == regex.CODE_SHA256

"""The required re-check of regex finds (stage `recheck` at `after_type`): a regex or model-kind extractor matched
words, a model now confirms each find inside its paragraph. One DSPy call per paragraph (`Recheck`), never one per
item. An item the model drops goes to `Rejected` (reason `out_of_scope`, the model's reason as the detail; read them
with `rejected_of(doc)`); a relabelled item keeps its spans and gets the new label. Items an LLM extractor found
are not re-checked: a model has already read them. `after_type` runs after every funnel round, so each item is
asked about once per document; later rounds reuse the verdict. Not registered here: the plan run registers
`recheck` at `after_type` (stages.register("recheck", "after_type", recheck) and
stages.register("recheck_report", "after_run", recheck_report))."""
from __future__ import annotations

import json
from typing import Any, Literal

import dspy
from dspy.utils.exceptions import AdapterParseError
from pydantic import BaseModel, ValidationError

from ..contract import Item, Rejected
from ..stages import StageCallError
from ..steps import Step
from ..unchecked import reason

LLM_KINDS = ("llm", "agent")        # extractor names starting so are the model kinds
LABEL_FIELDS = ("label", "name", "canonical")
PURPOSE = "recheck"
STATE_ATTR = "_recheck_state"
# run folder -> {document id: state}: what `recheck_report` writes at the end of the run
_STORE: dict[str, dict[str, dict[str, Any]]] = {}


class Verdict(BaseModel):
    number: int
    verdict: Literal["keep", "drop", "relabel"]
    new_label: str = ""
    reason: str = ""


class Recheck(dspy.Signature):
    """You check what a word search found inside one paragraph of a research paper.
    Input `paragraph`: the paragraph text.
    Input `items`: numbered finds, each as `number. type | fields | quote` where the quote is the matched passage.
    For each find decide: `keep` when the passage really is a find of that type in this paragraph, `drop` when it is
    not (a different meaning of the same word, or a passing mention), `relabel` when it is a find but its label is
    wrong (then give `new_label`). Give a short `reason` for every drop.
    Output `verdicts`: one entry per find with its `number`, `verdict`, `new_label` (empty unless relabel) and `reason`."""
    paragraph: str = dspy.InputField()
    items: list[str] = dspy.InputField()
    verdicts: list[Verdict] = dspy.OutputField()


def is_checkable(item: Item) -> bool:
    """Found by a regex or model-kind extractor only (an extractor id is `name@version#hash`)."""
    names = [f.split("@")[0] for f in item.found_by]
    return not any(n.startswith(LLM_KINDS) for n in names)


def label_field(item: Item) -> str | None:
    return next((f for f in LABEL_FIELDS if isinstance(item.fields.get(f), str)), None)


def paragraph_bounds(text: str, pos: int) -> tuple[int, int]:
    """The (start, end) of the blank-line-separated paragraph holding offset `pos`."""
    start = text.rfind("\n\n", 0, pos)
    start = 0 if start < 0 else start + 2
    end = text.find("\n\n", pos)
    return start, len(text) if end < 0 else end


def _state(doc: Any, ctx: Any = None) -> dict[str, Any]:
    state = doc.__dict__.get(STATE_ATTR)
    if state is None:
        state = doc.__dict__[STATE_ATTR] = {"verdicts": {}, "made": set(), "rejected": {}, "unchecked": {}}
        if ctx is not None and getattr(ctx, "run_dir", None) is not None:
            _STORE.setdefault(str(ctx.run_dir), {})[doc.doc.id] = state   # a later pass over the document replaces it
    return state


def rejected_of(doc: Any) -> list[Rejected]:
    """What the re-check dropped from this document, in the order it was dropped."""
    return list(_state(doc)["rejected"].values())


def _describe(number: int, item: Item, text: str) -> str:
    span = min(item.spans, key=lambda s: s.selector["start"]).selector
    # fields as sorted JSON: a fresh extraction and a cached one (replay) give the same prompt, whatever the key order
    fields = json.dumps(item.fields, sort_keys=True, ensure_ascii=False)
    return f"{number}. {item.evidence_type} | {fields} | {text[span['start']:span['end']]}"


def recheck(doc: Any, etype: str, merged: list[Item], ctx: Any, *, step: Step | None = None) -> list[Item]:
    state = _state(doc, ctx)
    fresh: dict[tuple[int, int], list[Item]] = {}
    for item in merged:
        if item.item_id in state["verdicts"] or item.item_id in state["made"] or not is_checkable(item):
            continue
        fresh.setdefault(paragraph_bounds(doc.text, item.first_start()), []).append(item)
    if fresh:
        # the model is this ctx's, given per call: the warm pass's threads never record on each other's model
        lm = ctx.dspy_lm(PURPOSE)
        step = step or Step(Recheck, "recheck")
        for (a, b), items in fresh.items():
            try:
                out = step(lm=lm, paragraph=doc.text[a:b], items=[_describe(n, i, doc.text) for n, i in enumerate(items, 1)])
                said = {v.number: v for v in out.verdicts}
            except AdapterParseError as exc:   # the finds stay, recorded as unchecked
                said, why = {}, f"unparseable reply: {str(exc)[:120]}"
            except (StageCallError, ValidationError) as exc:   # a failed call: the finds stay, unchecked (C3)
                said, why = {}, f"failed call: {reason(exc)[:120]}"
            else:
                why = "the model gave no verdict for this find"
            for n, item in enumerate(items, 1):
                if n not in said:
                    state["unchecked"][item.item_id] = why
                state["verdicts"][item.item_id] = said.get(n) or Verdict(number=n, verdict="keep")
    result: list[Item] = []
    for item in merged:
        verdict = state["verdicts"].get(item.item_id)
        if verdict is None or verdict.verdict == "keep":
            result.append(item)
        elif verdict.verdict == "drop":
            span = min(item.spans, key=lambda s: s.selector["start"]).selector
            state["rejected"].setdefault(item.item_id, Rejected(
                evidence_type=item.evidence_type, fields=item.fields,
                quotes=(doc.text[span["start"]:span["end"]],), reason="out_of_scope", detail=verdict.reason))
        else:
            field = label_field(item)
            if field is None or not verdict.new_label.strip():
                result.append(item)
                continue
            new = Item.build(item.evidence_type, {**item.fields, field: verdict.new_label.strip()}, list(item.spans),
                             dict(item.links), item.confidence).model_copy(update={"found_by": item.found_by})
            state["made"].add(new.item_id)
            result.append(new)
    return result



def recheck_report(run: Any, ctx: Any) -> dict[str, Any]:
    """The stage `recheck_report` at `after_run` (written as recheck_report.json): per document the verdict of every
    checked find, the finds dropped (as `Rejected`) and those left unchecked. Register it together with `recheck`."""
    docs = _STORE.pop(str(ctx.run_dir), {})
    return {doc_id: {
        "verdicts": [{"item_id": i, **v.model_dump(exclude={"number"})} for i, v in state["verdicts"].items()],
        "rejected": [r.model_dump(mode="json") for r in state["rejected"].values()],
        "unchecked": [{"item_id": i, "why": w} for i, w in state["unchecked"].items()],
    } for doc_id, state in sorted(docs.items())}

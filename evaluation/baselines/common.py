"""What both baselines share: the corpus as a system under test sees it, the mapping call, answer.json.

Hard rule (docs/evidence-system.md Part A): a baseline reads `manifest.json` and the files it lists
under `papers/`, nothing else of the corpus directory. `SystemCorpus` is the only reader the baselines
use; it opens exactly those files, checks each against its manifest sha256, and refuses (allow-list)
any listed file that does not resolve to a file directly in `<corpus>/papers/`, so neither
ground_truth.json, corpus.json, fidelity.json, decoys.json nor any later evaluation file can be read.

Neither baseline is asked for a label or per-paper stances: the retrieve-then-answer baseline writes
an answer with citations, the agent an answer table. One separate **mapping call** (`map_answer`:
MAP_INSTRUCTIONS + LABEL_RULES, AnswerReply, shared by both; docs/evidence-system.md Part G.1) turns
that answer into the label and the stance of every paper it relies on, for the synthesis score (C).

Every question kind (domains/rag/questions.yaml, `kind_params`): the mapping call of the default question
(rag-factuality) is the one above, unchanged (so existing caches still hit); another effect question gets
prompts/map-effect-v1.md, the same task with its own metric and direction (AnswerReply). The other kinds each have
their own reply model and versioned instructions (prompts/map-<kind>-v1.md, filled from the question's protocol:
the inventory target, the author claim's definition, the method kinds of a best question): InventoryReply,
ConsistencyReply, BestReply (whose `winner` and `tied` must name the protocol's kinds; a reply naming another kind
fails validation and gets pydantic-ai's retry). answer.json then has the kind's shape (evidence/kinds/*), with `system` the baseline's name; best's
`wins`, `winner` and `tied` are computed here from the per-paper winners (evidence.kinds.best.tally), never asked.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any, Literal, Optional, TypeVar

from pydantic import BaseModel, Field, create_model
from pydantic_ai.models import Model

from jsonio import sha256_hex
from evidence import protocol as protocol_module, questions as questions_module, rules
from evidence.kinds import best as best_kind
from evidence.kinds.inventory import fold
from evidence.pack import protocol_path
from evidence.protocol import Kind, Protocol
from modelcall import CallSettings, JsonlCache, Prompt, ask_sync, cache_key, load_prompt, model_name, prompt_sha256

DEFAULT_PROTOCOL = protocol_path("rag", "rag-factuality")
PROMPTS = Path(__file__).resolve().parent / "prompts"
DEFAULT_QUESTION = "Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?"
Stance = Literal["supports", "contradicts", "neutral"]
GROUPS = {"supports": "supporting", "contradicts": "contradicting", "neutral": "neutral"}
T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class Paper:
    id: str
    file: str
    text: str


class SystemCorpus:
    """manifest.json and papers/ of a corpus, read and hash-checked; never anything else."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        manifest = json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))
        self.corpus_id: str = manifest.get("corpus_id", self.root.name)
        self.papers: list[Paper] = []
        for entry in manifest["papers"]:
            file = entry.get("file") or f"papers/{entry['id']}.md"
            path = (self.root / file).resolve()
            if path.parent != self.root / "papers":
                raise ValueError(f"manifest lists {file!r}, which a system under test may not read "
                                 "(only files in papers/)")
            data = path.read_bytes()
            if entry.get("sha256") and sha256_hex(data) != entry["sha256"]:
                raise ValueError(f"{file}: sha256 differs from the manifest")
            self.papers.append(Paper(entry["id"], PurePosixPath(file).as_posix(), data.decode("utf-8")))

    @property
    def ids(self) -> list[str]:
        return [p.id for p in self.papers]


class StudyStance(BaseModel):
    document: str = Field(description="paper id, e.g. S001")
    stance: Stance = Field(description="what this paper's evidence says about the question")


class AnswerReply(BaseModel):
    """The schema of the mapping call: the label and per-paper stances a baseline's answer amounts to."""
    label: rules.Label = Field(description="supported, refuted, mixed, no_effect or insufficient")
    studies: list[StudyStance] = Field(description="one entry per paper the answer relies on")
    answer_text: str = Field(description="the answer in a few sentences")


LABEL_RULES = """Labels (the same rule for every system):
- supported: at least one paper shows retrieval improving factual accuracy (or lowering hallucination) and none shows it worsening;
- refuted: at least one paper shows it worsening and none improving;
- mixed: some papers show an improvement and others a worsening;
- no_effect: the papers show only differences too small to matter;
- insufficient: the evidence does not answer the question.
Stance per paper: supports (retrieval improved the result), contradicts (retrieval made it worse), neutral (no real difference)."""

# The mapping call's instructions (was the agent baseline's; shared since Part G.1). It names the two forms an
# answer takes: the agent's rows, facts and quotes; the retrieve-then-answer baseline's text and cited passages.
MAP_INSTRUCTIONS = f"""You are given a research question, the ids of the papers in a corpus, and the answer a system wrote after
reading the corpus: either a research agent's answer (its rows, the facts it recorded (subject | predicate | object)
with the quotes behind them, and its notes) or a retrieve-then-answer system's answer (its text and the passages it
cites). Do not add knowledge of your own: report what the answer says. Give the label the answer amounts to and, for
every corpus paper the answer relies on, the stance it attributes to that paper. Use only the paper ids listed.

{LABEL_RULES}"""


_STUDY_ID = re.compile(r"\bS\d+\b", re.IGNORECASE)


def paper_id(raw: Any, known: list[str]) -> str | None:
    """The manifest id in `known` that a mapped paper id `raw` names, else None. Exact first; then case-folded,
    without a file extension (`S001.md`) or a leading word (`Paper S001`); then the one `S<digits>` part, when it
    names exactly one known id. The mapping model writes ids loosely; the engine's ids are exact by construction."""
    text = " ".join(str(raw).split())
    if text in known:
        return text
    folded = {k.casefold(): k for k in known}
    stem = PurePosixPath(text).stem if PurePosixPath(text).suffix.lower() in (".md", ".txt", ".pdf") else text
    for form in (text, stem):
        if form.casefold() in folded:
            return folded[form.casefold()]
    parts = {m.group(0).casefold() for m in _STUDY_ID.finditer(stem)}
    hits = [folded[x] for x in parts if x in folded]
    return hits[0] if len(hits) == 1 else None


def answer_json(system: str, question: str, reply: AnswerReply, known: list[str], *, answer_text: str | None = None,
                **extra: Any) -> dict[str, Any]:
    """answer.json (section 4) for a baseline: the mapped label and per-paper stances, as stated.

    Entries for papers not in the corpus are dropped (listed in `dropped`); a paper named twice keeps
    its first stance. `answer_text` is the system's own answer when given, else the mapping call's
    summary. `label_by_rule` is evidence.rules.label over the stated stances by the label table of the
    default protocol (the baseline reads no corpus file for it), for reference; the score uses the
    mapped `label`.
    """
    studies, dropped, seen = [], [], set()
    for s in reply.studies:
        doc = paper_id(s.document, known)
        if doc is None:
            dropped.append(s.document)
        elif doc not in seen:
            seen.add(doc)
            studies.append({"document": doc, "direction": s.stance})
    studies.sort(key=lambda s: s["document"])
    groups = {g: [s["document"] for s in studies if s["direction"] == d] for d, g in GROUPS.items()}
    counts = {g: len(v) for g, v in groups.items()} | {"undetermined": 0}
    return {"system": system, "question": question, "label": reply.label, "counts": counts, "studies": studies,
            **groups, "undetermined": [], "answer_text": reply.answer_text if answer_text is None else answer_text,
            "label_by_rule": rules.label(counts, protocol_module.load(DEFAULT_PROTOCOL).synthesis.table),
            "dropped": dropped, **extra}


def cached_reply(cache: JsonlCache | None, instructions: str, prompt: str, *, model: Model, model_id: str | None,
                 seed: int = 0, max_tokens: int = 4096, output_type: type[T] = AnswerReply  # type: ignore[assignment]
                 ) -> tuple[T, dict[str, Any]]:
    """One schema-constrained call (temperature 0, fixed seed), cached by prompt hash, model and input.

    Returns the reply (an `output_type`) and its record: model, served model, tokens, prompt hash, cache
    key, whether it came from the cache. The key never contains the API key (modelcall reads it from the
    environment).
    """
    record = {"prompt_sha256": prompt_sha256(instructions, output_type), "model": model_id or model_name(model),
              "input_sha256": sha256_hex(prompt.encode("utf-8")),
              "settings": {"temperature": 0.0, "seed": seed, "max_tokens": max_tokens}}
    # A failure is modelcall.ModelCallError (a RuntimeError) with a redacted reason: provider errors can echo the key.
    answer = ask_sync(Prompt.inline(instructions, output_type), prompt, model=model,
                      settings=CallSettings(seed=seed, max_tokens=max_tokens), cache=cache, key=record)
    usage = {"served_model": answer.served_model, "input_tokens": answer.input_tokens,
             "output_tokens": answer.output_tokens}
    return answer.output, record | {"key": cache_key(record), "cached": answer.cached} | usage


def map_answer(cache: JsonlCache | None, question: str, known: list[str], text: str, *, model: Model,
               model_id: str | None, seed: int = 0, params: KindParams | None = None) -> tuple[Any, dict[str, Any]]:
    """The mapping call: a baseline's answer (as text) to the label and per-paper stances (no `params`, or an
    effect question), or to the reply of the question's kind (`map_prompt`), cached.

    The record (`mapping_call` in answer.json) is without `cached`, so a cached rerun writes the same
    bytes.
    """
    prompt = f"Question: {question}\n\nCorpus paper ids: {', '.join(known)}\n\nThe answer:\n{text}"
    instructions, reply_type = map_prompt(params)
    reply, call = cached_reply(cache, instructions, prompt, model=model, model_id=model_id, seed=seed,
                               output_type=reply_type)
    call.pop("cached")
    return reply, call


# --- every question kind ---------------------------------------------------------------------------

DEFAULT_QUESTION_ID = "rag-factuality"   # its mapping call is the original one
MAP_PROMPTS = {"effect": "map-effect-v1.md", "inventory": "map-inventory-v1.md", "consistency": "map-consistency-v1.md", "best": "map-best-v1.md"}
TARGET_NAME = {"metric": "evaluation metric", "condition": "method or system variant", "dataset": "dataset"}
TARGET_TEXT = {
    "metric": "the evaluation metrics the papers report results on (for example accuracy, exact match, latency).",
    "condition": "the methods or system variants the papers compare (for example a closed-book model, a RAG "
                 "pipeline, a fine-tuned model).",
    "dataset": "the datasets the papers evaluate on (for example Natural Questions, TriviaQA)."}
NOT_STATED = {"code": "not_stated", "text": "the answer does not say"}


@dataclass(frozen=True, eq=False)
class KindParams:
    """A question of domains/rag/questions.yaml as a baseline answers it: its id, text, kind and hand-written protocol
    (which gives the inventory target, the consistency metric and claim, the best metric and method kinds)."""
    question_id: str
    question: str
    kind: Kind
    protocol: Protocol | None


def kind_params(question_id: str) -> KindParams:
    """The question `question_id` of domains/rag/questions.yaml (ValueError for an unknown id)."""
    entries = {q.id: q for q in questions_module.load()}
    if question_id not in entries:
        raise ValueError(f"unknown question id {question_id!r} (domains/rag/questions.yaml has {', '.join(entries)})")
    entry = entries[question_id]
    protocol = protocol_module.load(questions_module.protocol_file(entry.protocol)) if entry.protocol else None
    if entry.kind != "effect" and protocol is None:
        raise ValueError(f"question {question_id!r} has no hand-written protocol; a baseline needs one for kind "
                         f"{entry.kind!r}")
    return KindParams(entry.id, entry.question, entry.kind, protocol)


class InventoryEntry(BaseModel):
    name: str = Field(min_length=1, description="the name exactly as the answer writes it")
    papers: list[str] = Field(description="the corpus paper ids the answer links to this name")


class InventoryReply(BaseModel):
    """The mapping call of an inventory question: every name of the target the answer gives, with its papers."""
    entries: list[InventoryEntry] = Field(description="one entry per distinct name the answer gives")


class ConsistencyStudy(BaseModel):
    paper: str = Field(description="a corpus paper id")
    claim: Literal["improves", "no_effect", "worsens"] | None = Field(
        description="the authors' conclusion the answer attributes to this paper, or null")
    agrees: bool | None = Field(description="whether the answer says the conclusion agrees with the results, or null")


class ConsistencyReply(BaseModel):
    """The mapping call of a consistency question: per paper, the claim and the stated agreement."""
    studies: list[ConsistencyStudy] = Field(description="one entry per paper the answer speaks about")


WINNER = "the method kind the answer says is best in this paper, or null (a tie, or not said)"
TIED = "the method kinds the answer says tie for the best in this paper (two or more), else empty"


class BestStudy(BaseModel):
    paper: str = Field(description="a corpus paper id")
    winner: str | None = Field(description=WINNER)
    tied: list[str] = Field(default_factory=list, description=TIED)


class BestReply(BaseModel):
    """The mapping call of a best question: per paper, the winning method kind or the kinds that tie. The call uses
    `best_reply(kinds)`, whose `winner` and `tied` must name the protocol's kinds."""
    studies: list[BestStudy] = Field(description="one entry per paper the answer speaks about")


@lru_cache(maxsize=None)
def best_reply(kinds: tuple[str, ...]) -> type[BestReply]:
    """BestReply with `winner` and `tied` limited to `kinds` (an enum in the schema, checked on validation)."""
    kind = Literal[kinds]  # type: ignore[valid-type]
    study = create_model("BestStudy", __base__=BestStudy,
                         winner=(Optional[kind], Field(description=WINNER)),  # noqa: UP045 - a run-time Literal
                         tied=(list[kind], Field(default_factory=list, description=TIED)))
    return create_model("BestReply", __base__=BestReply,
                        studies=(list[study], Field(description="one entry per paper the answer speaks about")))


def _protocol(params: KindParams) -> Protocol:
    assert params.protocol is not None, "kind_params gives every non-effect question its protocol"
    return params.protocol


def map_prompt(params: KindParams | None) -> tuple[str, type[BaseModel]]:
    """The mapping call's instructions and reply model for a question. No question, or the default question
    (rag-factuality): the original call, byte-identical (so existing caches hit). Another effect question:
    map-effect-v1.md with its metric and direction (AnswerReply). Other kinds: map-<kind>-v1.md."""
    if params is None or (params.kind == "effect" and (params.question_id == DEFAULT_QUESTION_ID
                                                       or params.protocol is None)):
        return MAP_INSTRUCTIONS, AnswerReply
    protocol = _protocol(params)
    text = load_prompt(PROMPTS / MAP_PROMPTS[params.kind]).text
    reply: type[BaseModel]
    if params.kind == "effect":
        metric = protocol.synthesis.metrics[0]  # type: ignore[union-attr]
        fill = {"METRIC": metric.canonical.replace("_", " "),
                "BETTER": "higher" if metric.higher_is_better else "lower",
                "WORSE": "lower" if metric.higher_is_better else "higher"}
        reply = AnswerReply
    elif params.kind == "inventory":
        target = protocol.inventory.target  # type: ignore[union-attr]
        fill = {"TARGET_TEXT": TARGET_TEXT[target], "TARGET": TARGET_NAME[target]}
        reply = InventoryReply
    elif params.kind == "consistency":
        fill = {"CLAIM_TEXT": " ".join(protocol.evidence_types["author_claim"].description.split())}
        reply = ConsistencyReply
    else:
        best = best_kind.spec(protocol)
        named = [(k, names[0]) for k, names in best.kinds.items() if names]
        assert len(named) >= 2, f"{protocol.id}: the best prompt's examples need two kinds with a name"
        (kind_a, name_a), (kind_b, name_b) = named[:2]
        fill = {"METRIC": best.metric.canonical, "DIRECTION": "higher" if best.metric.higher_is_better else "lower",
                "KINDS": "\n".join(f"- {k}: {'; '.join(names)}" for k, names in best.kinds.items()),
                "KIND_A": kind_a, "KIND_B": kind_b, "NAME_A": name_a, "NAME_B": name_b,
                "TIED_AB": ", ".join(json.dumps(k) for k in sorted((kind_a, kind_b)))}
        reply = best_reply(tuple(best.kinds))
    for name, value in fill.items():
        text = text.replace(f"<<{name}>>", value)
    assert "<<" not in text, f"{MAP_PROMPTS[params.kind]}: a placeholder is left"
    return text, reply


def empty_reply(params: KindParams) -> BaseModel:
    """The reply standing for an empty answer (no mapping call): no entries or studies."""
    _, reply = map_prompt(params)
    return reply.model_validate({"entries": []} if params.kind == "inventory" else {"studies": []})


def kind_answer_json(system: str, params: KindParams, reply: BaseModel, known: list[str],
                     **extra: Any) -> dict[str, Any]:
    """answer.json of a non-effect question in its kind's shape (evidence/kinds/*), with `system` the baseline's
    name. Papers not in the corpus are dropped (listed in `dropped`); a paper named twice keeps its first entry;
    studies and an entry's papers are in manifest order. A baseline has no items or values: inventory `items` and
    best `values` are empty, consistency `direction` (the measured one) is null. A best study with no winner and
    two or more `tied` kinds is a tie (tied sorted, reason null); a study the reply leaves null otherwise has
    reason `not_stated`. Inventory names that fold alike (case, whitespace) are one entry, named by the first form."""
    protocol = _protocol(params)
    dropped: list[str] = []
    head = {"kind": params.kind, "system": system, "question": params.question, "question_id": params.question_id}
    if isinstance(reply, InventoryReply):
        groups: dict[str, dict[str, Any]] = {}
        for e in reply.entries:
            form = " ".join(e.name.split())
            if not form:
                continue
            g = groups.setdefault(fold(form), {"name": form, "forms": [], "papers": set()})
            if form not in g["forms"]:
                g["forms"].append(form)
            for paper in e.papers:
                doc = paper_id(paper, known)
                if doc is not None:
                    g["papers"].add(doc)
                else:
                    dropped.append(paper)
        entries = [{"name": g["name"], "aliases": sorted(f for f in g["forms"] if f != g["name"]),
                    "papers": [p for p in known if p in g["papers"]], "items": []}
                   for g in sorted(groups.values(), key=lambda g: (fold(g["name"]), g["name"]))]
        body: dict[str, Any] = {"target": protocol.inventory.target, "entries": entries}  # type: ignore[union-attr]
        return head | body | {"dropped": dropped} | extra
    first: dict[str, Any] = {}
    for s in reply.studies:  # type: ignore[attr-defined]
        doc = paper_id(s.paper, known)
        if doc is None:
            dropped.append(s.paper)
        else:
            first.setdefault(doc, s)
    ordered = [(p, first[p]) for p in known if p in first]
    if isinstance(reply, ConsistencyReply):
        studies = [{"document": doc, "claim": s.claim, "direction": None, "agrees": s.agrees,
                    "reason": None if s.agrees is not None else dict(NOT_STATED)} for doc, s in ordered]
        lists = {name: [s["document"] for s in studies if s["agrees"] is value]
                 for name, value in (("agreeing", True), ("disagreeing", False), ("undetermined", None))}
        body = {"metric": protocol.synthesis.metric_names[0], "studies": studies, **lists}  # type: ignore[union-attr]
        return head | body | {"dropped": dropped} | extra
    best = best_kind.spec(protocol)
    studies = []
    for doc, s in ordered:   # a tie: no winner and two or more kinds (as evidence/kinds/best.py); a tie is complete
        tied = sorted(set(s.tied)) if s.winner is None and len(set(s.tied)) >= 2 else []
        studies.append({"document": doc, "winner": s.winner, "tied": tied, "values": {},
                        "reason": None if s.winner is not None or tied else dict(NOT_STATED)})
    body = {"metric": best.metric.canonical, "studies": studies,
            **best_kind.tally([s["winner"] for s in studies], best.kinds)}
    return head | body | {"dropped": dropped} | extra

"""What both baselines share: the corpus as a system under test sees it, the mapping call, answer.json.

Hard rule (docs/evidence-system.md Part A): a baseline reads `manifest.json` and the files it lists
under `papers/`, nothing else of the corpus directory. `SystemCorpus` is the only reader the baselines
use; it opens exactly those files, checks each against its manifest sha256, and refuses (allow-list)
any listed file that does not resolve to a file directly in `<corpus>/papers/`, so neither
ground_truth.json, corpus.json, fidelity.json, decoys.json nor any later evaluation file can be read.

Neither baseline is asked for a label or per-paper stances: the passage baseline (rag.py) writes
an answer with citations, the agent an answer table. One separate **mapping call** (`map_answer`, shared by both;
docs/evidence-system.md Part G.1) turns that answer into what the question's kind asks (`map_prompt`).

Every question kind (a pack's questions.yaml, `kind_params`; default the default pack's, `questions_path(DEFAULT_PACK)`,
and a drug question resolves through its own pack's file, plan 2 preflight P19): each kind has its own reply model and
versioned instructions (prompts/map-<kind>-v<n>.md, `MAP_PROMPTS`), filled from the question's protocol and its pack:
- effect: map-effect-v2.md with the metric, its direction and the pack's display names of the two compared sides
  (AnswerReply: the label and per-paper stances). The default question (`DEFAULT_QUESTION`, the first effect question
  of the default pack) has no special prompt any more: its mapping call is this one, so caches written before plan 2
  miss once (D36). An effect question whose protocol has subsets (`synthesis.moderators`) gets map-effect-subsets-v1.md
  instead (MAP_SUBSETS), with the protocol's candidate conditions and their levels (`subset_reply`: a verdict that
  may be `depends`, the condition, a stance per level, the untested levels, and the per-paper stances; a reply that
  breaks the form fails validation and gets pydantic-ai's retry). answer.json then also has `conclusion`, in the
  engine's shape (evidence/synthesis.py, Subsets), so every system's answer is scored against the same key; its
  `label` is the verdict, or for `depends`, which is no label, the label table's over the stated stances;
- inventory: the target and examples of it from the pack (`target_text`); consistency: the author claim's definition;
  best: the protocol's method kinds (BestReply, whose `winner` and `tied` must name them; a reply naming another kind
  fails validation and gets pydantic-ai's retry);
- chaining: source, target and metric (ChainingReply: verdict, via, papers, inferred); limitations: the pack's
  `limitation_categories` (LimitationsReply, `category` an enum of them); builds_on: the protocol's `reuses` values
  (BuildsOnReply: links and followers).
answer.json then has the kind's shape (evidence/kinds/*), with `system` the baseline's name; best's `wins`, `winner`
and `tied` (evidence.kinds.best.tally) and builds_on's `influence` and `ranking` (from `followers`) are computed here,
never asked.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, create_model, model_validator
from pydantic_ai.models import Model

from jsonio import sha256_hex
from evidence import protocol as protocol_module, questions as questions_module, rules
from evidence.kinds import best as best_kind
from evidence.kinds import builds_on as builds_on_kind
from evidence.kinds import chaining as chaining_kind
from evidence.kinds import limitations as limitations_kind
from evidence.kinds.inventory import fold
from evidence.pack import Pack, Role, questions_path
from evidence.protocol import DEFAULT_PACK, Kind, Protocol
from modelcall import CallSettings, JsonlCache, Prompt, ask_sync, cache_key, load_prompt, model_name, prompt_sha256

from ..realpapers.common import read_manifest

DEFAULT_QUESTIONS = questions_path(DEFAULT_PACK)
PROMPTS = Path(__file__).resolve().parent / "prompts"


def default_question_id(questions: Path = DEFAULT_QUESTIONS) -> str:
    """The default question of a questions file: its first effect question (evidence.questions.default_entry)."""
    return questions_module.default_entry(questions).id


_DEFAULT = questions_module.default_entry(DEFAULT_QUESTIONS)
DEFAULT_QUESTION = _DEFAULT.question
DEFAULT_PROTOCOL = questions_module.protocol_file(_DEFAULT.protocol or "", DEFAULT_QUESTIONS)   # its protocol file
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
        manifest = read_manifest(self.root)
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


class SideEffect(BaseModel):
    level: str = Field(description="a level id of the condition")
    effect: Stance = Field(description="the effect the answer states at this level")


class SubsetReply(BaseModel):
    """The mapping call of an effect question with subsets: the conclusion (one overall effect, or an effect that
    depends on one candidate condition) and the per-paper stances. The call uses `subset_reply(conditions)`, whose
    `condition`, `sides` and `untested` must name the protocol's conditions and levels."""
    verdict: Literal["depends", "supported", "refuted", "no_effect", "insufficient"] = Field(
        description="depends, supported, refuted, no_effect or insufficient")
    condition: str | None = Field(description="for depends, the id of the condition the effect depends on; else null")
    sides: list[SideEffect] = Field(description="for depends, one entry per level of that condition; else empty")
    untested: list[str] = Field(description="the levels the answer says no paper tested, as 'condition id.level id'")
    studies: list[StudyStance] = Field(description="one entry per paper the answer relies on")
    answer_text: str = Field(description="the answer in a few sentences")


@lru_cache(maxsize=None)
def subset_reply(conditions: tuple[tuple[str, tuple[str, ...]], ...]) -> type[SubsetReply]:
    """SubsetReply for the candidate `conditions` ((condition id, its level ids), ...): `condition` one of the ids, a
    side's `level` one of the level ids and an `untested` entry one of `<condition id>.<level id>` (enums in the
    schema), and, checked on validation, the form of synth2's answer: `depends` names a condition and gives each of
    its levels exactly once, with stances that are not all the same; any other verdict has no condition and no sides."""
    levels = dict(conditions)
    condition = Literal[tuple(levels)]  # type: ignore[valid-type]
    level = Literal[tuple(lv for ids in levels.values() for lv in ids)]  # type: ignore[valid-type]
    pair = Literal[tuple(f"{c}.{lv}" for c, ids in levels.items() for lv in ids)]  # type: ignore[valid-type]

    def check(self: SubsetReply) -> SubsetReply:
        if self.verdict == "depends":
            if self.condition is None:
                raise ValueError("verdict depends needs the condition the effect depends on")
            if sorted(s.level for s in self.sides) != sorted(levels[self.condition]):
                raise ValueError(f"verdict depends needs one side per level of {self.condition}: "
                                 f"{', '.join(levels[self.condition])}")
            if len({s.effect for s in self.sides}) < 2:
                raise ValueError("verdict depends needs different effects at the two levels; the same effect at "
                                 "both is one overall verdict")
        elif self.condition is not None or self.sides:
            raise ValueError(f"verdict {self.verdict} has condition null and no sides")
        return self

    side = create_model("SideEffect", __base__=SideEffect,
                        level=(level, Field(description="a level id of the condition")))
    return create_model(
        "SubsetReply", __base__=SubsetReply,
        condition=(Optional[condition], Field(description=SubsetReply.model_fields["condition"].description)),  # noqa: UP045
        sides=(list[side], Field(description=SubsetReply.model_fields["sides"].description)),
        untested=(list[pair], Field(description=SubsetReply.model_fields["untested"].description)),
        __validators__={"form": model_validator(mode="after")(check)})


def conclusion(reply: SubsetReply) -> dict[str, Any]:
    """A subsets reply as answer.json's `conclusion` (the engine's shape; evidence/synthesis.py, Subsets)."""
    return {"verdict": reply.verdict, "condition": reply.condition,
            "sides": {s.level: s.effect for s in reply.sides}, "untested": sorted(set(reply.untested))}


def answer_json(system: str, question: str, reply: AnswerReply | SubsetReply, known: list[str], *,
                answer_text: str | None = None, protocol: Protocol | None = None, **extra: Any) -> dict[str, Any]:
    """answer.json (section 4) for a baseline: the mapped label and per-paper stances, as stated.

    Entries for papers not in the corpus are dropped (listed in `dropped`); a paper named twice keeps
    its first stance. `answer_text` is the system's own answer when given, else the mapping call's
    summary. `label_by_rule` is evidence.rules.label over the stated stances by the label table of the
    question's `protocol` (default the default question's; the baseline reads no corpus file for it), for reference;
    the score uses the mapped `label`. A subsets reply (`SubsetReply`) also gives `conclusion`; its `label` is its
    verdict, or `label_by_rule` for the verdict `depends` (no label of the table).
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
    by_rule = rules.label(counts, protocol.synthesis.table if protocol is not None and
                          protocol.synthesis is not None else default_table())
    subsets = isinstance(reply, SubsetReply)
    label = reply.label if isinstance(reply, AnswerReply) else by_rule if reply.verdict == "depends" else reply.verdict
    return {"system": system, "question": question, "label": label, "counts": counts, "studies": studies,
            **groups, "undetermined": [], "answer_text": reply.answer_text if answer_text is None else answer_text,
            "label_by_rule": by_rule, "dropped": dropped, **({"conclusion": conclusion(reply)} if subsets else {}),
            **extra}


def default_table() -> Any:
    """The label table of the default question's protocol (answer_json's `label_by_rule`)."""
    synthesis = protocol_module.load(DEFAULT_PROTOCOL).synthesis
    assert synthesis is not None, "the default question is an effect question"
    return synthesis.table


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

MAP_PROMPTS = {"effect": "map-effect-v2.md", "inventory": "map-inventory-v2.md", "consistency": "map-consistency-v2.md",
               "best": "map-best-v2.md", "chaining": "map-chaining-v1.md", "limitations": "map-limitations-v1.md",
               "builds_on": "map-builds-on-v1.md"}
MAP_SUBSETS = "map-effect-subsets-v1.md"   # an effect question whose protocol has subsets (synthesis.moderators)
TARGET_NAME = {"metric": "evaluation metric", "condition": "method or system variant", "dataset": "dataset"}
TARGET_TEXT = {"metric": "the evaluation metrics the papers report results on",
               "condition": "the methods or system variants the papers compare",
               "dataset": "the datasets the papers evaluate on"}
NOT_STATED = {"code": "not_stated", "text": "the answer does not say"}


def pack_examples(target: str, pack: Pack) -> list[str]:
    """Names of `target` the pack gives: its question metrics (canonical names), the display names of its two compared
    sides; datasets have none."""
    examples = {"metric": [m.replace("_", " ") for m in dict.fromkeys(c for _, c, _ in pack.words.metrics)
                           if m != "other"][:3],
                "condition": [pack.display[side] for side in ("treatment", "control") if side in pack.display]}
    return examples.get(target) or []


def target_text(target: str, pack: Pack) -> str:
    """What an inventory of `target` lists, with examples from the pack (`pack_examples`) when it has any."""
    named = pack_examples(target, pack)
    return TARGET_TEXT[target] + (f" (for example {', '.join(named)})." if named else ".")


def abbreviation(name: str) -> str:
    """An abbreviation of `name` for a prompt example: its words' initials, or a one-word name's first three letters."""
    words = name.split()
    return ("".join(w[0] for w in words) if len(words) > 1 else name[:3]).upper()


@dataclass(frozen=True, eq=False)
class KindParams:
    """A question of a pack's questions.yaml as a baseline answers it: its id, text, kind and hand-written protocol
    (which gives the effect metric, the inventory target, the consistency metric and claim, the best metric and method
    kinds, the chain, and through its pack the display names, limitation categories and reuses values)."""
    question_id: str
    question: str
    kind: Kind
    protocol: Protocol


def kind_params(question_id: str, questions: Path | str | None = None) -> KindParams:
    """The question `question_id` of the questions file `questions` (default: whichever pack's questions file has
    it, `questions.find`; ValueError for an unknown id, one in two packs, or a question without a hand-written
    protocol). A questions file in a pack folder outside domains/ reads its protocol's pack from that folder's
    parent, so a test pack resolves (P19)."""
    if questions is None:
        entry, questions = questions_module.find(question_id)
    else:
        entries = {q.id: q for q in questions_module.load(questions)}
        if question_id not in entries:
            raise ValueError(f"unknown question id {question_id!r} ({questions} has {', '.join(entries)})")
        entry = entries[question_id]
    if entry.protocol is None:
        raise ValueError(f"question {question_id!r} has no hand-written protocol; a baseline needs one")
    protocol = questions_module.entry_protocol(entry.protocol, questions)
    return KindParams(entry.id, entry.question, entry.kind, protocol)


class InventoryEntry(BaseModel):
    name: str = Field(min_length=1, description="the name exactly as the answer writes it")
    papers: list[str] = Field(description="the corpus paper ids the answer links to this name")


class InventoryReply(BaseModel):
    """The mapping call of an inventory question: every name of the target the answer gives, with its papers."""
    entries: list[InventoryEntry] = Field(description="one entry per distinct name the answer gives")


CLAIM_ORDER = ["improves", "no_effect", "worsens"]


def _claim_enum_order(schema: dict[str, Any]) -> None:
    """Pin the enum order of the claim in the schema. `Literal` is cached by value, not by order, so another module
    that spells the same three values in another order and imports first would hand this field its order, and the
    prompt hash (which includes the schema) would depend on import order."""
    for branch in schema.get("anyOf", [schema]):
        if "enum" in branch:
            branch["enum"] = CLAIM_ORDER


class ConsistencyStudy(BaseModel):
    paper: str = Field(description="a corpus paper id")
    claim: Literal["improves", "no_effect", "worsens"] | None = Field(
        description="the authors' conclusion the answer attributes to this paper, or null",
        json_schema_extra=_claim_enum_order)
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


# The refusal reasons a chaining answer can give (rules.CHAIN_REASONS but direct_comparison, which is no refusal
# reason of its own: the engine also gives it to a direct result that concludes).
RefusalReason = Literal["no_path", "metric_differs", "context_differs", "mixed_directions", "paths_disagree"]
assert set(RefusalReason.__args__) == set(rules.CHAIN_REASONS) - {chaining_kind.DIRECT}


class ChainingReply(BaseModel):
    """The mapping call of a chaining question: the verdict, the things in between, the papers, inferred or direct."""
    verdict: rules.ChainVerdict | None = Field(
        description="better, worse, no_difference or refused (source over target); null when the answer does not "
                    "say")
    via: list[str] = Field(description="the things the answer goes through, in order, as it writes them")
    papers: list[str] = Field(description="the corpus paper ids the answer rests its verdict on")
    inferred: bool = Field(description="true when reached through `via` things, false for a direct comparison")
    reason: RefusalReason | None = Field(
        None, description="only for a refused verdict: why the papers cannot settle it")


CATEGORY = "the category of the limitation, one of the pack's list"


class LimitationEntry(BaseModel):
    thing: str | None = Field(description="the compared thing the limitation is about, or null (the study as a whole)")
    category: str = Field(description=CATEGORY)
    papers: list[str] = Field(description="the corpus paper ids the answer names this limitation for")


class LimitationsReply(BaseModel):
    """The mapping call of a limitations question: (thing, category) entries with their papers. The call uses
    `limitations_reply(categories)`, whose `category` must be one of the pack's limitation categories."""
    entries: list[LimitationEntry] = Field(description="one entry per thing and category the answer states")


@lru_cache(maxsize=None)
def limitations_reply(categories: tuple[str, ...]) -> type[LimitationsReply]:
    """LimitationsReply with `category` limited to `categories` (an enum in the schema, checked on validation)."""
    category = Literal[categories]  # type: ignore[valid-type]
    entry = create_model("LimitationEntry", __base__=LimitationEntry, category=(category, Field(description=CATEGORY)))
    return create_model("LimitationsReply", __base__=LimitationsReply,
                        entries=(list[entry], Field(description="one entry per thing and category the answer states")))


REUSES = "what the citing paper takes from the earlier one"


class Link(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    from_: str = Field(alias="from", description="the corpus paper id of the paper that builds on the other")
    to: str = Field(description="the corpus paper id of the earlier paper it builds on")
    reuses: str = Field(description=REUSES)


class Follower(BaseModel):
    thing: str = Field(description="a compared thing, as the answer writes it")
    papers: list[str] = Field(description="the corpus paper ids the answer says build on it, directly or not")


class BuildsOnReply(BaseModel):
    """The mapping call of a builds-on question: the links between papers and each thing's followers (influence is
    computed from them, never asked). The call uses `builds_on_reply(reuses)`, whose `reuses` is the protocol's enum."""
    links: list[Link] = Field(description="one entry per paper that builds on another")
    followers: list[Follower] = Field(description="one entry per compared thing later papers build on")


@lru_cache(maxsize=None)
def builds_on_reply(reuses: tuple[str, ...]) -> type[BuildsOnReply]:
    """BuildsOnReply with a link's `reuses` limited to `reuses` (an enum in the schema, checked on validation)."""
    value = Literal[reuses]  # type: ignore[valid-type]
    link = create_model("Link", __base__=Link, reuses=(value, Field(description=REUSES)))
    return create_model("BuildsOnReply", __base__=BuildsOnReply,
                        links=(list[link], Field(description="one entry per paper that builds on another")))


def _display(pack: Pack, side: str) -> str:
    if side not in pack.display:
        raise ValueError(f"pack {pack.name!r} has no display name {side!r} (pack.yaml display)")
    return pack.display[side]


def _reuses(protocol: Protocol) -> list[str]:
    """The `reuses` values of the protocol's dependency type (its field's enum)."""
    dependency = protocol.roles().type_in(Role.DEPENDENCY, protocol.evidence_types)
    assert dependency is not None, f"{protocol.id}: a builds-on protocol declares a dependency type"
    field = protocol.evidence_types[dependency].fields.get("properties", {}).get(builds_on_kind.REUSES, {})
    values = list(field.get("enum") or [])
    assert len(values) >= 2, f"{protocol.id}: the builds-on prompt's examples need two `reuses` values"
    return values


def map_prompt(params: KindParams | None) -> tuple[str, type[BaseModel]]:
    """The mapping call's instructions and reply model for a question (None: the default question; D36: it has no
    special case any more), from prompts/MAP_PROMPTS[kind] filled from the question's protocol and its pack."""
    params = params or kind_params(default_question_id(), DEFAULT_QUESTIONS)
    protocol = params.protocol
    pack = protocol.pack()
    mods = protocol.synthesis.moderators if params.kind == "effect" and protocol.synthesis is not None else None
    name = MAP_SUBSETS if mods is not None else MAP_PROMPTS[params.kind]
    text = load_prompt(PROMPTS / name).text
    reply: type[BaseModel]
    if params.kind == "effect":
        metric = protocol.synthesis.metrics[0]  # type: ignore[union-attr]
        fill = {"METRIC": metric.canonical.replace("_", " "),
                "BETTER": "higher" if metric.higher_is_better else "lower",
                "WORSE": "lower" if metric.higher_is_better else "higher",
                "TREATMENT": _display(pack, "treatment"), "CONTROL": _display(pack, "control")}
        reply = AnswerReply
        if mods is not None:
            first = mods.conditions[0]
            fill |= {"CONDITIONS": "\n".join(f"- {c.id} ({c.name}): " + "; ".join(f"{lv.id} = {lv.name}" for lv in c.levels)
                                             for c in mods.conditions),
                     "COND_A": first.id, "LEVEL_A1": first.levels[0].id, "LEVEL_A2": first.levels[1].id,
                     "LEVEL_A1_NAME": first.levels[0].name, "LEVEL_A2_NAME": first.levels[1].name}
            reply = subset_reply(tuple(mods.table))
    elif params.kind == "inventory":
        target = protocol.inventory.target  # type: ignore[union-attr]
        names = (pack_examples(target, pack) + [f"{TARGET_NAME[target]} {x}" for x in "AB"])[:2]
        fill = {"TARGET_TEXT": target_text(target, pack), "TARGET": TARGET_NAME[target], "NAME_A": names[0],
                "NAME_B": names[1], "ABBR_A": abbreviation(names[0])}
        reply = InventoryReply
    elif params.kind == "consistency":
        metric = protocol.synthesis.metrics[0]  # type: ignore[union-attr]
        fill = {"CLAIM_TEXT": " ".join(protocol.evidence_types["author_claim"].description.split()),
                "METRIC": metric.canonical.replace("_", " "),
                "BETTER": "higher" if metric.higher_is_better else "lower",
                "TREATMENT": _display(pack, "treatment"), "CONTROL": _display(pack, "control")}
        reply = ConsistencyReply
    elif params.kind == "best":
        best = best_kind.spec(protocol)
        named = [(k, names[0]) for k, names in best.kinds.items() if names]
        assert len(named) >= 2, f"{protocol.id}: the best prompt's examples need two kinds with a name"
        (kind_a, name_a), (kind_b, name_b) = named[:2]
        fill = {"METRIC": best.metric.canonical, "DIRECTION": "higher" if best.metric.higher_is_better else "lower",
                "KINDS": "\n".join(f"- {k}: {'; '.join(names)}" for k, names in best.kinds.items()),
                "KIND_A": kind_a, "KIND_B": kind_b, "NAME_A": name_a, "NAME_B": name_b,
                "TIED_AB": ", ".join(json.dumps(k) for k in sorted((kind_a, kind_b)))}
        reply = best_reply(tuple(best.kinds))
    elif params.kind == "chaining":
        chain = chaining_kind.spec(protocol)
        fill = {"SOURCE": chain.source, "TARGET": chain.target, "METRIC": chain.metric.canonical.replace("_", " "),
                "DIRECTION": "higher" if chain.metric.higher_is_better else "lower"}
        reply = ChainingReply
    elif params.kind == "limitations":
        categories = list(pack.limitation_categories)
        assert len(categories) >= 2, f"pack {pack.name!r}: the limitations prompt's examples need two categories"
        fill = {"CATEGORIES": "\n".join(f"- {c}" for c in categories),
                "THING": limitations_kind.spec(protocol).thing or _display(pack, "treatment"),
                "CATEGORY_A": categories[0], "CATEGORY_B": categories[1],
                "WORDS_A": categories[0].replace("_", " "), "WORDS_B": categories[1].replace("_", " ")}
        reply = limitations_reply(tuple(categories))
    else:
        reuses = _reuses(protocol)
        fill = {"REUSES": ", ".join(reuses), "REUSE_A": reuses[0], "REUSE_B": reuses[1],
                "THING": builds_on_kind.spec(protocol).thing or _display(pack, "treatment")}
        reply = builds_on_reply(tuple(reuses))
    for key, value in fill.items():
        text = text.replace(f"<<{key}>>", value)
    assert "<<" not in text, f"{name}: a placeholder is left"
    return text, reply


EMPTY = {"inventory": {"entries": []}, "limitations": {"entries": []}, "builds_on": {"links": [], "followers": []},
         "chaining": {"verdict": None, "via": [], "papers": [], "inferred": False}}


def empty_reply(params: KindParams) -> BaseModel:
    """The reply standing for an empty answer (no mapping call): no entries, studies, links or verdict."""
    _, reply = map_prompt(params)
    return reply.model_validate(EMPTY.get(params.kind, {"studies": []}))


def _docs(raw: list[str], known: list[str], dropped: list[str]) -> list[str]:
    """The corpus ids `raw` names, once each, in manifest order; the rest go to `dropped`."""
    found = set()
    for paper in raw:
        doc = paper_id(paper, known)
        if doc is None:
            dropped.append(paper)
        else:
            found.add(doc)
    return [p for p in known if p in found]


def _chaining_body(protocol: Protocol, reply: ChainingReply, known: list[str], dropped: list[str]) -> dict[str, Any]:
    """chaining: source, target and metric from the protocol; `studies` the reply's papers; `via` its things (once
    each, as written). No paths (a baseline has no comparisons); `reason` not_stated when no verdict is given, the
    reply's refusal reason for a refused verdict (null when it gives none), direct_comparison for a verdict not
    inferred (as the engine), else null; `note` as the engine's."""
    chain = chaining_kind.spec(protocol)
    via = list(dict.fromkeys(form for v in reply.via if (form := " ".join(v.split()))))
    direct = not reply.inferred and reply.verdict not in (None, "refused")
    reason = (NOT_STATED["code"] if reply.verdict is None else reply.reason if reply.verdict == "refused"
              else chaining_kind.DIRECT if direct else None)
    inferred = reply.inferred and reply.verdict is not None
    return {"source": chain.source, "target": chain.target, "metric": chain.metric.canonical,
            "verdict": reply.verdict, "inferred": inferred, "via": via,
            "studies": _docs(reply.papers, known, dropped), "paths": [], "reason": reason,
            "note": chaining_kind.NOTE.format(via=", ".join(via)) if inferred and via else None}


def _things(names: list[str | None]) -> dict[str, str]:
    """fold -> the first form met of each thing name (blank names left out)."""
    shown: dict[str, str] = {}
    for name in names:
        form = " ".join((name or "").split())
        if form:
            shown.setdefault(fold(form), form)
    return shown


def _limitations_body(protocol: Protocol, reply: LimitationsReply, known: list[str],
                      dropped: list[str]) -> dict[str, Any]:
    """limitations: entries (thing, category) with their papers; names that fold alike are one thing, shown by the
    first form; a blank or null thing is the unlinked entry. With the protocol's `thing`, only its entries. Sorted as
    the engine sorts (thing case-folded, unlinked last, then the pack's category order); `counts` and `unlinked` count
    papers."""
    wanted = limitations_kind.spec(protocol).thing
    order = {c: n for n, c in enumerate(protocol.pack().limitation_categories)}
    shown = _things([e.thing for e in reply.entries])
    papers: dict[tuple[str | None, str], list[str]] = {}
    for e in reply.entries:
        form = " ".join((e.thing or "").split())
        key = (fold(form) if form else None, e.category)
        papers[key] = papers.get(key, []) + list(e.papers)
    if wanted is not None:
        papers = {k: v for k, v in papers.items() if k[0] == fold(" ".join(wanted.split()))}
    keys = sorted(papers, key=lambda k: (k[0] is None, k[0] or "", order.get(k[1], len(order)), k[1]))
    entries = [{"thing": shown[k[0]] if k[0] is not None else None, "category": k[1],
                "papers": _docs(papers[k], known, dropped), "items": []} for k in keys]
    counts: dict[str, dict[str, int]] = {}
    unlinked: dict[str, int] = {}
    for e in entries:
        target = unlinked if e["thing"] is None else counts.setdefault(e["thing"], {})
        target[e["category"]] = len(e["papers"])
    return {"thing": wanted, "entries": entries, "counts": counts, "unlinked": unlinked}


def _builds_on_body(protocol: Protocol, reply: BuildsOnReply, known: list[str], dropped: list[str]) -> dict[str, Any]:
    """builds_on: `links` (corpus papers only, once each, in manifest order of the citing then the cited paper, then
    by `reuses`) and `followers` per thing (names that fold alike are one thing); `influence` (the number of
    followers) and `ranking` (influence descending, then name) are computed here, never asked. With the protocol's
    `thing`, only that thing. `origins` and `unresolved` are not asked: empty."""
    wanted = builds_on_kind.spec(protocol).thing
    position = {d: n for n, d in enumerate(known)}
    found = set()
    for link in reply.links:
        ends = [paper_id(link.from_, known), paper_id(link.to, known)]
        dropped += [raw for raw, doc in zip((link.from_, link.to), ends) if doc is None]
        if None not in ends:
            found.add((ends[0], ends[1], link.reuses))
    links = [{"from": f, "to": t, "reuses": r, "items": []}
             for f, t, r in sorted(found, key=lambda k: (position[k[0]], position[k[1]], k[2]))]
    shown = _things([f.thing for f in reply.followers])
    raw: dict[str, list[str]] = {}
    for f in reply.followers:
        form = " ".join(f.thing.split())
        if form:
            raw[fold(form)] = raw.get(fold(form), []) + list(f.papers)
    if wanted is not None:
        raw = {k: v for k, v in raw.items() if k == fold(" ".join(wanted.split()))}
    followers = {k: _docs(v, known, dropped) for k, v in raw.items()}
    ranking = sorted(followers, key=lambda k: (-len(followers[k]), shown[k].casefold(), shown[k]))
    return {"thing": wanted, "links": links, "origins": {},
            "followers": {shown[k]: followers[k] for k in ranking},
            "influence": {shown[k]: len(followers[k]) for k in ranking},
            "ranking": [shown[k] for k in ranking], "unresolved": []}


def kind_answer_json(system: str, params: KindParams, reply: BaseModel, known: list[str],
                     **extra: Any) -> dict[str, Any]:
    """answer.json of a non-effect question in its kind's shape (evidence/kinds/*), with `system` the baseline's
    name. Papers not in the corpus are dropped (listed in `dropped`); a paper named twice keeps its first entry;
    studies and an entry's papers are in manifest order. A baseline has no items or values: inventory `items` and
    best `values` are empty, consistency `direction` (the measured one) is null. A best study with no winner and
    two or more `tied` kinds is a tie (tied sorted, reason null); a study the reply leaves null otherwise has
    reason `not_stated`. Inventory names that fold alike (case, whitespace) are one entry, named by the first form.
    chaining, limitations and builds_on: `_chaining_body`, `_limitations_body`, `_builds_on_body`."""
    protocol = params.protocol
    dropped: list[str] = []
    head = {"kind": params.kind, "system": system, "question": params.question, "question_id": params.question_id}
    if isinstance(reply, ChainingReply):
        return head | _chaining_body(protocol, reply, known, dropped) | {"dropped": dropped} | extra
    if isinstance(reply, LimitationsReply):
        return head | _limitations_body(protocol, reply, known, dropped) | {"dropped": dropped} | extra
    if isinstance(reply, BuildsOnReply):
        return head | _builds_on_body(protocol, reply, known, dropped) | {"dropped": dropped} | extra
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

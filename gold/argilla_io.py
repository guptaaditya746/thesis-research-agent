"""Argilla datasets for the human review of D (milestone 3, plan "Gold"), ported from the labelling
repo's argilla_io.py to facts with quotes from Markdown papers.

Five datasets per gold version `<name>` (default `gold-v1`), in one workspace (default `thesis`):

- `<name>-review`: one record per pool record of C1's pool.jsonl (every candidate fact triage put in
  answers or context plus a seeded sample of the rest, in a seeded shuffle). A record shows the
  question, the concept, the fact s/p/o (and the row it belongs to), its quote and the passage around
  the quote in the corpus file. Questions: `label` correct / incorrect / unsure, `correction` (optional,
  `s | p | o`, an empty part keeps the candidate's), `vital` yes / no (optional), `note`. One reviewer.
  The stratum is not sent at all: Argilla hides "hidden" metadata from annotators only, and the owner
  who reviews would see which facts triage called irrelevant (gold/agreement.py takes the stratum from
  the pool instead).
- `<name>-overlap`: the same records for the agreement subset (about 20 % of the questions, a seeded
  choice kept in $GOLD/overlap.json), two reviewers each, answered independently. Those questions'
  records are only here, so nobody reviews a record twice.
- `<name>-missing`: one record per question to add facts D missed, one per line
  `s | p | o | file | quote` (gold/export.py anchors the quote with agent/anchor.py).
- `<name>-screening`: a seeded sample of the papers C1's screening marked not relevant
  (gold/screening_check.py): is the paper relevant after all, and which facts are missing.
- `<name>-judge`: fact-quote pairs sampled from runs to calibrate the judge (gold/judge.py), answered
  supports / partial / no without seeing the judge's answer or the run's condition (not sent; the
  calibration reads it from the sample file).

Record ids are stable (`<candidate id>-<fact digest>` (gold/review.py record_id), `missing-<qid>`,
`screening-<qid>-<paper>`, `judge-<hash>`), so a second push updates records in place and people's
responses stay; a candidate id that comes to name another fact gets a new record. Record dicts never
use a question's name as a key: Argilla would take it as a suggestion and show it to the reviewer.

The client reads $ARGILLA_API_URL and $ARGILLA_API_KEY when it is made; the key is never logged or
written. Argilla runs on Omen and is reached through `scripts/omen-tunnels` (gold/REVIEW.md).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, replace
from typing import Any

from agent import anchor

from .review import Corpus, record_id

DEFAULT_NAME = "gold-v1"
DEFAULT_WORKSPACE = "thesis"
DEFAULT_URL = "http://127.0.0.1:36900"  # the compute-node end of the omen-tunnels `argilla` service
DATASETS = ("review", "overlap", "missing", "screening", "judge")
PASSAGE_CHARS = 1500  # characters shown on each side of a quote (the web app's passage default)
PAPER_CHARS = 200_000  # a screening record shows the paper up to this length (papers are 45-230 KB)

LABEL = {
    "correct": "Correct: the quote states this fact (after your correction) and it belongs in the answer",
    "incorrect": "Incorrect: the quote does not state it, or it does not belong in the answer",
    "unsure": "Unsure: I cannot decide from the quote and the passage (write a note)",
}
VITAL = {"yes": "Vital: an answer without this fact misses the point of the question",
         "no": "Not vital: worth having, but a good answer could leave it out"}
RELEVANT = {"yes": "Relevant: it states facts that answer the question or are needed to read the answer",
            "no": "Not relevant"}
SUPPORT = {"supports": "Supports: a reader of the quote learns the fact",
           "partial": "Partly: the quote supports part of the fact, or a vaguer statement",
           "no": "No: the quote does not state the fact, or contradicts it"}
DONE = {"yes": "I checked this question", "no": "I have not checked this question"}
CORRECTION_FORMAT = "subject | predicate | object"
MISSING_FORMAT = "subject | predicate | object | file | quote"
GUIDELINES = "gold/guidelines.md in the thesis-research-agent repository"


# --- dataset settings ---------------------------------------------------------------------------------

@dataclass(frozen=True)
class Spec:
    """One dataset's settings, declared once: `settings()` builds the Argilla object from it, and tests
    check records against it without a server."""

    guidelines: str
    fields: tuple[tuple[str, str], ...]  # (name, title); every field is required Markdown text
    questions: tuple[tuple[str, str, dict[str, str] | None, bool], ...]  # (name, title, labels or None = text, required)
    metadata: tuple[tuple[str, str | None, str, bool], ...]  # (name, title, "terms" | "integer", visible)
    min_submitted: int = 1


_REVIEW = Spec(
    guidelines=(
        "Judge each candidate fact against its quote, using the passage only to see what the quote refers "
        "to; no outside knowledge. Correct = the quote states the fact and it belongs in the answer the "
        f"concept asks for. To fix a fact, write it as `{CORRECTION_FORMAT}` (leave a part empty to keep it) "
        f"and label it correct. Mark kept facts vital or not. Full guideline: {GUIDELINES}."),
    fields=(("question", "Question"), ("concept", "Concept (what the answer is)"), ("fact", "Candidate fact"),
            ("quote", "Quote"), ("passage", "Passage around the quote")),
    questions=(("label", "Is the fact correct and part of the answer?", LABEL, True),
               ("correction", f"Corrected fact ({CORRECTION_FORMAT}), optional", None, False),
               ("vital", "If correct: is it vital?", VITAL, False),
               ("note", "Note (optional)", None, False)),
    metadata=(("question_id", "Question", "terms", True), ("paper_id", "Paper", "terms", True)),
)

SPECS: dict[str, Spec] = {
    "review": _REVIEW,
    "overlap": replace(_REVIEW, min_submitted=2),
    "missing": Spec(
        guidelines=(
            "After reviewing a question's facts, add correct facts that belong in the answer and that D does "
            f"not contain, one per line: `{MISSING_FORMAT}` (the quote copied from the file). Mark Reviewed "
            f"even when nothing is missing. Full guideline: {GUIDELINES}."),
        fields=(("question", "Question"), ("concept", "Concept (what the answer is)"), ("scope", "What D already has")),
        questions=(("missing", f"Missing facts, one per line ({MISSING_FORMAT})", None, False),
                   ("done", "Reviewed", DONE, True)),
        metadata=(("question_id", "Question", "terms", True),),
    ),
    "screening": Spec(
        guidelines=(
            "The screening marked this paper not relevant to the question. Skim the whole paper (not only its "
            "title): is it relevant after all? If yes, add the facts the answer is missing, one per line: "
            f"`{MISSING_FORMAT}`. Check every record, also the obvious ones: the sample is random so that it "
            f"estimates what the screening missed. Full guideline: {GUIDELINES}."),
        fields=(("question", "Question"), ("concept", "Concept (what the answer is)"), ("paper", "Paper")),
        questions=(("relevant", "Is this paper relevant to the question?", RELEVANT, True),
                   ("missing", f"If yes: missing facts ({MISSING_FORMAT})", None, False),
                   ("note", "Note (optional)", None, False)),
        # The stratum: papers screened not relevant for the question, and how many were drawn.
        metadata=(("question_id", "Question", "terms", True), ("paper_id", "Paper", "terms", True),
                  ("not_relevant_total", None, "integer", False), ("sample_size", None, "integer", False)),
    ),
    "judge": Spec(
        guidelines=(
            "Does the quote support the fact? Judge the quote itself; the passage only shows what words such "
            "as 'we' or 'our model' refer to. Subjects such as p12 are the paper the quote is from. Numbers, "
            f"names, datasets and metrics must agree exactly. Full guideline: {GUIDELINES}."),
        fields=(("fact", "Fact"), ("quote", "Quote"), ("passage", "Passage around the quote")),
        questions=(("support", "Does the quote support the fact?", SUPPORT, True),
                   ("note", "Note (optional)", None, False)),
        # No condition (claim_on / claim_off): it must not sway the answer, and an owner sees hidden metadata.
        metadata=(("question_id", "Question", "terms", True),),
    ),
}


def settings(dataset: str, api: Any) -> Any:
    """The Argilla settings of one dataset. Every property gets `api` as its client, so building them
    never falls back to Argilla's global default client."""
    import argilla as rg

    spec = SPECS[dataset]
    return rg.Settings(
        guidelines=spec.guidelines,
        fields=[rg.TextField(name=n, title=t, use_markdown=True, client=api) for n, t in spec.fields],
        questions=[rg.LabelQuestion(name=n, title=t, labels=labels, required=req, client=api) if labels
                   else rg.TextQuestion(name=n, title=t, required=req, client=api)
                   for n, t, labels, req in spec.questions],
        metadata=[(rg.IntegerMetadataProperty if kind == "integer" else rg.TermsMetadataProperty)(
            name=n, title=t, visible_for_annotators=visible, client=api) for n, t, kind, visible in spec.metadata],
        distribution=rg.TaskDistribution(min_submitted=spec.min_submitted),
    )


# --- client, push and pull ------------------------------------------------------------------------------

def client() -> Any:
    """An Argilla client for $ARGILLA_API_URL with $ARGILLA_API_KEY (read now, never stored elsewhere)."""
    import argilla as rg
    import httpx

    url = os.environ.get("ARGILLA_API_URL", DEFAULT_URL)
    try:
        return rg.Argilla(api_url=url, api_key=os.environ.get("ARGILLA_API_KEY"))
    except httpx.ConnectError as exc:
        raise SystemExit(
            f"Argilla is not reachable at {url} ({exc}). It runs on Omen: check the stack there "
            "(`docker compose ps` in ~/stacks/argilla), then open the `argilla` tunnel, laptop side first "
            "(`omen-tunnels laptop start argilla`), then here (`omen-tunnels compute start argilla`). "
            "See gold/REVIEW.md.") from None


def _create_dataset(api: Any, name: str, workspace: str, settings: Any) -> Any:
    import argilla as rg

    return rg.Dataset(name=name, workspace=workspace, settings=settings, client=api).create()


def _create_workspace(api: Any, workspace: str) -> None:
    import argilla as rg

    rg.Workspace(name=workspace, client=api).create()


def ensure_dataset(api: Any, dataset: str, *, name: str, workspace: str) -> Any:
    """`<name>-<dataset>`, created with its settings if it does not exist yet (an existing one keeps its own)."""
    if api.workspaces(workspace) is None:
        _create_workspace(api, workspace)
    existing = api.datasets(name=f"{name}-{dataset}", workspace=workspace)
    if existing is not None:
        return existing
    return _create_dataset(api, f"{name}-{dataset}", workspace, settings(dataset, api))


def push(api: Any, dataset: str, records: list[dict[str, Any]], *, name: str = DEFAULT_NAME,
         workspace: str = DEFAULT_WORKSPACE) -> int:
    """Add or update `records` in `<name>-<dataset>` (upsert by record id)."""
    if not records:
        return 0
    ensure_dataset(api, dataset, name=name, workspace=workspace).records.log(records)
    return len(records)


def _usernames(api: Any) -> dict[str, str]:
    try:
        return {str(user.id): user.username for user in api.users}
    except Exception:  # an annotator's key may not list users: fall back to user ids
        return {}


def _plain(value: Any) -> Any:
    return getattr(value, "value", value)  # ResponseStatus and other enums -> their string


def plain_record(record: Any, dataset: str, usernames: dict[str, str]) -> dict[str, Any]:
    """One Argilla record as the JSON line gold/review.py stores."""
    metadata = record.metadata
    metadata = metadata.to_dict() if hasattr(metadata, "to_dict") else dict(metadata or {})
    responses = [{"question": r.question_name, "value": r.value, "status": str(_plain(r.status)),
                  "user": usernames.get(str(r.user_id), str(r.user_id))} for r in record.responses]
    return {"id": str(record.id), "dataset": dataset, "metadata": dict(metadata), "responses": responses}


def pull(api: Any, *, name: str = DEFAULT_NAME, workspace: str = DEFAULT_WORKSPACE,
         datasets: tuple[str, ...] = DATASETS) -> dict[str, list[dict[str, Any]]]:
    """Every record of each existing dataset with its responses (all statuses; readers keep submitted ones)."""
    if api.workspaces(workspace) is None:  # the SDK would fail on it with an AttributeError
        raise SystemExit(f"Argilla has no workspace {workspace!r} (--workspace or $ARGILLA_WORKSPACE): a mistyped "
                         "name, or nothing pushed yet (`gold push` creates it).")
    usernames = _usernames(api)
    out: dict[str, list[dict[str, Any]]] = {}
    for dataset in datasets:
        found = api.datasets(name=f"{name}-{dataset}", workspace=workspace)
        if found is None:
            continue
        out[dataset] = [plain_record(r, dataset, usernames)
                        for r in found.records(with_responses=True, with_suggestions=False)]
    return out


# --- record content -------------------------------------------------------------------------------------

def concept_markdown(concept: dict[str, Any] | None) -> str:
    """Title, definition and answer shape of the picked concept, as a reviewer needs them."""
    if not concept:
        return "_No concept picked yet: judge against the question._"
    shape = concept["answer_shape"]
    if shape["kind"] == "table":
        columns = ", ".join(f"{c['name']} ({c['type']})" for c in shape["columns"])
        answer = f"a table, one row per {shape['columns'][0]['name']}; columns: {columns}"
    else:
        edges = "; ".join(
            f"{e['source']} —{e['predicate']}→ {e['target']}"
            + (f" [{', '.join(a['name'] for a in e.get('attributes', []))}]" if e.get("attributes") else "")
            for e in shape["edges"])
        answer = f"a graph with edges {edges}"
    return f"**{concept.get('title', '')}**\n\n{concept.get('definition', '')}\n\nAnswer: {answer}."


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("*", "\\*").replace("_", "\\_")


def fact_markdown(fact: dict[str, Any], row: dict[str, Any] | None = None) -> str:
    text = f"**{_md(fact.get('s'))}** — _{_md(fact.get('p'))}_ — **{_md(fact.get('o'))}**"
    if row:
        cells = row["cells"] if isinstance(row.get("cells"), dict) else row  # table cells or graph edge fields
        shown = "; ".join(f"{_md(k)} = {_md(v)}" for k, v in cells.items() if v not in (None, "", [], {}))
        if shown:
            text += f"\n\nRow: {shown}"
    return text


def quote_markdown(quote: str, file: str | None = None) -> str:
    lines = "\n".join(f"> {line}" if line.strip() else ">" for line in str(quote).splitlines()) or "> "
    return (f"`{file}`\n\n" if file else "") + lines


def window(text: str, start: int, end: int, chars: int = PASSAGE_CHARS) -> tuple[int, int]:
    """About `chars` characters on each side of [start, end), cut at line ends."""
    a, b = max(0, start - chars), min(len(text), end + chars)
    if a > 0 and (nl := text.find("\n", a, start)) >= 0:
        a = nl + 1
    if b < len(text) and (nl := text.rfind("\n", end, b)) >= 0:
        b = nl
    return a, b


def passage_markdown(text: str, start: int, end: int, chars: int = PASSAGE_CHARS) -> str:
    """The window around a quote with the quote marked."""
    a, b = window(text, start, end, chars)
    return ("…\n\n" if a else "") + text[a:start] + "<mark>" + text[start:end] + "</mark>" + text[end:b] \
        + ("\n\n…" if b < len(text) else "")


def candidate_passage(corpus: Corpus, item: dict[str, Any], chars: int = PASSAGE_CHARS) -> str:
    """The passage around a candidate's quote, the quote marked. Only a quote that is really not in the
    file (anchor.AnchorError) gets "judge it as not stated"; a quote found several times shows the
    occurrence review.Corpus.locate picked, with a note. A file the corpus cannot give raises
    review.Rejected: the push leaves such a record out rather than show a reviewer a wrong instruction."""
    try:
        found = corpus.locate(item)
    except anchor.AnchorError as exc:
        return f"_The quote could not be found in `{corpus.file_name(item.get('file') or '')}` ({exc.reason}); judge it as not stated._"
    note = ""
    if found.occurrences > 1:
        which = "the one in the part of the paper the fact was read from" if found.how == "chunk" else "the first"
        note = f"_The quote occurs {found.occurrences} times in `{found.file}`; {which} is marked._\n\n"
    return note + passage_markdown(found.text, found.start, found.end, chars=chars)


def review_record(item: dict[str, Any], *, question: str, concept_md: str, passage_md: str) -> dict[str, Any]:
    """A review (or overlap) record for one pool record; its id is review.record_id (candidate id and
    fact digest). Neither the triage label nor the stratum is in it."""
    return {"id": record_id(item), "question": question, "concept": concept_md,
            "fact": fact_markdown(item, item.get("row")), "quote": quote_markdown(item.get("quote", ""), item.get("file")),
            "passage": passage_md, "question_id": item["qid"], "paper_id": item.get("paper_id") or "unknown"}


def scope_markdown(doc: dict[str, Any] | None, screening: list[dict[str, Any]], *, max_rows: int = 200) -> str:
    """What D already holds, for the missing-facts record: its rows and the papers screened relevant."""
    rows = (doc or {}).get("rows") or []
    relevant = sorted(str(p["paper_id"]) for p in screening if p.get("status") == "relevant")
    lines = [f"D has {len(rows)} rows from {len(relevant)} papers screened relevant."]
    if rows:
        lines += ["", "Rows:"] + [f"- {_md(r.get('key', r.get('cells', '')))}" for r in rows[:max_rows]]
        if len(rows) > max_rows:
            lines.append(f"- … and {len(rows) - max_rows} more (doc.md)")
    if relevant:
        lines += ["", "Papers screened relevant: " + ", ".join(f"`{p}.md`" for p in relevant)]
    return "\n".join(lines)


def missing_record(qid: str, *, question: str, concept_md: str, scope_md: str) -> dict[str, Any]:
    return {"id": f"missing-{qid}", "question": question, "concept": concept_md, "scope": scope_md,
            "question_id": qid}


def paper_markdown(text: str, file: str, chars: int = PAPER_CHARS) -> str:
    cut = len(text) > chars
    return f"`{file}`\n\n" + text[:chars] + (f"\n\n… (cut at {chars} characters)" if cut else "")


def screening_record(qid: str, paper_id: str, *, question: str, concept_md: str, paper_md: str,
                     not_relevant: int, sampled: int) -> dict[str, Any]:
    return {"id": f"screening-{qid}-{paper_id}", "question": question, "concept": concept_md,
            "paper": paper_md, "question_id": qid, "paper_id": paper_id,
            "not_relevant_total": not_relevant, "sample_size": sampled}


def judge_record(pair: dict[str, Any], *, passage_md: str) -> dict[str, Any]:
    """A calibration record for one sampled fact-quote pair (gold/judge.py sample_pairs)."""
    return {"id": pair["id"], "fact": fact_markdown(pair["fact"]),
            "quote": quote_markdown(pair["quote"], pair.get("file")), "passage": passage_md,
            "question_id": pair.get("qid") or "unknown"}

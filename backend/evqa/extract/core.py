"""Extract: marked passages -> quote-checked rows, one per value. The LLM writes row drafts; code does the rest.

    rows = run(spec, hits, domain, cfg)

Per passage one LLM call (ExtractRows, at most 3 at once). Then, by code only:
  1. value   norm.py reads `raw` (sign rule: "reduced by 1.1" -> -1.1 change) and finds the same number in the
             quote as the paper prints it, so the direction words around it count; the quote's reading wins.
  2. quote   anchor.spans finds the quote in paper.md (tolerant to whitespace, unicode minus, curly quotes). Found
             more than once: the occurrence inside the passage is used and the choice noted. quote_ok = found and
             the quote holds a value equal to std (norm.same). Rows with quote_ok False stay, flagged.
  3. spec    subject, comparator and measure are matched to the spec's names (label + synonyms) and written in the
             spec's words; a row of another subject or measure is kept with a `dropped` reason, and so is a row
             whose subject the paper never names (the model put the question's drug on another drug's value).
  4. settings settings_v2.py: per paper the setting sets (LLM + quote checks + separate verifier); each row gets its
             paper's set (one set: by code; several: an extra setting quoted in the row, else one pick call).
             Links between sets (same/different) are a separate step (extract/links.py, run.py "link").
  5. merge   same paper + same subject/comparator/measure/patient group/dose/time point + same value -> one row
             (other quotes in `also`). Different values for the same key stay as separate rows, noted as a conflict.
"""
from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from typing import Any

import dspy

from evqa import corpus, norm
from evqa.answer import canon
from evqa.contracts import FindHit, Passage, Row, RunConfig, Spec, StdValue
from evqa.extract import anchor, settings_v2
from evqa.extract.prompt import ExtractRows, RowDraft
from evqa.llm import cap_for, service_failed

log = logging.getLogger(__name__)
ATTEMPTS = 3
CONTEXT_CHARS = 2500
# words that name the kind of number, not the thing measured ("change in HbA1c from baseline" = "HbA1c")
NAME_FILLER = {"change", "changes", "in", "from", "baseline", "the", "of", "mean", "difference", "vs", "versus",
               "placebo", "a", "an", "and", "to", "at", "on", "with", "daily", "once", "mg", "dose"}


# ---------------------------------------------------------------- LLM inputs
def spec_text(spec: Spec) -> str:
    """The question as plain lines for the prompt (no corpus, no seed)."""
    def name(n: Any) -> str:
        extra = f" (other names: {', '.join(n.synonyms)})" if n.synonyms else ""
        return f"{n.label}{extra}" + (f" - {n.definition}" if n.definition else "")
    subjects = "; ".join(name(s) for s in spec.subjects) or "any treatment (the question names none)"
    lines = [f"question: {spec.question}", f"subjects: {subjects}"]
    if spec.comparator:
        lines.append(f"comparator: {name(spec.comparator)}")
    lines.append(f"measure: {name(spec.measure)}" if spec.measure.label else
                 "measure: any measure (the question names none)")
    if spec.fixed:
        lines.append("fixed by the question: " + "; ".join(f"{k.replace('_', ' ')} = {v}" for k, v in spec.fixed.items()))
    if spec.columns:
        lines.append("write a row for every value of: " + ", ".join(spec.columns))
    return "\n".join(lines)


def paper_context(text: str) -> str:
    """Title and abstract: everything before the first numbered section, capped."""
    m = re.search(r"^##\s+1[.\s]", text, re.M)
    return text[: m.start() if m else CONTEXT_CHARS][:CONTEXT_CHARS].strip()


# ---------------------------------------------------------------- code checks
def unit_iri(unit_text: str) -> str | None:
    u = (unit_text or "").strip()
    if not u:
        return None
    return norm.unit_of_word(u) or norm.unit_in(u) or norm.unit_in(f"({u})")


def _num_equal(a: norm.Value, b: norm.Value, signed: bool) -> bool:
    """Same printed number(s): same decimals and value (or absolute value when `signed` is False)."""
    if a.is_range != b.is_range or a.decimals != b.decimals:
        return False
    pa = [a.low, a.high] if a.is_range else [a.value]
    pb = [b.low, b.high] if b.is_range else [b.value]
    if signed:
        return pa == pb
    return sorted(abs(x) for x in pa if x is not None) == sorted(abs(x) for x in pb if x is not None)


def std_of(v: norm.Value) -> StdValue:
    return StdValue(value=str(v.value) if v.value is not None else "", unit=v.unit or "", decimals=v.decimals,
                    sign_basis=v.sign_basis, low=None if v.low is None else str(v.low),
                    high=None if v.high is None else str(v.high))


def value_of(std: StdValue) -> norm.Value:
    return norm.Value(value=Decimal(std.value) if std.value else None, unit=std.unit or None, decimals=std.decimals,
                      sign_basis=std.sign_basis, low=None if std.low is None else Decimal(std.low),
                      high=None if std.high is None else Decimal(std.high))


def check(draft: RowDraft, paper: str, text: str, index: anchor.Index, passage: Passage) -> Row:
    """One draft -> Row with std, quote offsets and quote_ok (code only)."""
    notes: list[str] = []
    unit = unit_iri(draft.unit)
    raw_v = norm.normalize_value(draft.raw, unit)
    row = Row(paper=paper, subject=draft.subject.strip(), comparator=(draft.comparator or None),
              measure=draft.measure.strip(), patient_group=draft.patient_group or None,
              patient_group_raw=draft.patient_group or None, dose=draft.dose or None,
              time_point=draft.time_point or None, statistic=draft.statistic or "mean difference vs comparator",
              raw=draft.raw, quote=draft.quote, unit_text=draft.unit or "")
    spans = anchor.spans(index, draft.quote)
    if len(spans) > 1:
        inside = [s for s in spans if passage.start <= s[0] and s[1] <= passage.end]
        pick = inside[0] if inside else spans[0]
        where = "inside the passage" if inside else "none inside the passage, first one used"
        notes.append(f"quote found {len(spans)} times; {where} (at {pick[0]})")
        spans = [pick]
    if raw_v is None:
        notes.append("raw holds no number")
        row.note = "; ".join(notes)
        return row
    if not spans:
        notes.append("quote not found in the paper")
        row.std = std_of(raw_v)
        row.note = "; ".join(notes)
        return row
    start, end = spans[0]
    row.quote_start, row.quote_end = start, end
    found = norm.find_values(text[start:end], unit)
    hit = next((f for f in found if _num_equal(f.value, raw_v, signed=True)), None) \
        or next((f for f in found if _num_equal(f.value, raw_v, signed=False)), None)
    if hit is None:
        notes.append(f"the quote does not hold the value {raw_v.raw!r}")
        row.std = std_of(raw_v)
        row.note = "; ".join(notes)
        return row
    v = hit.value
    if v.unit is None and unit:
        v = norm.Value(v.value, unit, v.decimals, v.sign_basis, v.low, v.high, v.raw)
    if v.sign_basis == "level" and re.search(r"\b(change|difference|reduction|increase)\b",
                                             f"{draft.statistic} {draft.measure}", re.I):
        v = norm.Value(v.value, v.unit, v.decimals, "change", v.low, v.high, v.raw)   # a difference of change
    row.std = std_of(v)
    same = norm.same(value_of(row.std), v) if v.unit else norm.Match(norm.Verdict.SAME, "no unit on either side")
    row.quote_ok = same.verdict == norm.Verdict.SAME
    if v.unit is None:
        notes.append("no unit stated")
    if raw_v.value is not None and v.value is not None and raw_v.value != v.value:
        notes.append(f"sign read from the quote: {v.value} (raw {draft.raw!r})")
    row.note = "; ".join(notes)
    return row


# ---------------------------------------------------------------- spec matching
def _words(text: str) -> set[str]:
    """Content words of a name; a name made only of filler ("placebo") keeps all its words."""
    words = set(re.findall(r"[a-z0-9]+", (text or "").lower()))
    return words - NAME_FILLER or words


def match_name(text: str | None, names: list[Any]) -> str | None:
    """The spec label `text` names (label or a synonym; word sets, one inside the other), else None."""
    got = _words(text or "")
    if not got:
        return None
    for n in names:
        for alias in [n.label, *n.synonyms]:
            want = _words(alias)
            if want and (want <= got or got <= want):
                return n.label
    return None


def to_spec(row: Row, spec: Spec) -> Row:
    """Write subject/comparator/measure (and a same patient group) in spec words; set `dropped` when off-spec.
    A spec with no subjects or an empty measure (list questions) accepts any subject or measure, as written."""
    subject = match_name(row.subject, spec.subjects) if spec.subjects else row.subject
    measure = match_name(row.measure, [spec.measure]) if spec.measure.label else row.measure
    if subject is None:
        row.dropped = f"subject {row.subject!r} is not a spec subject"
    elif measure is None:
        row.dropped = f"measure {row.measure!r} is not the spec measure"
    else:
        row.subject, row.measure = subject, measure
    if spec.comparator and row.comparator:
        comp = match_name(row.comparator, [spec.comparator])
        if comp is None and row.dropped is None:
            row.dropped = f"comparator {row.comparator!r} is not the spec comparator"
        row.comparator = comp or row.comparator
    elif spec.comparator and not row.comparator:
        row.comparator = spec.comparator.label
    fixed_group = next((v for k, v in spec.fixed.items() if canon.slot(k) == "patient_group"), None)
    if fixed_group and row.patient_group and canon.group(row.patient_group) == canon.group(fixed_group):
        row.patient_group = fixed_group
    return row


def named_in_paper(row: Row, spec: Spec, text: str, found_names: list[str] = ()) -> Row:
    """Drop a row whose spec subject the paper never names (by its label, a synonym, or another name Find's agent
    found for a subject, `found_names`, e.g. the code name 'MRB-613'): the model wrote the question's drug for
    another drug's value (a paper on drug X read for a question on drug Y)."""
    if row.dropped or not spec.subjects:
        return row
    name = next((n for n in spec.subjects if n.label == row.subject), None)
    if name is None:
        return row
    low = text.lower()
    if not any(re.search(rf"(?<![a-z0-9]){re.escape(a.lower())}(?![a-z0-9])", low)
               for a in (name.label, *name.synonyms, *found_names) if a.strip()):
        row.dropped = f"subject {row.subject!r} is not named in the paper"
    return row


# ---------------------------------------------------------------- merge
def key(row: Row) -> tuple[str, ...]:
    return (row.paper, row.subject.lower(), (row.comparator or "").lower(), row.measure.lower(),
            (row.settings or canon.value("patient_group", row.patient_group)), canon.value("dose", row.dose),
            canon.value("time_point", row.time_point))


def _same_value(a: Row, b: Row) -> bool:
    if a.std is None or b.std is None:
        return False
    va, vb = value_of(a.std), value_of(b.std)
    if (va.unit is None) != (vb.unit is None):
        return _num_equal(va, vb, signed=True)
    return norm.same(va, vb).verdict == norm.Verdict.SAME and norm.same(vb, va).verdict == norm.Verdict.SAME


def merge(rows: list[Row]) -> list[Row]:
    """One row per fact (table and text stating the same value merge); different values stay, noted as conflict."""
    out: list[Row] = []
    by_key: dict[tuple[str, ...], list[Row]] = {}
    for r in rows:
        if r.dropped or r.std is None:
            out.append(r)
            continue
        group = by_key.setdefault(key(r), [])
        twin = next((g for g in group if _same_value(g, r)), None)
        if twin is None:
            group.append(r)
            out.append(r)
            continue
        if r.quote_ok and not twin.quote_ok:          # keep the checked one in place of the unchecked twin
            r.also = [twin.quote, *twin.also]
            out[out.index(twin)] = r
            group[group.index(twin)] = r
        elif r.quote != twin.quote and r.quote not in twin.also:
            twin.also.append(r.quote)
    for group in by_key.values():
        ok = [g for g in group if g.quote_ok]
        if len(ok) > 1:
            for g in ok:
                others = ", ".join(o.std.value for o in ok if o is not g and o.std)
                g.note = "; ".join(x for x in [g.note, f"conflict: the same paper also gives {others}"] if x)
    return out


# ---------------------------------------------------------------- run
def read_passage(spec_lines: str, context: str, passage: Passage, lm: dspy.BaseLM) -> list[RowDraft]:
    """One LLM call (asked again with a new recorded attempt when the reply does not parse; after ATTEMPTS bad
    replies the passage is skipped). A failed model service raises: skipping would write a short rows.jsonl that a
    rerun takes as done."""
    for attempt in range(ATTEMPTS):
        try:
            with dspy.context(lm=lm, adapter=dspy.JSONAdapter()):
                out = dspy.Predict(ExtractRows)(question_spec=spec_lines, paper_context=context, passage=passage.text,
                                                config={"attempt": attempt})
            return [d if isinstance(d, RowDraft) else RowDraft.model_validate(d) for d in (out.rows or [])]
        except Exception as exc:   # noqa: BLE001 - a bad reply is logged and retried, then the passage is skipped
            if service_failed(exc):
                raise
            log.warning("extract: passage %s-%s attempt %d failed: %s", passage.start, passage.end, attempt, exc)
    return []


def run(spec: Spec, hits: list[FindHit], domain: str, cfg: RunConfig, lm: dspy.BaseLM | None = None,
        texts: dict[str, str] | None = None, audit: list[dict] | None = None) -> list[Row]:
    """Rows for the spec from the marked passages of `hits` (see module doc). `lm`/`texts` let tests pass a fake LM
    and hand-made papers; by default the step's LM from `cfg` and the domain's paper.md files. `audit` (optional)
    gets one record per paper: every setting-reading attempt (candidate sets, failed checks, verifier verdicts),
    the final setting sets, the extras kept, and which set each row got (run.py saves it as settings.jsonl)."""
    if lm is None:
        from evqa.lm import make_lm
        lm = make_lm(cfg.llm_for("extract"))
    texts = texts if texts is not None else corpus.papers(domain)
    spec_lines = spec_text(spec)
    jobs = [(h.paper, p) for h in hits if h.paper in texts and h.screen != "no" for p in h.passages]
    indexes = {paper: anchor.Index(texts[paper]) for paper in {j[0] for j in jobs}}
    found_names = {h.paper: [str(t) for t in h.details.get("agent", [])] for h in hits}   # Find's other names

    def one(job: tuple[str, Passage]) -> list[Row]:
        paper, passage = job
        drafts = read_passage(spec_lines, paper_context(texts[paper]), passage, lm)
        return [named_in_paper(to_spec(check(d, paper, texts[paper], indexes[paper], passage), spec), spec,
                               texts[paper], found_names.get(paper, [])) for d in drafts]

    with ThreadPoolExecutor(cap_for(cfg.llm_for("extract").backend)) as pool:   # the backend's call cap
        found = [r for rows in pool.map(one, jobs) for r in rows]
        papers = sorted({r.paper for r in found if not r.dropped})
        traces: dict[str, list[dict]] = {p: [] for p in papers}
        settings = dict(zip(papers, pool.map(lambda p: settings_v2.read(
            p, spec.dimensions, paper_context(texts[p]),
            "\n\n".join(passage.text for hit in hits if hit.paper == p for passage in hit.passages)[:12000],
            texts[p], lm, trace=traces[p]), papers), strict=True))
    if cfg.extract is not None and not cfg.extract.extras:   # ablation: no extra settings
        for sets in settings.values():
            for g in sets:
                g.settings = [x for x in g.settings if not x.extra]
    kept: dict[str, list[str]] = {}
    for paper in papers:
        kept[paper] = sorted(settings_v2.retain_extras([r for r in found if r.paper == paper], settings.get(paper, [])))
    for row in found:
        section = next((p.section for paper, p in jobs if paper == row.paper
                        and p.start <= row.quote_start < p.end), "")
        if not row.dropped:
            settings_v2.assign(row, settings.get(row.paper, []), section, lm)
    if audit is not None:
        for paper in papers:
            audit.append({"paper": paper, "attempts": traces[paper],
                          "final_sets": [g.model_dump() for g in settings.get(paper, [])],
                          "extras_kept": kept[paper],
                          "rows": [{"quote": r.quote, "quote_ok": r.quote_ok, "settings": r.settings,
                                    "note": r.note} for r in found if r.paper == paper and not r.dropped]})
    return merge(found)


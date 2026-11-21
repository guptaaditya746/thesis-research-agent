"""The invented world: entities and, per paper, the planted facts (claims + decoys, sometimes a planted conflict).

Format (same for every field):
  {"field", "genre",
   "entities": {id: {"kind", "label", "alt": [...], "attrs": {...}}},
   "papers": {pid: {"title_hint", "issue", "thesis", "claims": [[s, r, o]], "decoys": [[s, r, o]],
                    "conflict": [[s, r, o], [s, r, o]] (optional)}}}
A world comes from a file (hand-written) or from the world agent (draft), and is always checked by `check` in code.
The agent works in two calls: entities, then papers in batches; each gets one repair call with the errors. A batch
with fewer papers than asked gets up to 2 calls for the missing papers only, then stops with an error.
"""
from __future__ import annotations

import json
from typing import Any

from paperfactory.packs import Field, Genre
from paperfactory.text import alias_table, find_mentions

Fact = tuple[str, str, str]


def check(w: dict[str, Any], f: Field, g: Genre, n_papers: int | None = None) -> list[str]:
    """Every rule a world must keep. Returns a list of errors (empty = ok)."""
    err: list[str] = []
    ents = w.get("entities", {})
    labels: dict[str, str] = {}
    for eid, e in ents.items():
        if e.get("kind") not in f.kinds:
            err.append(f"{eid}: unknown kind {e.get('kind')!r}")
            continue
        for name in [e.get("label", "")] + e.get("alt", []):
            k = name.strip().lower()
            if not k:
                err.append(f"{eid}: empty name")
            elif k in labels and labels[k] != eid:
                err.append(f"name {name!r} used by {labels[k]} and {eid}")
            labels[k] = eid
        for a, typ in f.kinds[e["kind"]].get("attrs", {}).items():
            v = e.get("attrs", {}).get(a)
            if v is None:
                err.append(f"{eid}: missing attr {a}")
            elif typ == "int" and not isinstance(v, int):
                err.append(f"{eid}: attr {a} must be an integer")
            elif typ.startswith("ref:") and (v not in ents or ents[v].get("kind") != typ[4:]):
                err.append(f"{eid}: attr {a} must name a {typ[4:]}")
    # a name inside another entity's name (whole words): papers could not tell the two apart
    # (label and alt only: names the pack derives, e.g. a first party, are marked ambiguous at scoring instead)
    named = {eid: [e["label"]] + e.get("alt", []) for eid, e in ents.items() if e.get("kind") in f.kinds
             and e.get("label")}
    for eid in named:
        tab = alias_table({"entities": {eid: {**ents[eid], "kind": "-"}}}, f)
        for other, ons in named.items():
            for on in ons if other != eid else []:
                err += [f"name {m.surface!r} ({eid}) inside {on!r} ({other})" for m in find_mentions(on, tab)]
    papers = w.get("papers", {})
    if n_papers is not None and len(papers) != n_papers:
        err.append(f"{len(papers)} papers, need {n_papers}")
    want = {"claims": g.raw.get("claims_per_paper"), "decoys": g.raw.get("decoys_per_paper")}
    for pid, p in papers.items():
        for key in ("title_hint", "issue", "thesis"):
            if not str(p.get(key, "")).strip():
                err.append(f"{pid}: missing {key}")
        facts = [tuple(x) for x in p.get("claims", []) + p.get("decoys", [])]
        for role, n in want.items():
            if n is not None and len(p.get(role, [])) != n:
                err.append(f"{pid}: {len(p.get(role, []))} {role}, need {n}")
        if len(set(facts)) != len(facts):
            err.append(f"{pid}: the same fact twice")
        pairs = [(s, o) for s, _, o in facts]
        if len(set(pairs)) != len(pairs):
            err.append(f"{pid}: two relations between the same pair (contradicts itself)")
        for fact in facts:
            err += [f"{pid} {list(fact)}: {m}" for m in fact_errors(fact, ents, f)]
        c = p.get("conflict")
        if c:
            (s1, r1, o1), (s2, r2, o2) = c
            if [s1, r1, o1] not in p["claims"] + p["decoys"] or [s2, r2, o2] not in p["claims"] + p["decoys"]:
                err.append(f"{pid}: conflict facts must be planted facts of the paper")
            if o1 != o2 or s1 == s2 or ((r1, r2) not in f.conflict_pairs and (r2, r1) not in f.conflict_pairs):
                err.append(f"{pid}: conflict must be two subjects, one object, a conflict pair of relations")
    # the same pair must not get different relations in different papers (one world, one truth)
    seen: dict[tuple[str, str], str] = {}
    for pid, p in papers.items():
        for s, r, o in p.get("claims", []) + p.get("decoys", []):
            if seen.setdefault((s, o), r) != r:
                err.append(f"{s}->{o}: relation {seen[(s, o)]} in one paper, {r} in {pid}")
    return err


def fact_errors(fact: Fact, ents: dict[str, Any], f: Field) -> list[str]:
    s, r, o = fact
    if s not in ents or o not in ents:
        return ["unknown entity"]
    if r not in f.relations:
        return [f"unknown relation {r}"]
    out = []
    if ents[s]["kind"] not in f.subject_kinds:
        out.append(f"subject must be a {'/'.join(f.subject_kinds)}")
    if ents[o]["kind"] not in f.relations[r]["object_kinds"]:
        out.append(f"object of {r} must be a {'/'.join(f.relations[r]['object_kinds'])}")
    oa = f.order_attr
    if oa and ents[o]["kind"] in f.subject_kinds and s != o:
        if not ents[s].get("attrs", {}).get(oa, 0) > ents[o].get("attrs", {}).get(oa, 0):
            out.append(f"a {ents[s]['kind']} can only relate to an earlier one ({oa})")
    if s == o:
        out.append("subject and object are the same")
    return out


# ------------------------------------------------------------------ world agent
ENT_SYS = """You invent the entities of a fictional research world for a benchmark. Nothing may be real: invent
every name (people, parties, places, products, institutions), and do not reuse names of real cases, drugs, trials,
companies or laws. Real concepts (areas of law, diseases, properties, methods) are fine. Follow the field notes.
Return entities with ids (short, unique, upper-case letters and digits), kind, label (full name), alt (short names a
paper would use; each must be unique across all entities) and attrs (exactly the listed attributes)."""
PAPER_SYS = """You plan papers for a fictional research world. Each paper argues one thesis about the entities given.
For each paper give a title hint, the issue, the thesis, the claims (facts the paper is about) and the decoys
(other true facts of the same world it also states, near-misses of the claims: same entities, other relation, or
same relation, other entity). Facts are [subject id, relation, object id] using ONLY the given ids and relations,
and must respect each relation's allowed object kinds and the time order. A pair (subject, object) has ONE relation
in the whole world: reuse the relation if a pair already appears. When asked, add a conflict: two planted facts of
the paper, different subjects, the same object, relations from a conflict pair."""


def _schema_entities(f: Field) -> dict[str, Any]:
    attr_props = {}
    for k in f.kinds.values():
        for a, typ in k.get("attrs", {}).items():
            attr_props[a] = {"type": "integer"} if typ == "int" else {"type": "string"}
    return {"type": "object", "required": ["entities"], "properties": {"entities": {"type": "array", "items": {
        "type": "object", "required": ["id", "kind", "label", "alt", "attrs"], "properties": {
            "id": {"type": "string"}, "kind": {"type": "string", "enum": list(f.kinds)},
            "label": {"type": "string"}, "alt": {"type": "array", "items": {"type": "string"}},
            "attrs": {"type": "object", "properties": attr_props}}}}}}


FACT = {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3}
PAPERS_SCHEMA = {"type": "object", "required": ["papers"], "properties": {"papers": {"type": "array", "items": {
    "type": "object", "required": ["title_hint", "issue", "thesis", "claims", "decoys"], "properties": {
        "title_hint": {"type": "string"}, "issue": {"type": "string"}, "thesis": {"type": "string"},
        "claims": {"type": "array", "items": FACT}, "decoys": {"type": "array", "items": FACT},
        "conflict": {"type": "array", "items": FACT}}}}}}


def _pack_text(f: Field) -> str:
    return json.dumps({k: f.raw[k] for k in ("setting", "kinds", "relations", "conflict_pairs", "world_notes")
                       if k in f.raw}, indent=1)


def draft(s, f: Field, g: Genre, call) -> dict[str, Any]:
    """World agent: entities (1 call + 1 repair), then papers in batches of 5 (1 call + 1 repair each)."""
    n_subj = max(8, s.papers * 2)
    user = (f"FIELD PACK:\n{_pack_text(f)}\n\nMake about {n_subj} entities of kind "
            f"{'/'.join(f.subject_kinds)} and enough of the other kinds (see the notes). Random seed: {s.seed}.")
    sch = _schema_entities(f)
    got = _need(call("world", "world:entities", ENT_SYS, user, sch), "world:entities")
    w = {"field": f.name, "genre": g.name, "entities": _ents(got), "papers": {}}
    errs = check(w, f, g)
    if errs:
        got = _need(call("world", "world:entities:repair", ENT_SYS, user + "\n\nYOUR LAST ANSWER:\n" + json.dumps(got)
                         + "\n\nFIX THESE ERRORS:\n" + "\n".join(errs[:40]), sch), "world:entities:repair")
        w["entities"] = _ents(got)
        errs = check(w, f, g)
        if errs:
            raise ValueError("world entities failed the checks after one repair:\n" + "\n".join(errs[:40]))
    prefix = "".join(ch for ch in f.name.upper() if ch.isalpha())[:3]
    for b in range(0, s.papers, 5):
        n = min(5, s.papers - b)
        sofar = sorted({(x[0], x[1], x[2]) for p in w["papers"].values() for x in p["claims"] + p["decoys"]})
        user = (f"FIELD PACK:\n{_pack_text(f)}\n\nENTITIES:\n{json.dumps(w['entities'], indent=1)}\n\n"
                f"FACTS ALREADY USED (keep their relations):\n{json.dumps(sofar)}\n\n"
                f"Plan {n} papers. Each has exactly {g.raw['claims_per_paper']} claims and "
                f"{g.raw['decoys_per_paper']} decoys. Give a conflict in at least one of them. Spread the papers over "
                f"different entities and issues.")
        step = f"world:papers:{b}"
        got = _top_up(_need(call("world", step, PAPER_SYS, user, PAPERS_SCHEMA), step), n, user, call, step)
        for attempt in range(2):
            trial = dict(w, papers=dict(w["papers"]))
            for i, p in enumerate(got["papers"][:n]):
                trial["papers"][f"{prefix}-{b + i + 1:02d}"] = {k: v for k, v in p.items() if v or k != "conflict"}
            errs = check(trial, f, g, n_papers=b + n)
            if not errs:
                w = trial
                break
            if attempt:
                raise ValueError(f"papers {b + 1}-{b + n} failed the checks after one repair:\n" + "\n".join(errs[:40]))
            rstep = f"{step}:repair"
            got = _top_up(_need(call("world", rstep, PAPER_SYS, user + "\n\nYOUR LAST ANSWER:\n" + json.dumps(got)
                                     + "\n\nFIX THESE ERRORS:\n" + "\n".join(errs[:40]), PAPERS_SCHEMA), rstep),
                          n, user, call, rstep)
    return w


def _top_up(got: dict[str, Any], n: int, user: str, call, step: str, tries: int = 2) -> dict[str, Any]:
    """The model may plan fewer papers than asked: ask only for the missing ones (up to `tries` more calls), then
    stop with a clear error."""
    for t in range(tries):
        missing = n - len(got["papers"])
        if missing <= 0:
            break
        more = _need(call("world", f"{step}:more:{t + 1}", PAPER_SYS, user + "\n\nPAPERS ALREADY PLANNED:\n"
                          + json.dumps(got["papers"]) + f"\n\nPlan only {missing} more papers, different from these.",
                          PAPERS_SCHEMA), f"{step}:more:{t + 1}")
        got = {"papers": got["papers"] + more["papers"][:missing]}
    if len(got["papers"]) < n:
        raise ValueError(f"{step}: the world model planned {len(got['papers'])} of {n} papers after {tries} "
                         "requests for the missing ones")
    return got


def _need(got: dict[str, Any] | None, step: str) -> dict[str, Any]:
    """The world agent cannot go on without an answer: stop with a clear error (calls.jsonl has the reasons)."""
    if got is None:
        raise ValueError(f"{step}: the world model gave no answer in the required form (parse_error, see calls.jsonl)")
    return got


def _ents(got: dict[str, Any]) -> dict[str, Any]:
    return {e["id"]: {k: e[k] for k in ("kind", "label", "alt", "attrs")} for e in got["entities"]}

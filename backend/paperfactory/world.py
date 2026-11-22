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

import copy
import json
import random
import re
from typing import Any

from paperfactory import names, quant, topics
from paperfactory.packs import Field, Genre
from paperfactory.text import alias_table, find_mentions, name_variants, norm

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
            if v is None and typ.endswith("?"):      # optional ("text?", 22 Nov 2026)
                continue
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
    err += name_errors(ents, f)
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
        by_pair: dict[tuple[str, str], list[str]] = {}
        for s, r, o in facts:
            by_pair.setdefault((s, o), []).append(r)
        err += [f"{pid}: two relations between the same pair {s}->{o} ({', '.join(rs)}): keep one; a decoy must use "
                "the same relation as a claim with one entity different" for (s, o), rs in by_pair.items()
                if len(rs) > 1 and len(set(rs)) > 1]
        for fact in facts:
            err += [f"{pid} {list(fact)}: {m}" for m in fact_errors(fact, ents, f)]
        c = p.get("conflict")
        if c and (len(c) != 2 or any(not isinstance(x, list) or len(x) != 3 for x in c)):
            err.append(f"{pid}: a conflict is exactly two facts [subject, relation, object]")
        elif c:
            (s1, r1, o1), (s2, r2, o2) = c
            if [s1, r1, o1] not in p["claims"] + p["decoys"] or [s2, r2, o2] not in p["claims"] + p["decoys"]:
                err.append(f"{pid}: conflict facts must be planted facts of the paper")
            if o1 != o2 or s1 == s2 or ((r1, r2) not in f.conflict_pairs and (r2, r1) not in f.conflict_pairs):
                err.append(f"{pid}: conflict must be two subjects, one object, a conflict pair of relations")
    # no paper twice (review finding 9: a paper the agent adds to fill a short batch may repeat an earlier one)
    first: dict[tuple[str, str], str] = {}
    for pid, p in papers.items():
        claims = json.dumps(sorted(map(list, p.get("claims", []))))
        for what, v in (("claims", claims), ("title", norm(str(p.get("title_hint", ""))).strip()),
                        ("thesis", norm(str(p.get("thesis", ""))).strip())):
            if v and v != "[]" and (other := first.setdefault((what, v), pid)) != pid:
                err.append(f"{pid}: same {what} as {other} (a paper planned twice)")
    if "numbers" in w:
        err += quant.errors(w, f)
    # the same pair must not get different relations in different papers (one world, one truth)
    seen: dict[tuple[str, str], str] = {}
    for pid, p in papers.items():
        for s, r, o in p.get("claims", []) + p.get("decoys", []):
            if seen.setdefault((s, o), r) != r:
                err.append(f"{s}->{o}: relation {seen[(s, o)]} in one paper, {r} in {pid}")
    return err


def _k(name: str) -> str:
    return norm(name).strip()


def name_errors(ents: dict[str, Any], f: Field) -> list[str]:
    """D4: no name may match the pack's list of real names (whole words, any case).
    D5: a label or short name of one entity must not equal a name the pack derives for another entity (e.g. the
    first party of a decision title): papers would use it for both."""
    err: list[str] = []
    ok = {eid: e for eid, e in ents.items() if e.get("kind") in f.kinds and e.get("label")}
    own = {eid: [e["label"]] + e.get("alt", []) for eid, e in ok.items()}
    derived = {eid: name_variants(f, e["kind"], e["label"]) for eid, e in ok.items()}
    real = [(r, re.compile(rf"(?<!\w){re.escape(_k(r))}(?!\w)")) for r in f.raw.get("real_names", [])]
    for eid, ns in own.items():
        for n in ns + derived[eid]:
            err += [f"{eid}: name {n!r} contains the real name {r!r}" for r, rx in real if rx.search(_k(n))]
    by_derived: dict[str, set[str]] = {}
    for eid, ns in derived.items():
        for n in ns:
            by_derived.setdefault(_k(n), set()).add(eid)
    for eid, ns in own.items():
        for n in ns:
            err += [f"name {n!r} ({eid}) is also a derived name of {other}" for other in
                    sorted(by_derived.get(_k(n), set()) - {eid})]
    return sorted(set(err))


def decoy_warnings(w: dict[str, Any], f: Field) -> list[str]:
    """D4: a decoy should be a near miss of one of its paper's claims: the same relation, the same kinds, exactly one
    entity different (the time order is already a rule for every fact, fact_errors). Warnings, not errors: the law
    pilot has decoys that only share an entity with a claim."""
    ents, out = w.get("entities", {}), []
    kind = lambda e: ents.get(e, {}).get("kind")  # noqa: E731
    for pid, p in w.get("papers", {}).items():
        for d in p.get("decoys", []):
            near = [c for c in p.get("claims", []) if c[1] == d[1] and (c[0] == d[0]) != (c[2] == d[2])
                    and kind(c[0]) == kind(d[0]) and kind(c[2]) == kind(d[2])]
            if not near:
                out.append(f"{pid} decoy {d}: not a near miss of any claim (same relation and kinds, one entity "
                           "different)")
    return out


def shape(w: dict[str, Any], f: Field, g: Genre, pages: int) -> dict[str, Any]:
    """D4: what each paper will contain (facts, decoys, conflict, plan, sections, length)."""
    lo, hi = g.raw["words_per_page"]
    sections = sum(1 for line in (g.folder / "template.md").read_text(encoding="utf-8").splitlines()
                   if line.startswith("#"))
    return {"papers": len(w.get("papers", {})), "entities": len(w.get("entities", {})),
            "per_paper": {pid: {"claims": len(p.get("claims", [])), "decoys": len(p.get("decoys", [])),
                                "facts": len(p.get("claims", [])) + len(p.get("decoys", [])),
                                "conflict": bool(p.get("conflict")),
                                "relations": sorted({x[1] for x in p.get("claims", []) + p.get("decoys", [])}),
                                "plan_points": len(g.raw.get("argument_plan", [])), "template_sections": sections,
                                "words": [pages * lo, pages * hi]}
                          for pid, p in w.get("papers", {}).items()}}


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
# v1 (until 22 Nov 2026): the model wrote label and alt; at 20 papers Qwen reused names ("Mora" / "Mora App") and
# law and llm failed the entity checks after the repair, twice each. Now code writes every name (names.py).
ENT_SYS_V1 = """You invent the entities of a fictional research world for a benchmark. Nothing may be real: invent
every name (people, parties, places, products, institutions), and do not reuse names of real cases, drugs, trials,
companies or laws. Real concepts (areas of law, diseases, properties, methods) are fine. Follow the field notes.
Return entities with ids (short, unique, upper-case letters and digits), kind, label (full name), alt (short names a
paper would use; each must be unique across all entities) and attrs (exactly the listed attributes)."""
ENT_SYS = """You plan the entities of a fictional research world for a benchmark. Follow the field notes.
For each entity return:
- id: short and unique, upper-case letters and digits (e.g. A2, K7)
- kind: one of the given kinds
- name_parts: exactly the name parts listed for its kind, in plain common words or numbers ({} when it lists none)
- attrs: exactly the attributes listed for its kind
Code adds every invented proper name afterwards. Never write an invented person, party, place, company, product or
title anywhere, in name_parts or in attrs. Real concepts (diseases, properties, areas of study) are fine.
Each kind in the field pack has an example entity: follow its form.
Wrong: a name part such as "Brindle prompting" or an attribute such as "Mora sued DataFlow": both contain
invented proper names, which code adds."""
# v1 (until 22 Nov 2026): allowed a decoy with "same entities, other relation", which world.check rejects (one pair,
# one relation); in the Qwen smoke runs medicine and materials failed on exactly that, twice each
PAPER_SYS_V1 = """You plan papers for a fictional research world. Each paper argues one thesis about the entities given.
For each paper give a title hint, the issue, the thesis, the claims (facts the paper is about) and the decoys
(other true facts of the same world it also states, near-misses of the claims: same entities, other relation, or
same relation, other entity). Facts are [subject id, relation, object id] using ONLY the given ids and relations,
and must respect each relation's allowed object kinds and the time order. A pair (subject, object) has ONE relation
in the whole world: reuse the relation if a pair already appears. When asked, add a conflict: two planted facts of
the paper, different subjects, the same object, relations from a conflict pair."""
# v2 (until 22 Nov 2026): no FOCUS; at 20 papers Qwen copied the claims of earlier papers into later batches
# (law: 5 of 20 papers dropped as "a paper planned twice"). Now code gives each paper its own focus subjects.
PAPER_SYS_V2 = """You plan papers for a fictional research world. Each paper argues one thesis about the entities given.
For each paper give a title hint, the issue, the thesis, the claims (facts the paper is about) and the decoys (other
true facts of the same world that the paper also states).
Facts are [subject id, relation, object id], using ONLY the given ids and relations; each must respect the
relation's allowed object kinds and the time order (a subject relates only to an earlier one).
Rules:
1. One pair, one relation: a pair (subject, object) gets ONE relation in the whole world. Within a paper, every fact
   has a different pair. If a pair is in FACTS ALREADY USED, reuse its relation or do not use the pair.
2. A decoy is a near miss of a claim: the SAME relation and exactly ONE entity different (another subject of the same
   kind, or another object of the same kind). Never the same two entities with another relation (that breaks rule 1).
3. When asked, add a conflict: two CLAIMS of the paper (not decoys) with different subjects, the SAME object, and
   the two relations of a conflict pair.
Example (ids only): claim [A1, r1, B1] -> decoy [A2, r1, B1] or [A1, r1, B2]; never [A1, r2, B1].
Conflict: [A1, r1, B1] and [A3, r2, B1] where (r1, r2) is a conflict pair."""
PAPER_SYS = """You plan papers for a fictional research world. Each paper argues one thesis about the entities given.
For each paper give a title hint, the issue, the thesis, the claims (facts the paper is about) and the decoys (other
true facts of the same world that the paper also states).
Facts are [subject id, relation, object id], using ONLY the given ids and relations; each must respect the
relation's allowed object kinds and the time order (a subject relates only to an earlier one).
Rules:
1. One pair, one relation: a pair (subject, object) gets ONE relation in the whole world. Within a paper, every fact
   has a different pair. If a pair is in FACTS ALREADY USED, reuse its relation or do not use the pair.
2. A decoy is a near miss of a claim: the SAME relation and exactly ONE entity different (another subject of the same
   kind, or another object of the same kind). Never the same two entities with another relation (that breaks rule 1).
3. When asked, add a conflict: two CLAIMS of the paper (not decoys) with different subjects, the SAME object, and
   the two relations of a conflict pair.
Example (ids only): claim [A1, r1, B1] -> decoy [A2, r1, B1] or [A1, r1, B2]; never [A1, r2, B1].
Conflict: [A1, r1, B1] and [A3, r2, B1] where (r1, r2) is a conflict pair.
4. Each paper has its FOCUS subjects, given in PAPERS TO PLAN: every claim's subject is one of the paper's FOCUS
   subjects, and each FOCUS subject is the subject of at least one claim. Decoys may use other subjects. Return the
   papers in the order of PAPERS TO PLAN.
Example: FOCUS [A1, A3] -> claims [A1, r1, B1], [A3, r2, B1], [A3, r1, B2]; never a claim with subject A2."""


def _schema_entities(f: Field, kind: str) -> dict[str, Any]:
    """One kind only (one entity call per kind)."""
    attr_props = {a: {"type": "integer"} if typ == "int" else {"type": "string"}
                  for a, typ in f.kinds[kind].get("attrs", {}).items()}
    part_props = {p: {"type": "string"} for p in names.parts_of(f, kind)}
    return {"type": "object", "required": ["entities"], "properties": {"entities": {"type": "array", "items": {
        "type": "object", "required": ["id", "kind", "name_parts", "attrs"], "properties": {
            "id": {"type": "string"}, "kind": {"type": "string", "enum": [kind]},
            "name_parts": {"type": "object", "properties": part_props},
            "attrs": {"type": "object", "properties": attr_props}}}}}}


FACT = {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3}
PAPERS_SCHEMA = {"type": "object", "required": ["papers"], "properties": {"papers": {"type": "array", "items": {
    "type": "object", "required": ["title_hint", "issue", "thesis", "claims", "decoys"], "properties": {
        "title_hint": {"type": "string"}, "issue": {"type": "string"}, "thesis": {"type": "string"},
        "claims": {"type": "array", "items": FACT}, "decoys": {"type": "array", "items": FACT},
        "conflict": {"type": "array", "items": FACT, "minItems": 2, "maxItems": 2}}}}}}


def _pack_text(f: Field) -> str:
    """The pack as the world agent sees it ("confusable_with" is for reviewers and checks, not for this prompt; of a
    kind's name pattern only the parts the model gives)."""
    rels = {r: {k: v for k, v in d.items() if k != "confusable_with"} for r, d in f.relations.items()}
    kinds = {k: {"about": d.get("about", ""), "attrs": d.get("attrs", {}), "name_parts": names.parts_of(f, k),
                 "example": d.get("name", {}).get("example", {})} for k, d in f.kinds.items()}
    pick = {"relations": rels, "kinds": kinds}
    return json.dumps({k: pick.get(k, f.raw.get(k)) for k in ("setting", "kinds", "relations", "conflict_pairs",
                                                              "world_notes") if k in f.raw}, indent=1)


PAPER_REPAIRS = 2      # repair calls per batch of papers (each gets the errors of the last answer)
REFILL = 10            # papers planned beyond the target to replace dropped ones (fresh focus pairs)


def count_errors(ents: dict[str, Any], f: Field, n_subj: int) -> list[str]:
    """Enough entities of each kind: at least 3/4 of the asked subjects and 2 of every other kind. Why: the medicine 40
    entity answer (22 Nov 2026) had 100 entities, all of kind treatment and no trial; every paper then failed."""
    have: dict[str, int] = {}
    for e in ents.values():
        have[e.get("kind")] = have.get(e.get("kind"), 0) + 1
    need = {k: max(2, n_subj * 3 // 4) if k in f.subject_kinds else 2 for k in f.kinds}
    return [f"{have.get(k, 0)} entities of kind {k}: make at least {n} (about {n_subj} asked)" if k in f.subject_kinds
            else f"{have.get(k, 0)} entities of kind {k}: make at least {n}" for k, n in need.items()
            if have.get(k, 0) < n]


def kind_order(f: Field) -> list[str]:
    """Other kinds first (subjects refer to them in their attributes), subject kinds last."""
    return [k for k in f.kinds if k not in f.subject_kinds] + [k for k in f.kinds if k in f.subject_kinds]


def id_prefix(f: Field, kind: str) -> str:
    """A short id prefix per kind, different for every kind of the pack (court C, model MO, trial TR...)."""
    used: dict[str, str] = {}
    for k in f.kinds:
        n = 1
        while k[:n].upper() in used.values() and n < len(k):
            n += 1
        used[k] = k[:n].upper()
    return used[kind]


def _entities_of_kind(s, f: Field, g: Genre, call, so_far: dict[str, Any], kind: str, n_subj: int,
                      namer: names.Namer, cluster: dict[str, Any] | None = None,
                      others: dict[str, Any] | None = None) -> dict[str, Any]:
    """One entity call per kind (1 call + 1 repair). Why: the medicine 40 entity call for all kinds at once
    (22 Nov 2026) returned the treatment example 100 times and no trial, twice (call and repair)."""
    """cluster: {"id": letter, "topic": {...}} -> the entities belong to that cluster's topic and their ids start
    with its letter; others: entities of other clusters (checked for name clashes, not shown to the model)."""
    ask = (f"Make about {n_subj} entities of kind {kind}" if kind in f.subject_kinds
           else f"Make the entities of kind {kind} that the field notes ask for (at least 2)")
    pre = (cluster["id"] if cluster else "") + id_prefix(f, kind)
    user = (f"FIELD PACK:\n{_pack_text(f)}\n\nENTITIES ALREADY MADE (refer to their ids in attributes):\n"
            f"{json.dumps({k: {'kind': e['kind'], 'attrs': e['attrs']} for k, e in so_far.items()})}\n\n"
            f"{cluster_text(f, cluster)}{ask}. Every entity has kind {kind}; ids start with {pre} and are not used "
            f"above. Random seed: {s.seed}.")
    sch, step = _schema_entities(f, kind), f"world:entities:{kind}" + (f":{cluster['id']}" if cluster else "")

    def judge(got: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        ids = [e.get("id", "") for e in got["entities"]]
        new, errs = names.assign(got["entities"], f, s.seed, namer)
        errs += [f"id {i} used twice" for i in sorted({i for i in ids if ids.count(i) > 1})]
        errs += [f"id {i} is already used by an entity above" for i in ids if i in so_far]
        errs += [f"{i}: kind must be {kind}" for i, e in new.items() if e["kind"] != kind]
        errs += [e for e in count_errors(new, f, n_subj) if f" kind {kind}:" in e]
        if cluster:     # ids of different clusters must never clash
            errs += [f"id {i} must start with {pre}" for i in ids if not i.startswith(pre)]
        errs += check({"entities": (others or {}) | so_far | new, "papers": {}}, f, g)
        return new, errs
    got = _need(call("world", step, ENT_SYS, user, sch), step)
    new, errs = judge(got)
    if errs:
        got = _need(call("world", f"{step}:repair", ENT_SYS, user + "\n\nYOUR LAST ANSWER:\n" + json.dumps(got)
                         + "\n\nFIX THESE ERRORS:\n" + "\n".join(errs[:40]), sch, cache=False), f"{step}:repair")
        new, errs = judge(got)
        if errs:
            raise ValueError(f"world entities of kind {kind} failed the checks after one repair:\n"
                             + "\n".join(errs[:40]))
    return new


def cluster_text(f: Field, cluster: dict[str, Any] | None) -> str:
    if not cluster:
        return ""
    t = cluster["topic"]
    kw = f" Keywords: {', '.join(t['keywords'])}." if t.get("keywords") else ""
    return (f"CLUSTER TOPIC ({cluster['id']}): {t['name']} ({t['subfield']}). {t.get('description', '')}{kw}\n"
            f"{f.raw.get('cluster_note', '')}\n\n")


def plan_focus(w: dict[str, Any], f: Field, seed: Any, n: int, among: list[str] | None = None) -> list[list[str]]:
    """Two focus subjects per paper, chosen in code so no two papers lead with the same pair (at 20 papers Qwen
    copied earlier papers' claims). Every subject leads one paper before any leads a second; pairs never repeat.
    among: the entity ids to choose from (one cluster's); default all."""
    subj = sorted(eid for eid, e in w["entities"].items() if e.get("kind") in f.subject_kinds
                  and (among is None or eid in among))
    if len(subj) < 2:
        return [subj] * n
    tag = f":{among[0][:1]}" if among else ""
    rng, out, used, pool = random.Random(f"{seed}:focus:{f.name}{tag}"), [], set(), []
    while len(out) < n:
        if len(pool) < 2:
            pool = subj[:]
            rng.shuffle(pool)
        a, b = pool.pop(), pool.pop()
        if frozenset((a, b)) in used and len(used) < len(subj) * (len(subj) - 1) // 2:
            pool.insert(0, b)
            continue
        used.add(frozenset((a, b)))
        out.append(sorted((a, b)))
    return out


def fix_decoys(p: dict[str, Any], truth: dict[tuple[str, str], str], ents: dict[str, Any], f: Field,
               rng: Any) -> list[str]:
    """Replace each decoy that breaks a rule with a near miss made in code: a claim's relation with exactly one
    entity swapped for another of the same kind. Kept decoys and new ones respect the time order, one relation per
    pair in the paper, and the relations the world already has (`truth`). Why: in the llm 40 world (22 Nov 2026)
    Qwen made decoys by flipping a claim's relation ([S42, reports_drop, M6] next to the claim [S42, reports_gain,
    M6]): 29 such errors across the 28 dropped papers, despite the prompt's rule 2. Returns notes for the world file."""
    claims = [tuple(c) for c in p.get("claims", []) if isinstance(c, list) and len(c) == 3]
    pairs = {(s, o) for s, _, o in claims}
    kept, notes = [], []

    def ok(d: tuple[str, str, str]) -> bool:
        s, r, o = d
        return (not fact_errors(d, ents, f) and (s, o) not in pairs and truth.get((s, o), r) == r
                and d not in claims and d not in kept)
    bad = []
    for d in map(tuple, p.get("decoys", [])):
        if len(d) == 3 and ok(d):
            kept.append(d)
            pairs.add((d[0], d[2]))
        else:
            bad.append(d)
    for d in bad:
        cands = []
        for s, r, o in claims:
            cands += [(x, r, o) for x, e in ents.items() if x != s and e.get("kind") == ents.get(s, {}).get("kind")]
            cands += [(s, r, x) for x, e in ents.items() if x != o and e.get("kind") == ents.get(o, {}).get("kind")]
        cands = [c for c in cands if ok(c)]
        if not cands:
            kept.append(d)
            continue
        # prefer pairs the world already has with that relation (fewer new facts), then any
        known = [c for c in cands if (c[0], c[2]) in truth]
        new = rng.choice(sorted(known or cands))
        kept.append(new)
        pairs.add((new[0], new[2]))
        notes.append(f"decoy {list(d)} -> {list(new)}")
    p["decoys"] = [list(d) for d in kept]
    return notes


def conflict_errors(p: dict[str, Any], f: Field) -> list[str]:
    """The conflict rules of check() for one paper."""
    c = p.get("conflict")
    if not c:
        return []
    if len(c) != 2 or any(not isinstance(x, list) or len(x) != 3 for x in c):
        return ["a conflict is exactly two facts"]
    (s1, r1, o1), (s2, r2, o2) = c
    err = []
    if [s1, r1, o1] not in p.get("claims", []) + p.get("decoys", []) or \
            [s2, r2, o2] not in p.get("claims", []) + p.get("decoys", []):
        err.append("conflict facts must be planted facts of the paper")
    if o1 != o2 or s1 == s2 or ((r1, r2) not in f.conflict_pairs and (r2, r1) not in f.conflict_pairs):
        err.append("conflict must be two subjects, one object, a conflict pair of relations")
    return err


def focus_errors(papers: dict[str, Any]) -> list[str]:
    err = []
    for pid, p in papers.items():
        fo = p.get("focus")
        if not fo:
            continue
        subs = [c[0] for c in p.get("claims", []) if isinstance(c, list) and c]
        err += [f"{pid}: claim subject {s} is not one of its FOCUS {fo}" for s in dict.fromkeys(subs) if s not in fo]
        err += [f"{pid}: FOCUS subject {x} is the subject of no claim" for x in fo if x not in subs]
    return err


def split(n: int, k: int) -> list[int]:
    """n papers over k clusters, as even as possible (the first clusters get the extra ones)."""
    return [n // k + (1 if i < n % k else 0) for i in range(k)]


def draft(s, f: Field, g: Genre, call) -> dict[str, Any]:
    """World agent. With a topic list in the pack (packs/topics/<field>.json): `s.clusters` clusters, each with its own
    real topic, its own entities (1 call + 1 repair per kind) and its own papers; kinds in the pack's "shared_kinds"
    (e.g. courts) are made once for all clusters. Without one: one cluster, as before (22 Nov 2026).
    Papers are planned in batches of 5 (1 call + PAPER_REPAIRS repairs); dropped papers are refilled."""
    w = {"field": f.name, "genre": g.name, "entities": {}, "papers": {}}
    namer = names.Namer(s.seed, f)
    k = getattr(s, "clusters", 0)
    if f.raw.get("topics") and k > 0:
        clusters = [{"id": chr(65 + i), "topic": t} for i, t in enumerate(topics.pick(f, s.seed, k))]
        w["clusters"] = clusters
    else:
        clusters = [None]
    shared = [x for x in kind_order(f) if x in f.raw.get("shared_kinds", [])]
    for kind in shared:
        w["entities"] |= _entities_of_kind(s, f, g, call, w["entities"], kind, max(8, s.papers * 2), namer)
    prefix = "".join(ch for ch in f.name.upper() if ch.isalpha())[:3]
    counter = [0]
    for cl, n_c in zip(clusters, split(s.papers, len(clusters))):
        n_subj = max(8, s.papers * 2) if cl is None else max(6, n_c * 2)
        own: dict[str, Any] = {}
        base = {e: x for e, x in w["entities"].items() if x["kind"] in shared}
        for kind in [x for x in kind_order(f) if x not in shared]:
            others = {e: x for e, x in w["entities"].items() if e not in base}
            own |= _entities_of_kind(s, f, g, call, base | own, kind, n_subj, namer, cl, others)
        w["entities"] |= own
        if n_c:
            w = _plan_papers(s, f, g, call, w, base | own, n_c, cl, prefix, counter)
    if not w["papers"]:
        raise ValueError("no paper passed the checks: " + json.dumps(w.get("dropped_papers", {}))[:2000])
    if len(w["papers"]) < s.papers:
        print(f"world: {len(w['papers'])} of {s.papers} papers after the refill papers")
    return w


def _plan_papers(s, f: Field, g: Genre, call, w: dict[str, Any], ents: dict[str, Any], target: int,
                 cl: dict[str, Any] | None, prefix: str, counter: list[int]) -> dict[str, Any]:
    """The papers of one cluster: `target` papers about `ents` (its entities + shared ones), refilled with up to
    REFILL papers (in proportion to the cluster's share) when some fail the checks. counter[0]: papers numbered so
    far in the world (ids continue across clusters)."""
    refill = max(2, round(REFILL * target / max(1, s.papers))) if cl else REFILL
    focus = plan_focus(w, f, s.seed, target + refill, sorted(ents) if cl else None)
    have0 = len(w["papers"])
    ctext = cluster_text(f, cl)
    b = 0
    while len(w["papers"]) - have0 < target and b < target + refill:
        # first the target's batches, then refill batches for the papers dropped so far
        n = (min(5, target - b) if b < target
             else min(5, target - (len(w["papers"]) - have0), target + refill - b))
        want = focus[b:b + n]
        sofar = sorted({(x[0], x[1], x[2]) for p in w["papers"].values() for x in p["claims"] + p["decoys"]})
        # FIXED: the facts the world already has for this paper's focus subjects (medicine 20-paper test, 22 Nov:
        # 7 of 10 drops gave a focus pair a second relation; the long FACTS ALREADY USED list was missed)
        fixed = lambda fo: [list(x) for x in sofar if x[0] in fo or x[2] in fo]  # noqa: E731
        todo = "\n".join(f"{i + 1}. FOCUS {json.dumps(x)}" + (f"; FIXED {json.dumps(fixed(x))}" if fixed(x) else "")
                         for i, x in enumerate(want))
        user = (f"FIELD PACK:\n{_pack_text(f)}\n\n{ctext}ENTITIES:\n{json.dumps(ents, indent=1)}\n\n"
                f"FACTS ALREADY USED (keep their relations):\n{json.dumps(sofar)}\n\n"
                f"PAPERS TO PLAN, in this order:\n{todo}\n"
                "FIXED lists facts the world already has for a paper's FOCUS subjects: a pair in FIXED keeps exactly "
                "that relation (or is not used).\n\n"
                f"Plan {n} papers. Each has exactly {g.raw['claims_per_paper']} claims and "
                f"{g.raw['decoys_per_paper']} decoys. "
                + ("Give a conflict in at least one of them." if n > 1 else "Give a conflict if two claims allow it."))
        step = f"world:papers:{cl['id'] if cl else ''}{b}"
        got = _top_up(_need(call("world", step, PAPER_SYS, user, PAPERS_SCHEMA), step), n, user, call, step)
        for attempt in range(1 + PAPER_REPAIRS):
            trial = dict(w, papers=dict(w["papers"]), decoy_repairs=dict(w.get("decoy_repairs", {})))
            rng = random.Random(f"{s.seed}:decoys:{f.name}:{cl['id'] if cl else ''}{b}:{attempt}")
            for i, p in enumerate(got["papers"][:n]):
                pid = f"{prefix}-{counter[0] + i + 1:02d}"
                q = {k: v for k, v in copy.deepcopy(p).items() if v or k != "conflict"} | {"focus": want[i]}
                if cl:
                    q["cluster"] = cl["id"]
                truth = {(x[0], x[2]): x[1] for pp in trial["papers"].values() for x in pp["claims"] + pp["decoys"]
                         if isinstance(x, list) and len(x) == 3}
                for x in q.get("claims", []):
                    if isinstance(x, list) and len(x) == 3:
                        truth.setdefault((x[0], x[2]), x[1])
                if notes := fix_decoys(q, truth, ents, f, rng):
                    trial["decoy_repairs"][pid] = notes
                if q.get("conflict") and conflict_errors(q, f):
                    # an optional extra: a wrong conflict goes, the paper stays (v2 pilot, 22 Nov 2026: with one paper
                    # per batch every law paper had to carry a conflict, and 6 of 9 were dropped for a wrong one)
                    trial.setdefault("conflicts_dropped", {})[pid] = q.pop("conflict")
                trial["papers"][pid] = q
            errs = check(trial, f, g, n_papers=len(trial["papers"])) + focus_errors(trial["papers"])
            if not errs:
                w = trial
                break
            if attempt == PAPER_REPAIRS:
                # keep the papers of this batch that pass on their own; drop the rest (recorded), never the field
                new = [pid for pid in trial["papers"] if pid not in w["papers"]]
                bad = {pid for pid in new if any(re.search(rf"(?<![\w-]){re.escape(pid)}(?![\w-])", e) for e in errs)}
                kept = dict(w, papers={k: v for k, v in trial["papers"].items() if k not in bad})
                still = check(kept, f, g, n_papers=len(kept["papers"]))
                if still:
                    raise ValueError(f"papers {b + 1}-{b + n} failed the checks after {PAPER_REPAIRS} repairs:\n"
                                     + "\n".join(errs[:40]))
                kept["dropped_papers"] = dict(w.get("dropped_papers", {})) | {
                    pid: [e for e in errs if pid in e][:10] for pid in sorted(bad)}
                print(f"world: dropped {sorted(bad)} (failed the checks after {PAPER_REPAIRS} repairs), kept "
                      f"{len(kept['papers']) - len(w['papers'])} of {n}")
                w = kept
                break
            rstep = f"{step}:repair" + (f":{attempt + 1}" if attempt else "")
            got = _top_up(_need(call("world", rstep, PAPER_SYS, user + "\n\nYOUR LAST ANSWER:\n" + json.dumps(got)
                                     + "\n\nFIX THESE ERRORS:\n" + "\n".join(errs[:40]), PAPERS_SCHEMA,
                                     cache=False), rstep),
                          n, user, call, rstep)
        b += n
        counter[0] += n
    return w


def _top_up(got: dict[str, Any], n: int, user: str, call, step: str, tries: int = 2) -> dict[str, Any]:
    """The model may plan fewer papers than asked: ask only for the missing ones (up to `tries` more calls), then
    stop with a clear error."""
    for t in range(tries):
        missing = n - len(got["papers"])
        if missing <= 0:
            break
        more = _need(call("world", f"{step}:more:{t + 1}", PAPER_SYS, user + "\n\nPAPERS ALREADY PLANNED:\n"
                          + json.dumps(got["papers"]) + f"\n\nPlan only papers {len(got['papers']) + 1}-{n} of PAPERS "
                          "TO PLAN, different from these.",
                          PAPERS_SCHEMA, cache=False), f"{step}:more:{t + 1}")
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



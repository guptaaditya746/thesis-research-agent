"""S2: questions, gold answers and intent cards, made by code from the seed. No LLM anywhere here.

A question names what it asks about and leaves some points open on purpose (in medicine: time point, patient
group, dose, how the change is measured), so the Spec step has real work. The intent card is the fixed answer a user
gives for each open point. For a setting (context, factor, time) the answer is "all": keep every value, one column
per open point, never pick one silently. Gold = what the question's SPARQL returns over the seed, as a table.
Slot names, cell formats, intent cards and hand-written questions come from the blueprint's generator section
(profile.py); nothing here is domain-bound.

Two question types:
  lookup  every matching row; each row is unique on the open-point columns.
  best    which candidate (a factor value or a subject) is best. Open points the candidates share (time point, patient group)
          split the answer into groups, one winner per group; a group where a candidate has no row is "not reported
          for X". An open point that is the candidate's own setting (the dose of a drug) is not split: each
          candidate counts with its best value. A winner must beat the runner-up by more than the rounding step of
          the measure, else the group is a "tie". A question with no group that has a winner is rejected.

Files written by `build(domain)`:
  data/dataset/<domain>/questions/<split>.jsonl   question text + intent card (what the QA system may read)
  data/seed/<domain>/gold/<qid>.json              SPARQL, gold rows, answer (the truth; the QA system never reads it)
  data/seed/<domain>/gold/manifest.json           sha256 of each file above and of each question; freezes the set
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from rdflib import Graph

from evqa.paths import DATASET, REPO, domain_dir
from evqa.seed import build as seed_build
from evqa.seed.check import full_graph
from evqa.seed.profile import Gen, default_gen
from evqa.seed.rdf import query as locked_query


class Rejected(ValueError):
    """A question whose gold is not a clear answer (no row, duplicate rows, or no group with a winner)."""


class Frozen(RuntimeError):
    """The questions on disk are frozen by a manifest and the new build differs from them."""


@dataclass(frozen=True)
class Choice:
    """One open point of a question and the fixed answer a user gives for it."""
    label: str                 # plain name shown to people
    ask: str                   # the question Spec would ask about it
    answer: str                # the fixed answer (the intent card text; baselines get the same words)
    rule: dict[str, Any]       # slot -> value this answer pins in the query (empty for "all")
    column: str | None = None  # "all": the slot kept open and shown as a column of the gold table
    own_setting: bool = False  # a setting of the subject itself (a dose): not split when subjects compete


@dataclass(frozen=True)
class Spec:
    """One question before it is turned into SPARQL. `fixed` slots are stated in the question text."""
    qid: str
    type: str                  # lookup | best
    split: str                 # test | practice
    text: str                  # may use {drug_a} etc. (item keys; made-up names from names.json)
    fixed: dict[str, Any]
    open: tuple[str, ...]
    candidate: str | None = None   # best only: the slot whose values compete (the factor slot or "subject")
    notes: str = ""
    extra: dict[str, Any] = field(default_factory=dict)   # bench types (bench.py): axis, template kind, why, ...


class ByDomain(dict):
    """domain -> value, loaded from the domain's blueprint on first use (tests may set or patch entries)."""

    def __init__(self, load: Any):
        super().__init__()
        self._load = load

    def __missing__(self, domain: str) -> Any:
        self[domain] = value = self._load(domain)
        return value


def _intent(domain: str) -> dict[str, Choice]:
    """The intent card policy of a domain: open point -> fixed choice. `other_names` has no query rule; it is the
    answer to Spec's "do you know other names for these?" and is on every card."""
    return {k: Choice(v["label"], v["ask"], v["answer"], dict(v.get("rule") or {}), column=v.get("column"),
                      own_setting=bool(v.get("own_setting", False)))
            for k, v in gen_of(domain).g["intent"].items()}


def _specs(domain: str) -> list[Spec]:
    """The hand-written questions of a domain, kept as they are."""
    out = []
    for q in (gen_of(domain).g.get("questions") or {}).get(domain, []):
        out.append(Spec(q["qid"], q["type"], q["split"], q["text"], dict(q["fixed"]), tuple(q["open"]),
                        candidate=q.get("candidate"), notes=q.get("notes", "")))
    return out


INTENT: dict[str, dict[str, Choice]] = ByDomain(_intent)
SPECS: dict[str, list[Spec]] = ByDomain(_specs)

PREFIXES = """PREFIX ex: <https://w3id.org/evqa/seed#>
PREFIX d: <https://w3id.org/evqa/data/>
PREFIX sosa: <http://www.w3.org/ns/sosa/>
PREFIX qudt: <http://qudt.org/schema/qudt/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
"""


# ---------- names ----------

_MEMO: dict[tuple, Any] = {}


def _cached(path: Path, load: Any, tag: str = "") -> Any:
    """`load(path)`, reused while the file's mtime and size stay the same (the generator asks thousands of times)."""
    st = path.stat()
    key = (tag, str(path), st.st_mtime_ns, st.st_size)
    if key not in _MEMO:
        _MEMO[key] = load(path)
    return _MEMO[key]


def _blueprint(domain: str) -> dict[str, Any]:
    return _cached(domain_dir(domain) / "blueprint.yaml", lambda _: seed_build.load_blueprint(domain))


def gen_of(domain: str) -> Gen:
    """The generator section of the domain's blueprint."""
    return _cached(domain_dir(domain) / "blueprint.yaml", lambda _: Gen(_blueprint(domain)), tag="gen")


def slots(domain: str) -> tuple[str, ...]:
    return gen_of(domain).slots


def names(domain: str) -> dict[str, str]:
    """Blueprint item key -> the label used in the seed (made-up names for invented items)."""
    bp = _blueprint(domain)
    path = domain_dir(domain) / "names.json"
    picked = _cached(path, lambda p: json.loads(p.read_text(encoding="utf-8")))["slots"] if path.is_file() else {}
    return {k: picked[k]["name"] if "invent" in v else v["label"] for k, v in bp["items"].items()}


def item_iri(domain: str, key: str) -> str:
    """The seed IRI of a blueprint item; a key the blueprint lacks (an out-of-scope drug) gets d:<slug>, which
    matches nothing in the seed."""
    bp = _blueprint(domain)
    if key not in bp["items"]:
        return f"d:{seed_build.slug(key).replace(' ', '-')}"
    return f"d:{names(domain)[key]}" if "invent" in bp["items"][key] else f"d:{seed_build.slug(key)}"


LABEL = "label:"   # a slot value "label:<text>" matches by label words, not by key (bench: near misses, topics)


def _lit(text: str) -> str:
    return json.dumps(text.lower(), ensure_ascii=False)


# ---------- slots and SPARQL ----------

def open_columns(domain: str, spec: Spec) -> list[str]:
    """The open points kept as columns ("all" answers), in question order."""
    return [p for p in spec.open if INTENT[domain][p].column]


def resolve(domain: str, spec: Spec, *, use_card: bool = True) -> dict[str, Any]:
    """Every slot of the query: from the question text, else from the intent card, else None (= any value).
    With the card, every slot must be stated, pinned by the card, an "all" column, or the competing candidate."""
    order = gen_of(domain).slots
    slots: dict[str, Any] = {s: None for s in order}
    slots.update(spec.fixed)
    if not use_card:
        return slots
    covered = {k for k, v in spec.fixed.items() if v is not None}
    for point in spec.open:
        choice = INTENT[domain][point]
        for slot, value in choice.rule.items():
            if slot in covered:
                raise ValueError(f"{spec.qid}: {slot} is stated in the question and also open ({point})")
            slots[slot] = value
            covered.add(slot)
        if choice.column:
            if choice.column in covered:
                raise ValueError(f"{spec.qid}: {choice.column} is stated in the question and also open ({point})")
            covered.add(choice.column)
    if spec.candidate:
        covered.add(spec.candidate)
    missing = [s for s in order if s not in covered]
    if missing:
        raise ValueError(f"{spec.qid}: slots {missing} are neither stated, pinned nor open")
    if spec.type == "lookup" and len(slots["subject"]) != 1:
        raise ValueError(f"{spec.qid}: a lookup asks about one subject")
    return slots


def _num(x: Any) -> str:
    return format(Decimal(str(x)).normalize(), "f")


def sparql(domain: str, spec: Spec, *, use_card: bool = True) -> str:
    """The SPARQL of a question: stated and pinned slots are fixed; open ("all") slots stay variables."""
    s = resolve(domain, spec, use_card=use_card)
    gen = gen_of(domain)
    C, F, T = gen.C, gen.F, gen.T
    lines = [PREFIXES + f"SELECT ?r ?paper ?subject ?{C} ?{C}Label ?{F} ?{T} ?value ?unit WHERE {{"]
    if s["subject"]:
        lines.append(f"  VALUES ?subject {{ {' '.join(item_iri(domain, k) for k in s['subject'])} }}")
    if s[C] and not str(s[C]).startswith(LABEL):
        lines.append(f"  VALUES ?{C} {{ d:{seed_build.slug(s[C])} }}")
    body = ["a ex:Result", "ex:subject ?subject", "ex:reportedIn ?paper"]
    if s.get("comparator"):
        body.append(f"ex:comparator {item_iri(domain, s['comparator'])}")
    if s["measure"] and str(s["measure"]).startswith(LABEL):
        body.append("sosa:observedProperty ?measure")
    elif s["measure"]:
        body.append(f"sosa:observedProperty d:{seed_build.slug(s['measure'])}")
    body.append(f"sosa:hasFeatureOfInterest ?{C}")
    if s["statistic"]:
        body.append(f"ex:statistic ex:{s['statistic']}")
    body += [f"ex:condition/ex:setting/qudt:numericValue ?{F}", f"ex:atTime/qudt:numericValue ?{T}",
             "sosa:hasResult [ qudt:numericValue ?value ; qudt:unit ?unit ]"]
    lines.append("  ?r " + " ;\n     ".join(body) + " .")
    lines.append(f'  ?paper ex:split "{spec.split}" .')
    lines.append(f"  ?{C} skos:prefLabel ?{C}Label .")
    if s[C] and str(s[C]).startswith(LABEL):
        lines.append(f"  FILTER(LCASE(STR(?{C}Label)) = {_lit(s[C][len(LABEL):])})")
    if s["measure"] and str(s["measure"]).startswith(LABEL):
        lines.append(f"  ?measure skos:prefLabel ?measureLabel .\n  FILTER(CONTAINS(LCASE(STR(?measureLabel)), "
                     f"{_lit(s['measure'][len(LABEL):])}))")
    for slot in (F, T):
        if isinstance(s[slot], (int, float)):
            lines.append(f"  FILTER(?{slot} = {_num(s[slot])})")
    lines.append(f"}} ORDER BY ?subject ?{C} ?{F} ?{T} ?r")
    return "\n".join(lines) + "\n"


# ---------- running the query ----------

def _local(iri: Any) -> str:
    return str(iri).rsplit("/", 1)[-1].rsplit("#", 1)[-1]


FIXED_VARS = ("r", "paper", "subject", "value", "unit")


def run_query(g: Graph, query: str) -> list[dict[str, Any]]:
    """Rows of a question query (sparql()): the setting variables keep the query's slot names; a slot X with an
    ?XLabel variable is its label text, any other setting is a number."""
    sym = {str(r.u): str(r.s) for r in locked_query(
        g, "PREFIX qudt: <http://qudt.org/schema/qudt/> SELECT ?u ?s WHERE { ?u qudt:symbol ?s }")}
    out = []
    for r in locked_query(g, query):
        names = [str(v) for v in r.labels]
        row: dict[str, Any] = {"id": _local(r.r), "paper": _local(r.paper), "subject": _local(r.subject)}
        for v in names:
            if v in FIXED_VARS or v.endswith("Label"):
                continue
            row[v] = str(r[v + "Label"]) if v + "Label" in names else Decimal(str(r[v].toPython()))
        row.update(value=Decimal(str(r.value)), unit=sym.get(str(r.unit), _local(r.unit)))
        out.append(row)
    return out


def cell(row: dict[str, Any], slot: str, gen: Gen | None = None) -> str:
    """How a slot value is shown in a gold table cell (factor and time with the blueprint's cell format)."""
    return (gen or default_gen()).cell(slot, row[slot])


def _sort_key(row: dict[str, Any], slots: list[str], gen: Gen | None = None) -> tuple:
    numeric = (gen or default_gen()).numeric
    return tuple(row[s] if s in numeric else str(row[s]) for s in slots)


def pick_best(values: dict[str, Decimal], higher_is_better: bool, step: Decimal) -> tuple[str, Decimal]:
    """The winner and its margin over the runner-up. Rejects a margin not larger than the rounding step."""
    if len(values) < 2:
        raise Rejected(f"a best question needs at least two candidates, got {sorted(values)}")
    ranked = sorted(values.items(), key=lambda kv: kv[1], reverse=higher_is_better)
    margin = abs(ranked[0][1] - ranked[1][1])
    if margin <= step:
        raise Rejected(f"winner {ranked[0][0]} beats {ranked[1][0]} by {margin}, not more than the rounding {step}")
    return ranked[0][0], margin


def _table_row(row: dict[str, Any], keys: list[tuple[str, str]], gen: Gen | None = None) -> dict[str, Any]:
    return {"row": row["id"], "paper": row["paper"], "cells": {k: cell(row, slot, gen) for k, slot in keys},
            "value": str(row["value"]), "unit": row["unit"]}


def decide(rows: list[dict[str, Any]], candidate: str, candidates: list[str], split: list[str], own: list[str],
           higher_is_better: bool, step: Decimal, gen: Gen | None = None) -> list[dict[str, Any]]:
    """Best-question groups. `split` and `own` are slots; `candidates` are the cell texts of the candidate slot.
    One group per value combination of the split slots; each candidate counts with its best row over `own`."""
    groups: dict[tuple, list[dict[str, Any]]] = {}
    for r in sorted(rows, key=lambda r: _sort_key(r, split, gen)):
        groups.setdefault(tuple(cell(r, s, gen) for s in split), []).append(r)
    out = []
    for key, members in groups.items():
        best: dict[str, dict[str, Any]] = {}
        for r in members:
            c = cell(r, candidate, gen)
            if c in best and not own:
                raise Rejected(f"candidate {c} has more than one row in group {key}")
            if c not in best:
                best[c] = r
            elif (r["value"] > best[c]["value"]) if higher_is_better else (r["value"] < best[c]["value"]):
                best[c] = r
        ranking = sorted(best.items(), key=lambda kv: kv[1]["value"], reverse=higher_is_better)
        group: dict[str, Any] = {
            "cells": dict(zip(split, key, strict=True)),
            "ranking": [{"candidate": c, "row": r["id"], "value": str(r["value"]), "unit": r["unit"],
                         "cells": {s: cell(r, s, gen) for s in own}} for c, r in ranking],
            "missing": [c for c in candidates if c not in best]}
        if group["missing"]:
            group.update(status="not reported", winner=None, margin=None)
        else:
            try:
                winner, margin = pick_best({c: r["value"] for c, r in best.items()}, higher_is_better, step)
                group.update(status="winner", winner=winner, margin=str(margin))
            except Rejected:
                group.update(status="tie", winner=None,
                             margin=str(abs(ranking[0][1]["value"] - ranking[1][1]["value"])))
        out.append(group)
    return out


def gold(domain: str, spec: Spec, g: Graph | None = None) -> dict[str, Any]:
    """Run the question's SPARQL over the seed and turn the rows into the gold table (or raise Rejected)."""
    g = g if g is not None else full_graph(domain)
    gen = gen_of(domain)
    query = sparql(domain, spec)
    rows = run_query(g, query)
    if not rows:
        raise Rejected(f"{spec.qid}: the query finds no row")
    papers = {str(r.r): str(r.split) for r in locked_query(
        g, "PREFIX ex: <https://w3id.org/evqa/seed#> SELECT ?r ?split WHERE { ?r ex:reportedIn/ex:split ?split }")}
    bad = [r["id"] for r in rows if papers[f"https://w3id.org/evqa/data/{r['id']}"] != spec.split]
    if bad:
        raise Rejected(f"{spec.qid}: rows {bad} are not in the {spec.split} split")
    m = _blueprint(domain)["measures"][spec.fixed["measure"]]
    step = Decimal(1).scaleb(-m["decimals"])
    points = open_columns(domain, spec)
    slot_of = {p: INTENT[domain][p].column for p in points}
    if spec.type == "lookup":
        keys = [(p, slot_of[p]) for p in points]
        seen: set[tuple] = set()
        for r in rows:
            k = tuple(cell(r, s, gen) for _, s in keys)
            if k in seen:
                raise Rejected(f"{spec.qid}: two rows share the open-point values {k}")
            seen.add(k)
        ordered = sorted(rows, key=lambda r: _sort_key(r, [s for _, s in keys], gen))
        answer = {"columns": [{"key": p, "label": INTENT[domain][p].label} for p in points],
                  "table": [_table_row(r, keys, gen) for r in ordered],
                  "text": f"{len(rows)} value(s): " + "; ".join(
                      ", ".join([*(cell(r, s, gen) for _, s in keys), f"{r['value']} {r['unit']}"]) for r in ordered)}
    elif spec.type == "best":
        cand = spec.candidate or ""
        own = [p for p in points if INTENT[domain][p].own_setting and cand == "subject" and slot_of[p] != cand]
        split = [p for p in points if p not in own and slot_of[p] != cand]
        keys = [("candidate", cand), *((p, slot_of[p]) for p in points)]
        candidates = (names(domain)[k] for k in spec.fixed["subject"]) if cand == "subject" else \
            sorted({cell(r, cand, gen) for r in rows}, key=lambda c: Decimal(c.split()[0]))
        groups = decide(rows, cand, list(candidates), [slot_of[p] for p in split], [slot_of[p] for p in own],
                        m["higher_is_better"], step, gen)
        for grp in groups:   # name the cells by open point, not by slot
            grp["cells"] = {p: grp["cells"][slot_of[p]] for p in split}
            for r in grp["ranking"]:
                r["cells"] = {p: r["cells"][slot_of[p]] for p in own}
        if not any(grp["status"] == "winner" for grp in groups):
            raise Rejected(f"{spec.qid}: no group has a clear winner")
        ordered = sorted(rows, key=lambda r: _sort_key(r, [cand, *(slot_of[p] for p in points)], gen))

        def say(grp: dict[str, Any]) -> str:
            where = ", ".join(grp["cells"].values()) or "all"
            if grp["status"] == "winner":
                return f"{where}: {grp['winner']} (ahead by {grp['margin']})"
            if grp["status"] == "tie":
                return f"{where}: tie"
            return f"{where}: not reported for {', '.join(grp['missing'])}"
        cand_label = gen.g["candidate_labels"]["factor" if cand == gen.F else "subject"]
        answer = {"columns": [{"key": "candidate", "label": cand_label},
                              *({"key": p, "label": INTENT[domain][p].label} for p in points)],
                  "table": [_table_row(r, keys, gen) for r in ordered],
                  "split_by": [{"key": p, "label": INTENT[domain][p].label} for p in split],
                  "own": [{"key": p, "label": INTENT[domain][p].label} for p in own],
                  "groups": groups, "rounding_step": str(step), "higher_is_better": m["higher_is_better"],
                  "text": "; ".join(say(grp) for grp in groups)}
    else:
        raise ValueError(f"unknown question type {spec.type!r}")
    loose = run_query(g, sparql(domain, spec, use_card=False))
    return {"qid": spec.qid, "domain": domain, "type": spec.type, "split": spec.split, "sparql": query,
            "slots": {k: v for k, v in resolve(domain, spec).items() if v is not None},
            "open_columns": points, "row_ids": [r["id"] for r in rows], "answer": answer,
            "rows_without_card": len(loose), "notes": spec.notes}


# ---------- question records (what the QA system reads) ----------

def card(domain: str, spec: Spec) -> list[dict[str, str]]:
    points = [*spec.open, "other_names"]
    return [{"point": p, "label": INTENT[domain][p].label, "ask": INTENT[domain][p].ask,
             "answer": INTENT[domain][p].answer} for p in points]


def card_text(entries: list[dict[str, str]]) -> str:
    return "\n".join(f"{e['label']}: {e['answer']}" for e in entries)


def record(domain: str, spec: Spec) -> dict[str, Any]:
    entries = card(domain, spec)
    return {"qid": spec.qid, "domain": domain, "split": spec.split, "type": spec.type,
            "question": spec.text.format(**names(domain)), "intent_card": entries, "intent_text": card_text(entries)}


# ---------- files and the manifest ----------

def questions_dir(domain: str) -> Path:
    return DATASET / domain / "questions"


def gold_dir(domain: str) -> Path:
    return domain_dir(domain) / "gold"


def _dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def render(domain: str, g: Graph | None = None) -> dict[Path, str]:
    """Every file of the question set as path -> text (nothing written). Paths are the canonical ones (the
    manifest records them repo-relative); `g` = another seed graph (a rebuild) instead of seed.ttl on disk."""
    g = g if g is not None else full_graph(domain)
    files: dict[Path, str] = {}
    by_split: dict[str, list[str]] = {}
    for spec in SPECS[domain]:
        by_split.setdefault(spec.split, []).append(json.dumps(record(domain, spec), ensure_ascii=False))
        files[gold_dir(domain) / f"{spec.qid}.json"] = _dump(gold(domain, spec, g))
    for split, lines in sorted(by_split.items()):
        files[questions_dir(domain) / f"{split}.jsonl"] = "\n".join(lines) + "\n"
    files[gold_dir(domain) / "manifest.json"] = _dump(manifest(domain, files))
    return files


def manifest(domain: str, files: dict[Path, str]) -> dict[str, Any]:
    """sha256 of each file, of each question (record + gold), and of the whole set."""
    shas = {p.relative_to(REPO).as_posix(): sha(t) for p, t in sorted(files.items()) if p.name != "manifest.json"}
    per_q = {}
    for spec in SPECS[domain]:
        rec = record(domain, spec)
        g = json.loads(files[gold_dir(domain) / f"{spec.qid}.json"])
        per_q[spec.qid] = sha(json.dumps({"record": rec, "gold": g}, sort_keys=True, ensure_ascii=False))
    return {"domain": domain, "set_sha256": sha(json.dumps(shas, sort_keys=True)), "questions": per_q, "files": shas}


def write_files(files: dict[Path, str], out: Path | None = None) -> list[Path]:
    """Write path -> text (unchanged files are left alone); with `out`, under out/<repo-relative path>."""
    written = []
    for path, text in files.items():
        target = seed_build.relocate(path, out)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_file() or target.read_text(encoding="utf-8") != text:
            target.write_text(text, encoding="utf-8")
        written.append(target)
    return written


def verify(domain: str) -> list[str]:
    """Problems with the frozen files on disk: missing manifest, missing or changed files."""
    path = gold_dir(domain) / "manifest.json"
    if not path.is_file():
        return [f"{path.relative_to(REPO)} is missing"]
    m = json.loads(path.read_text(encoding="utf-8"))
    problems = []
    for rel, want in m["files"].items():
        f = REPO / rel
        if not f.is_file():
            problems.append(f"{rel} is missing")
        elif sha(f.read_text(encoding="utf-8")) != want:
            problems.append(f"{rel} changed since the manifest was written")
    return problems


def build(domain: str, *, force: bool = False, out: Path | None = None, g: Graph | None = None) -> dict[str, Any]:
    """Make the questions, gold and manifest and write them. A frozen set that would change needs `force`.
    With `out`, every file goes to out/<repo-relative path> and the frozen files are only compared, never written."""
    old_path = gold_dir(domain) / "manifest.json"
    if old_path.is_file() and "generator" in json.loads(old_path.read_text(encoding="utf-8")):
        raise Frozen("the frozen set was made by `evqa seed bench` (100 questions); rebuild it with that command")
    files = render(domain, g)
    new = json.loads(files[gold_dir(domain) / "manifest.json"])
    if old_path.is_file() and not force and out is None:
        old = json.loads(old_path.read_text(encoding="utf-8"))
        if old["set_sha256"] != new["set_sha256"]:
            changed = sorted(q for q in {*old["questions"], *new["questions"]}
                             if old["questions"].get(q) != new["questions"].get(q))
            raise Frozen(f"the frozen question set would change ({changed}); rebuild with --force on purpose")
    write_files(files, out)
    golds = {s.qid: json.loads(files[gold_dir(domain) / f"{s.qid}.json"])["answer"]["text"] for s in SPECS[domain]}
    return {"domain": domain, "set_sha256": new["set_sha256"], "answers": golds,
            "files": sorted(new["files"]) + [old_path.relative_to(REPO).as_posix()]}

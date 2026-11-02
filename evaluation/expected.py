"""The expected answer of a question, computed from a corpus's ground truth (question-first redesign).

`expected(truth, kind, params, protocol=None)` gives the answer shape of the kind's rules module
(evidence/kinds/), with study ids as documents and `system` "ground-truth". The truth parameters (`params`, from
domains/rag/questions.yaml) decide the metric, the neutral band and the inventory target. Everything else (the
compared roles, the claim vocabulary, the flag thresholds, the label table) is the generator's own spec: the
synthesis block of the corpus domain's effect protocol (`effect_spec`: generator.yaml `effect_protocol`, read as
YAML data; plan 2 Task 12, preflight P15), never the passed protocol, which a user may have
edited (Part D): truth must not change with the user's protocol. The protocol supplies only the effect answer's
`question` text and its id for the shortcut below.

For the question the corpus was generated for (kind effect, `params.metric` factual_accuracy, protocol id in
SAVED_ANSWER_IDS: rag-factuality and its agentic variant) the saved `truth.answer` is returned unchanged: it was
computed with that protocol's metric priority list (factual accuracy, then hallucination rate), which one truth
metric cannot express. Another effect protocol that reuses the question text does not get it.

Rules:
- Counted studies: relevant, not `duplicate_of`, and (effect, consistency) not `missing` the needed side (the
  `missing` measurement is on the study's question metric, its first metric; it counts as missing for that metric
  only). best keeps a `missing` study: the kinds that remain measured are compared. A study that is
  not counted keeps an entry with a reason (`screened_out`, `duplicate`, `missing_control|missing_treatment`);
  effect reports a duplicate's direction as the engine does, and lists it under `duplicates` when that direction
  is determined on the question metric (else it is undetermined, as the engine would find it).
- Main experiment: the experiment of the study's `effect.treatment` measurement (else `effect.control`, else
  the first measurement); only its measurements are read. A study without experiments has one.
- Metric: a truth metric matches `params.metric` when its `canonical` equals it (factual_accuracy,
  hallucination_rate) or when both names have the same `Canon.key` (latency, written "latency" or "Lat.").
- Dataset: the first dataset in measurement order within the main experiment that has the values needed (both
  compared roles for effect and consistency, two method kinds for best); the first value of each side there.
- effect: `rules.effect` with `params.min_effect` and the metric's `higher_is_better`, `rules.label` over the
  counts. The author claim is about the study's question metric (its first): `agrees_with_data`, and so the
  `claim_disagrees` flag, only when that metric matches `params.metric` (else null: a claim about accuracy says
  nothing about latency). consistency: only studies whose question metric (their first) matches `params.metric`; `agrees` is
  `rules.claim_agrees` while both the claim and the direction are known. inventory: the `Canon.key` of every
  name over the relevant papers (a name the table does not know is its own key, whitespace collapsed); `aliases`
  are the other forms truth uses for the key, `papers` sorted study ids, `items` the fact ids. best: each
  condition's kind is `Canon.kind_of` its label; the kind with the top value wins, a tie gives none.
- chaining, limitations, builds_on (plan 2 Task 13; truth of a recipe with a network and the builds_on preset): a
  compared thing is its `Canon.key` (`thing_key`; the label, whitespace collapsed, when the table has none) and is
  shown by it. chaining: the truth `network` (synth/network.py) on `params.metric`. Comparisons of `params.source`
  and `params.target` are a direct result (reason `direct_comparison`, verdict source over target, `refused` when
  they differ); else the truth `chains` of that pair (2 steps, each judged by `rules.chain_verdict`) are combined
  by `rules.chain_paths`, the engine's rule; none gives `no_path` (truth lists comparisons on the question metric
  only, so `metric_differs` is never expected). `via` and `studies` are those of the paths the answer rests on.
  limitations: every study's planted limitations, by (thing, category), papers in study order; `counts` keyed by
  thing for the linked ones, `unlinked` for those without a thing. builds_on: links (from, to, reuses) from the
  planted dependencies; a dependency marked `outside_corpus` is `unresolved` (its cited label), never a link. A
  thing's origin and followers are the engine's rules (`builds_on.origin_of`, `followers_of`) over the truth's
  conditions (mentions), dependency things (taken) and study labels (years).

The name table (`Canon`) is the corpus's own, `Canon.from_truth(truth)`, unless the caller passes one.
"""
from __future__ import annotations

import copy
from functools import cache
from pathlib import Path
from typing import Any

from evidence import rules
from evidence.kinds import best as best_rules
from evidence.kinds import builds_on as builds_on_rules
from evidence.kinds import chaining as chaining_rules
from evidence.pack import DOMAINS
from evidence.protocol import DEFAULT_PACK, Kind, Protocol, Synthesis
from evidence.protocol import load as load_protocol
from evidence.questions import QuestionTruth

from .canon import Canon, fold, recipe_data
from .truth import GroundTruth

SYSTEM = "ground-truth"
SAVED_ANSWER_IDS = frozenset({"rag-factuality", "rag-factuality-agentic"})   # protocols of the corpus's own question
SAVED_ANSWER_METRIC = "factual_accuracy"
NAME_FIELD = {"condition": "label", "metric": "name"}
GROUPS = (("supporting", "supports"), ("contradicting", "contradicts"), ("neutral", "neutral"),
          ("undetermined", "undetermined"))
SKIP_TEXT = {"screened_out": "not relevant (no experiment)", "duplicate": "a duplicate of {of}",
             "missing_control": "the paper never states the control value",
             "missing_treatment": "the paper never states the treatment value",
             "no_question_metric": "no metric of the question", "no_pair": "no {treatment} and {control} value on "
             "one dataset of the main experiment", "no_claim": "no author claim"}


@cache
def effect_spec(domain: str = DEFAULT_PACK, root: Path = DOMAINS) -> Synthesis:
    """The synthesis block of `domain`'s effect protocol: generator.yaml `effect_protocol` (read as YAML data) in
    `<root>/<domain>/protocols/`; the generator draws a corpus of that domain by it."""
    recipe = recipe_data(domain, root)
    if recipe is None or not recipe.get("effect_protocol"):
        raise ValueError(f"no effect protocol for domain {domain!r}: {Path(root) / domain / 'generator.yaml'} is "
                         "missing or names no effect_protocol")
    path = Path(root) / domain / "protocols" / f"{recipe['effect_protocol']}.yaml"
    return load_protocol(path, None if Path(root) == DOMAINS else root).synthesis


def _reason(code: str, **fmt: Any) -> dict[str, str]:
    return {"code": code, "text": SKIP_TEXT[code].format(**fmt)}


def _matches(metric: dict[str, Any], wanted: str, canon: Canon) -> bool:
    if metric.get("canonical") == wanted:
        return True
    k = canon.key("metric", wanted)
    return k is not None and canon.key("metric", metric.get("name", "")) == k


def _main(study: dict[str, Any]) -> list[dict[str, Any]]:
    """The measurements of the study's main experiment, in measurement order."""
    ms = study.get("measurements") or []
    by_id = {m["id"]: m for m in ms}
    effect = study.get("effect") or {}
    anchor = by_id.get(effect.get("treatment") or "") or by_id.get(effect.get("control") or "") or (ms[0] if ms else None)
    main = anchor.get("experiment") if anchor else None
    return [m for m in ms if m.get("experiment") == main]


def _question_metric(study: dict[str, Any]) -> dict[str, Any] | None:
    metrics = study.get("metrics") or []
    return metrics[0] if metrics else None


def _skip(study: dict[str, Any], metric: str, canon: Canon) -> dict[str, str] | None:
    """Why a relevant study is not counted (duplicate, missing side), or why an irrelevant one is undetermined."""
    if not study.get("relevant", True):
        return _reason("screened_out")
    side = study.get("missing")
    q = _question_metric(study)
    if side and q is not None and _matches(q, metric, canon):
        return _reason(f"missing_{side}")
    return None


def _first_dataset(ms: list[dict[str, Any]], side_of: dict[str, str], need: int) -> dict[str, dict[str, Any]] | None:
    """side -> its first value on the first dataset (measurement order) that has `need` sides; None when none has.

    Truth always names a dataset and has one condition per role or kind in the main experiment, so the engine's
    dataset=None fallback (synthesis._pair, kinds.best) and its `best_value` choice are not needed here."""
    for dataset in dict.fromkeys(m.get("dataset") for m in ms):
        chosen: dict[str, dict[str, Any]] = {}
        for m in ms:
            if m.get("dataset") == dataset and m["condition"] in side_of:
                chosen.setdefault(side_of[m["condition"]], m)
        if len(chosen) >= need:
            return chosen
    return None


def _on_metric(study: dict[str, Any], metric: str, canon: Canon) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    metrics = {k["id"]: k for k in study.get("metrics") or [] if _matches(k, metric, canon)}
    return [m for m in _main(study) if m["metric"] in metrics], metrics


# effect ------------------------------------------------------------------------------------------------------

def _effect_study(study: dict[str, Any], params: QuestionTruth, spec: Synthesis, canon: Canon) -> dict[str, Any]:
    assert params.metric is not None and params.min_effect is not None, "effect truth takes metric and min_effect"
    entry: dict[str, Any] = {"document": study["paper"], "direction": "undetermined", "delta": None, "metric": None,
                             "treatment": None, "control": None, "author_claim": None, "reason": None, "flags": [],
                             "duplicate_of": None}
    claim = study.get("author_claim")
    skip = _skip(study, params.metric, canon)
    if skip is not None:
        entry["reason"] = skip
        return entry
    ms, metrics = _on_metric(study, params.metric, canon)
    roles = {c["id"]: c["role"] for c in study.get("conditions") or []
             if c["role"] in (spec.compare.treatment, spec.compare.control)}
    pair = _first_dataset(ms, roles, 2)
    if pair is None:
        entry["reason"] = (_reason("no_question_metric") if not metrics else
                           _reason("no_pair", treatment=spec.compare.treatment, control=spec.compare.control))
    else:
        t, c = pair[spec.compare.treatment], pair[spec.compare.control]
        direction, delta = rules.effect(float(t["value"]), float(c["value"]), bool(metrics[t["metric"]]["higher_is_better"]),
                                        params.min_effect)
        entry.update(direction=direction, delta=delta, metric=params.metric,
                     treatment={"condition": t["condition"], "measurement": t["id"], "value": t["value"]},
                     control={"condition": c["condition"], "measurement": c["id"], "value": c["value"]})
    if claim:
        # the claim is about the study's question metric, its first; on another metric it says nothing: null
        on_metric = (q := _question_metric(study)) is not None and _matches(q, params.metric, canon)
        determined = entry["direction"] != "undetermined" and on_metric
        entry["author_claim"] = {"item": claim["id"], "direction": claim["direction"],
                                 "agrees_with_data": rules.claim_agrees(claim["direction"], entry["direction"],
                                                                        spec.claim_map) if determined else None}
    return entry


def _effect(truth: GroundTruth, params: QuestionTruth, protocol: Protocol | None, canon: Canon) -> dict[str, Any]:
    spec = effect_spec(canon.domain, canon.root)
    studies = [_effect_study(s, params, spec, canon) for s in truth.studies]
    determined = {e["document"] for e in studies if e["direction"] != "undetermined"}
    dup_of = {s["paper"]: s["duplicate_of"] for s in truth.studies   # the engine finds duplicates among determined studies
              if s.get("duplicate_of") and s["paper"] in determined}
    large = rules.large_effects({e["document"]: e["delta"] for e in studies
                                 if e["direction"] != "undetermined" and e["document"] not in dup_of},
                                spec.flags.large_effect.factor, spec.flags.large_effect.min_studies, params.min_effect or 0)
    flags: dict[str, list[str]] = {name: [] for name in rules.FLAGS}
    for e in studies:
        e["duplicate_of"] = dup_of.get(e["document"])
        found = set()
        if e["duplicate_of"]:
            found.add("duplicate")
        if e["document"] in large:
            found.add("large_effect")
        if e["author_claim"] is not None and e["author_claim"]["agrees_with_data"] is False:
            found.add("claim_disagrees")
        e["flags"] = sorted(found)
        for name in e["flags"]:
            flags[name].append(e["document"])
    groups = {k: [e["document"] for e in studies if e["direction"] == d and e["duplicate_of"] is None] for k, d in GROUPS}
    groups["duplicates"] = [e["document"] for e in studies if e["duplicate_of"] is not None]
    counts = {k: len(v) for k, v in groups.items()}
    return {"system": SYSTEM, "question": protocol.question if protocol is not None else "",
            "label": rules.label(counts, spec.table), "counts": counts, "studies": studies, **groups, "flags": flags}


# consistency -------------------------------------------------------------------------------------------------

def _consistency(truth: GroundTruth, params: QuestionTruth, protocol: Protocol | None, canon: Canon) -> dict[str, Any]:
    assert params.metric is not None, "consistency truth takes metric"
    spec = effect_spec(canon.domain, canon.root)
    studies = []
    for s in truth.studies:
        q = _question_metric(s)
        if not s.get("relevant", True) or q is None or not _matches(q, params.metric, canon):
            continue
        full = _effect_study(s, params, spec, canon)
        claim = (s.get("author_claim") or {}).get("direction")
        reason = full["reason"]
        if reason is None and s.get("duplicate_of"):
            reason = _reason("duplicate", of=s["duplicate_of"])
        if reason is None and claim is None:
            reason = _reason("no_claim")
        determined = reason is None
        studies.append({"document": s["paper"], "claim": claim, "direction": full["direction"],
                        "agrees": rules.claim_agrees(claim, full["direction"], spec.claim_map) if determined else None,
                        "reason": reason})
    groups = {name: [s["document"] for s in studies if s["agrees"] is value]
              for name, value in (("agreeing", True), ("disagreeing", False), ("undetermined", None))}
    return {"kind": "consistency", "system": SYSTEM, "metric": params.metric, "studies": studies, **groups}


# inventory ---------------------------------------------------------------------------------------------------

def _forms(truth: GroundTruth, study: dict[str, Any], target: str) -> list[tuple[str, str]]:
    """(fact id, name as truth writes it) of the study's `target` facts."""
    if target == "dataset":
        return [(f.id, f.data["name"]) for f in truth.of(study["paper"], "dataset")]
    entries = study.get({"condition": "conditions", "metric": "metrics"}[target]) or []
    return [(e["id"], " ".join(str(e[NAME_FIELD[target]]).split())) for e in entries]


def _inventory(truth: GroundTruth, params: QuestionTruth, protocol: Protocol | None, canon: Canon) -> dict[str, Any]:
    target = params.target
    assert target is not None, "inventory truth takes target"
    groups: dict[str, dict[str, Any]] = {}
    for s in truth.studies:
        if not s.get("relevant", True):
            continue
        for fact_id, form in _forms(truth, s, target):
            name = canon.key(target, form) or form
            g = groups.setdefault(fold(name), {"name": name, "forms": set(), "papers": set(), "items": []})
            g["forms"].add(form)
            g["papers"].add(s["paper"])
            g["items"].append(fact_id)
    entries = [{"name": g["name"], "aliases": sorted(f for f in g["forms"] if f != g["name"]),
                "papers": sorted(g["papers"]), "items": g["items"]}
               for g in sorted(groups.values(), key=lambda g: (fold(g["name"]), g["name"]))]
    return {"kind": "inventory", "system": SYSTEM, "target": target, "entries": entries}


# best --------------------------------------------------------------------------------------------------------

def _best_study(study: dict[str, Any], metric: str, canon: Canon) -> dict[str, Any]:
    entry: dict[str, Any] = {"document": study["paper"], "winner": None, "tied": [], "values": {}, "reason": None}
    skip = _reason("screened_out") if not study.get("relevant", True) else None   # a `missing` study still counts
    if skip is None and study.get("duplicate_of"):
        skip = _reason("duplicate", of=study["duplicate_of"])
    if skip is not None:
        entry["reason"] = skip
        return entry
    ms, metrics = _on_metric(study, metric, canon)
    main = {m["condition"] for m in _main(study)}
    kinds = {c["id"]: k for c in study.get("conditions") or [] if c["id"] in main
             and (k := canon.kind_of(c["label"])) is not None}
    if len(set(kinds.values())) < 2:
        entry["reason"] = {"code": "too_few_kinds", "text": best_rules.REASONS["too_few_kinds"]}
        return entry
    chosen = _first_dataset(ms, kinds, 2)
    if chosen is None:
        entry["reason"] = {"code": "no_comparison", "text": best_rules.REASONS["no_comparison"].format(metric=metric)}
        return entry
    values = {k: float(chosen[k]["value"]) for k in canon.kinds if k in chosen}
    higher = bool(metrics[next(iter(chosen.values()))["metric"]]["higher_is_better"])
    top = (max if higher else min)(values.values())
    leaders = sorted(k for k, v in values.items() if v == top)
    entry.update(values=values, winner=leaders[0] if len(leaders) == 1 else None,
                 tied=leaders if len(leaders) > 1 else [])
    return entry


def _best(truth: GroundTruth, params: QuestionTruth, protocol: Protocol | None, canon: Canon) -> dict[str, Any]:
    assert params.metric is not None, "best truth takes metric"
    studies = [_best_study(s, params.metric, canon) for s in truth.studies]
    wins = {k: n for k in canon.kinds if (n := sum(1 for s in studies if s["winner"] == k))}
    most = max(wins.values(), default=0)
    leaders = sorted(k for k, n in wins.items() if n == most) if most else []
    return {"kind": "best", "system": SYSTEM, "metric": params.metric, "studies": studies, "wins": wins,
            "winner": leaders[0] if len(leaders) == 1 else None, "tied": leaders if len(leaders) > 1 else []}


# chaining ----------------------------------------------------------------------------------------------------

def thing_key(canon: Canon, name: str) -> str:
    """A compared thing as truth and the scores name it: its `Canon.key`, else the name (whitespace collapsed)."""
    return canon.key("condition", name) or " ".join(str(name).split())


def _on(metric: str, wanted: str, canon: Canon) -> bool:
    return _matches({"canonical": metric, "name": metric}, wanted, canon)


def _papers(truth: GroundTruth) -> dict[str, int]:
    """paper -> its position (study order: the manifest's)."""
    return {s["paper"]: n for n, s in enumerate(truth.studies)}


def _chaining(truth: GroundTruth, params: QuestionTruth, protocol: Protocol | None, canon: Canon) -> dict[str, Any]:
    assert params.metric and params.source and params.target, "chaining truth takes metric, source and target"
    network = truth.network or {}
    source, target = thing_key(canon, params.source), thing_key(canon, params.target)
    position = _papers(truth)
    out: dict[str, Any] = {"kind": "chaining", "system": SYSTEM, "source": params.source, "target": params.target,
                           "metric": params.metric, "verdict": "refused", "inferred": False, "via": [],
                           "studies": [], "paths": [], "reason": None, "note": None}
    direct = []
    for c in network.get("comparisons") or []:
        a, b = thing_key(canon, c["a"]), thing_key(canon, c["b"])
        if {a, b} == {source, target} and a != b and _on(c["metric"], params.metric, canon):
            turned = c["direction"] if a == source else chaining_rules.FLIP[c["direction"]]
            direct.append({"via": [], "studies": [c["document"]], "context": c["context"],
                           "verdict": chaining_rules.VERDICT[turned] or "refused", "reason": chaining_rules.DIRECT})
    if direct:
        verdicts = {p["verdict"] for p in direct}
        out.update(verdict=verdicts.pop() if len(verdicts) == 1 else "refused", reason=chaining_rules.DIRECT)
        return _chain_finish(out, direct, direct, position)
    paths = [{"via": [thing_key(canon, v) for v in c["via"]], "studies": list(c["studies"]), "context": c["context"],
              "verdict": c["verdict"], "reason": c["reason"]}
             for c in network.get("chains") or []
             if thing_key(canon, c["source"]) == source and thing_key(canon, c["target"]) == target
             and _on(c["metric"], params.metric, canon)]
    if not paths:
        out.update(reason=chaining_rules.NO_PATH)
        return out
    verdict, why, chosen = rules.chain_paths([(p["verdict"], p["reason"]) for p in paths])
    out.update(verdict=verdict, inferred=why is None, reason=why)
    return _chain_finish(out, paths, [paths[n] for n in chosen], position)


def _chain_finish(out: dict[str, Any], paths: list[dict[str, Any]], chosen: list[dict[str, Any]],
                  position: dict[str, int]) -> dict[str, Any]:
    """`paths`, and the chosen paths' `via` (path order), `studies` (study order) and `note` (the engine's _finish)."""
    via: list[str] = []
    for p in chosen:
        via += [v for v in p["via"] if v not in via]
    docs = {d for p in chosen for d in p["studies"]}
    out.update(paths=paths, via=via, studies=sorted(docs, key=lambda d: (position.get(d, len(position)), d)))
    if out["inferred"]:
        out["note"] = chaining_rules.NOTE.format(via=", ".join(via))
    return out


# limitations -------------------------------------------------------------------------------------------------

def _limitations(truth: GroundTruth, params: QuestionTruth, protocol: Protocol | None, canon: Canon) -> dict[str, Any]:
    wanted = thing_key(canon, params.thing) if params.thing is not None else None
    found: dict[tuple[str | None, str], dict[str, Any]] = {}
    for s in truth.studies:
        labels = {c["id"]: c["label"] for c in s.get("conditions") or []}
        for lim in s.get("limitations") or []:
            label = labels.get(lim.get("thing") or "")
            thing = thing_key(canon, label) if label is not None else None
            if wanted is not None and thing != wanted:
                continue
            entry = found.setdefault((thing, lim["category"]), {"thing": thing, "category": lim["category"],
                                                                "papers": [], "items": []})
            if s["paper"] not in entry["papers"]:
                entry["papers"].append(s["paper"])
            entry["items"].append(lim["id"])
    entries = [found[k] for k in sorted(found, key=lambda k: (k[0] is None, (k[0] or "").casefold(), k[1]))]
    counts: dict[str, dict[str, int]] = {}
    unlinked: dict[str, int] = {}
    for e in entries:
        (unlinked if e["thing"] is None else counts.setdefault(e["thing"], {}))[e["category"]] = len(e["papers"])
    return {"kind": "limitations", "system": SYSTEM, "thing": params.thing, "entries": entries, "counts": counts,
            "unlinked": unlinked}


# builds_on ---------------------------------------------------------------------------------------------------

def truth_links(truth: GroundTruth) -> tuple[list[dict[str, Any]], list[str]]:
    """The planted dependency links (from, to, reuses, items: the dependency ids), in study order of the citing
    then the cited study, then by reuses; and the cited labels of the dependencies `outside_corpus` (each once)."""
    paper = {s["study_id"]: s["paper"] for s in truth.studies}
    position = _papers(truth)
    found: dict[tuple[str, str, str], list[str]] = {}
    unresolved: list[str] = []
    for s in truth.studies:
        for d in s.get("dependencies") or []:
            to = paper.get(d["cites"])
            if d.get("outside_corpus") or to is None:
                if d.get("label") and d["label"] not in unresolved:
                    unresolved.append(d["label"])
                continue
            found.setdefault((s["paper"], to, str(d["reuses"])), []).append(d["id"])
    ordered = sorted(found, key=lambda k: (position[k[0]], position[k[1]], k[2]))
    return [{"from": f, "to": t, "reuses": r, "items": found[(f, t, r)]} for f, t, r in ordered], unresolved


def _builds_on(truth: GroundTruth, params: QuestionTruth, protocol: Protocol | None, canon: Canon) -> dict[str, Any]:
    wanted = thing_key(canon, params.thing) if params.thing is not None else None
    position = _papers(truth)
    links, unresolved = truth_links(truth)
    citers: dict[str, list[str]] = {}
    for link in links:
        citers.setdefault(link["to"], []).append(link["from"])
    mentions: dict[str, list[str]] = {}
    taken: set[tuple[str, str]] = set()
    years: dict[str, int | None] = {}
    for s in truth.studies:
        doc = s["paper"]
        labels = {c["id"]: c["label"] for c in s.get("conditions") or []}
        years[doc] = builds_on_rules.year_of((s.get("study_label") or {}).get("label"))
        for label in labels.values():
            docs = mentions.setdefault(thing_key(canon, label), [])
            if doc not in docs:
                docs.append(doc)
        for d in s.get("dependencies") or []:   # a dependency links its thing whether or not it resolves
            if d.get("thing") in labels:
                taken.add((doc, thing_key(canon, labels[d["thing"]])))
    origins: dict[str, str | None] = {}
    followers: dict[str, list[str]] = {}
    for key, docs in mentions.items():
        if wanted is not None and key != wanted:
            continue
        origin = builds_on_rules.origin_of([d for d in docs if (d, key) not in taken], years, position)
        origins[key] = origin
        followers[key] = builds_on_rules.followers_of(origin, citers, position) if origin is not None else []
    if wanted is not None and wanted not in origins:   # the asked thing is mentioned nowhere
        origins[wanted], followers[wanted] = None, []
    ranking = sorted(origins, key=lambda k: (-len(followers[k]), k.casefold(), k))
    return {"kind": "builds_on", "system": SYSTEM, "thing": params.thing, "links": links,
            "origins": {k: origins[k] for k in ranking}, "followers": {k: followers[k] for k in ranking},
            "influence": {k: len(followers[k]) for k in ranking}, "ranking": ranking, "unresolved": unresolved}


BUILDERS = {"effect": _effect, "consistency": _consistency, "inventory": _inventory, "best": _best,
            "chaining": _chaining, "limitations": _limitations, "builds_on": _builds_on}


def saved_answer(truth: GroundTruth, kind: Kind, params: QuestionTruth, protocol: Protocol | None) -> bool:
    """Whether `expected` returns the saved `truth.answer` (the corpus's own question; module docstring)."""
    return bool(kind == "effect" and truth.answer and params.metric == SAVED_ANSWER_METRIC and protocol is not None
                and protocol.id in SAVED_ANSWER_IDS)


def expected(truth: GroundTruth, kind: Kind, params: QuestionTruth, protocol: Protocol | None = None,
             canon: Canon | None = None) -> dict[str, Any]:
    """The kind's answer as ground truth gives it (module docstring); `canon` defaults to the corpus's own table."""
    if saved_answer(truth, kind, params, protocol):
        return copy.deepcopy(truth.answer)
    return BUILDERS[kind](truth, params, protocol, canon or Canon.from_truth(truth))

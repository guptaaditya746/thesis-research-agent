"""A hand-labeling test set for the verifier, built WITHOUT the verifier (#11), and the metrics on it.

The old verifier test (evaluate.verifier_test) only uses sentences the verifier itself already accepted, so its score
is circular. Here the items come from code alone:

  candidate       every sentence of tagged.json that names a subject and a possible object (pack rules, as in
                  repair.Checker.pairs), checked against the relation the world gives that pair
  no_world_rel    the same, for a pair the world gives no relation (checked against each possible relation)
  other_relation  the same sentence and pair, another relation the pair could have
  decoy           the same sentence, a planted fact of the paper that shares exactly one entity with the pair
  not_recorded    a sentence made by code that says the relation for the pair is unknown
  impossible_pair another relation the pack does not allow for the pair (world.fact_errors): reported apart

export() writes a CSV (id, field, paper, sentence, context, subject, relation, object, label, notes) with an empty
label column, plus <name>.key.json (what each id is). The kind of an item is only in the key file, so labelers do not
see it. Labels: yes (the sentence itself states the claim) / no; anything else counts as unlabeled.
metrics() compares labels with the verifier's answers: precision, recall, false accept / false reject rates with
Wilson 95% intervals, by field, relation and kind; Cohen's kappa between two labelers.
"""
from __future__ import annotations

import csv
import json
import random
from pathlib import Path
from typing import Any

from paperfactory.evaluate import wilson
from paperfactory.packs import Field
from paperfactory.text import alias_table, defined_terms, find_mentions, normalize_paper
from paperfactory.world import fact_errors

COLUMNS = ["id", "field", "paper", "sentence", "context", "subject", "relation", "object", "label", "notes"]
KINDS = ("candidate", "no_world_rel", "other_relation", "decoy", "not_recorded", "impossible_pair")
NOT_RECORDED = ("It is not recorded how {s} treated {o}.",
                "How {s} dealt with {o} is not addressed here.",
                "Whether {s} {w} {o} is left open.")


def items(w: dict[str, Any], f: Field, tagged: dict[str, Any], papers_md: dict[str, str] | None = None,
          seed: int = 0) -> list[dict[str, Any]]:
    """Every test item for the papers in tagged ({pid: {"sentences": [[a, b, text], ...]}}). papers_md (optional)
    gives the paper text, so that terms a paper defines are found as names too."""
    rng = random.Random(seed)
    ents = w["entities"]
    base = alias_table(w, f)
    truth = {(s, o): r for p in w["papers"].values() for s, r, o in p["claims"] + p["decoys"]}
    possible = lambda s, o: [r for r in f.relations if not fact_errors((s, r, o), ents, f)]  # noqa: E731
    out: list[dict[str, Any]] = []
    for pid, t in tagged.items():
        md = (papers_md or {}).get(pid)
        table = alias_table(w, f, defined_terms(normalize_paper(md).text, base, f)) if md else base
        planted = [tuple(x) for x in w["papers"].get(pid, {}).get("claims", []) + w["papers"].get(pid, {}).get(
            "decoys", [])]
        S = t["sentences"]
        for n, (_, _, sent) in enumerate(S):
            ctx = S[n - 1][2] if n else ""
            named = list(dict.fromkeys(m.eid for m in find_mentions(sent, table)))
            pairs = [(a, b) for a in named for b in named if a != b and ents[a]["kind"] in f.subject_kinds
                     and possible(a, b)]

            def add(kind: str, s: str, r: str, o: str, sentence: str = sent, context: str = ctx) -> None:
                out.append({"field": f.name, "paper": pid, "n": n, "kind": kind, "s": s, "r": r, "o": o,
                            "sentence": sentence, "context": context})
            for a, b in pairs:
                true = truth.get((a, b))
                if true:
                    add("candidate", a, true, b)
                else:
                    for r in possible(a, b):
                        add("no_world_rel", a, r, b)
                for r in f.relations:
                    if r == true:
                        continue
                    if fact_errors((a, r, b), ents, f):
                        add("impossible_pair", a, r, b)
                    elif true:
                        add("other_relation", a, r, b)
                for s, r, o in planted:
                    if len({s, o} & {a, b}) == 1 and not {s, o} <= set(named):
                        add("decoy", s, r, o)
                r = true or rng.choice(possible(a, b))
                tpl = rng.choice(NOT_RECORDED)
                add("not_recorded", a, r, b, tpl.format(s=ents[a]["label"], o=ents[b]["label"], w=f.rel_words(r)), "")
    seen: set[tuple] = set()
    uniq = []
    for it in out:
        k = (it["paper"], it["sentence"], it["s"], it["r"], it["o"])
        if k not in seen:
            seen.add(k)
            uniq.append(it)
    return uniq


def sample(its: list[dict[str, Any]], per_field: int, seed: int = 0) -> list[dict[str, Any]]:
    """per_field items per field, spread evenly over the kinds (round robin over shuffled kinds), plus up to
    max(10, per_field // 10) impossible pairs, which are reported apart."""
    rng = random.Random(seed)
    picked: list[dict[str, Any]] = []
    for fld in sorted({it["field"] for it in its}):
        mine = [it for it in its if it["field"] == fld]
        by_kind = {k: [it for it in mine if it["kind"] == k] for k in KINDS if k != "impossible_pair"}
        for xs in by_kind.values():
            rng.shuffle(xs)
        take: list[dict[str, Any]] = []
        while len(take) < per_field and any(by_kind.values()):
            for xs in by_kind.values():
                if xs and len(take) < per_field:
                    take.append(xs.pop())
        imp = [it for it in mine if it["kind"] == "impossible_pair"]
        take += rng.sample(imp, min(len(imp), max(10, per_field // 10)))
        picked += sorted(take, key=lambda it: (it["paper"], it["n"], it["kind"] == "not_recorded", it["s"], it["r"],
                                               it["o"]))
    return picked


def export(w: dict[str, Any], f: Field, tagged: dict[str, Any], dest: Path, per_field: int = 200,
           papers_md: dict[str, str] | None = None, seed: int = 0) -> dict[str, Any]:
    """Write dest (CSV, label column empty) and dest.key.json. Returns counts per kind."""
    rows = sample(items(w, f, tagged, papers_md, seed), per_field, seed)
    ents = w["entities"]
    key = {}
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=COLUMNS)
        wr.writeheader()
        for i, it in enumerate(rows):
            rid = f"{it['field']}-{i + 1:04d}"
            key[rid] = it
            wr.writerow({"id": rid, "field": it["field"], "paper": it["paper"], "sentence": it["sentence"],
                         "context": it["context"], "subject": ents[it["s"]]["label"], "relation": it["r"],
                         "object": ents[it["o"]]["label"], "label": "", "notes": ""})
    key_path(dest).write_text(json.dumps(key, indent=1, ensure_ascii=False), encoding="utf-8")
    counts: dict[str, int] = {}
    for it in rows:
        counts[it["kind"]] = counts.get(it["kind"], 0) + 1
    return {"rows": len(rows), "by_kind": counts, "csv": str(dest), "key": str(key_path(dest))}


def key_path(csv_path: Path) -> Path:
    return csv_path.with_name(csv_path.stem + ".key.json")


def verifier_answers(ev, key: dict[str, Any]) -> dict[str, str | None]:
    """The verifier's answer for every item (model calls; evaluate.Eval.verify): yes / no / None (parse_error)."""
    ids = sorted(key)
    got = ev.verify([(key[i]["context"], key[i]["sentence"], {"s": key[i]["s"], "r": key[i]["r"], "o": key[i]["o"]})
                     for i in ids], "label_test")
    return {i: None if g is None else "yes" if g else "no" for i, g in zip(ids, got)}


# ------------------------------------------------------------------ metrics
def read_labels(path: Path) -> dict[str, str | None]:
    """id -> "yes" / "no" / None (empty or anything else)."""
    norm = {"yes": "yes", "y": "yes", "1": "yes", "true": "yes", "no": "no", "n": "no", "0": "no", "false": "no"}
    with path.open(newline="", encoding="utf-8") as fh:
        return {r["id"]: norm.get((r.get("label") or "").strip().lower()) for r in csv.DictReader(fh)}


def kappa(a: dict[str, str | None], b: dict[str, str | None]) -> dict[str, Any]:
    """Cohen's kappa on the items both labelers labeled."""
    both = [(a[i], b[i]) for i in a if i in b and a[i] and b[i]]
    n = len(both)
    if not n:
        return {"n": 0, "agree": 0, "kappa": None}
    po = sum(x == y for x, y in both) / n
    pe = sum((sum(x == c for x, _ in both) / n) * (sum(y == c for _, y in both) / n) for c in ("yes", "no"))
    return {"n": n, "agree": sum(x == y for x, y in both), "observed": round(po, 3),
            "kappa": None if pe == 1 else round((po - pe) / (1 - pe), 3)}


def _rate(h: int, n: int) -> dict[str, Any]:
    return {"value": round(h / n, 3) if n else None, "of": n, "ci95": wilson(h, n)}


def scores(pairs: list[tuple[str, str | None]]) -> dict[str, Any]:
    """pairs: (gold label, verifier answer). Answers that are missing or parse errors are counted, not scored."""
    done = [(g, v) for g, v in pairs if v in ("yes", "no")]
    tp = sum(g == "yes" and v == "yes" for g, v in done)
    fp = sum(g == "no" and v == "yes" for g, v in done)
    fn = sum(g == "yes" and v == "no" for g, v in done)
    tn = sum(g == "no" and v == "no" for g, v in done)
    return {"n": len(pairs), "unanswered": len(pairs) - len(done), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": _rate(tp, tp + fp), "recall": _rate(tp, tp + fn),
            "false_accept": _rate(fp, fp + tn), "false_reject": _rate(fn, fn + tp)}


def metrics(labels: list[dict[str, str | None]], key: dict[str, Any], answers: dict[str, str | None]) -> dict[str, Any]:
    """labels: one {id: label} per labeler. The gold label of an item is the labelers' label when all who labeled it
    agree; items they disagree on are counted and left out. Impossible pairs are reported apart."""
    gold: dict[str, str] = {}
    disagree = 0
    for i in key:
        got = {lab[i] for lab in labels if lab.get(i)}
        if len(got) == 1:
            gold[i] = got.pop()
        elif got:
            disagree += 1
    agreement = [{"labelers": [x, y], **kappa(labels[x], labels[y])}
                 for x in range(len(labels)) for y in range(x + 1, len(labels))]

    def by(field: str, ids: list[str]) -> dict[str, Any]:
        return {v: scores([(gold[i], answers.get(i)) for i in ids if key[i][field] == v])
                for v in sorted({key[i][field] for i in ids})}
    main = [i for i in gold if key[i]["kind"] != "impossible_pair"]
    imp = [i for i in gold if key[i]["kind"] == "impossible_pair"]
    return {"items": len(key), "labeled": len(gold), "labelers_disagree": disagree, "agreement": agreement,
            "overall": scores([(gold[i], answers.get(i)) for i in main]),
            "by_field": by("field", main), "by_relation": by("r", main), "by_kind": by("kind", main),
            "impossible_pairs": scores([(gold[i], answers.get(i)) for i in imp]),
            "note": "impossible pairs (relations the pack does not allow for the pair) are left out of the overall "
                    "numbers: a verifier gets them right without reading the sentence"}


# ------------------------------------------------------------------ file entry points (cli)
def export_run(out: Path, f: Field, dest: Path, per_field: int = 200, seed: int = 0) -> dict[str, Any]:
    """export() from a run folder (world.json, tagged.json, work/<paper>/paper.md)."""
    w = json.loads((out / "world.json").read_text(encoding="utf-8"))
    tagged = json.loads((out / "tagged.json").read_text(encoding="utf-8"))["papers"]
    md = {p: (out / "work" / p / "paper.md").read_text(encoding="utf-8") for p in tagged
          if (out / "work" / p / "paper.md").is_file()}
    return export(w, f, tagged, dest, per_field, md, seed)


def metrics_files(label_csvs: list[Path], key_file: Path | None, answers_file: Path, make_eval=None) -> dict[str, Any]:
    """metrics() from files. With make_eval (a function returning an evaluate.Eval) and no answers file yet, the
    verifier is asked first (model calls) and its answers are written to answers_file."""
    key = json.loads((key_file or key_path(label_csvs[0])).read_text(encoding="utf-8"))
    if make_eval is not None and not answers_file.is_file():
        answers_file.write_text(json.dumps(verifier_answers(make_eval(), key), indent=1), encoding="utf-8")
    answers = json.loads(answers_file.read_text(encoding="utf-8"))
    return metrics([read_labels(p) for p in label_csvs], key, answers)

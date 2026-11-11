"""SciREX real-paper check (D21, spec 6.12): how well the engine finds the names of methods, datasets, tasks and
metrics in real ML papers (Jain et al., ACL 2020, github.com/allenai/SciREX).

`to_corpus` turns SciREX JSON lines into a corpus (manifest.json, papers/<doc_id>.md) plus the gold, which only
`score` reads (D31). A paper's text is its words joined by single spaces, its sections joined by a blank line, so
every token span maps exactly to a character span. SciREX spans are token index pairs, start inclusive and end
exclusive.

What the gold holds, per paper: `ner` (typed mentions), `coref` (clusters: a name and its mention spans) and
`n_ary_relations` (dicts of type -> cluster name, plus a score). The SciREX README defines `coref` as "Salient
Entities in the document and mentions belonging to it", so every coref cluster is salient. Its type is the relation
key it is named under, else the `ner` type of a mention at one of its spans; a cluster with neither is left out and
counted. How many clusters a relation filter would drop (no relation names them) is counted too, so a real run shows
whether "coref" and "named in a relation" differ. SciREX calls datasets "Material"; "Dataset" is taken too.

`score` counts per name type, at two levels:
  mention   an item is right when one of its spans overlaps a gold mention of its type in its paper; precision is
            right items over items, recall matched mentions over mentions;
  salient   (headline) a name is right when its `names.clean` form equals the cleaned text of a mention of a
            salient cluster of its type in its paper; precision is distinct right names over distinct names (per
            paper), recall clusters hit over salient clusters.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from evidence.names import clean
from evidence.pack import RoleMap, load_pack
from evidence.rundir import PaperIndex
from jsonio import sha256_hex

from ..wholerun import RealQuestion
from .common import (add_paper, items_of, manifest_ids, ratio, read_json, write_json,
                     write_manifest)

GOLD_FILE = "scirex_gold.json"
SOURCE_FILE = "scirex_corpus.json"
PACK = "ml"
# SciREX type -> the ml pack's type
TYPES = {"Method": "method", "Material": "dataset", "Dataset": "dataset", "Task": "task", "Metric": "metric"}
NAME_TYPES = ("method", "dataset", "task", "metric")
DOC_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")   # a file name, never a path
GOLD_NOTES = [
    "gold per paper: ner (typed mentions), coref (clusters: a name and its mention spans), n_ary_relations "
    "(type -> cluster name, plus a score)",
    "salient cluster: every coref cluster (SciREX README: coref is \"Salient Entities in the document and mentions "
    "belonging to it\"); its type is the relation key it is named under, else the ner type of a mention at its span",
    "clusters_in_no_relation: coref clusters no n_ary_relation names (a relation filter would drop them); they are "
    "salient here",
    "clusters_untyped: coref clusters named in no relation and with no ner mention at their spans; left out",
    "clusters_without_spans: salient clusters with no mention span; they count in the recall denominator and can "
    "never be hit",
    "SciREX labels datasets Material; mapped to dataset",
    "the gold is read by this scorer only; the engine run reads manifest.json and papers/ (D31)",
]


def _text(words: list[str], sections: list[list[int]]) -> tuple[str, list[tuple[int, int]]]:
    """The paper text and each token's character span. Sections must cover the words in order, without gaps."""
    bounds = [(int(a), int(b)) for a, b in sections] or [(0, len(words))]
    at = 0
    for a, b in bounds:
        if a != at or b < a:
            raise ValueError(f"sections {bounds} do not cover the {len(words)} words in order")
        at = b
    if at != len(words):
        raise ValueError(f"sections {bounds} do not cover the {len(words)} words in order")
    parts, chars, pos = [], [], 0
    for n, (a, b) in enumerate(bounds):
        if n:
            pos += 2   # "\n\n"
        part = []
        for w in words[a:b]:
            if part:
                pos += 1
            chars.append((pos, pos + len(w)))
            pos += len(w)
            part.append(w)
        parts.append(" ".join(part))
    return "\n\n".join(parts), chars


def _chars(tokens: list[tuple[int, int]], start: int, end: int) -> tuple[int, int]:
    if not 0 <= start < end <= len(tokens):
        raise ValueError(f"token span [{start}, {end}) is not inside the {len(tokens)} words")
    return tokens[start][0], tokens[end - 1][1]


def _type(label: str) -> str:
    if label not in TYPES:
        raise ValueError(f"unknown SciREX type {label!r}; known: {sorted(TYPES)}")
    return TYPES[label]


def paper_gold(doc: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """(text, gold) of one SciREX JSON line."""
    text, tokens = _text(list(doc["words"]), doc.get("sections") or [])
    mentions = []
    for start, end, label in doc.get("ner", []):
        s, e = _chars(tokens, int(start), int(end))
        mentions.append([s, e, _type(str(label)), text[s:e]])
    mentions.sort(key=lambda m: (m[0], m[1]))
    clusters = {str(name): [list(_chars(tokens, int(a), int(b))) for a, b in spans]
                for name, spans in (doc.get("coref") or {}).items()}
    types: dict[str, str] = {}
    for relation in doc.get("n_ary_relations", []):
        for label, name in relation.items():
            if label in TYPES and str(name) in clusters:
                types.setdefault(str(name), TYPES[label])
    in_no_relation = sorted(n for n in clusters if n not in types)
    by_span = {(m[0], m[1]): m[2] for m in reversed(mentions)}   # the first mention at a span wins
    for name in in_no_relation:
        found = next((by_span[(a, b)] for a, b in clusters[name] if (a, b) in by_span), None)
        if found is not None:
            types[name] = found
    salient = sorted(types)
    return text, {"mentions": mentions, "clusters": clusters, "salient": salient,
                  "types": {name: types[name] for name in salient}, "in_no_relation": in_no_relation,
                  "untyped": sorted(n for n in clusters if n not in types)}


def to_corpus(jsonl: Path, out: Path, *, limit: int | None = None) -> Path:
    """Write the corpus of the first `limit` papers of `jsonl` (all when None) to `out`: manifest.json,
    papers/<doc_id>.md, the gold (scirex_gold.json, `{doc: {mentions: [[start, end, type, text]], clusters:
    {name: [[start, end]]}, salient: [name], types: {salient name: type}, in_no_relation: [name], untyped:
    [name]}}`) and scirex_corpus.json (the source file, its sha256, the papers in it, the limit and the cluster
    counts). Returns `out`."""
    if limit is not None and limit < 1:
        raise ValueError(f"limit must be at least 1, not {limit}")
    raw = Path(jsonl).read_bytes()
    lines = [line for line in raw.decode("utf-8").splitlines() if line.strip()]
    chosen = lines if limit is None else lines[:limit]
    (out / "papers").mkdir(parents=True, exist_ok=True)
    papers, gold = [], {}
    for line in chosen:
        doc = json.loads(line)
        doc_id = str(doc["doc_id"])
        if not DOC_ID.match(doc_id) or doc_id in gold:
            raise ValueError(f"doc_id {doc_id!r} is not a plain file name or occurs twice")
        try:
            text, gold[doc_id] = paper_gold(doc)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"SciREX paper {doc_id}: {type(exc).__name__}: {exc}") from exc
        papers.append(add_paper(out, doc_id, text.encode("utf-8")))
    write_manifest(out, f"scirex-{Path(jsonl).stem}", papers)
    write_json(out / GOLD_FILE, gold)
    write_json(out / SOURCE_FILE, {"jsonl": Path(jsonl).name, "jsonl_sha256": sha256_hex(raw),
                                   "papers_in_file": len(lines), "limit": limit, "papers": len(papers),
                                   "coref_clusters": sum(len(g["clusters"]) for g in gold.values()),
                                   "clusters_in_no_relation": sum(len(g["in_no_relation"]) for g in gold.values()),
                                   "clusters_untyped": sum(len(g["untyped"]) for g in gold.values()),
                                   "clusters_without_spans": sum(not g["clusters"][n] for g in gold.values()
                                                                 for n in g["salient"])})
    return out


def _overlaps(s: int, e: int, gs: int, ge: int) -> bool:
    return s < ge and gs < e


def score(run_dir: Path, corpus: Path) -> dict[str, Any]:
    """Mention-level and salient-cluster-level precision and recall per name type (module docstring), and the
    number of papers."""
    gold: dict[str, Any] = read_json(Path(corpus) / GOLD_FILE)
    papers = PaperIndex.of_corpus(corpus)
    roles = RoleMap(load_pack(PACK))
    # per (doc, type): the items' spans and names
    spans: dict[tuple[str, str], list[list[tuple[int, int]]]] = {}
    names: dict[tuple[str, str], set[str]] = {}
    for item in items_of(run_dir):
        if item.evidence_type not in NAME_TYPES:
            continue
        doc = papers.of(item)   # a run of another corpus: UnknownPaper rather than scored against the wrong gold
        if doc not in gold:
            raise ValueError(f"item {item.item_id} is in paper {doc!r}, no paper of the gold of {corpus}")
        key = (doc, item.evidence_type)
        spans.setdefault(key, []).append([(int(s.selector["start"]), int(s.selector["end"])) for s in item.spans
                                          if s.selector.get("file") == item.spans[0].selector.get("file")])
        name = item.fields.get(roles.field(item.evidence_type, "name"))
        if name is not None and str(name).strip():
            names.setdefault(key, set()).add(clean(str(name)))
    mention = {t: _mention_level(t, gold, spans) for t in NAME_TYPES}
    texts = {doc: (Path(corpus) / f"papers/{doc}.md").read_bytes().decode("utf-8") for doc in gold}
    salient = {t: _salient_level(t, gold, texts, names) for t in NAME_TYPES}
    return {"papers": len(gold), "mention": mention, "salient": salient}


def _mention_level(etype: str, gold: dict[str, Any], spans: dict[tuple[str, str], list[list[tuple[int, int]]]]) -> dict[str, Any]:
    items = right = mentions = matched = 0
    for doc, g in gold.items():
        theirs = [(s, e) for s, e, t, _ in g["mentions"] if t == etype]
        ours = spans.get((doc, etype), [])
        items += len(ours)
        right += sum(any(_overlaps(s, e, gs, ge) for s, e in item for gs, ge in theirs) for item in ours)
        mentions += len(theirs)
        matched += sum(any(_overlaps(s, e, gs, ge) for item in ours for s, e in item) for gs, ge in theirs)
    return {"items": items, "right_items": right, "mentions": mentions, "matched_mentions": matched,
            "precision": ratio(right, items), "recall": ratio(matched, mentions)}


def _salient_level(etype: str, gold: dict[str, Any], papers: dict[str, str],
                   names: dict[tuple[str, str], set[str]]) -> dict[str, Any]:
    found = right = clusters = hit = 0
    for doc, g in gold.items():
        texts = {}   # salient cluster of this type -> the cleaned texts of its mentions
        for name in g["salient"]:
            if g["types"][name] == etype:
                texts[name] = {clean(papers[doc][s:e]) for s, e in g["clusters"][name]}
        ours = names.get((doc, etype), set())
        allowed = set().union(*texts.values()) if texts else set()
        found += len(ours)
        right += len(ours & allowed)
        clusters += len(texts)
        hit += sum(bool(ours & t) for t in texts.values())
    return {"names": found, "right_names": right, "clusters": clusters, "clusters_hit": hit,
            "precision": ratio(right, found), "recall": ratio(hit, clusters)}


def report(run_dir: Path, corpus: Path, estimate: dict[str, Any] | None = None) -> dict[str, Any]:
    """The real.json of the check: `score`, where the papers came from (scirex_corpus.json: the file, the papers in
    it, the limit), the saved `evidence estimate` output that chose the limit (None when not given) and the notes
    on what the gold holds."""
    source = read_json(Path(corpus) / SOURCE_FILE)
    result = score(run_dir, corpus)
    chosen = ("--limit chosen with `evidence estimate` (Task 5), whose output is under `estimate`" if estimate is not None
              else "no `evidence estimate` output given: the --limit was not checked against the budget")
    return {"papers": result["papers"], "papers_in_file": source["papers_in_file"], "limit": source["limit"],
            "source": source["jsonl"], "source_sha256": source["jsonl_sha256"], "run": Path(run_dir).name,
            **{k: source[k] for k in ("coref_clusters", "clusters_in_no_relation", "clusters_untyped",
                                      "clusters_without_spans")},
            "salient": result["salient"], "mention": result["mention"], "estimate": estimate,
            "notes": [chosen, "headline: the salient-cluster level", *GOLD_NOTES]}


def questions(src: Path, corpus_dir: Path | None = None) -> list[RealQuestion]:
    """The whole-run questions of a SciREX JSON-lines file: one per task named in a relation with at least two
    distinct datasets, "Which datasets are used for <task>?"; gold = those datasets (the relations' dataset
    names, cleaned of the file's underscores), `papers` = the documents holding such a relation. Field `cs`;
    the corpus is `corpus_dir` (default: the file's folder, where `to_corpus` writes it)."""
    tasks: dict[str, dict[str, set[str]]] = {}
    corpus = Path(corpus_dir) if corpus_dir is not None else Path(src).parent
    in_corpus = _in_corpus(corpus)
    for line in Path(src).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        doc = json.loads(line)
        if in_corpus is not None and str(doc["doc_id"]) not in in_corpus:
            continue        # a dataset used only in a paper outside the corpus cannot be found: not in the gold
        for relation in doc.get("n_ary_relations", []):
            dataset = relation.get("Material") or relation.get("Dataset")
            task = relation.get("Task")
            if task and dataset:
                tasks.setdefault(str(task).replace("_", " "), {}).setdefault(str(dataset).replace("_", " "),
                                                                             set()).add(str(doc["doc_id"]))
    keys = truth_items(src, corpus)
    out = []
    for task in sorted(tasks):
        datasets = tasks[task]
        if len(datasets) < 2:
            continue
        out.append(RealQuestion(
            id=f"scirex-{len(out) + 1:03d}", question=f"Which datasets are used for {task}?", field="cs",
            corpus_dir=corpus, kind="list",
            gold={"items": sorted(datasets), "papers": sorted(set().union(*datasets.values())), "task": task},
            records=[r for r in keys if r["settings"]["task"] == task]))
    return out


def _in_corpus(corpus: Path | None) -> set[str] | None:
    """The document ids of `corpus/manifest.json`; None when there is no manifest (then every document counts)."""
    ids = manifest_ids(corpus)
    return set(ids) if ids is not None else None


def left_out(src: Path, corpus_dir: Path | None = None, qs: list[RealQuestion] | None = None) -> str:
    """The report line of the gold filter: relations of documents that are not in the corpus (with no manifest: 0).
    arXiv papers are all open, so only the gold of documents outside the corpus is left out."""
    in_corpus = _in_corpus(Path(corpus_dir) if corpus_dir is not None else Path(src).parent)
    total = gone = 0
    for line in Path(src).read_text(encoding="utf-8").splitlines():
        if line.strip():
            doc = json.loads(line)
            n = len(doc.get("n_ary_relations", []))
            total += n
            gone += n if in_corpus is not None and str(doc["doc_id"]) not in in_corpus else 0
    return f"left out: {gone} of {total} relations (document not in the corpus)"


def truth_items(src: Path, corpus_dir: Path | None = None) -> list[dict[str, Any]]:
    """The answer-key records of a SciREX file (one per relation with a method, a dataset and a score): thing = the
    method, metric, number = the score, context = the dataset, settings task and dataset (keystore.py). With a
    `corpus_dir` holding manifest.json, only documents in the manifest."""
    out = []
    in_corpus = _in_corpus(corpus_dir)
    for line in Path(src).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        doc = json.loads(line)
        if in_corpus is not None and str(doc["doc_id"]) not in in_corpus:
            continue
        for rel in doc.get("n_ary_relations", []):
            dataset = rel.get("Material") or rel.get("Dataset")
            try:
                number = float(str(rel.get("score")).rstrip("%"))
            except ValueError:
                continue
            if not (rel.get("Method") and dataset and rel.get("Metric")):
                continue
            out.append({"paper": str(doc["doc_id"]), "thing": str(rel["Method"]).replace("_", " "),
                        "metric": str(rel["Metric"]).replace("_", " "), "number": number, "higher_is_better": None,
                        "context": str(dataset).replace("_", " "),
                        "settings": {"task": str(rel.get("Task", "")).replace("_", " "),
                                     "dataset": str(dataset).replace("_", " ")}})
    return out


def prepare_step(jsonl: Path, out: Path, limit: int | None = None) -> str:
    """`evaluate scirex corpus`: write the corpus; its SOURCE_FILE is printed."""
    return json.dumps(read_json(to_corpus(jsonl, out, limit=limit) / SOURCE_FILE), indent=1)


def check_step(run: Path, corpus: Path, estimate: Path | None = None) -> dict[str, Any]:
    """`evaluate scirex score`: the real.json result."""
    return report(run, corpus, read_json(estimate) if estimate else None)

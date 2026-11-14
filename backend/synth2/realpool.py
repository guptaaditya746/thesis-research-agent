"""Real papers for the synthetic-paper tests: split a paper set into test and source pools, clean Docling markdown,
and cut papers (real or synthetic) into pieces of about 1,000 words."""
from __future__ import annotations

import html
import json
import random
import re
from pathlib import Path

POOL_TOPIC = re.compile(r"retriev", re.I)
QA = re.compile(r"retrieval[- ]?augment|\bRAG\b|open[- ]domain|knowledge[- ]intensive|"
                r"retrieved (?:documents|passages|evidence|contexts)", re.I)
N_TEST = 30  # of the close-topic papers; the rest stay as the closest sources
SPLIT_SEED = "hf-split-v2"

TARGET, LOW, HIGH = 1000, 800, 1100
BODY_CAP = 1040  # window size before the title line is added
CUT_TOPIC = re.compile(
    r"closed[- ]book|no[- ]retrieval|without retrieval|w/o retrieval|parametric|retriev|exact match|\bEM\b|"
    r"accuracy|no context|zero[- ]shot|baseline", re.I)

KNOWN = re.compile(r"^(introduction|related work|background|method(s|ology)?|approach|experiments?|"
                   r"experimental (setup|settings?|results)|results|analysis|discussion|conclusions?|"
                   r"conclusion and future work|limitations|ethics statement|ethical considerations|broader impact|"
                   r"future work|evaluation|datasets?)\b", re.I)
START = re.compile(r"^(1\.?|I\.?)\s+\S|^introduction\b", re.I)
STOP = re.compile(r"^(references|bibliography)\b", re.I)
DROP = re.compile(r"acknowledg|author contributions", re.I)
NUM = re.compile(r"^((?:[A-Z]|\d+)(?:\.\d+)*)\.?\s+(\S.*)$")
FOOTNOTE_MARK = re.compile("^[*∗†‡§¶]")


def read_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def split_pool(rows: list[dict], old: dict) -> dict:
    """Test papers (old eval papers in the set, then a seeded draw from the QA side) and the source pool.
    Old style papers (their paragraphs were shown to writers) go to neither side."""
    style, old_eval = set(old["style"]), set(old["eval"])
    meta = {r["arxiv_id"]: r for r in rows}
    pool = [i for i, r in meta.items() if POOL_TOPIC.search(r["title"] + " " + r["summary"])]
    qa = [i for i in pool if QA.search(meta[i]["title"] + " " + meta[i]["summary"])
          and meta[i]["published"][:4] >= "2020" and i not in style]
    test = sorted(i for i in pool if i in old_eval)
    rnd = random.Random(SPLIT_SEED)
    rest = sorted(set(qa) - set(test))
    rnd.shuffle(rest)
    test += rest[:N_TEST - len(test)]
    sources = sorted(set(pool) - set(test) - style)
    return {"seed": SPLIT_SEED, "test": sorted(test), "sources": sources,
            "old_eval_in_test": sorted(set(test) & old_eval), "style_excluded": sorted(set(pool) & style),
            "counts": {"topic_pool": len(pool), "qa_side": len(qa), "test": len(test), "sources": len(sources)}}


def split_file(rows_path: Path, old_path: Path, out_path: Path) -> dict:
    out = split_pool(read_rows(rows_path), json.loads(old_path.read_text(encoding="utf-8")))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def words(text: str) -> int:
    return len(text.split())


def clean_text(b: str) -> str:
    b = html.unescape(b).replace("\\_", "_")
    if b.lstrip().startswith("|"):  # tables: compact cells ("| a | b |", "|---|---|")
        rows = []
        for ln in b.splitlines():
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            rows.append("|" + "---|" * len(cells) if all(re.fullmatch(r":?-+:?", c) for c in cells)
                        else "| " + " | ".join(cells) + " |")
        return "\n".join(rows)
    b = re.sub(r"([a-z])- ([a-z])", r"\1\2", b)
    b = re.sub(r"\b(e\.g|i\.e|cf|resp)\s+\.", r"\1.", b)
    b = re.sub(r"\s+([,.;:)\]])", r"\1", b)
    b = re.sub(r"([(\[])\s+", r"\1", b)
    return re.sub(r"[ \t]+", " ", b).strip()


def body_blocks(content: str) -> list[tuple[str, str]]:
    """(section, markdown block) for the body of a Docling paper: from the first "1 ..."/Introduction heading to
    References. Comment markers, figure captions, footnote lines and acknowledgement sections are dropped."""
    out, section, started, skip = [], "", False, False
    for raw in re.split(r"\n\s*\n", content):
        b = re.sub(r"<!--.*?-->", "", raw).strip()
        if not b:
            continue
        m = re.match(r"^#{1,6}\s+(.*)$", b.splitlines()[0])
        if m:
            title = m.group(1).strip()
            n = NUM.match(title)
            if not started:
                if START.search(title):
                    started = True
                else:
                    continue
            if STOP.search(title):
                break
            if n and len(n.group(2)) < 120 and not n.group(2).endswith("."):
                depth = n.group(1).count(".") + 2
                name = n.group(2).strip()
                if depth == 2:
                    section, skip = name, bool(DROP.search(name))
                if not skip:
                    out.append((section, "#" * min(depth, 4) + " " + name))
                continue
            if KNOWN.search(title) or DROP.search(title):
                section, skip = title, bool(DROP.search(title))
                if not skip:
                    out.append((section, "## " + title))
                continue
            b = title  # bold run-in text or figure text turned into a heading: keep as a paragraph
        if not started or skip:
            continue
        if re.match(r"^(Figure|Fig\.)\s*\d+", b) or FOOTNOTE_MARK.match(b) or re.match(r"^\d+\s*https?://", b):
            continue
        out.append((section, clean_text(b)))
    return out


def windows(body: list[tuple[str, str]]) -> list[list[int]]:
    """Consecutive runs of block indexes, each up to about TARGET words."""
    runs, cur, n = [], [], 0
    for i, (_, b) in enumerate(body):
        w = words(b)
        if cur and n + w > BODY_CAP:
            runs.append(cur)
            cur, n = [], 0
        cur.append(i)
        n += w
    if cur:
        runs.append(cur)
    return runs


def score(idx: list[int], body) -> float:
    text = " ".join(body[i][1] for i in idx)
    return len(CUT_TOPIC.findall(text)) + 3 * sum(b.lstrip().startswith("|") or "\n|" in b
                                                  for _, b in (body[i] for i in idx))


def with_headings(idx: list[int], body) -> str:
    """Join blocks, re-adding the section heading when a piece starts mid-section."""
    first_section = body[idx[0]][0]
    parts = [] if body[idx[0]][1].startswith("#") else [f"## {first_section}"] if first_section else []
    return "\n\n".join(parts + [body[i][1] for i in idx])


def trim(idx: list[int], body, budget: int) -> list[int]:
    keep, n = [], 0
    for i in idx:
        w = words(body[i][1])
        if keep and n + w > budget:
            break
        keep.append(i)
        n += w
    return keep


def cut_pieces(title: str, abstract: list[str], body: list[tuple[str, str]]) -> list[str]:
    """Up to three pieces: title + abstract + the most on-topic stretch, then the next most on-topic stretches,
    each headed by the title. Word limits are not applied here."""
    ranked = sorted(windows(body), key=lambda w: -score(w, body))
    pieces = []
    head = "\n\n".join([title] + abstract)
    if ranked:
        first = trim(ranked[0], body, TARGET - words(head))
        pieces.append(head + "\n\n" + with_headings(first, body))
        for w in ranked[1:]:
            if len(pieces) == 3 or score(w, body) == 0:
                break
            pieces.append(title + "\n\n" + with_headings(w, body))
    return pieces


def write_pieces(name: str, pieces: list[str], dst: Path, index: list[dict], notes: list[str]) -> None:
    """Write the pieces inside LOW..HIGH words as <name>_pN.md; add them to `index`, say why others were left out."""
    for k, text in enumerate(pieces, 1):
        n = words(text)
        if LOW <= n <= HIGH:
            file = f"{name}_p{k}.md"
            (dst / file).write_text(text, encoding="utf-8")
            index.append({"piece": file, "paper": name, "words": n})
        else:
            notes.append(f"{name} piece {k} skipped: {n} words")


def cut_side(rows_path: Path, split_path: Path, side: str, dst: Path) -> dict:
    """Clean the papers of one side of the split. Writes <dst>/full/<id>.md and, for side 'test',
    <dst>/pieces/<id>_pN.md with index.json. Returns {"pieces", "papers", "full", "no_body", "notes"}."""
    want = set(json.loads(split_path.read_text(encoding="utf-8"))[side])
    (dst / "full").mkdir(parents=True, exist_ok=True)
    if side == "test":
        (dst / "pieces").mkdir(parents=True, exist_ok=True)
    index, no_body, notes = [], [], []
    for r in read_rows(rows_path):
        pid = r["arxiv_id"]
        if pid not in want:
            continue
        title = "# " + re.sub(r"\s+", " ", r["title"]).strip()
        abstract = ["## Abstract", re.sub(r"\s+", " ", r["summary"]).strip()]
        body = body_blocks(r["content"])
        if not body:
            no_body.append(pid)
            continue
        (dst / "full" / f"{pid}.md").write_text("\n\n".join([title] + abstract + [b for _, b in body]),
                                                encoding="utf-8")
        if side == "test":
            write_pieces(pid, cut_pieces(title, abstract, body), dst / "pieces", index, notes)
    if side == "test":
        (dst / "pieces" / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    return {"pieces": len(index), "papers": len({x["paper"] for x in index}),
            "full": len(list((dst / "full").glob("*.md"))), "no_body": no_body, "notes": notes}


def md_blocks(text: str) -> list[tuple[str, str]]:
    """Blocks of one of our markdown papers: the title stays, the author line under it is dropped, section
    numbers are stripped from headings."""
    out, section, after_title = [], "", False
    for raw in re.split(r"\n\s*\n", text):
        b = raw.strip()
        if not b:
            continue
        if b.startswith("# "):
            out.append(("", b.splitlines()[0]))
            rest = "\n".join(b.splitlines()[1:]).strip()
            after_title = True
            if rest and not re.search(r"et al\.|\(\d{4}\)", rest):
                out.append(("", rest))
            continue
        if after_title and len(b) < 200 and re.search(r"et al\.|\(\d{4}\)|^\*", b) and not b.startswith("#"):
            after_title = False  # the author line
            continue
        after_title = False
        m = re.match(r"^(#{2,4})\s+(.*)", b)
        if m:
            level, title = len(m.group(1)), re.sub(r"^[A-Z]?\d*(\.\d+)*\s+", "", m.group(2)).strip()
            if level == 2:
                section = "Abstract" if title.lower().startswith("abstract") else title
            out.append((section, "#" * level + " " + title))
            body = "\n".join(b.splitlines()[1:]).strip()
            if body:
                out.append((section, body))
            continue
        out.append((section, b))
    return out


def slice_papers(src: Path, dst: Path) -> dict:
    """Cut every S*.md paper in `src` into pieces with the rules used for the real papers; writes index.json."""
    dst.mkdir(parents=True, exist_ok=True)
    index, notes = [], []
    for f in sorted(src.glob("S*.md")):
        bl = md_blocks(f.read_text(encoding="utf-8"))
        title = next((b for _, b in bl if b.startswith("# ")), f"# {f.stem}")
        abstract = [b for s, b in bl if s == "Abstract"]
        body = [(s, b) for s, b in bl if s not in ("", "Abstract")]
        write_pieces(f.stem, cut_pieces(title, abstract, body), dst, index, notes)
    (dst / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    return {"pieces": len(index), "papers": len({x["paper"] for x in index}), "notes": notes}

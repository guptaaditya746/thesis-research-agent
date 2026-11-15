"""Real-edit papers: take a real source paper, rename every name in it (seeded), let a writer plant the study with
a small set of edits, and check the result in code and against a blind reader's notes.

Renaming: names are acronyms, CamelCase and names with digits (NAME), cited surnames, and proper nouns (a
capitalised word that follows a lower-case word and never appears in lower case in the source). Each name is split
on hyphens; every component is mapped once per paper, so "FiD" and "FiD-RAG" stay consistent. A component keeps its
shape: letter case, vowel/consonant pattern, digits and length; generic field words (KEEP) and lower-case or digit
components are kept. URLs become invented ones.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
from pathlib import Path

from synth2.realpool import QA, read_rows

# Generic field words and algorithms that are not a person, paper, model or dataset name.
ALLOWED = set("""LLM LLMs LM LMs QA NLP RAG EM F1 IR ID IDs API APIs GPU GPUs CPU BM25 TF-IDF AI ML NLI MLP ANN
kNN k-NN AdamW FAISS ROUGE ROUGE-L BLEU URL URLs JSON HTML PDF OOV SOTA FP16 BF16 GB TB MB""".split())
NAME = re.compile(r"\b[A-Za-z]*[A-Z][A-Za-z]*[A-Z0-9][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*\b")
KEEP = ALLOWED | set("""Wikipedia Google Bing Reddit Twitter GitHub Amazon English Chinese Transformer Transformers
Adam Python PyTorch TensorFlow Internet Web Bayesian Gaussian Euclidean Markov Monte Carlo Table Tables Figure Figures
Section Sections Appendix Equation Eq Algorithm Theorem Lemma Definition Step Stage Phase Part Type Task Setting
Question Answer Context Input Output Note Example Human Model Training Test Dev January February March April May June
July August September October November December Monday Tuesday Wednesday Thursday Friday Saturday Sunday
Bonferroni Jaccard Pearson Spearman Kendall Wilcoxon Fisher Student Kullback Leibler Cohen Likert Zipf Gumbel
Softmax Bernoulli Poisson Dirichlet Laplace Fleiss Krippendorff""".split())
# Plausible surnames from many origins for cited authors (drawn per paper, never a surname of the source).
SURNAME_POOL = """Abara Achebe Adair Aguilar Ahlberg Akande Alvarado Amari Ambrose Andersen Aoki Arslan Ashby Bajwa
Banerjee Barlow Bastos Becerra Bellamy Benedek Berger Bianchi Birkeland Bose Brandt Brennan Brosnan Caldera Calloway
Carvalho Castillo Cervantes Chandra Choudhury Ciobanu Coelho Colquitt Cordero Crowley Dahl Dalton Danjuma Dasgupta
Deane Demir Desai Dimitrov Dobson Dubois Duarte Ebner Ekström Elbaz Engel Esposito Estrada Farouk Fenwick Ferraro
Figueroa Fitzgerald Flores Forsberg Fujita Gallo Gandhi Garnier Gaspar Ghosh Giordano Godinho Goldberg Gonzaga Greco
Gunawardena Haddad Halvorsen Hamid Hansen Harada Hartmann Hayashi Hegde Henriksen Herrera Hirano Hoffmann Holm Horvat
Hosseini Hughes Ibrahim Iqbal Ishikawa Iyer Jablonski Jensen Jovanovic Kader Kamau Kapoor Karimi Kato Keller Khalil
Kimura Kirby Klein Koenig Kovacs Kramer Krishnan Kumar Kuznetsov Laine Lambert Landry Larsen Lazaro Leclerc Lehmann
Lemaire Levesque Lindqvist Lopes Lozano Lund Machado Madsen Mahmoud Malik Mancini Marin Matsuda Mazur Medina Mehta
Meier Mendes Menon Mikkelsen Mishra Miyazaki Molina Monteiro Morales Moretti Mukherjee Murata Nadeem Nagy Nair Navarro
Neumann Nikolaidis Noguchi Novak Nyberg Obi Ogawa Okafor Olsen Omondi Ortega Osei Otieno Pal Palmer Pandey Papadopoulos
Pastor Pereira Petrov Pham Pires Popescu Prakash Quinn Rahman Rajan Ramos Rao Reddy Reyes Richter Rinaldi Rios Roberts
Rocha Romano Rossi Ruiz Saeed Saito Salas Salazar Santoro Sato Schmid Sen Serrano Shah Shapiro Sharma Shimizu Silva
Singh Sokolov Soto Srinivasan Stein Suarez Sugimoto Sundberg Suzuki Szabo Takahashi Tan Tanaka Thakur Toivonen Torres
Tran Trivedi Ueda Uysal Valdez Varga Vargas Venkatesan Vidal Vogel Volkov Wagner Walsh Watanabe Weber Wiśniewski
Yadav Yamada Yildiz Yoshida Young Zaman Zapata Zhou Zimmermann""".split()
SUFFIXES = ("QA", "LM", "LLM", "LMs", "LLMs", "Net", "Bench", "GPT")
VOW, CONS = "aeiou", "bcdfghjklmnprstvwz"
SURNAME = re.compile(r"\b([A-Z][a-zA-Z'-]+) (?:et al\.|and ([A-Z][a-zA-Z'-]+),? \(?\d{4})")
CITED = re.compile(r"\b([A-Z][a-zA-Z'-]+) (?:et al\.|and [A-Z][a-zA-Z'-]+,? \(?\d{4})")
CONTROL_WORDS = re.compile(r"closed[- ]book|no[- ]retrieval|without retrieval|w/o retrieval|vanilla|"
                           r"parametric[- ]only|llm alone|without (?:any )?(?:documents|passages|evidence|context)", re.I)
META = ["claim is kept", "as instructed", "instructions", "the json", " json ", "json file", "planted", "the world",
        "skeleton", "renamed", "source paper"]
KEEP_FIELDS = ["label", "treatment", "control", "system_names", "benchmark", "metric", "claim_sentence", "cells"]
MAX_INSERTED = 1800
SKELETON_SEED = "synth2-v10-skeleton"


# ---- source assignment -------------------------------------------------------------------------------------

def skeleton_candidates(rows: list[dict], split: dict, full: Path) -> list[str]:
    """Source-pool papers on the close topic, published 2017 or later, 4,000-9,000 cleaned words, author-year
    citations (more "et al. (year)" than "[n]"), not a survey; sorted by id."""
    sources = set(split["sources"])
    if sources & set(split["test"]):
        raise ValueError("a paper is on both sides of the split")
    cands = []
    for r in rows:
        pid = r["arxiv_id"]
        if pid not in sources or not QA.search(r["title"] + " " + r["summary"]) or r["published"][:4] < "2017":
            continue
        if "survey" in r["title"].lower():
            continue
        text = (full / f"{pid}.md").read_text(encoding="utf-8")
        n_words = len(text.split())
        if 4000 <= n_words <= 9000 and len(re.findall(r"et al\.,? \(?\d{4}", text)) > len(re.findall(r"\[\d+", text)):
            cands.append(pid)
    return sorted(cands)


def assign_sources(inputs: Path, rows_path: Path, split_path: Path, full: Path, out: Path) -> list[tuple[str, str]]:
    """Copy each S*.json input with an added "skeleton_source" (a different candidate per study, seeded)."""
    split = json.loads(split_path.read_text(encoding="utf-8"))
    cands = skeleton_candidates(read_rows(rows_path), split, full)
    random.Random(SKELETON_SEED).shuffle(cands)
    files = sorted(inputs.glob("S*.json"))
    if len(cands) < len(files):
        raise ValueError(f"{len(cands)} candidate sources for {len(files)} studies")
    out.mkdir(parents=True, exist_ok=True)
    done = []
    for f, pid in zip(files, cands):
        inp = json.loads(f.read_text(encoding="utf-8"))
        inp["skeleton_source"] = str((full / f"{pid}.md").resolve())
        (out / f.name).write_text(json.dumps(inp, indent=1, ensure_ascii=False), encoding="utf-8")
        done.append((f.stem, pid))
    return done


# ---- names in a source paper (src_checks) -----------------------------------------------------------------

def source_names(source: str, allowed_text: str) -> set[str]:
    """Names in the source (acronyms, CamelCase, names with digits, cited surnames) not in our input or ALLOWED."""
    names = set(NAME.findall(source)) | set(CITED.findall(source))
    ours = set(NAME.findall(allowed_text)) | set(re.findall(r"[A-Za-z][A-Za-z0-9-]*", allowed_text))
    return {n for n in names if n not in ALLOWED and n not in ours and len(n) > 1 and not n.isdigit()}


def surviving_names(text: str, source: str, allowed_text: str) -> list[str]:
    return sorted(n for n in source_names(source, allowed_text)
                  if re.search(r"(?<![A-Za-z0-9])" + re.escape(n) + r"(?![A-Za-z0-9])", text))


def tokens(t: str) -> list[str]:
    return re.findall(r"[a-z]+", t.lower())


def copied_runs(text: str, source: str, n: int = 6) -> list[str]:
    s = tokens(source)
    grams = {tuple(s[i:i + n]) for i in range(len(s) - n + 1)}
    w = tokens(text)
    return sorted({" ".join(w[i:i + n]) for i in range(len(w) - n + 1) if tuple(w[i:i + n]) in grams})


# ---- renaming ----------------------------------------------------------------------------------------------

def names_in(source: str) -> set[str]:
    """Single names, plus Title Case phrases of 2-4 words found mid-sentence whose lower-case form never appears
    (e.g. "Natural Questions", "Dense Passage Retriever"); URLs are ignored when looking for lower-case forms."""
    names = set(NAME.findall(source))
    for a, b in SURNAME.findall(source):
        names |= {a, b} - {""}
    plain = re.sub(r"https?://\S+", " ", source)
    lower_text = re.sub(r"\s+", " ", plain)
    lower = set(re.findall(r"\b[a-z]+\b", plain))
    for w in set(re.findall(r"(?<=[a-z,;] )([A-Z][a-z]{2,})\b", plain)):
        if w.lower() not in lower:
            names.add(w)
    word = r"(?:[A-Z][a-z]+(?:-[A-Za-z][a-z]+)*|[A-Za-z]*[A-Z][A-Za-z]*[A-Z0-9][A-Za-z0-9]*)"
    for p in set(re.findall(rf"(?<=[a-z,;] )({word}(?: {word}){{1,3}})(?![A-Za-z0-9])", plain)):
        if set(p.split()) & {"The", "To", "In", "Of", "And", "For", "On", "With", "As", "At", "By", "From", "We",
                             "Our", "This", "That", "These", "It", "If", "When", "While", "However", "Data"}:
            continue  # run-in headings glued to a sentence ("Data Collection To build ..."), not names
        if not all(w in KEEP for w in p.split()) and p.lower() not in lower_text:
            names.add(p)
    return {n for n in names if n not in KEEP and not n.isdigit() and len(n) > 1}


def shape(comp: str, rnd: random.Random) -> str:
    out = []
    for ch in comp:
        lo = ch.lower()
        if lo in VOW:
            c = rnd.choice(VOW)
        elif lo.isalpha():
            c = rnd.choice(CONS)
        else:
            out.append(ch)
            continue
        out.append(c.upper() if ch.isupper() else c)
    return "".join(out)


def map_component(comp: str, seed: str, taken: set[str]) -> str:
    if comp in KEEP or not re.search(r"[A-Z]", comp) or comp.isdigit():
        return comp
    for suf in SUFFIXES:
        if comp.endswith(suf) and len(comp) > len(suf) + 1:
            return map_component(comp[:-len(suf)], seed, taken) + suf
    for k in range(50):
        rnd = random.Random(hashlib.sha256(f"{seed}|{comp}|{k}".encode()).hexdigest())
        new = shape(comp, rnd)
        if new != comp and new not in taken:
            taken.add(new)
            return new
    raise ValueError(comp)


def build_map(source: str, seed: str) -> dict[str, str]:
    """real name -> invented name, the same for the same source and seed."""
    names = names_in(source)
    comps, taken = {}, set(names)
    surnames = sorted({s for pair in SURNAME.findall(source) for s in pair if s and s not in KEEP})
    pool = [p for p in SURNAME_POOL if p not in names]
    random.Random(seed + "|surnames").shuffle(pool)
    for s, p in zip(surnames, pool):
        comps[s] = p
        taken.add(p)
    for n in sorted(names):
        for c in re.split(r"[- ]", n):
            if c and c not in comps:
                comps[c] = map_component(c, seed, taken)
    out = {}
    for n in sorted(names):  # sorted, so the map file is the same on every run
        new = re.sub(r"[^- ]+", lambda m: comps.get(m.group(0), m.group(0)), n)
        if new != n:
            out[n] = new
    return out


def apply_map(text: str, mapping: dict[str, str], seed: str) -> str:
    rnd = random.Random(seed)
    text = re.sub(r"https?://\S+?(?=[\s)\]]|[.,;](?:\s|$))",
                  lambda m: f"https://github.com/{shape('anonlab', rnd)}/{shape('toolkit', rnd)}", text)
    if not mapping:
        return text
    keys = sorted(mapping, key=len, reverse=True)
    pat = re.compile(r"(?<![A-Za-z0-9])(" + "|".join(map(re.escape, keys)) + r")(?![A-Za-z0-9])")
    return pat.sub(lambda m: mapping[m.group(1)], text)


def surviving(text: str, mapping: dict[str, str]) -> list[str]:
    """Real names of the map that still occur in the text."""
    return sorted(n for n in mapping if re.search(r"(?<![A-Za-z0-9])" + re.escape(n) + r"(?![A-Za-z0-9])", text))


# ---- prepare / apply / check -------------------------------------------------------------------------------

def prepare(inputs: Path, base: Path) -> list[dict]:
    """Rename every real name in each study's source paper and keep only the planted fields.
    Writes <base>/sources/<id>.md (renamed source), <base>/maps/<id>.json (real -> invented, kept private for
    checks) and <base>/inputs/<id>.json. Returns one summary per study."""
    for d in ("sources", "maps", "inputs", "edits", "papers", "inserted"):
        (base / d).mkdir(parents=True, exist_ok=True)
    done = []
    for f in sorted(inputs.glob("S*.json")):
        inp = json.loads(f.read_text(encoding="utf-8"))
        source_path = Path(inp["skeleton_source"])
        source = source_path.read_text(encoding="utf-8")
        seed = f"synth2-v11:{f.stem}:{source_path.stem}"
        mapping = build_map(source, seed)
        renamed = apply_map(source, mapping, seed)
        left = surviving(renamed, mapping)
        if left:
            raise ValueError(f"{f.stem}: real names survive the renaming {left[:5]}")
        out = {k: inp[k] for k in KEEP_FIELDS}
        out["source"] = str((base / "sources" / f"{f.stem}.md").resolve())
        (base / "sources" / f"{f.stem}.md").write_text(renamed, encoding="utf-8")
        (base / "maps" / f"{f.stem}.json").write_text(
            json.dumps({"source_id": source_path.stem, "map": mapping}, indent=1, ensure_ascii=False),
            encoding="utf-8")
        (base / "inputs" / f.name).write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
        done.append({"study": f.stem, "source": source_path.stem, "names": len(mapping),
                     "words": len(renamed.split())})
    return done


def apply_edits(renamed: str, edits: dict, label: str) -> tuple[str, list[str], list[str]]:
    """Returns (paper, inserted texts, problems). Every anchor/old string must occur exactly once."""
    problems, inserted = [], []
    lines = renamed.split("\n", 1)
    text = f"# {edits['title'].strip()}\n\n{label}\n\n" + (lines[1].lstrip("\n") if len(lines) > 1 else "")
    inserted.append(edits["title"])
    for r in edits.get("rename", []):  # every whole-word occurrence; for leftover real names
        pat = r"(?<![A-Za-z0-9])" + re.escape(r["old"]) + r"(?![A-Za-z0-9])"
        if not re.search(pat, text):
            problems.append(f"rename: {r['old']!r} not found")
            continue
        if CONTROL_WORDS.search(r["new"]):
            problems.append(f"rename: new name {r['new']!r} contains control wording")
        text = re.sub(pat, lambda m: r["new"], text)
    for r in edits.get("replace", []):
        n = text.count(r["old"])
        if n != 1:
            problems.append(f"replace: old text found {n} times: {r['old'][:70]!r}")
            continue
        text = text.replace(r["old"], r["new"])
        if r["new"].strip():
            inserted.append(r["new"])
    for ins in edits.get("insert_after", []):
        n = text.count(ins["anchor"])
        if n != 1:
            problems.append(f"insert_after: anchor found {n} times: {ins['anchor'][:70]!r}")
            continue
        i = text.index(ins["anchor"]) + len(ins["anchor"])
        text = text[:i] + "\n\n" + ins["text"].strip() + "\n\n" + text[i:].lstrip("\n")
        inserted.append(ins["text"])
    return text, inserted, problems


def pct_forms(k: int, n: int) -> set[str]:
    x = 100 * k / n
    return {f"{x:.1f}", f"{x + 1e-9:.1f}", f"{x - 1e-9:.1f}"}


# Claim rules (writer-v12): our inserted text was the last classifier cue ("overall the SYS lowers", "subset",
# "correctly", "asked"), because writers copied the claim sentence nearly word for word.
CLAIM_RUN = 4
INSERTED_LIMITS = {("overall",): 1, ("subset", "subsets"): 2, ("correctly",): 1, ("asked",): 1}


def claim_problems(inserted: list[str], claim_sentence: str) -> list[str]:
    """No run of CLAIM_RUN words from the claim sentence, and the INSERTED_LIMITS, in our inserted text."""
    problems = []
    claim = tokens(claim_sentence)
    grams = {tuple(claim[i:i + CLAIM_RUN]) for i in range(len(claim) - CLAIM_RUN + 1)}
    runs = sorted({" ".join(t[i:i + CLAIM_RUN]) for t in map(tokens, inserted)
                   for i in range(len(t) - CLAIM_RUN + 1) if tuple(t[i:i + CLAIM_RUN]) in grams})
    if runs:
        problems.append(f"inserted text copies the claim sentence: {runs[:4]}")
    toks = tokens(" ".join(inserted))
    for words, cap in INSERTED_LIMITS.items():
        n = sum(t in words for t in toks)
        if n > cap:
            problems.append(f"inserted text: '{'/'.join(words)}' {n} times (limit {cap})")
    return problems


def check_paper(text: str, inserted: list[str], inp: dict, mapping: dict[str, str],
                claim_rules: bool = False) -> list[str]:
    """Code checks; the claim and the level reading are checked by the blind reader. `claim_rules` adds the
    writer-v12 rules on our inserted text (claim_problems)."""
    problems = claim_problems(inserted, inp["claim_sentence"]) if claim_rules else []
    low = text.lower()
    if text.split("\n")[2].strip() != inp["label"]:
        problems.append("label is not the author line under the title")
    if text.count(inp["benchmark"]) < 2:
        problems.append(f"dataset {inp['benchmark']} named {text.count(inp['benchmark'])} times")
    numbers = set(re.findall(r"(?<![\d.])\d+(?![\d.])", text))
    for c in inp["cells"]:
        for x in (c["treatment_correct"], c["treatment_total"], c["control_correct"], c["control_total"]):
            if str(x) not in numbers:
                problems.append(f"count {x} missing")
        for k, n in ((c["treatment_correct"], c["treatment_total"]), (c["control_correct"], c["control_total"])):
            if not pct_forms(k, n) & set(re.findall(r"\d+\.\d", text)):
                problems.append(f"accuracy of {k}/{n} missing")
        for lv in c["levels"]:
            if lv["name"].lower() in low:
                problems.append(f"level name '{lv['name']}' written verbatim")
    lines = text.split("\n")
    left = surviving("\n".join(lines[:2] + lines[3:]), mapping)   # the author line is our invented label
    if left:
        problems.append(f"real names survive {left[:8]}")
    rest = text
    for t in sorted(inserted, key=len, reverse=True):
        rest = rest.replace(t.strip(), " ")
    ctrl = [m.group(0) for m in CONTROL_WORDS.finditer(rest)]
    ctrl += [inp["system_names"]["control"]] * rest.count(inp["system_names"]["control"])
    if ctrl:
        problems.append(f"control or no-retrieval wording outside the inserted text: {sorted(set(ctrl))}")
    added_low = " ".join(inserted).lower()
    for m in META:  # only in our own text: real papers say "the world" or "instructions" naturally
        if m in added_low:
            problems.append(f"meta wording '{m.strip()}'")
    added = sum(len(t.split()) for t in inserted)
    if added > MAX_INSERTED:
        problems.append(f"{added} inserted words (limit 1,800: the paper must stay mostly real text)")
    return problems


def apply_study(base: Path, sid: str, edits_path: Path | None = None, claim_rules: bool = False) -> dict:
    """Apply a writer's edits (<base>/edits/<id>.json) to the renamed source, run the code checks, write
    <base>/papers/<id>.md and <base>/inserted/<id>.json. Returns {"words", "inserted", "problems"}.
    An unreadable edits file is a problem and nothing is written."""
    inp = json.loads((base / "inputs" / f"{sid}.json").read_text(encoding="utf-8"))
    renamed = (base / "sources" / f"{sid}.md").read_text(encoding="utf-8")
    mapping = json.loads((base / "maps" / f"{sid}.json").read_text(encoding="utf-8"))["map"]
    try:
        edits = json.loads((edits_path or base / "edits" / f"{sid}.json").read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as err:
        return {"words": 0, "inserted": 0, "problems": [f"edits file unreadable: {err}"]}
    paper, inserted, problems = apply_edits(renamed, edits, inp["label"])
    problems += check_paper(paper, inserted, inp, mapping, claim_rules)
    (base / "papers" / f"{sid}.md").write_text(paper, encoding="utf-8")
    (base / "inserted" / f"{sid}.json").write_text(json.dumps(inserted, indent=1, ensure_ascii=False),
                                                   encoding="utf-8")
    return {"words": len(paper.split()), "inserted": sum(len(t.split()) for t in inserted), "problems": problems}


def check_base(grid_family: Path, base: Path, reader_files: list[Path],
               claim_rules: bool = False) -> tuple[dict, int]:
    """Code checks plus the blind reader against the ground truth of a grid family folder. Only studies with a
    paper are reported. Label, benchmark, claim and cells must match exactly; other results are counted, and any
    that mentions the control fails. Writes <base>/check.json; returns (report, number of other results)."""
    reader = [r for f in reader_files for r in json.loads(f.read_text(encoding="utf-8-sig"))]
    truth = json.loads((grid_family / "ground_truth.json").read_text(encoding="utf-8"))
    id_of = {lv["name"].lower(): lv["id"] for c in truth["conditions"] for lv in c["levels"]}
    got = {r["paper"]: r for r in reader}
    report, extras = {}, 0
    for s in truth["studies"]:
        sid = s["id"]
        p = base / "papers" / f"{sid}.md"
        if not p.is_file():
            continue
        inp = json.loads((base / "inputs" / f"{sid}.json").read_text(encoding="utf-8"))
        mapping = json.loads((base / "maps" / f"{sid}.json").read_text(encoding="utf-8"))["map"]
        inserted = json.loads((base / "inserted" / f"{sid}.json").read_text(encoding="utf-8"))
        problems = check_paper(p.read_text(encoding="utf-8"), inserted, inp, mapping, claim_rules)
        r = got.get(sid)
        if reader and r is None:
            problems.append("reader gave nothing")
        elif r is not None:
            for field, want in (("label", s["label"]), ("claim", s["claim"]), ("benchmark", s["dataset"])):
                if r.get(field) != want:
                    problems.append(f"reader {field} {r.get(field)!r} != {want!r}")
            other = r.get("other_results") or []
            extras += len(other)
            ctrl = [o for o in other if CONTROL_WORDS.search(str(o))]
            if ctrl:
                problems.append(f"reader: other results mention the control {ctrl[:2]}")
            want = sorted((sorted(c["levels"].values()), c["k_t"], c["n_t"], c["k_c"], c["n_c"])
                          for c in s["cells"])
            try:
                have = sorted((sorted(id_of[x.lower()] for x in c["levels"]), c["treatment_correct"],
                               c["treatment_total"], c["control_correct"], c["control_total"])
                              for c in r.get("cells", []))
            except (KeyError, AttributeError) as err:
                have = None
                problems.append(f"reader: unknown level {err}")
            if have is not None and have != want:
                problems.append(f"reader cells {have} != {want}")
        report[sid] = {"ok": not problems, "words": len(p.read_text(encoding="utf-8").split()),
                       "inserted": sum(len(t.split()) for t in inserted), "problems": problems}
    (base / "check.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return report, extras

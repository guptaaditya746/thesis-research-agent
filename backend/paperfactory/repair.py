"""After writing, before tagging: every paper must agree with the WORLD, not only with its own notes (#4).

All papers of a field share one world and QA systems read them together, so a sentence such as "This analysis
records no treatment of section 9 in Pell" (true for one paper's notes) looks like a disagreement nobody planted.

  detect  1. pack patterns ("text"."absence_patterns") flag wording about the notes or about missing relations;
          2. the verifier (a separate call) compares every sentence that names a subject and a possible object with
             what the world says about that pair: SUPPORTS | CONTRADICTS | ABSENCE_CLAIM | NEUTRAL.
  policy  CONTRADICTS and ABSENCE_CLAIM are fixed; a pattern hit in a sentence with no pair is fixed; a pattern
          hit with a pair is left to the verifier.
  repair  each flagged paragraph is rewritten once (role "repair") and its new sentences are checked again; if any
          is still flagged, the whole paper is written again once (fresh PaperOrchestra cache) and checked and
          repaired the same way; still flagged -> the paper is marked failed and left out of the evaluation.
  files   work/<paper>/paper.raw.md (as first written), paper.md (repaired), paper.repairs.json (every step).
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel

from paperfactory import files
from paperfactory.evaluate import ids_check
from paperfactory.packs import Field
from paperfactory.text import alias_table, defined_terms, find_mentions, normalize_paper, split_rules, split_sents
from paperfactory.world import fact_errors

VERDICTS = ("SUPPORTS", "CONTRADICTS", "ABSENCE_CLAIM", "NEUTRAL")
FIX = ("CONTRADICTS", "ABSENCE_CLAIM")


class WorldVerdict(BaseModel):
    id: str
    verdict: Literal["SUPPORTS", "CONTRADICTS", "ABSENCE_CLAIM", "NEUTRAL"]


class WorldOut(BaseModel):
    answers: list[WorldVerdict]


class RepairOut(BaseModel):
    paragraph: str


def failed(out_dir, pid: str) -> bool:
    p = out_dir / "work" / pid / "paper.repairs.json"
    return p.is_file() and json.loads(p.read_text(encoding="utf-8")).get("status") == "failed"


class Checker:
    def __init__(self, s, w: dict[str, Any], f: Field, call):
        self.s, self.w, self.f, self.call = s, w, f, call
        self.rules = split_rules(f, w)
        self.base = alias_table(w, f)
        self.patterns = [re.compile(p) for p in f.raw["text"]["absence_patterns"]]
        self.truth: dict[tuple[str, str], str] = {(a, b): r for p in w["papers"].values()
                                                  for a, r, b in p["claims"] + p["decoys"]}

    # ------------------------------------------------------------ helpers
    def label(self, e: str) -> str:
        return self.w["entities"][e]["label"]

    def says(self, a: str, b: str) -> str:
        """What the world says about the pair, in the pack's words."""
        actor = self.f.word("actor")
        for x, y in ((a, b), (b, a)):
            if (x, y) in self.truth:
                return f"{self.label(x)}: {actor} {self.f.rel_words(self.truth[(x, y)])} {self.label(y)}."
        return f"No relation between {self.label(a)} and {self.label(b)} is true in this world."

    def pairs(self, sentence: str, table) -> list[tuple[str, str]]:
        ents = self.w["entities"]
        ids = list(dict.fromkeys(m.eid for m in find_mentions(sentence, table)))
        out = []
        for a in ids:
            for b in ids:
                if a != b and ents[a]["kind"] in self.f.subject_kinds and \
                        any(not fact_errors((a, r, b), ents, self.f) for r in self.f.relations):
                    out.append((a, b))
        return out

    def system(self) -> str:
        sk, rels = self.f.word("subject_kind"), list(self.f.relations.values())
        r1, r2 = rels[0]["words"], rels[min(1, len(rels) - 1)]["words"]
        return f"""You compare one sentence of a paper with what is TRUE in the paper's world about one pair: a {sk}
and a source. Each item has an id, the sentence, the sentence before it (context), the pair, and the truth.
Answer with one verdict per item, using its id:
SUPPORTS: the sentence states the true relation for this pair (in any wording).
CONTRADICTS: the sentence states a relation for this pair that is not the true one, or a relation where the truth
  has none.
ABSENCE_CLAIM: the sentence says the relation for this pair is unknown, not recorded, not addressed, not treated,
  absent or left open.
NEUTRAL: the sentence names both but says nothing about how the {sk} treated the source.
Examples (truth "X: {self.f.word('actor')} {r1} Y."):
"In X, the {sk} {r1} Y." -> SUPPORTS.  "X {r2} Y." -> CONTRADICTS.  "It is not recorded how X treated Y." ->
ABSENCE_CLAIM.  "X and Y are discussed together in this section." -> NEUTRAL."""

    # ------------------------------------------------------------ detection
    def check(self, pid: str, md: str, only: set[str] | None = None) -> tuple[list[dict[str, Any]], list[str]]:
        """(flags, notes) for the sentences of md (only those whose text is in `only`, if given)."""
        text = normalize_paper(md).text
        table = alias_table(self.w, self.f, defined_terms(text, self.base, self.f))
        sents = split_sents(md, self.rules)
        flags, items, notes = [], [], []
        for n, (a, b, t) in enumerate(sents):
            if only is not None and t not in only:
                continue
            hits = [p.pattern for p in self.patterns if p.search(t)]
            prs = self.pairs(t, table)
            if hits and not prs:
                flags.append({"n": n, "start": a, "end": b, "text": t, "kind": "pattern", "pair": None,
                              "reason": f"wording about the notes or a missing relation ({hits[0]})"})
            for x, y in prs:
                items.append((n, x, y, hits))
        for i in range(0, len(items), 25):
            chunk = items[i:i + 25]
            ids = [f"W{j + 1}" for j in range(len(chunk))]
            user = json.dumps([{"id": k, "context": sents[n - 1][2] if n else "", "sentence": sents[n][2],
                                "pair": [self.label(x), self.label(y)], "truth": self.says(x, y)}
                               for k, (n, x, y, _) in zip(ids, chunk)], indent=1)
            got = self.call("verifier", f"worldcheck:{pid}", self.system(), user, WorldOut, ids_check(ids))
            if got is None:
                notes.append(f"worldcheck parse_error: {len(chunk)} items unchecked")
                continue
            verdict = {a["id"]: a["verdict"] for a in got["answers"]}
            for k, (n, x, y, hits) in zip(ids, chunk):
                if verdict[k] in FIX:
                    a, b, t = sents[n]
                    flags.append({"n": n, "start": a, "end": b, "text": t, "kind": verdict[k], "pair": [x, y],
                                  "reason": f"{verdict[k]}: the world says: {self.says(x, y)}"})
        return flags, notes

    # ------------------------------------------------------------ repair
    # v1 (until 22 Nov 2026): the model was not told which names to keep, and the check knew only full names and
    # pack variants; in the Qwen smoke run (llm, LLM-02) six repairs in a row dropped a name and the paper failed
    REPAIR_SYS_V1 = """You fix one paragraph of a paper. You get the paragraph, the problems found in it, and the facts
this paper states. Return the paragraph rewritten so that every problem is gone.
Rules: keep every other statement, name and fact as it is; keep the meaning of each listed fact exactly; add no new
facts. Never mention the materials, notes or records the paper was written from, and never say that how one source
treated another is unknown, unrecorded, unaddressed or absent: if a sentence only says that, drop it. Return only the
paragraph text (no heading).
Example. Problem: "ABSENCE_CLAIM: It is not recorded how X treated Y." -> drop that sentence, keep the rest."""
    REPAIR_SYS = """You fix one paragraph of a paper. You get the paragraph, the problems found in it, the facts this
paper states, and names_to_keep. Return the paragraph rewritten so that every problem is gone.
Rules: keep every other statement, name and fact as it is; keep the meaning of each listed fact exactly; add no new
facts. Every name in names_to_keep must still appear in the paragraph (the full name or the short name the paragraph
already uses). Never mention the materials, notes or records the paper was written from, and never say that how one
source treated another is unknown, unrecorded, unaddressed or absent: if a sentence only says that, drop it. The
simplest fix is often to drop the flagged sentence or the wrong part of it. Return only the paragraph text (no
heading).
Example. Problem: "ABSENCE_CLAIM: It is not recorded how X treated Y." -> drop that sentence, keep the rest.
Example. Problem: "CONTRADICTS: the world says: no relation between X and Y. Sentence: X and Z relied on Y." with
names_to_keep ["Z", "Y"] -> "Z relied on Y." """

    def must_keep(self, para: str, facts: list[list[str]], table) -> list[tuple[str, str]]:
        """(subject, object) of each fact of the paper whose two names appear together in one sentence of the
        paragraph (names in two different sentences do not state a fact, so they need not stay together)."""
        sents = [{m.eid for m in find_mentions(t, table)} for _, _, t in split_sents(para, self.rules)]
        return [(s_, o) for s_, _, o in facts if any({s_, o} <= named for named in sents)]

    def lost(self, new: str, must: list[tuple[str, str]], table) -> list[str]:
        ents = self.w["entities"]
        named = {m.eid for m in find_mentions(new, table)}
        return [f"{ents[s_]['label']} / {ents[o]['label']}" for s_, o in must if not {s_, o} <= named]

    def repair_unit(self, pid: str, para: str, problems: list[str], facts: list[list[str]],
                    table=None) -> str | None:
        """One rewrite call. table: the paper's alias table (its own short names count as names)."""
        table = table or self.base
        must = self.must_keep(para, facts, table)

        def check(out: dict[str, Any]) -> str | None:
            new = out["paragraph"].strip()
            if not new:
                return "the paragraph is empty"
            gone = self.lost(new, must, table)
            return f"keep the names of these facts: {gone}" if gone else None
        keep = sorted({self.label(e) for pair in must for e in pair})
        user = json.dumps({"paragraph": para, "problems": problems, "facts_of_this_paper": [
            f"{self.label(s_)}: {self.f.word('actor')} {self.f.rel_words(r)} {self.label(o)}." for s_, r, o in facts],
            "names_to_keep": keep}, indent=1, ensure_ascii=False)
        got = self.call("repair", f"repair:{pid}", self.REPAIR_SYS, user, RepairOut, check)
        return got["paragraph"].strip() if got else None

    def drop_flagged(self, md: str, a: int, b: int, flags: list[dict[str, Any]], p,
                     must: list[tuple[str, str]], table) -> str | None:
        """Fallback by code: the paragraph md[a:b] without its flagged sentences, if every fact named in it before
        is still named; else None. A flagged sentence states something the world does not (or talks about the
        notes), so dropping it never adds an error."""
        para = md[a:b]
        cuts = sorted(((p.back[fl["start"]] - a, p.back[fl["end"] - 1] + 1 - a) for fl in flags), reverse=True)
        for x, y in cuts:
            while y < len(para) and para[y] == " ":
                y += 1
            para = para[:x] + para[y:]
        para = para.strip()
        return para if not self.lost(para, must, table) else None

    def fix_round(self, pid: str, md: str, log: list[dict[str, Any]], label: str) -> tuple[str, list[dict]]:
        """Check md; rewrite each flagged paragraph once; check the new sentences. -> (md, flags still open)."""
        flags, notes = self.check(pid, md)
        log.append({"step": f"{label}:check", "flags": flags, "notes": notes})
        if not flags:
            return md, []
        p = normalize_paper(md)
        table = alias_table(self.w, self.f, defined_terms(p.text, self.base, self.f))
        facts = self.w["papers"][pid]["claims"] + self.w["papers"][pid]["decoys"]
        by_unit: dict[int, list[dict[str, Any]]] = {}
        for fl in flags:
            u = next(i for i, u in enumerate(p.units) if u.start <= fl["start"] < u.end)
            by_unit.setdefault(u, []).append(fl)
        old_sents = {t for _, _, t in split_sents(md, self.rules)}
        still = []
        for ui in sorted(by_unit, reverse=True):              # from the end, so earlier offsets stay valid
            u = p.units[ui]
            a, b = p.back[u.start], p.back[u.end - 1] + 1
            problems = [f"{fl['reason']} Sentence: {fl['text']}" for fl in by_unit[ui]]
            new = self.repair_unit(pid, md[a:b], problems, facts, table)
            log.append({"step": f"{label}:repair", "unit": ui, "old": md[a:b], "new": new, "problems": problems})
            if new is None:                   # the model could not do it: drop the flagged sentences by code
                new = self.drop_flagged(md, a, b, by_unit[ui], p, self.must_keep(md[a:b], facts, table), table)
                log.append({"step": f"{label}:drop_sentences", "unit": ui, "new": new})
            if new is None:
                still += by_unit[ui]
                continue
            md = md[:a] + new + md[b:]
        # new sentences, and flagged ones that are still there (a repair may return the paragraph unchanged)
        now = {t for _, _, t in split_sents(md, self.rules)}
        recheck = (now - old_sents) | ({fl["text"] for fl in flags} & now)
        again, notes = self.check(pid, md, only=recheck)
        log.append({"step": f"{label}:recheck", "flags": again, "notes": notes})
        return md, still + again

    def repair_paper(self, pid: str, redo: Callable[[str], str | None]) -> dict[str, Any]:
        work = self.s.out_dir / "work" / pid
        md = (work / "paper.md").read_text(encoding="utf-8")
        raw = work / "paper.raw.md"
        if not raw.is_file():
            files.write_text(raw, md)
        log: list[dict[str, Any]] = []
        md, left = self.fix_round(pid, md, log, "first")
        status = "clean" if len(log) == 1 else "repaired"     # one log entry: the first check found nothing
        if left:
            new = redo(pid)
            log.append({"step": "redo", "ok": new is not None})
            if new is not None:
                md, left = self.fix_round(pid, new, log, "after_redo")
            status = "failed" if left or new is None else "redone"
        files.write_text(work / "paper.md", md)
        rec = {"pid": pid, "status": status, "open_flags": left, "log": log}
        files.write_json(work / "paper.repairs.json", rec)
        return {"pid": pid, "status": status, "open_flags": len(left)}

"""After writing: find where each planted fact sits (tagging), test the checks, then question answering + scoring.

Steps (each LLM call is a separate fresh call; the model per job comes from the settings):
  tag       tagger marks sentences per fact; code checks names; verifier (separate call) confirms each tag;
            a sweep sends untagged sentences that name both ends of a fact to the verifier too.
  verifier  test (circular, accepted tags only): accepted tags must get "yes"; the same sentence with another
            possible relation (made by code) "no"; impossible pairs apart. The real test is labels.py (hand labels).
  judge     multiple-choice meaning judge, validated on paper wording and on reworded answer wording.
  qa        one call per question over its papers; each item quotes the paper; provenance by code (gold span,
            distractor span, no planted span, made-up quote); the relation by the judge; quotes must be unique
            in their paper (one repair call otherwise).
  leak      style-leak test: one planted sentence among 19 other claim-like sentences; can a model spot it?
Output: tagged.json ({scoring_version, papers}), report.json in the run folder.
"""
from __future__ import annotations

import json
import math
import random
import re
from typing import Any, Literal

from pydantic import BaseModel

from paperfactory import SCORING_VERSION
from paperfactory.llm import pmap
from paperfactory.packs import Field
from paperfactory.text import (AliasTable, alias_table, defined_terms, find_mentions, names, norm, norm_text,
                                normalize_paper, split_rules,
                                split_sents)
from paperfactory.world import fact_errors
from paperfactory.write import repeated_phrases


# ------------------------------------------------------------------ output types (parsed by llm.Caller)
class Tag(BaseModel):
    id: str
    sentences: list[int]


class TagOut(BaseModel):
    tags: list[Tag]


class Verdict(BaseModel):
    id: str
    verdict: Literal["yes", "no"]


class VerOut(BaseModel):
    answers: list[Verdict]


class Rewrite(BaseModel):
    n: int
    text: str


class RewordOut(BaseModel):
    rewritten: list[Rewrite]


class QAItem(BaseModel):
    paper: str
    subject: str
    relation: str
    object: str
    quote: str
    answer_sentence: str


class QAOut(BaseModel):
    items: list[QAItem]


class LeakOut(BaseModel):
    pick: int


def ids_check(expected: list[str], key: str = "answers") -> Any:
    """Every expected id answered exactly once, and no other id (a model that counts from 0 or 1 instead of
    using the ids is rejected, never shifted)."""
    def check(out: dict[str, Any]) -> str | None:
        got = [a["id"] for a in out[key]]
        missing, extra = sorted(set(expected) - set(got)), sorted(set(got) - set(expected))
        dup = sorted({x for x in got if got.count(x) > 1})
        if missing or extra or dup:
            return (f"answer every id exactly once, using the ids given; missing {missing[:10]}, unknown "
                    f"{extra[:10]}, repeated {dup[:10]}")
        return None
    return check


class Eval:
    def __init__(self, s, w: dict[str, Any], f: Field, gold: dict[str, Any], call, max_mentions: int = 3):
        self.s, self.w, self.f, self.G, self.call = s, w, f, gold, call
        self.max_mentions = max_mentions
        self.facts = gold["facts"]
        self.rng = random.Random(s.seed)
        self.options = list(f.relations) + ["none"]        # the judge answers with one of these
        self.rules = split_rules(f, w)
        self.table = alias_table(w, f)          # world + pack names; per paper: table_for(pid)
        self._tables: dict[str, tuple[AliasTable, dict[str, str]]] = {}
        tail = f.raw["text"]["citation_tail"]
        self.citation_tail = re.compile(tail) if tail else None

    # -------------------------------------------------------------- helpers
    def table_for(self, pid: str | None) -> AliasTable:
        """Alias table of one paper: the world table plus the terms the paper itself defines."""
        if pid is None:
            return self.table
        if pid not in self._tables:
            extra = defined_terms(normalize_paper(self.paper(pid)).text, self.table, self.f)
            self._tables[pid] = (alias_table(self.w, self.f, extra), extra)
        return self._tables[pid][0]

    def save_aliases(self, pid: str) -> dict[str, Any]:
        tab, extra = self.table_for(pid), self._tables[pid][1]
        rec = {"aliases": dict(sorted(tab.by_key.items())), "defined_in_paper": extra, "ambiguous": tab.ambiguous}
        (self.s.out_dir / "work" / pid / "paper.aliases.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False),
                                                                          encoding="utf-8")
        return rec

    def mentions(self, text: str, eid: str, pid: str | None = None) -> bool:
        return any(m.eid == eid for m in find_mentions(text, self.table_for(pid)))

    def label(self, e: str) -> str:
        return self.w["entities"][e]["label"]

    def fact_text(self, fa: dict[str, Any]) -> str:
        return f"{self.label(fa['s'])}: {self.f.words['actor']} {self.f.rel_words(fa['r'])} {self.label(fa['o'])}."

    def paper(self, pid: str) -> str:
        return (self.s.out_dir / "work" / pid / "paper.md").read_text(encoding="utf-8")

    def rel_list(self) -> str:
        return "; ".join(f"{d['words']} ({d['meaning']})" for d in self.f.relations.values())

    # -------------------------------------------------------------- tagging
    def tag_sys(self) -> str:
        sk, actor = self.f.words["subject_kind"], self.f.words["actor"]
        return f"""You mark which sentences of a paper state given holdings.
Input: numbered sentences of one paper, and a list of holdings, each with an id. A holding says what was done
with a source in one {sk}. Possible actions: {self.rel_list()}.
For each holding, list the numbers of ALL sentences that state that holding (the {sk}, the source and the action).
A sentence that only names the {sk} or the source, or states a different holding, does not count. A sentence may
refer to the {sk} by a short name, as "{actor}" or "it" when the previous sentence names it. Use only numbers from
the list. If no sentence states a holding, give an empty list."""

    def ver_sys(self) -> str:
        sk = self.f.words["subject_kind"]
        return f"""You check single claims. For each item you get a sentence (with the sentence before it as context)
and one holding: what was done with a source in one {sk}. Possible actions: {self.rel_list()}.
Answer "yes" only if the sentence itself states exactly this holding: the same {sk}, the same source and the same
action. A different action, a different {sk}, a view the paper only reports from someone else, or a mere mention
is "no"."""

    def verify(self, pairs: list[tuple[str, str, dict]], step: str) -> list[bool | None]:
        """yes -> True, no -> False, None when the verifier's answer failed the checks (parse_error)."""
        out: list[bool | None] = []
        for i in range(0, len(pairs), 25):
            chunk = pairs[i:i + 25]
            ids = [f"V{j + 1}" for j in range(len(chunk))]
            items = [{"id": k, "context": c, "sentence": s, "holding": self.fact_text(fa)}
                     for k, (c, s, fa) in zip(ids, chunk)]
            got = self.call("verifier", step, self.ver_sys(), json.dumps(items, indent=1), VerOut, ids_check(ids))
            by = {a["id"]: a["verdict"] == "yes" for a in got["answers"]} if got else {}
            out += [by.get(k) for k in ids]
        return out

    def tag_paper(self, pid: str) -> dict[str, Any]:
        sents = split_sents(self.paper(pid), self.rules)
        facts = [fa for fa in self.facts.values() if pid in fa["papers"]]
        user = json.dumps({"sentences": [{"n": i, "text": s[2]} for i, s in enumerate(sents)],
                           "holdings": [{"id": fa["id"], "holding": self.fact_text(fa)} for fa in facts]}, indent=1)
        got = self.call("tagger", f"tag:{pid}", self.tag_sys(), user, TagOut)
        notes, tags = [] if got else ["tagger parse_error: no tags; only the sweep can find spans"], \
            {fa["id"]: set() for fa in facts}
        actor = self.f.words["actor"].split()[-1].lower()
        for t in got["tags"] if got else []:
            if t["id"] not in tags:
                notes.append(f"unknown id {t['id']}")
                continue
            fa = self.facts[t["id"]]
            for n in t["sentences"]:
                if not 0 <= n < len(sents):
                    notes.append(f"bad sentence number {n}")
                    continue
                ctx = sents[n - 1][2] + " " if n else ""
                sent = sents[n][2]
                subj_ok = (self.mentions(ctx + sent, fa["s"], pid) or actor in sent.lower()
                           or " it " in f" {sent.lower()}")
                if not self.mentions(sent, fa["o"], pid) or not subj_ok:     # kept: the verifier decides
                    who = "the source" if subj_ok else "the " + self.f.words["subject_kind"]
                    notes.append(f"{t['id']} s{n}: unknown_name (no known name of {who}; sent to verifier)")
                tags[t["id"]].add(n)
        pairs = [(n, i) for i, ns in tags.items() for n in sorted(ns)]
        sweep = [(n, fa["id"]) for fa in facts for n, s in enumerate(sents)
                 if n not in tags[fa["id"]] and self.mentions(s[2], fa["o"], pid) and self.mentions(s[2], fa["s"], pid)]
        ok = self.verify([(sents[n - 1][2] if n else "", sents[n][2], self.facts[i]) for n, i in pairs + sweep],
                         f"verify:{pid}")
        kept: dict[str, set[int]] = {i: set() for i in tags}
        rejected, added, unverified = [], [], []
        for (n, i), v in zip(pairs + sweep, ok):
            if v is None:
                unverified.append((i, n))
            elif (n, i) in pairs and v:
                kept[i].add(n)
            elif (n, i) in pairs:
                rejected.append((i, n))
            elif v:
                kept[i].add(n)
                added.append((i, n))
        subsections = [f"s{n}: {m.surface}{m.subsection}" for n, st in enumerate(sents)
                       for m in find_mentions(st[2], self.table_for(pid)) if m.subsection]
        aliases = self.save_aliases(pid)
        text = self.paper(pid)
        all_names = [x for e in self.w["entities"] for x in names(self.w, e)]
        return {"pid": pid, "words": len(text.split()), "n_sentences": len(sents), "tags_proposed": len(pairs),
                "tags_rejected_by_verifier": rejected, "tags_added_by_sweep": added,
                "unverified_parse_error": unverified, "code_notes": notes,
                "subsection_mentions": subsections, "ambiguous_names": len(aliases["ambiguous"]),
                "names_defined_in_paper": aliases["defined_in_paper"],
                "facts_without_tag": [i for i, ns in kept.items() if not ns],
                "over_mention_budget": [i for i, ns in kept.items() if len(ns) > self.max_mentions],
                "repeated_phrases": repeated_phrases(text, all_names)[:10],
                "spans": {i: [list(sents[n][:2]) for n in sorted(ns)] for i, ns in kept.items()},
                "sentences": [list(s) for s in sents]}

    # -------------------------------------------------------------- verifier test
    def verifier_test(self, tagged: dict[str, Any]) -> dict[str, Any]:
        items = []
        for t in tagged.values():
            S = t["sentences"]
            idx = {tuple(s[:2]): i for i, s in enumerate(S)}
            for i, spans in t["spans"].items():
                fa = self.facts[i]
                for sp in spans:
                    j = idx[tuple(sp)]
                    ctx = S[j - 1][2] if j else ""
                    items.append((ctx, S[j][2], fa, True))
                    items += [(ctx, S[j][2], {**fa, "r": r}, False) for r in self.f.relations if r != fa["r"]]
        got = self.verify([(c, s, fa) for c, s, fa, _ in items], "verifier_test")
        ents = self.w["entities"]
        imp = [bool(fact_errors((fa["s"], fa["r"], fa["o"]), ents, self.f)) for _, _, fa, _ in items]
        pos = [g for g, it in zip(got, items) if it[3]]
        neg = [g for g, it, x in zip(got, items, imp) if not it[3] and not x]
        neg_imp = [g for g, it, x in zip(got, items, imp) if not it[3] and x]
        right = sum(bool(g) for g in pos) + sum(g is False for g in neg)
        return {"note": "circular: positives are sentences this verifier already accepted while tagging; not a "
                        "precision estimate. The hand-labeled test is labels.py (export-labels, label-metrics)",
                "positives": len(pos), "pos_yes": sum(bool(g) for g in pos),
                "negatives": len(neg), "neg_no": sum(g is False for g in neg),
                "accuracy_accepted_tags_only": round(right / max(1, len(pos) + len(neg)), 3),
                "impossible_pair_negatives": {"n": len(neg_imp), "no": sum(g is False for g in neg_imp),
                                              "note": "relations the pack does not allow for the pair; left out of "
                                                      "the accuracy"}}

    # -------------------------------------------------------------- meaning judge
    def judge_sys(self) -> str:
        sk = self.f.words["subject_kind"]
        opts = "\n".join(f"{r} = {d['words']} ({d['meaning']})" for r, d in self.f.relations.items())
        return (f"Read the sentence. It is about what one {sk} did with a source. Choose what the sentence says, "
                f"answering with one of these labels exactly:\n{opts}\nnone = none of these / the sentence does not "
                "say.\nJudge only from the sentence.")

    def judge(self, sentence: str, s: str, o: str, step: str) -> str:
        """A relation of the pack, "none", or "parse_error" (the judge's answer was not one of the labels)."""
        schema = {"type": "object", "required": ["choice"],
                  "properties": {"choice": {"type": "string", "enum": self.options}}}
        user = json.dumps({self.f.words["subject_kind"]: self.label(s), "source": self.label(o),
                           "sentence": sentence}, indent=1)
        def check(out: dict[str, Any]) -> str | None:
            return None if out["choice"] in self.options else f"choice must be one of {self.options}"
        got = self.call("judge", step, self.judge_sys(), user, schema, check)
        return got["choice"] if got else "parse_error"

    REWORD_SYS = """Rewrite each sentence as a short plain answer sentence, as a question-answering system would
write it. Keep its meaning exactly: same subject, same source, same action. Do not add facts. Return one per input."""

    def judge_validation(self, tagged: dict[str, Any]) -> dict[str, Any]:
        items = []
        for t in tagged.values():
            S = t["sentences"]
            for i, spans in t["spans"].items():
                for sp in spans:
                    items.append((i, next(s[2] for s in S if [s[0], s[1]] == sp)))
        rew: dict[int, str] = {}
        for b in range(0, len(items), 40):
            ns = list(range(b, min(b + 40, len(items))))
            check = lambda out, ns=ns: None if sorted(r["n"] for r in out["rewritten"]) == ns else \
                f"return exactly one rewrite for each n in {ns}"  # noqa: E731
            got = self.call("rewriter", f"reword:{b}", self.REWORD_SYS, json.dumps(
                [{"n": n, "text": items[n][1]} for n in ns], indent=1), RewordOut, check)
            rew |= {r["n"]: r["text"] for r in got["rewritten"]} if got else {}

        def ok(it: tuple[str, str], step: str) -> bool | None:
            fa = self.facts[it[0]]
            got = self.judge(it[1], fa["s"], fa["o"], step)
            return None if got == "parse_error" else got == fa["r"]
        paper = pmap(lambda it: ok(it, "judge:paper"), items)
        ans_items = [(i, rew[n]) for n, (i, _) in enumerate(items) if n in rew]
        answer = pmap(lambda it: ok(it, "judge:answer"), ans_items)

        def summary(xs: list[bool | None]) -> dict[str, Any]:
            done = [x for x in xs if x is not None]
            return {"n": len(done), "correct": sum(done), "acc": round(sum(done) / max(1, len(done)), 3),
                    "parse_errors": len(xs) - len(done)}
        return {"paper_wording": summary(paper),
                "answer_wording": summary(answer) | {"missing_rewrites": len(items) - len(ans_items)}}

    # -------------------------------------------------------------- QA
    def qa_sys(self) -> str:
        sk = self.f.words["subject_kind"]
        return f"""You answer a question using ONLY the papers given. Return items. Each item is one holding: the
{sk} (subject), what was done (relation, in your own words), the source (object), an exact quote copied character
for character from one paper that states it, and a short answer sentence. The quote must occur only ONCE in that
paper: if the sentence is repeated, quote a longer stretch around it. List every holding that answers the
question and nothing else. If the papers do not answer it, return no items."""


    def entities_in(self, text: str, pid: str | None = None) -> list[str]:
        """Entity ids named in text, in order. A citation tail after a subject, e.g. "Marrin v. Tolst Media
        (Veldra Court of Appeal, 2019)", belongs to that subject: names inside it are not separate mentions."""
        t = norm_text(text)
        ms = find_mentions(t, self.table_for(pid))
        ents = self.w["entities"]
        skip: set[int] = set()
        for m in ms if self.citation_tail else []:
            if ents[m.eid]["kind"] in self.f.subject_kinds and (x := self.citation_tail.match(t, m.end)):
                skip |= {k for k, n in enumerate(ms) if m.end <= n.start < x.end()}
        return list(dict.fromkeys(m.eid for k, m in enumerate(ms) if k not in skip))

    def resolve(self, it: dict[str, Any], step: str, pid: str | None = None) -> dict[str, Any]:
        """QA item -> fact id, by the pack's rules (world.fact_errors: allowed kinds, time order), never by name
        length. Status: resolved | resolved_by_judge | no_valid_subject | ambiguous_subject | no_valid_object |
        relation_none | invalid_fact | ambiguous_object."""
        ents = self.w["entities"]
        subj = [e for e in self.entities_in(it["subject"], pid) if ents[e]["kind"] in self.f.subject_kinds]
        if len(subj) != 1:
            return {"resolution": "ambiguous_subject" if subj else "no_valid_subject", "as_fact": None,
                    "object_candidates": []}
        s = subj[0]

        def cands(text: str) -> list[str]:
            return [o for o in self.entities_in(text, pid) if o != s
                    and any(not fact_errors((s, r, o), ents, self.f) for r in self.f.relations)]
        objs = cands(it["object"]) or cands(it["quote"])
        out: dict[str, Any] = {"object_candidates": objs, "as_fact": None}
        if not objs:
            return out | {"resolution": "no_valid_object"}
        judged = {o: self.judge(it["answer_sentence"], s, o, step) for o in objs}
        ok = {o: r for o, r in judged.items() if r not in ("none", "parse_error")
              and not fact_errors((s, r, o), ents, self.f)}
        if all(r == "parse_error" for r in judged.values()):
            return out | {"resolution": "parse_error"}
        if len(objs) == 1:
            o = objs[0]
            if judged[o] == "none":
                return out | {"resolution": "relation_none"}
            if o not in ok:
                return out | {"resolution": "invalid_fact", "judged": f"{s}-{judged[o]}-{o}"}
            return out | {"resolution": "resolved", "as_fact": f"{s}-{ok[o]}-{o}"}
        if len(ok) == 1:
            (o, r), = ok.items()
            return out | {"resolution": "resolved_by_judge", "as_fact": f"{s}-{r}-{o}"}
        return out | {"resolution": "ambiguous_object", "judged": judged}

    def evidence(self, it: dict[str, Any], papers: dict[str, str], tagged: dict[str, Any]) -> dict[str, Any]:
        """The strict evidence rule (#2). The quote, normalized like the paper, must occur exactly once across the
        papers given (not_found / ambiguous_quote otherwise). Then, for the item's fact (or, for a wrong answer,
        all gold facts): at least min_inside of the quote's characters lie in sentences tagged for that fact
        (outside_gold if none, too_long if some), and the quote names both the subject and the object or covers
        at least min_sentence_cover of one tagged sentence (too_short otherwise). Returns {"pid", "ok"}, where
        ok(fact or None, gold) -> (bool, reason)."""
        qn = norm(it["quote"])
        hits = [(p, i) for p, t in papers.items() for i in _find_all(t.lower(), qn)] if qn else []
        if len(hits) != 1:
            reason = "not_found" if not hits else "ambiguous_quote"
            return {"pid": None, "ok": lambda fact, gold: (False, reason)}
        pid, a = hits[0]
        b = a + len(qn)
        cfg = self.s.evidence

        def ok(fact: str | None, gold: list[str]) -> tuple[bool, str]:
            spans = [sp for i in ([fact] if fact else gold) for sp in tagged[pid]["spans"].get(i, [])]
            inside = sum(max(0, min(b, e) - max(a, s_)) for s_, e in spans) / max(1, b - a)
            if inside == 0:
                return False, "outside_gold"
            if inside < cfg["min_inside"]:
                return False, "too_long"
            facts = [self.facts[i] for i in ([fact] if fact else gold)]
            named = {m.eid for m in find_mentions(papers[pid][a:b], self.table_for(pid))}
            both = any({fa["s"], fa["o"]} <= named for fa in facts)
            cover = max((max(0, min(b, e) - max(a, s_)) / max(1, e - s_) for s_, e in spans), default=0)
            if not both and cover < cfg["min_sentence_cover"]:
                return False, "too_short"
            return True, "ok"
        return {"pid": pid, "ok": ok}

    def qa_one(self, q: dict[str, Any], tagged: dict[str, Any]) -> dict[str, Any]:
        raw = {pid: self.paper(pid) for pid in q["papers"]}
        blob = "\n\n".join(f"=== paper {pid} ===\n{md}" for pid, md in raw.items())
        papers = {pid: normalize_paper(md).text for pid, md in raw.items()}   # same normalization as the sentences
        user = f"Question: {q['text']}\n\n{blob}"
        got = self.call("qa", f"qa:{q['id']}", self.qa_sys(), user, QAOut)
        if got is None:          # the system under test gave no usable answer: it scores 0, and the report says why
            return {"id": q["id"], "question": q["text"], "papers": q["papers"], "gold": q["gold"], "items": [],
                    "parse_error": True, "quote_repair": False, "recall": 0.0, "answer_recall": 0.0,
                    "precision": None}
        locate = lambda it: it["paper"] if it["paper"] in papers else next(  # noqa: E731
            (p for p in papers if norm(it["quote"]) in norm(papers[p])), None)
        bad = [it["quote"] for it in got["items"] if (p := locate(it)) and norm(papers[p]).count(norm(it["quote"])) > 1]
        repaired = False
        if bad:      # one repair call: quotes must be unique in their paper
            fixed = self.call("qa", f"qa:{q['id']}:repair", self.qa_sys(), user + "\n\nYOUR LAST ANSWER:\n"
                              + json.dumps(got) + "\n\nThese quotes occur more than once in their paper; quote a "
                              "longer, unique stretch instead:\n" + "\n".join(bad), QAOut)
            repaired = fixed is not None
            got = fixed or got
        scored = []
        for it in got["items"]:
            pid = locate(it)
            ev = self.evidence(it, papers, tagged)
            qn = norm(it["quote"])
            prov, span_fact, ambiguous = "made_up_quote", None, False
            if pid and qn in norm(papers[pid]):
                ambiguous = norm(papers[pid]).count(qn) > 1
                S = tagged[pid]["sentences"]
                cover = [s for s in S if norm(s[2]) in qn or qn in norm(s[2]) or
                         (len(qn) > 40 and (qn[:40] in norm(s[2]) or qn[-40:] in norm(s[2])))]
                over = {i for i, spans in tagged[pid]["spans"].items() for sp in spans
                        for s in cover if s[0] < sp[1] and sp[0] < s[1]}
                hit = over & set(q["gold"])
                prov, span_fact = (("gold_span", sorted(hit)[0]) if hit else ("distractor_span", sorted(over)[0])
                                   if over else ("no_planted_span", None))
            res = self.resolve(it, f"judge:qa:{q['id']}", ev["pid"] or pid)
            as_fact = res["as_fact"]
            right = as_fact in q["gold"]
            strict = ev["ok"](as_fact if right else None, q["gold"])
            scored.append({**it, "provenance": prov, "ambiguous_quote": ambiguous, "span_fact": span_fact,
                           **res, "answer_right": right,
                           "evidence_ok": strict[0], "evidence_reason": strict[1],
                           "evidence_ok_legacy": prov == "gold_span",
                           "correct": right and strict[0], "correct_legacy": right and prov == "gold_span"})
        found = {x["as_fact"] for x in scored if x["correct"]}
        found_legacy = {x["as_fact"] for x in scored if x["correct_legacy"]}
        answered = {x["as_fact"] for x in scored if x["answer_right"]}
        n = len(q["gold"])
        return {"id": q["id"], "question": q["text"], "papers": q["papers"], "gold": q["gold"], "items": scored,
                "parse_error": False, "quote_repair": repaired, "recall": round(len(found) / n, 3),
                "answer_recall": round(len(answered) / n, 3),     # right answer, whatever the evidence
                "precision": round(sum(x["correct"] for x in scored) / len(scored), 3) if scored else None,
                "recall_legacy": round(len(found_legacy) / n, 3),
                "precision_legacy": round(sum(x["correct_legacy"] for x in scored) / len(scored), 3)
                if scored else None}

    # -------------------------------------------------------------- style-leak
    LEAK_SYS = """A test builder took the paper below and planted benchmark facts in it. After the paper is a list of
sentences from it. Exactly ONE of them is a planted fact sentence; the others are ordinary sentences of the paper.
Use the whole paper to decide. Pick exactly one number."""

    def leak(self, tagged: dict[str, Any], k: int = 20) -> dict[str, Any]:
        items = [(pid, i) for pid, t in tagged.items() for i, sp in t["spans"].items() if sp]
        trials = []
        for n in range(self.s.leak_trials):
            pid, i = items[n % len(items)] if n < len(items) else self.rng.choice(items)
            t = tagged[pid]
            S = t["sentences"]
            tagged_idx = {j for sp in t["spans"].values() for j, s in enumerate(S) if [s[0], s[1]] in sp}
            span = self.rng.choice(t["spans"][i])
            gi = next(j for j, s in enumerate(S) if [s[0], s[1]] == span)
            n_names = lambda txt: len({m.eid for m in find_mentions(txt, self.table_for(pid))})  # noqa: E731
            two = [j for j in range(len(S)) if j not in tagged_idx and n_names(S[j][2]) >= 2]
            one = sorted((j for j in range(len(S)) if j not in tagged_idx and n_names(S[j][2]) == 1),
                         key=lambda j: abs(len(S[j][2].split()) - len(S[gi][2].split())))
            pool = self.rng.sample(two, min(k - 1, len(two)))
            pool += one[:k - 1 - len(pool)] + [gi]
            self.rng.shuffle(pool)
            trials.append((n, pid, [S[j][2] for j in pool], pool.index(gi), len(pool)))

        def run(tr: tuple) -> tuple[bool, float] | None:
            n, pid, texts, gold, size = tr
            lst = "\n".join(f"{j}. {s}" for j, s in enumerate(texts))
            check = lambda out: None if 0 <= out["pick"] < size else f"pick a number from 0 to {size - 1}"  # noqa: E731
            got = self.call("leak", f"leak:{n}", self.LEAK_SYS, f"PAPER:\n{self.paper(pid)}\n\nSENTENCES:\n{lst}",
                            LeakOut, check)
            return (got["pick"] == gold, 1 / size) if got else None
        every = pmap(run, trials)
        res = [x for x in every if x is not None]
        h, n = sum(x for x, _ in res), len(res)
        return {"trials": n, "parse_errors": len(every) - n, "hits": h, "rate": round(h / max(1, n), 3),
                "ci95": wilson(h, n), "chance": round(sum(c for _, c in res) / max(1, n), 3), "bar": 0.10}

    # -------------------------------------------------------------- all
    def run(self) -> dict[str, Any]:
        from paperfactory.repair import failed      # a paper that still disagrees with the world is left out
        pids = [p for p in self.w["papers"] if (self.s.out_dir / "work" / p / "paper.md").is_file()
                and not failed(self.s.out_dir, p)]
        tagged = dict(zip(pids, pmap(self.tag_paper, pids)))
        (self.s.out_dir / "tagged.json").write_text(json.dumps({"scoring_version": SCORING_VERSION, "papers": tagged},
                                                               indent=1), encoding="utf-8")
        qs = [q for q in self.G["questions"] if all(p in tagged for p in q["papers"])]
        rep: dict[str, Any] = {"scoring_version": SCORING_VERSION, "settings": dict(vars(self.s)),
                               "papers_written": len(pids), "papers_planned": len(self.w["papers"]),
                               "papers_failed_world_check": [p for p in self.w["papers"] if failed(self.s.out_dir, p)],
                               "tagging": {p: {k: v for k, v in t.items() if k not in ("sentences", "spans")}
                                           | {"spans_per_fact": {i: len(x) for i, x in t["spans"].items()}}
                                           for p, t in tagged.items()}}
        rep["verifier_test"] = self.verifier_test(tagged)
        rep["judge_validation"] = self.judge_validation(tagged)
        rep["qa"] = pmap(lambda q: self.qa_one(q, tagged), qs)
        qa = rep["qa"]
        mean = lambda xs: round(sum(xs) / max(1, len(xs)), 3)  # noqa: E731
        rep["qa_summary"] = {"questions": len(qa), "recall": mean([q["recall"] for q in qa]),
                             "answer_recall": mean([q["answer_recall"] for q in qa]),
                             "precision": mean([q["precision"] for q in qa if q["precision"] is not None]),
                             "quote_repairs": sum(q["quote_repair"] for q in qa),
                             "parse_errors": sum(q["parse_error"] for q in qa),
                             "recall_legacy": mean([q["recall_legacy"] for q in qa if "recall_legacy" in q]),
                             "precision_legacy": mean([q["precision_legacy"] for q in qa
                                                       if q.get("precision_legacy") is not None])}
        right = [it for q in qa for it in q["items"] if it["answer_right"]]
        rep["evidence"] = {
            "thresholds": self.s.evidence, "right_answers": len(right),
            "strict_accuracy": mean([it["evidence_ok"] for it in right]),
            "legacy_accuracy": mean([it["evidence_ok_legacy"] for it in right]),
            "legacy_only": [{"question": q["id"], "as_fact": it["as_fact"], "reason": it["evidence_reason"],
                             "quote": it["quote"][:200]} for q in qa for it in q["items"]
                            if it["evidence_ok_legacy"] and not it["evidence_ok"]]}
        rep["style_leak"] = self.leak(tagged) if self.s.leak_trials else None
        return rep


def _find_all(text: str, sub: str) -> list[int]:
    out, i = [], text.find(sub)
    while i >= 0:
        out.append(i)
        i = text.find(sub, i + 1)
    return out


def wilson(h: int, n: int, z: float = 1.96) -> list[float]:
    if not n:
        return [0.0, 1.0]
    p = h / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    w = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - w, 3), round(c + w, 3)]

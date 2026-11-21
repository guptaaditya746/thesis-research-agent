"""After writing: find where each planted fact sits (tagging), test the checks, then question answering + scoring.

Steps (each LLM call is a separate fresh call; the model per job comes from the settings):
  tag       tagger marks sentences per fact; code checks names; verifier (separate call) confirms each tag;
            a sweep sends untagged sentences that name both ends of a fact to the verifier too.
  verifier  test: accepted tags must get "yes"; the same sentence with another relation (made by code) "no".
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
from typing import Any

from paperfactory import SCORING_VERSION
from paperfactory.llm import pmap
from paperfactory.packs import Field
from paperfactory.text import (alias_table, find_mentions, names, norm, norm_text, normalize_paper, split_rules,
                                split_sents)
from paperfactory.world import fact_errors
from paperfactory.write import repeated_phrases


class Eval:
    def __init__(self, s, w: dict[str, Any], f: Field, gold: dict[str, Any], call, max_mentions: int = 3):
        self.s, self.w, self.f, self.G, self.call = s, w, f, gold, call
        self.max_mentions = max_mentions
        self.facts = gold["facts"]
        self.rng = random.Random(s.seed)
        self.letters = {chr(65 + i): r for i, r in enumerate(f.relations)} | {chr(65 + len(f.relations)): "none"}
        self.rules = split_rules(f, w)
        self.table = alias_table(w, f)
        tail = f.raw["text"]["citation_tail"]
        self.citation_tail = re.compile(tail) if tail else None

    # -------------------------------------------------------------- helpers
    def mentions(self, text: str, eid: str) -> bool:
        return any(m.eid == eid for m in find_mentions(text, self.table))

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

    TAG_SCHEMA = {"type": "object", "required": ["tags"], "properties": {"tags": {"type": "array", "items": {
        "type": "object", "required": ["id", "sentences"], "properties": {
            "id": {"type": "string"}, "sentences": {"type": "array", "items": {"type": "integer"}}}}}}}
    VER_SCHEMA = {"type": "object", "required": ["answers"], "properties": {"answers": {"type": "array", "items": {
        "type": "object", "required": ["n", "verdict"], "properties": {
            "n": {"type": "integer"}, "verdict": {"type": "string", "enum": ["yes", "no"]}}}}}}

    def verify(self, pairs: list[tuple[str, str, dict]], step: str) -> list[bool | None]:
        out: list[bool | None] = []
        for i in range(0, len(pairs), 25):
            chunk = pairs[i:i + 25]
            items = [{"n": j, "context": c, "sentence": s, "holding": self.fact_text(fa)}
                     for j, (c, s, fa) in enumerate(chunk)]
            got = self.call("verifier", step, self.ver_sys(), json.dumps(items, indent=1), self.VER_SCHEMA)
            by = {a["n"]: a["verdict"] == "yes" for a in got["answers"]}
            out += [by.get(j) for j in range(len(chunk))]
        return out

    def tag_paper(self, pid: str) -> dict[str, Any]:
        sents = split_sents(self.paper(pid), self.rules)
        facts = [fa for fa in self.facts.values() if pid in fa["papers"]]
        user = json.dumps({"sentences": [{"n": i, "text": s[2]} for i, s in enumerate(sents)],
                           "holdings": [{"id": fa["id"], "holding": self.fact_text(fa)} for fa in facts]}, indent=1)
        got = self.call("tagger", f"tag:{pid}", self.tag_sys(), user, self.TAG_SCHEMA)
        notes, tags = [], {fa["id"]: set() for fa in facts}
        actor = self.f.words["actor"].split()[-1].lower()
        for t in got["tags"]:
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
                subj_ok = self.mentions(ctx + sent, fa["s"]) or actor in sent.lower() or " it " in f" {sent.lower()}"
                if not self.mentions(sent, fa["o"]) or not subj_ok:
                    notes.append(f"{t['id']} s{n}: names missing (code)")
                    continue
                tags[t["id"]].add(n)
        pairs = [(n, i) for i, ns in tags.items() for n in sorted(ns)]
        sweep = [(n, fa["id"]) for fa in facts for n, s in enumerate(sents)
                 if n not in tags[fa["id"]] and self.mentions(s[2], fa["o"]) and self.mentions(s[2], fa["s"])]
        ok = self.verify([(sents[n - 1][2] if n else "", sents[n][2], self.facts[i]) for n, i in pairs + sweep],
                         f"verify:{pid}")
        kept: dict[str, set[int]] = {i: set() for i in tags}
        rejected, added = [], []
        for (n, i), v in zip(pairs + sweep, ok):
            if (n, i) in pairs and v:
                kept[i].add(n)
            elif (n, i) in pairs:
                rejected.append((i, n))
            elif v:
                kept[i].add(n)
                added.append((i, n))
        subsections = [f"s{n}: {m.surface}{m.subsection}" for n, st in enumerate(sents)
                       for m in find_mentions(st[2], self.table) if m.subsection]
        text = self.paper(pid)
        all_names = [x for e in self.w["entities"] for x in names(self.w, e)]
        return {"pid": pid, "words": len(text.split()), "n_sentences": len(sents), "tags_proposed": len(pairs),
                "tags_rejected_by_verifier": rejected, "tags_added_by_sweep": added, "code_notes": notes,
                "subsection_mentions": subsections,
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
        pos = [g for g, it in zip(got, items) if it[3]]
        neg = [g for g, it in zip(got, items) if not it[3]]
        right = sum(bool(g) for g in pos) + sum(g is False for g in neg)
        return {"positives": len(pos), "pos_yes": sum(bool(g) for g in pos), "negatives": len(neg),
                "neg_no": sum(g is False for g in neg), "accuracy": round(right / max(1, len(items)), 3)}

    # -------------------------------------------------------------- meaning judge
    def judge_sys(self) -> str:
        sk = self.f.words["subject_kind"]
        opts = "\n".join(f"{k} = {self.f.relations[r]['words']} ({self.f.relations[r]['meaning']})"
                         for k, r in self.letters.items() if r != "none")
        none = next(k for k, r in self.letters.items() if r == "none")
        return (f"Read the sentence. It is about what one {sk} did with a source. Choose what the sentence says:\n"
                f"{opts}\n{none} = none of these / the sentence does not say.\nJudge only from the sentence.")

    def judge(self, sentence: str, s: str, o: str, step: str) -> str:
        schema = {"type": "object", "required": ["choice"],
                  "properties": {"choice": {"type": "string", "enum": list(self.letters)}}}
        user = json.dumps({self.f.words["subject_kind"]: self.label(s), "source": self.label(o),
                           "sentence": sentence}, indent=1)
        return self.letters[self.call("judge", step, self.judge_sys(), user, schema)["choice"]]

    REWORD_SYS = """Rewrite each sentence as a short plain answer sentence, as a question-answering system would
write it. Keep its meaning exactly: same subject, same source, same action. Do not add facts. Return one per input."""
    REWORD_SCHEMA = {"type": "object", "required": ["rewritten"], "properties": {"rewritten": {"type": "array",
        "items": {"type": "object", "required": ["n", "text"], "properties": {
            "n": {"type": "integer"}, "text": {"type": "string"}}}}}}

    def judge_validation(self, tagged: dict[str, Any]) -> dict[str, Any]:
        items = []
        for t in tagged.values():
            S = t["sentences"]
            for i, spans in t["spans"].items():
                for sp in spans:
                    items.append((i, next(s[2] for s in S if [s[0], s[1]] == sp)))
        rew: dict[int, str] = {}
        for b in range(0, len(items), 40):
            got = self.call("judge", f"reword:{b}", self.REWORD_SYS, json.dumps(
                [{"n": b + j, "text": s} for j, (_, s) in enumerate(items[b:b + 40])], indent=1), self.REWORD_SCHEMA)
            rew |= {r["n"]: r["text"] for r in got["rewritten"]}

        def ok(it: tuple[str, str], step: str) -> bool:
            fa = self.facts[it[0]]
            return self.judge(it[1], fa["s"], fa["o"], step) == fa["r"]
        paper = pmap(lambda it: ok(it, "judge:paper"), items)
        ans_items = [(i, rew[n]) for n, (i, _) in enumerate(items) if n in rew]
        answer = pmap(lambda it: ok(it, "judge:answer"), ans_items)
        acc = lambda xs: round(sum(xs) / max(1, len(xs)), 3)  # noqa: E731
        return {"paper_wording": {"n": len(paper), "correct": sum(paper), "acc": acc(paper)},
                "answer_wording": {"n": len(answer), "correct": sum(answer), "acc": acc(answer),
                                   "missing_rewrites": len(items) - len(ans_items)}}

    # -------------------------------------------------------------- QA
    def qa_sys(self) -> str:
        sk = self.f.words["subject_kind"]
        return f"""You answer a question using ONLY the papers given. Return items. Each item is one holding: the
{sk} (subject), what was done (relation, in your own words), the source (object), an exact quote copied character
for character from one paper that states it, and a short answer sentence. The quote must occur only ONCE in that
paper: if the sentence is repeated, quote a longer stretch around it. List every holding that answers the
question and nothing else. If the papers do not answer it, return no items."""

    QA_SCHEMA = {"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {
        "type": "object", "required": ["paper", "subject", "relation", "object", "quote", "answer_sentence"],
        "properties": {k: {"type": "string"} for k in
                       ("paper", "subject", "relation", "object", "quote", "answer_sentence")}}}}}

    def entities_in(self, text: str) -> list[str]:
        """Entity ids named in text, in order. A citation tail after a subject, e.g. "Marrin v. Tolst Media
        (Veldra Court of Appeal, 2019)", belongs to that subject: names inside it are not separate mentions."""
        t = norm_text(text)
        ms = find_mentions(t, self.table)
        ents = self.w["entities"]
        skip: set[int] = set()
        for m in ms if self.citation_tail else []:
            if ents[m.eid]["kind"] in self.f.subject_kinds and (x := self.citation_tail.match(t, m.end)):
                skip |= {k for k, n in enumerate(ms) if m.end <= n.start < x.end()}
        return list(dict.fromkeys(m.eid for k, m in enumerate(ms) if k not in skip))

    def resolve(self, it: dict[str, Any], step: str) -> dict[str, Any]:
        """QA item -> fact id, by the pack's rules (world.fact_errors: allowed kinds, time order), never by name
        length. Status: resolved | resolved_by_judge | no_valid_subject | ambiguous_subject | no_valid_object |
        relation_none | invalid_fact | ambiguous_object."""
        ents = self.w["entities"]
        subj = [e for e in self.entities_in(it["subject"]) if ents[e]["kind"] in self.f.subject_kinds]
        if len(subj) != 1:
            return {"resolution": "ambiguous_subject" if subj else "no_valid_subject", "as_fact": None,
                    "object_candidates": []}
        s = subj[0]

        def cands(text: str) -> list[str]:
            return [o for o in self.entities_in(text) if o != s
                    and any(not fact_errors((s, r, o), ents, self.f) for r in self.f.relations)]
        objs = cands(it["object"]) or cands(it["quote"])
        out: dict[str, Any] = {"object_candidates": objs, "as_fact": None}
        if not objs:
            return out | {"resolution": "no_valid_object"}
        judged = {o: self.judge(it["answer_sentence"], s, o, step) for o in objs}
        ok = {o: r for o, r in judged.items() if r != "none" and not fact_errors((s, r, o), ents, self.f)}
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

    def qa_one(self, q: dict[str, Any], tagged: dict[str, Any]) -> dict[str, Any]:
        raw = {pid: self.paper(pid) for pid in q["papers"]}
        blob = "\n\n".join(f"=== paper {pid} ===\n{md}" for pid, md in raw.items())
        papers = {pid: normalize_paper(md).text for pid, md in raw.items()}   # same normalization as the sentences
        user = f"Question: {q['text']}\n\n{blob}"
        got = self.call("qa", f"qa:{q['id']}", self.qa_sys(), user, self.QA_SCHEMA)
        locate = lambda it: it["paper"] if it["paper"] in papers else next(  # noqa: E731
            (p for p in papers if norm(it["quote"]) in norm(papers[p])), None)
        bad = [it["quote"] for it in got["items"] if (p := locate(it)) and norm(papers[p]).count(norm(it["quote"])) > 1]
        repaired = False
        if bad:      # one repair call: quotes must be unique in their paper
            got = self.call("qa", f"qa:{q['id']}:repair", self.qa_sys(), user + "\n\nYOUR LAST ANSWER:\n"
                            + json.dumps(got) + "\n\nThese quotes occur more than once in their paper; quote a longer,"
                            " unique stretch instead:\n" + "\n".join(bad), self.QA_SCHEMA)
            repaired = True
        scored = []
        for it in got["items"]:
            pid = locate(it)
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
            res = self.resolve(it, f"judge:qa:{q['id']}")
            as_fact = res["as_fact"]
            scored.append({**it, "provenance": prov, "ambiguous_quote": ambiguous, "span_fact": span_fact,
                           **res, "answer_right": as_fact in q["gold"],
                           "correct": prov == "gold_span" and as_fact in q["gold"]})
        found = {x["as_fact"] for x in scored if x["correct"]}
        answered = {x["as_fact"] for x in scored if x["answer_right"]}
        n = len(q["gold"])
        return {"id": q["id"], "question": q["text"], "papers": q["papers"], "gold": q["gold"], "items": scored,
                "quote_repair": repaired, "recall": round(len(found) / n, 3),
                "answer_recall": round(len(answered) / n, 3),     # right answer, whatever the evidence
                "precision": round(sum(x["correct"] for x in scored) / len(scored), 3) if scored else None}

    # -------------------------------------------------------------- style-leak
    LEAK_SYS = """A test builder took the paper below and planted benchmark facts in it. After the paper is a list of
sentences from it. Exactly ONE of them is a planted fact sentence; the others are ordinary sentences of the paper.
Use the whole paper to decide. Pick exactly one number."""
    LEAK_SCHEMA = {"type": "object", "required": ["pick"], "properties": {"pick": {"type": "integer"}}}

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
            n_names = lambda txt: len({m.eid for m in find_mentions(txt, self.table)})  # noqa: E731
            two = [j for j in range(len(S)) if j not in tagged_idx and n_names(S[j][2]) >= 2]
            one = sorted((j for j in range(len(S)) if j not in tagged_idx and n_names(S[j][2]) == 1),
                         key=lambda j: abs(len(S[j][2].split()) - len(S[gi][2].split())))
            pool = self.rng.sample(two, min(k - 1, len(two)))
            pool += one[:k - 1 - len(pool)] + [gi]
            self.rng.shuffle(pool)
            trials.append((n, pid, [S[j][2] for j in pool], pool.index(gi), len(pool)))

        def run(tr: tuple) -> tuple[bool, float]:
            n, pid, texts, gold, size = tr
            lst = "\n".join(f"{j}. {s}" for j, s in enumerate(texts))
            got = self.call("leak", f"leak:{n}", self.LEAK_SYS, f"PAPER:\n{self.paper(pid)}\n\nSENTENCES:\n{lst}",
                            self.LEAK_SCHEMA)
            return got["pick"] == gold, 1 / size
        res = pmap(run, trials)
        h, n = sum(x for x, _ in res), len(res)
        return {"trials": n, "hits": h, "rate": round(h / max(1, n), 3), "ci95": wilson(h, n),
                "chance": round(sum(c for _, c in res) / max(1, n), 3), "bar": 0.10}

    # -------------------------------------------------------------- all
    def run(self) -> dict[str, Any]:
        pids = [p for p in self.w["papers"] if (self.s.out_dir / "work" / p / "paper.md").is_file()]
        tagged = dict(zip(pids, pmap(self.tag_paper, pids)))
        (self.s.out_dir / "tagged.json").write_text(json.dumps({"scoring_version": SCORING_VERSION, "papers": tagged},
                                                               indent=1), encoding="utf-8")
        qs = [q for q in self.G["questions"] if all(p in tagged for p in q["papers"])]
        rep: dict[str, Any] = {"scoring_version": SCORING_VERSION, "settings": dict(vars(self.s)),
                               "papers_written": len(pids), "papers_planned": len(self.w["papers"]),
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
                             "quote_repairs": sum(q["quote_repair"] for q in qa)}
        rep["style_leak"] = self.leak(tagged) if self.s.leak_trials else None
        return rep


def wilson(h: int, n: int, z: float = 1.96) -> list[float]:
    if not n:
        return [0.0, 1.0]
    p = h / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    w = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - w, 3), round(c + w, 3)]

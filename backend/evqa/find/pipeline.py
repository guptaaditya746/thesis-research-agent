"""Find v0: from a locked Spec to the papers and passages that hold its values.

    hits = evqa.find.run(spec, "medical", cfg)            # list[FindHit], kept papers only
    res = evqa.find.find(spec, "medical", cfg)            # FindResult: hits + dropped papers + agent log + coverage

Sub-steps (each one's findings are kept in FindHit.details and FindResult):
1. regex   (code)  every subject name/synonym as a tolerant whole word over every paper.
2. terms   (LLM+code, cfg.find.search_terms) the model lists other wordings of the subjects and the measure from
                   general knowledge (abbreviations, spellings, brand names); code keeps a term only when it is short,
                   new, aimed at a spec target and written in some paper, then searches it as an exact word. Subject
                   terms make candidates (the screen still decides) but never become the subject's names; measure
                   terms make candidates only when the spec names no subject. No BM25, no embeddings (Aditya, 21 Nov).
3. screen  (LLM)   per candidate paper (title, abstract, the passages holding the most search words): yes/no/unsure.
4. mark    (LLM)   per kept paper, all its passages numbered: which hold values (or a column's value); code checks
                   the id, the quote (inside the passage; a quote shortened with "..." checks when every piece is
                   inside, in order, and its longest piece is kept) and the offsets (exactly the paper's text).
5. coverage (code) spec subjects without a value passage, spec columns without any passage.
6. agent   (LLM+code, cfg.find.agent) one gap at a time: the model proposes one term seen in the papers' text,
                   code checks it occurs in the corpus and re-runs regex + screen + mark. The number of model
                   steps is capped by code at cfg.find.agent_max_steps. Every subject first gets an "other names?"
                   gap, because a paper that calls the drug only by a code name leaves no coverage hole.
Reads papers only through evqa.corpus.papers."""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import dspy
from pydantic import BaseModel

from evqa import corpus
from evqa.contracts import FindHit, Passage, RunConfig, Spec
from evqa.llm import pmap
from evqa.find import passages as P
from evqa.find.prompts import PROMPTS_VERSION, MarkPassages, NextSearch, ScreenPaper, SearchTerms
from evqa.find.search import find_term, rank_passages

MARK_CHUNK_CHARS = 4000       # passages per marking call, by text size (Qwen gave empty replies at 12000)
SCREEN_PASSAGES = 6           # matched passages shown to the screen
SHOW_CHARS = 1200             # a passage shown to the screen is cut here
SNIPPET_CHARS = 200           # agent text: characters each side of a name match
AGENT_SNIPPETS = 12
MAX_SEARCH_TERMS = 12         # model terms read per question
MAX_TERM_WORDS = 6
GENERAL = set("level levels change changes effect effects result results outcome outcomes value values patients "
              "treatment therapy drug drugs dose doses study trial measure".split())   # too general to search


class FindResult(BaseModel):
    """Everything Find did, for the run folder and the UI. `hits` is what Extract reads."""
    qid: str
    hits: list[FindHit] = []          # kept papers (screen yes, or unsure with a value passage for a subject)
    dropped: list[FindHit] = []       # candidates not kept (screen no, unsure without marks, over the screen cap)
    agent: list[dict[str, Any]] = []  # one entry per agent step
    aliases: list[dict[str, str]] = []   # other names the agent found: subject, term, paper
    coverage: dict[str, Any] = {}     # gaps before and after the agent
    problems: list[str] = []
    prompts: str = PROMPTS_VERSION


# ---------------------------------------------------------------- spec as text
def _label(point_id: str) -> str:
    return point_id.replace("_", " ")


def spec_text(spec: Spec, found: dict[str, list[str]] | None = None) -> str:
    """The spec in plain words for the prompts. `found`: subject label -> other names found in the papers."""
    found = found or {}
    lines = [f"Question: {spec.question}"]
    for s in spec.subjects:
        bits = [f"Subject: {s.label}"]
        if s.synonyms:
            bits.append(f"other names: {', '.join(s.synonyms)}")
        if found.get(s.label):
            bits.append(f"names the papers use for it: {', '.join(found[s.label])}")
        if not s.known and not s.synonyms:
            bits.append("no other names known")
        if s.definition:
            bits.append(s.definition)
        lines.append("; ".join(bits))
    if spec.comparator:
        lines.append(f"Compared with: {spec.comparator.label}")
    if not spec.subjects:
        lines.append("Subject: any drug (the question names none)")
    m = spec.measure
    if not m.label:
        lines.append("Measure: any measure (the question names none)")
    else:
        lines.append(f"Measure: {m.label}" + (f" (other names: {', '.join(m.synonyms)})" if m.synonyms else "")
                     + (f"; {m.definition}" if m.definition else ""))
    fixed = {**spec.fixed, **{_label(o.id): o.choice for o in spec.open_points if o.choice.strip().lower() != "all"}}
    lines.append("Fixed: " + ("; ".join(f"{_label(k)} = {v}" for k, v in fixed.items()) if fixed else "nothing"))
    alls = [_label(o.id) for o in spec.open_points if o.choice.strip().lower() == "all"]
    if alls:
        lines.append("Open, answered \"all\" (show every value, never a reason to drop a paper): " + ", ".join(alls))
    if spec.columns:
        lines.append("Answer columns: " + ", ".join(spec.columns))
    return "\n".join(lines)


# ---------------------------------------------------------------- the run state
class _Find:
    def __init__(self, spec: Spec, domain: str, cfg: RunConfig, lm: dspy.BaseLM | None,
                 log: Callable[[dict[str, Any]], None] | None):
        self.spec, self.cfg = spec, cfg
        self.texts = corpus.papers(domain)
        self.passages = {pid: P.split(t) for pid, t in self.texts.items()}
        self._lm = lm
        self._log = log or (lambda e: None)
        self.names = {s.label: [s.label, *s.synonyms] for s in spec.subjects}
        self.found: dict[str, list[str]] = {}          # subject -> other names found by the agent
        self.measure_terms = [t for t in (spec.measure.label, *spec.measure.synonyms) if t.strip()]
        self.terms: dict[str, list[str]] = {}          # "measure" or subject label -> model search terms code kept
        self.details: dict[str, dict[str, Any]] = {}   # paper -> details (regex, terms, agent, screen passages, ...)
        self.sources: dict[str, set[str]] = {}
        self.screen: dict[str, tuple[str, str, str]] = {}   # paper -> (decision, reason, spec text used)
        self.marks: dict[str, dict[int, Passage]] = {}      # paper -> passage index -> marked passage
        self.marked_with: dict[str, str] = {}               # paper -> spec text its marking used
        self.res = FindResult(qid=spec.qid)

    # ----------------------------------------------------------- llm
    def lm(self) -> dspy.BaseLM:
        if self._lm is None:
            from evqa.lm import make_lm
            self._lm = make_lm(self.cfg.llm_for("find"))
        return self._lm

    def predict(self, sig: type[dspy.Signature], **inputs: Any) -> dspy.Prediction | None:
        try:
            with dspy.context(lm=self.lm(), adapter=dspy.JSONAdapter()):
                return dspy.Predict(sig)(**inputs)
        except Exception as e:  # noqa: BLE001 - an unreadable reply is recorded, the run goes on
            first = " ".join(str(e).split("\n\n")[0].split())
            self.problem(f"{sig.__name__}: {type(e).__name__}: {first[:300]}")
            return None

    def problem(self, text: str) -> None:
        self.res.problems.append(text)
        self._log({"kind": "problem", "text": text})

    # ----------------------------------------------------------- 1 + 2: code search
    def _detail(self, pid: str) -> dict[str, Any]:
        return self.details.setdefault(pid, {"regex": {}, "terms": {}, "agent": []})

    def regex(self, term: str, source: str, key: str = "regex", candidate: bool = True) -> dict[str, int]:
        """Match `term` over every paper (counts go to details[key]); with `candidate`, papers with a match become
        candidates from `source`."""
        got = {}
        for pid, text in self.texts.items():
            n = len(find_term(term, text))
            if n:
                got[pid] = n
                d = self._detail(pid)
                d.setdefault(key, {})[term] = n
                if candidate:
                    self.sources.setdefault(pid, set()).add(source)
                if source == "agent" and term not in d["agent"]:
                    d["agent"].append(term)
        return got

    def measure_words(self) -> list[str]:
        return self.measure_terms + self.terms.get("measure", [])

    def search_words(self) -> list[str]:
        """Every word Find searches: subject names (with found other names), subject terms, measure words."""
        subj = [t for ts in self.names.values() for t in ts]
        return subj + [t for k, ts in self.terms.items() if k != "measure" for t in ts] + self.measure_words()

    def search_terms(self) -> None:
        """Step 2: the model proposes other wordings; code keeps a term only when it is aimed at a spec target, short,
        new, not too general and written in some paper. Every proposal and its fate goes to coverage."""
        log: list[dict[str, Any]] = []
        self.res.coverage["search_terms"] = log
        if not self.cfg.find.search_terms or not (self.spec.subjects or self.measure_terms):
            return
        out = self.predict(SearchTerms, spec=spec_text(self.spec, self.found))
        labels = {s.label.lower(): s.label for s in self.spec.subjects}
        known = {t.lower() for t in self.search_words()}
        for t in (out.terms or [] if out is not None else [])[:MAX_SEARCH_TERMS]:
            term = " ".join(str(t.term).split())
            target = "measure" if t.target.strip().lower() == "measure" else labels.get(t.target.strip().lower())
            why = ""
            if target is None:
                why = "target not in the spec"
            elif not term or len(term.split()) > MAX_TERM_WORDS or len(term) > 60:
                why = "empty or too long"
            elif len(re.findall(r"[A-Za-z]", term)) < 2:          # "A1c" passes, "24" does not
                why = "no word in it"
            elif term.lower() in known:
                why = "already known"
            elif term.lower() in GENERAL:
                why = "too general"
            elif not any(find_term(term, text) for text in self.texts.values()):
                why = "not in any paper"
            log.append({"target": target or t.target, "term": term, "kept": not why, "why": why})
            if not why:
                known.add(term.lower())
                self.terms.setdefault(target, []).append(term)   # type: ignore[arg-type]
        self._log({"kind": "search_terms", "terms": log})

    def matched_passages(self, pid: str) -> list[int]:
        """Passage indexes of `pid` holding search words: passages naming a subject first, then by how many distinct
        search words they hold, then reading order."""
        names = [t for terms in self.names.values() for t in terms]
        ps = self.passages[pid]
        ranked = rank_passages({pid: ps}, self.search_words(), len(ps))
        named = {i for i, p in enumerate(ps) if any(find_term(t, p.text) for t in names)}
        return [r.index for r, n in sorted(ranked, key=lambda x: (x[0].index not in named, -x[1], x[0].index))]

    # ----------------------------------------------------------- 3: screen
    def screen_papers(self, pids: list[str]) -> None:
        text = spec_text(self.spec, self.found)

        def one(pid: str) -> tuple[str, str, str, list[int]]:
            ps = self.passages[pid]
            show = [i for i in self.matched_passages(pid) if ps[i].section.lower() != "abstract"][:SCREEN_PASSAGES]
            shown = "\n\n".join(f"({ps[i].section}) {ps[i].text[:SHOW_CHARS]}" for i in show) or "(none)"
            out = self.predict(ScreenPaper, spec=text, title=P.title(self.texts[pid]), abstract=P.abstract(ps),
                               passages=shown)
            if out is None:
                return pid, "unsure", "the screen reply could not be read", show
            return pid, str(out.decision), " ".join(str(out.reason).split())[:300], show

        for pid, decision, reason, show in pmap(one, pids):
            self.screen[pid] = (decision, reason, text)
            self._detail(pid)["screen_passages"] = show
            self._log({"kind": "screen", "paper": pid, "decision": decision, "reason": reason})

    # ----------------------------------------------------------- 4: mark
    def _norm(self, s: str) -> str:
        return " ".join(re.sub(r"[|*_`]+", " ", s.lower()).split())

    def _canon(self, values: list[str], allowed: list[str]) -> list[str]:
        by = {a.lower(): a for a in allowed}
        return [by[v.strip().lower()] for v in values if v.strip().lower() in by]

    def mark_papers(self, pids: list[str]) -> None:
        text = spec_text(self.spec, self.found)

        def one(pid: str) -> tuple[str, dict[int, Passage], list[dict[str, Any]]]:
            ps = self.passages[pid]
            chunks: list[list[int]] = [[]]
            size = 0
            for i, p in enumerate(ps):
                if chunks[-1] and size + len(p.text) > MARK_CHUNK_CHARS:
                    chunks.append([])
                    size = 0
                chunks[-1].append(i)
                size += len(p.text)
            got: dict[int, Passage] = {}
            rejected: list[dict[str, Any]] = []
            failed: list[list[int]] = []
            fill = self.screen.get(pid, ("",))[0] == "yes"   # one-subject spec: a value mark without subjects is it

            def ask(chunk: list[int]) -> list[Any]:
                """Mark one chunk; an unreadable reply is asked again as two halves (new, smaller prompts)."""
                shown = "\n\n".join(f"[{i}] ({ps[i].section}) {ps[i].text}" for i in chunk)
                out = self.predict(MarkPassages, spec=text, passages=shown)
                if out is not None:
                    return [(m, chunk) for m in out.marks or []]
                if len(chunk) == 1:
                    failed.append(chunk)
                    return []
                half = len(chunk) // 2
                return ask(chunk[:half]) + ask(chunk[half:])

            for m, chunk in [x for c in chunks for x in ask(c)]:
                why = self._check_mark(pid, m, chunk)
                if why:
                    rejected.append({"id": m.id, "quote": m.quote[:200], "why": why})
                    continue
                labels = [s.label for s in self.spec.subjects]
                alias_of = {t.lower(): s for s, ts in {**self.found}.items() for t in ts}
                subjects = self._canon(m.subjects, labels) + [alias_of[v.lower()] for v in m.subjects
                                                              if v.lower() in alias_of]
                if m.role == "value" and not subjects and len(labels) == 1 and fill:
                    subjects = labels
                p = ps[m.id].model_copy(update={
                    "role": m.role, "quote": self._quote_part(m.quote, ps[m.id].text) or m.quote,
                    "subjects": sorted(set(subjects)),
                    "columns": self._canon(m.columns, self.spec.columns)})
                if m.id in got:   # the same passage marked twice: keep the union
                    old = got[m.id]
                    p = p.model_copy(update={
                        "role": "value" if "value" in (old.role, p.role) else "context",
                        "subjects": sorted(set(old.subjects) | set(p.subjects)),
                        "columns": [c for c in self.spec.columns if c in old.columns or c in p.columns]})
                got[m.id] = p
            if failed:
                rejected.append({"id": [i for c in failed for i in c], "quote": "", "why": "reply unreadable"})
            return pid, got, rejected

        for pid, got, rejected in pmap(one, pids):
            self.marks[pid] = got
            self.marked_with[pid] = text
            d = self._detail(pid)
            d["marks"] = sorted(got)
            d["marks_rejected"] = rejected
            self._log({"kind": "mark", "paper": pid, "marked": sorted(got), "rejected": len(rejected)})

    def _check_mark(self, pid: str, m: Any, chunk: list[int]) -> str:
        """Code acceptance of one mark; '' when accepted, else the reason."""
        if m.id not in chunk:
            return "id not among the passages shown"
        p = self.passages[pid][m.id]
        if not P.check(self.texts[pid], p):
            return "passage offsets do not match the paper"
        if not m.quote.strip() or self._quote_part(m.quote, p.text) is None:
            return "quote not in the passage"
        return ""

    ELLIPSIS = re.compile(r"\s*(?:\.\.\.|\u2026)\s*")

    def _quote_part(self, quote: str, text: str) -> str | None:
        """The checkable part of a mark's quote: the quote itself when it is in the passage; for a quote shortened
        with '...', its longest piece, when every piece is in the passage in order. None when it does not check."""
        body = self._norm(text)
        if self._norm(quote) in body:
            return quote
        parts = [x for x in self.ELLIPSIS.split(quote.strip()) if x.strip()]
        if len(parts) < 2:
            return None
        at = 0
        for part in parts:
            i = body.find(self._norm(part), at)
            if i < 0:
                return None
            at = i + len(self._norm(part))
        return max(parts, key=len)

    # ----------------------------------------------------------- 5: coverage
    def kept(self) -> list[str]:
        out = []
        for pid, (decision, _, _) in self.screen.items():
            if decision == "yes" or (decision == "unsure" and any(
                    p.role == "value" and p.subjects for p in self.marks.get(pid, {}).values())):
                out.append(pid)
        return sorted(out)

    def coverage(self) -> list[dict[str, str]]:
        marked = [p for pid in self.kept() for p in self.marks.get(pid, {}).values()]
        gaps = []
        for s in self.spec.subjects:
            if not any(p.role == "value" and s.label in p.subjects for p in marked):
                gaps.append({"kind": "subject", "name": s.label,
                             "text": f"no passage with values of {self.spec.measure.label} for {s.label}"})
        for c in self.spec.columns:
            if not any(c in p.columns for p in marked):
                gaps.append({"kind": "column", "name": c, "text": f"no passage states the {c} of the values"})
        return gaps

    # ----------------------------------------------------------- 6: agent
    def snippets_for(self, gap: dict[str, str]) -> str:
        """The papers' text the agent sees for one gap."""
        out: list[str] = []
        if gap["kind"] in ("alias", "subject"):
            for pid, text in self.texts.items():
                spans = [sp for t in self.names[gap["name"]] for sp in find_term(t, text)]
                spans.sort(key=lambda sp: (text[sp[1]:sp[1] + 3].lstrip()[:1] != "(", sp[0]))  # "(" right after first
                last = -10**9
                for a, b in spans:
                    if a - last < SNIPPET_CHARS:
                        continue
                    last = a
                    out.append(f"{pid}: ...{' '.join(text[max(0, a - SNIPPET_CHARS):b + SNIPPET_CHARS].split())}...")
                    if len([o for o in out if o.startswith(pid + ":")]) >= 3:
                        break
        if gap["kind"] != "alias":
            query = [gap["name"], *self.search_words()]
            for ref, _ in rank_passages(self.passages, query, 8):
                p = self.passages[ref.paper][ref.index]
                out.append(f"{ref.paper}: ({p.section}) {' '.join(p.text[:600].split())}")
        return "\n".join(out[:AGENT_SNIPPETS]) or "(no text)"

    def agent(self) -> None:
        cap = self.cfg.find.agent_max_steps
        tried = {t.lower() for ts in self.names.values() for t in ts}
        attempted: set[tuple[str, str]] = set()
        queue = [{"kind": "alias", "name": s.label, "text": f"other names the papers use for {s.label}"}
                 for s in self.spec.subjects]
        steps = 0
        while steps < cap:
            todo = [g for g in queue + self.coverage() if (g["kind"], g["name"]) not in attempted]
            if not todo:
                break
            gap = todo[0]
            attempted.add((gap["kind"], gap["name"]))
            text = self.snippets_for(gap)
            steps += 1
            entry: dict[str, Any] = {"step": steps, "gap": gap["text"], "gap_kind": gap["kind"]}
            out = self.predict(NextSearch, spec=spec_text(self.spec, self.found), gap=gap["text"],
                               tried=sorted(tried), text=text)
            if out is None:
                entry.update(kind="error", term="", reason="reply could not be read", outcome="no search")
                self._agent_log(entry)
                continue
            kind, term = str(out.kind), " ".join(str(out.term).split())
            entry.update(kind=kind, term=term, reason=" ".join(str(out.reason).split())[:300])
            if kind == "stop" or not term:
                entry["outcome"] = "stop"
            elif term.lower() in tried:
                entry["outcome"] = "already tried"
            elif not any(find_term(term, t) for t in self.texts.values()):
                entry["outcome"] = "term not in any paper"
                tried.add(term.lower())
            else:
                tried.add(term.lower())
                self._search(gap, kind, term, text, entry)
            self._agent_log(entry)
        self.res.coverage["agent_steps"] = steps

    def next_to_known(self, subject: str, term: str) -> bool:
        """Some paper has `term` within SNIPPET_CHARS of one of the subject's current names."""
        for text in self.texts.values():
            near = [a for t in self.names.get(subject, []) for a, _ in find_term(t, text)]
            if near and any(abs(a - b) <= SNIPPET_CHARS for b, _ in find_term(term, text) for a in near):
                return True
        return False

    def _agent_log(self, entry: dict[str, Any]) -> None:
        self.res.agent.append(entry)
        self._log({"kind": "agent", **entry})

    def _search(self, gap: dict[str, str], kind: str, term: str, shown: str, entry: dict[str, Any]) -> None:
        if kind == "other_name" and gap["kind"] in ("alias", "subject"):
            # code checks: the name is in the text the agent saw, and some paper writes it next to a name the
            # subject already has ("brenoxalin (BRN-233)"); else a drug no paper mentions could borrow another
            # drug's name and its values
            if find_term(term, shown) and self.next_to_known(gap["name"], term):
                self.names[gap["name"]].append(term)
                self.found.setdefault(gap["name"], []).append(term)
                where = shown.split(":", 1)[0] if shown else ""
                for line in shown.splitlines():
                    if find_term(term, line):
                        where = line.split(":", 1)[0]
                        break
                self.res.aliases.append({"subject": gap["name"], "term": term, "paper": where})
                entry["alias_accepted"] = True
            else:
                entry["alias_accepted"] = False
        before = set(self.kept())
        hit = self.regex(term, "agent")
        entry["regex_papers"] = hit
        cap = self.cfg.find.screen_max_papers
        spec_now = spec_text(self.spec, self.found)
        # papers the term hit that are not kept: (re)screen them when the spec text changed or they are new
        fresh = [pid for pid in sorted(hit) if pid not in before
                 and (pid not in self.screen or self.screen[pid][2] != spec_now)]
        room = max(0, cap - len(self.screen))
        new = [p for p in fresh if p not in self.screen][:room] + [p for p in fresh if p in self.screen]
        if new:
            self.screen_papers(new)
        newly = [p for p in self.kept() if p not in before] + [
            p for p in new if self.screen[p][0] == "unsure" and p not in self.marks]
        # kept papers whose marking used an older spec text are marked again (the found name is now in the spec)
        stale = [p for p in before if self.marked_with.get(p) != spec_now and p in hit]
        to_mark = sorted(set(newly) | set(stale))
        n_before = sum(len(self.marks.get(p, {})) for p in to_mark)
        if to_mark:
            self.mark_papers(to_mark)
        entry["screened"] = {p: self.screen[p][0] for p in new}
        entry["new_papers_kept"] = sorted(set(self.kept()) - before)
        entry["marked_again"] = sorted(stale)
        entry["passages_marked_change"] = sum(len(self.marks.get(p, {})) for p in to_mark) - n_before
        for p in entry["new_papers_kept"]:
            self._detail(p).setdefault("found_by_agent_step", entry["step"])
        entry["outcome"] = "searched"

    # ----------------------------------------------------------- the whole step
    def run(self) -> FindResult:
        if self.cfg.closed_book:
            self.res.coverage = {"closed_book": True}
            return self.res
        regex_hits: dict[str, int] = {}
        for terms in self.names.values():
            for t in terms:
                for pid, n in self.regex(t, "regex").items():
                    regex_hits[pid] = regex_hits.get(pid, 0) + n
        self.search_terms()
        term_hits: dict[str, int] = {}
        for k, ts in self.terms.items():
            for t in ts if k != "measure" else []:
                for pid, n in self.regex(t, "terms", key="terms").items():
                    term_hits[pid] = term_hits.get(pid, 0) + n
        no_subject = not self.spec.subjects   # measure words make candidates only when no subject is named
        for t in self.measure_words():
            for pid, n in self.regex(t, "terms", key="measure_regex", candidate=no_subject).items():
                if no_subject:
                    term_hits[pid] = term_hits.get(pid, 0) + n
        cands = sorted(self.sources, key=lambda pid: (pid not in regex_hits, -regex_hits.get(pid, 0),
                                                      -term_hits.get(pid, 0), pid))
        cap = self.cfg.find.screen_max_papers
        for pid in cands[cap:]:
            self._detail(pid)["not_screened"] = "over screen_max_papers"
        self.screen_papers(cands[:cap])
        self.mark_papers([p for p in cands[:cap] if self.screen[p][0] in ("yes", "unsure")])
        self.res.coverage["gaps_before_agent"] = self.coverage()
        if self.cfg.find.agent:
            self.agent()
        else:
            self.res.coverage["agent_steps"] = 0
        self.res.coverage["gaps_after_agent"] = self.coverage()
        kept = set(self.kept())
        for pid in sorted(self.sources):
            hit = self._hit(pid)
            (self.res.hits if pid in kept else self.res.dropped).append(hit)
        self.res.hits.sort(key=lambda h: h.paper)
        return self.res

    def _hit(self, pid: str) -> FindHit:
        decision, reason, _ = self.screen.get(pid, ("unsure", "not screened", ""))
        if pid not in self.screen:
            reason = self._detail(pid).get("not_screened", "not screened")
        ps = sorted(self.marks.get(pid, {}).values(), key=lambda p: p.start)
        order = ["regex", "terms", "agent"]
        return FindHit(paper=pid, sources=[s for s in order if s in self.sources.get(pid, set())],  # type: ignore[misc]
                       screen=decision, screen_reason=reason, passages=ps,  # type: ignore[arg-type]
                       details=self._detail(pid))


def find(spec: Spec, domain: str, cfg: RunConfig, *, lm: dspy.BaseLM | None = None,
         log: Callable[[dict[str, Any]], None] | None = None) -> FindResult:
    """Find with its full record. `lm` overrides the step's model (tests); `log` gets one dict per sub-step event."""
    return _Find(spec, domain, cfg, lm, log).run()


def run(spec: Spec, domain: str, cfg: RunConfig, *, lm: dspy.BaseLM | None = None,
        log: Callable[[dict[str, Any]], None] | None = None) -> list[FindHit]:
    """The kept papers with their marked passages (find.jsonl)."""
    return find(spec, domain, cfg, lm=lm, log=log).hits

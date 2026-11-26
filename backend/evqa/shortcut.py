"""Shortcut test (closed book; data-quality metric 4): every gold question is asked with NO papers. The papers
describe an invented world, so the share answered right should be near the guessing rate of the question's type.

    python -m evqa.shortcut [--domains bench_law ...] [--models claude-haiku-5-5 orch-model] [--data DIR]
        -> data/seed/<domain>/shortcut.json   (per question: text sent, each model's reply, class, score)

Question: the question text plus the user's intent card answers, written exactly as the systems receive it
(thesis_baselines.contract.question_text: question, "What the user wants:", one "- point: answer" line each).
No answer format is added: the systems get none.
Answer: one call per question and model (PROMPT): a best guess even when unsure, "Not reported." when the model
thinks papers of this kind would not report it, or "unknown" when it cannot guess. Code sorts the reply into
answer / not_reported / unknown (classify). Replies are cached by the sha256 of (model, prompt, question) in
<data>/seed/<domain>/shortcut.json (and SHORTCUT_CACHE, a jsonl), so a second run makes no calls.
Models: Claude through evqa.claude_gateway.complete (the `claude -p` CLI, in process), Qwen ("orch-model" and
the like) through the LiteLLM gateway at LITELLM_BASE_URL with LITELLM_MASTER_KEY; a gateway that does not
answer is recorded as unreachable and that model is skipped.
Score: the project scorer, thesis_scorer.text (L3-text, paperfactory gold from evqa.scoring.gold_file), the same
rule the real systems are graded by: answerable types get F1 and "exact"; not-reported types (absent, near_miss,
out_of_scope) are right iff no value claim is kept, so "unknown" counts as right there. This module adds the strict
view asked for by the spec: abstaining ("unknown") is wrong everywhere; a not-reported question is strictly right
only when the reply is "Not reported." and holds no value claim. Its chance level is the same model's
"Not reported." rate on the answerable questions of the domain (a reply that cannot tell the types apart).
The scorer's reader is orch-model; when Qwen is unreachable the reader and judge are the Claude model (recorded).
Same-model mark (26 Nov 2026 rule: no Sonnet; every number judged by Haiku is marked): when the scorer's claim
reader is Haiku or one of the answering models, the report, each summary row and each scored answer carry
"judge": <reader> and "note": "same model as writer" (judge_mark).
Typical-value baseline (code only, lookup and effect): each gold value is guessed as the most common value of the
same field (attr, or effect statistic, same unit) over the domain's other subjects in facts.jsonl.
Intervals: exact Clopper-Pearson 95% on the binary "right" (exact) counts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import threading
import time
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from thesis_scorer.stats import clopper_pearson as _shared_cp

VERSION = "shortcut-1"
DOMAINS = ("bench_law", "bench_llm", "bench_materials", "bench_medicine")
CLAUDE = "claude-haiku-5-5"            # evqa.llm.CHEAPEST_CLAUDE, the model of the bench4h runs
QWEN = "orch-model"
NOT_REPORTED_TYPES = ("absent", "near_miss", "out_of_scope")
UNKNOWN = "unknown"
NOT_REPORTED = "Not reported."
SAME_MODEL_NOTE = "same model as writer"

PROMPT = """Task: answer the question from what you already know. No papers are given to you.

Input: question is what the user asks about studies, trials, court decisions or materials, followed by what the
user wants for each open point.

Output: plain text, at most 8 lines, in one of three forms.
- A best guess: give it even when you are unsure. Each value on its own line with its unit, what it is for and,
  when the question has several studies, decisions or settings, which one it belongs to. For a "which" question,
  the names, separated by semicolons.
- If you think papers of this kind would not report what is asked, write exactly: Not reported.
- Only if you cannot form any guess at all, write exactly: unknown

Examples:
- Question "For the KELAD-4 trial, what number is reported for sites?" -> "KELAD-4 trial: 24 sites"
- Question "What hazard ratio did the BRUMON-6 trial report for drugX, with its 95% confidence interval?"
  -> "BRUMON-6 trial, drugX: HR 0.80 (95% CI 0.65 to 0.98)"
- Question "Which decisions followed Arno v. Bel Bank?" -> "Cato v. Dex Media; Fen v. Gol Bank"
- Question "For the study, what number is reported?" (no item and no measure named) -> "unknown"

Question:
{question}
"""
PROMPT_SHA = hashlib.sha256(PROMPT.encode()).hexdigest()[:12]

# one-line reasons for the chance level of each type (reported next to the rate)
GUESS: dict[str, tuple[float, str]] = {
    "lookup": (0.0, "one open number about an invented entity: exact match by chance ~0"),
    "effect": (0.0, "three open numbers (estimate and both 95% CI bounds) must all match: ~0"),
    "best": (0.0, "the candidates are not in the question; their names and values must be given: ~0"),
    "trend": (0.0, "every study/decision of the series must be named with its value: ~0"),
    "list": (0.0, "invented entity names must be named exactly (F1 = 1 for exact): ~0"),
    "conflict": (0.0, "invented entity names must be named exactly: ~0"),
    "absent": (math.nan, "strict: chance = the model's 'Not reported.' rate on answerable questions"),
    "near_miss": (math.nan, "strict: chance = the model's 'Not reported.' rate on answerable questions"),
    "out_of_scope": (math.nan, "strict: chance = the model's 'Not reported.' rate on answerable questions"),
}


# ---------------------------------------------------------------- data root
def use_data(root: Path) -> None:
    """Point evqa at another data folder (a worktree of the data repo): paths and the modules that copied them."""
    from evqa import corpus, paths, scoring
    root = Path(root)
    paths.DATA, paths.SEED, paths.DATASET = root, root / "seed", root / "dataset"
    corpus.DATASET = scoring.DATASET = paths.DATASET
    scoring.gold.cache_clear()


def questions(domain: str, split: str = "test") -> list[dict[str, Any]]:
    """Dataset question records (with type, for the report; only question + intent card are sent)."""
    from evqa import paths
    path = paths.DATASET / domain / "questions" / f"{split}.jsonl"
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def question_text(rec: dict[str, Any]) -> str:
    """The question plus the user's intent card answers, as thesis_baselines.contract.question_text writes it."""
    card = [c for c in rec.get("intent_card") or [] if str(c.get("answer", "")).strip()]
    if not card:
        return str(rec["question"])
    lines = [f"- {c.get('point', '').replace('_', ' ')}: {c['answer']}" for c in card]
    return f"{rec['question']}\n\nWhat the user wants:\n" + "\n".join(lines)


def classify(text: str) -> str:
    """answer | not_reported | unknown, by the exact forms PROMPT asks for (an empty reply is unknown)."""
    t = " ".join((text or "").split()).strip().strip(".").strip().casefold()
    if not t or t == UNKNOWN or t.startswith(UNKNOWN + " ") or t.startswith(UNKNOWN + ":"):
        return "unknown"
    if t == NOT_REPORTED.strip(".").casefold() or t.startswith(NOT_REPORTED.strip(".").casefold()):
        return "not_reported"
    return "answer"


def input_sha(model: str, prompt: str) -> str:
    return hashlib.sha256(json.dumps({"model": model, "prompt": prompt}, sort_keys=True).encode()).hexdigest()


# ---------------------------------------------------------------- models
Send = Callable[[str, str], dict[str, Any]]      # (model, prompt) -> {"text", "usage"}


def claude_send(model: str, prompt: str) -> dict[str, Any]:
    from evqa import claude_gateway
    r = claude_gateway.complete({"model": model, "messages": [{"role": "user", "content": prompt}]})
    return {"text": r["choices"][0]["message"].get("content") or "", "usage": r.get("usage") or {}}


def _base_url() -> str:
    return os.environ.get("LITELLM_BASE_URL", "http://127.0.0.1:4000/v1").rstrip("/")


def qwen_reachable(timeout: float = 5.0) -> tuple[bool, str]:
    """(answers, served model ids or the error) of the LiteLLM gateway; the key is sent, never printed."""
    import urllib.request
    req = urllib.request.Request(_base_url() + "/models",
                                 headers={"Authorization": f"Bearer {os.environ.get('LITELLM_MASTER_KEY', '')}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ids = [m.get("id") for m in json.loads(resp.read()).get("data", [])]
        return True, ",".join(str(i) for i in ids)
    except Exception as e:  # noqa: BLE001 - any failure means unreachable
        return False, f"{type(e).__name__}: {str(e)[:200]}"


def qwen_send(model: str, prompt: str) -> dict[str, Any]:
    """One chat call through LiteLLM: greedy, thinking off (the systems' setting, think: false)."""
    import urllib.request
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.0, "seed": 0,
            "max_tokens": 1024, "chat_template_kwargs": {"enable_thinking": False}}
    req = urllib.request.Request(_base_url() + "/chat/completions", data=json.dumps(body).encode(), headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {os.environ.get('LITELLM_MASTER_KEY', '')}",
        "X-Caller": "evqa-shortcut"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        out = json.loads(resp.read())
    return {"text": out["choices"][0]["message"].get("content") or "", "usage": out.get("usage") or {}}


def sender(model: str) -> Send:
    return claude_send if model.startswith("claude-") else qwen_send


# ---------------------------------------------------------------- cache + asking
class Cache:
    """sha -> {"text", "usage", "model"}: a jsonl file plus the replies of an earlier shortcut.json."""

    def __init__(self, path: Path | None, seed: dict[str, dict[str, Any]] | None = None) -> None:
        self.path, self.lock, self.data = path, threading.Lock(), dict(seed or {})
        if path is not None and path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    self.data[rec["sha"]] = rec
        self.calls = 0

    def get(self, sha: str) -> dict[str, Any] | None:
        return self.data.get(sha)

    def put(self, sha: str, rec: dict[str, Any]) -> None:
        with self.lock:
            self.data[sha] = {"sha": sha, **rec}
            self.calls += 1
            if self.path is not None:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"sha": sha, **rec}, ensure_ascii=False) + "\n")


def ask_all(recs: list[dict[str, Any]], model: str, send: Send, cache: Cache, parallel: int = 8,
            log: Callable[[str], None] = print) -> dict[str, dict[str, Any]]:
    """qid -> {question_sent, input_sha256, text, class, usage, error} for one model (cached replies reused)."""
    def one(rec: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        qtext = question_text(rec)
        sha = input_sha(model, PROMPT.format(question=qtext))
        hit = cache.get(sha)
        err = ""
        if hit is None:
            try:
                t0 = time.monotonic()
                got = send(model, PROMPT.format(question=qtext))
                hit = {"model": model, "text": got["text"], "usage": got.get("usage") or {},
                       "seconds": round(time.monotonic() - t0, 2)}
                cache.put(sha, hit)
            except Exception as e:  # noqa: BLE001 - one failed call must not stop the others
                err = f"{type(e).__name__}: {str(e)[:300]}"
                hit = {"text": None, "usage": {}}
                log(f"{rec['qid']} {model}: {err}")
        text = hit["text"]
        return rec["qid"], {"question_sent": qtext, "input_sha256": sha, "text": text,
                            "class": classify(text) if text is not None else "error",
                            "usage": hit.get("usage") or {}, "error": err}
    with ThreadPoolExecutor(max_workers=max(1, parallel)) as pool:
        return dict(pool.map(one, recs))


# ---------------------------------------------------------------- scoring
def scorer_chat(model: str, cache_dir: Path | None = None) -> Any:
    """A thesis_scorer Chat: Qwen through LiteLLM, or Claude through evqa.claude_gateway (in process)."""
    from thesis_scorer.llm import Chat
    if not model.startswith("claude-"):
        return Chat(model, cache=cache_dir)

    def send(body: dict[str, Any]) -> str:
        from evqa import claude_gateway
        return claude_gateway.complete(body)["choices"][0]["message"].get("content") or ""
    return Chat(model, send=send, cache=cache_dir)


def score_answers(domain: str, answers: dict[str, dict[str, Any]], model: str, reader: Any, judge_chat: Any,
                  parallel: int = 8) -> dict[str, dict[str, Any]]:
    """qid -> the scorer's per-question text score (thesis_scorer.text.score_question) of one model's replies."""
    from thesis_scorer import text
    from thesis_scorer.gold import Gold
    from thesis_scorer.schema import GoldFile, Record

    from evqa import scoring
    g = Gold(GoldFile.model_validate(scoring.gold_file(domain, "test")))
    recs = {q: Record(qid=q, system=f"closed-book:{model}", answer=a["text"], cannot_answer=a["class"] != "answer",
                      citations=[]) for q, a in answers.items() if q in g.questions}
    instr = text.READ_CLAIMS_PF if g.is_pf else text.READ_CLAIMS
    with ThreadPoolExecutor(max_workers=max(1, parallel)) as pool:      # fill the reader's reply cache in parallel
        claims = dict(zip(recs, pool.map(
            lambda q: text.read_claims(g.questions[q].get("question", ""), recs[q].answer or "", reader, q, instr)
            if recs[q].answer is not None else None, list(recs))))
    out = {}
    for q, rec in recs.items():
        s = text.score_question(g.questions[q], rec, claims[q], g, judge_chat)
        out[q] = {**{k: s[k] for k in ("score", "exact", "claims") if k in s},
                  "kept_claims": [c.value_text for c in claims[q].claims] if claims[q] else [],
                  **{k: s[k] for k in ("recall", "precision", "entities", "matched") if k in s}}
    return out


def strict_right(qtype: str, cls: str, sc: dict[str, Any]) -> bool:
    """Abstaining is wrong everywhere; a not-reported question needs "Not reported." and no kept claim."""
    if cls in ("unknown", "error"):
        return False
    if qtype in NOT_REPORTED_TYPES:
        return cls == "not_reported" and not sc.get("claims")
    return bool(sc.get("exact"))


def judge_mark(judge: str, models: list[str]) -> dict[str, str]:
    """{"judge", "note"} when the claim reader is Haiku or one of the answering models (its scores are not
    independent of the writer); {} otherwise."""
    if judge.startswith("claude-haiku") or judge in models:
        return {"judge": judge, "note": SAME_MODEL_NOTE}
    return {}


# ---------------------------------------------------------------- typical-value baseline (code)
def _num(v: str) -> float | None:
    try:
        return float(str(v).replace("−", "-"))
    except ValueError:
        return None


def typical_baseline(gold_q: dict[str, Any], facts: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """lookup / effect: guess each gold row's value as the most common value of the same field and unit over the
    other subjects of the domain (facts.jsonl); None for other types. Ties: the smallest value."""
    if gold_q["type"] not in ("lookup", "effect"):
        return None
    rows = gold_q.get("answer", {}).get("table", [])
    hits, guesses = [], []
    for r in rows:
        f = facts.get(r["row"])
        if f is None:
            hits.append(False)
            guesses.append(None)
            continue
        field = f.get("attr") or f.get("stat")
        pool = [_num(x["value"]) for x in facts.values()
                if x.get("what") == f["what"] and (x.get("attr") or x.get("stat")) == field
                and x.get("unit") == f.get("unit") and x.get("subject") != f.get("subject")]
        pool = [p for p in pool if p is not None]
        if not pool:
            hits.append(False)
            guesses.append(None)
            continue
        counts = Counter(pool)
        guess = min(counts, key=lambda v: (-counts[v], v))
        gv = _num(r["value"])
        guesses.append(guess)
        hits.append(gv is not None and math.isclose(guess, gv, abs_tol=1e-9))
    n = len(rows)
    return {"guesses": guesses, "score": round(sum(hits) / n, 4) if n else 0.0, "exact": bool(n) and all(hits)}


def load_facts(domain: str) -> dict[str, dict[str, Any]]:
    from evqa import paths
    path = paths.SEED / domain / "facts.jsonl"
    return {f["id"]: f for f in (json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip())}


# ---------------------------------------------------------------- statistics
def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact interval from the one shared version (thesis_scorer.stats.clopper_pearson); (0, 1) when n = 0."""
    return tuple(_shared_cp(k, n, alpha) or (0.0, 1.0))


def summarize(qs: list[dict[str, Any]], models: list[str], mark: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """One row per model and type: n, right (strict), rate, exact CI, chance level, above chance, mean scorer score,
    scorer-right count, abstain and not-reported shares; plus the same-model mark (judge_mark) when given."""
    out = []
    for m in models:
        mine = [q for q in qs if m in q["answers"]]
        if not mine:
            continue
        ans = [q for q in mine if q["type"] not in NOT_REPORTED_TYPES]
        false_alarm = sum(q["answers"][m]["class"] == "not_reported" for q in ans)
        fa_rate = false_alarm / len(ans) if ans else 0.0
        for t in GUESS:
            rows = [q for q in mine if q["type"] == t]
            if not rows:
                continue
            a = [q["answers"][m] for q in rows]
            k = sum(x["strict_right"] for x in a)
            n = len(rows)
            guess = fa_rate if t in NOT_REPORTED_TYPES else GUESS[t][0]
            lo, hi = clopper_pearson(k, n)
            out.append({"model": m, "type": t, "n": n, "right": k, "rate": round(k / n, 4), "ci95": [lo, hi],
                        "guess": round(guess, 4), "guess_why": GUESS[t][1], "above_guess": lo > guess,
                        "scorer_mean": round(sum(x["score"] for x in a) / n, 4),
                        "scorer_right": sum(bool(x["exact"]) for x in a),
                        "abstain": sum(x["class"] == "unknown" for x in a),
                        "not_reported": sum(x["class"] == "not_reported" for x in a),
                        "errors": sum(x["class"] == "error" for x in a), **(mark or {})})
    return out


def baseline_rows(qs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for t in ("lookup", "effect"):
        rows = [q["typical_baseline"] for q in qs if q["type"] == t and q.get("typical_baseline")]
        if rows:
            k = sum(r["exact"] for r in rows)
            out.append({"type": t, "n": len(rows), "right": k, "rate": round(k / len(rows), 4),
                        "ci95": list(clopper_pearson(k, len(rows))),
                        "mean_score": round(sum(r["score"] for r in rows) / len(rows), 4)})
    return out


# ---------------------------------------------------------------- run
def run_domain(domain: str, models: list[str], reader_model: str, judge_model: str, parallel: int = 8,
               cache_path: Path | None = None, sends: dict[str, Send] | None = None,
               chats: tuple[Any, Any] | None = None, log: Callable[[str], None] = print) -> dict[str, Any]:
    """Ask, score and summarize one domain; writes <data>/seed/<domain>/shortcut.json."""
    from evqa import paths, scoring
    out_path = paths.SEED / domain / "shortcut.json"
    old = json.loads(out_path.read_text(encoding="utf-8")) if out_path.is_file() else {}
    seed = {a["input_sha256"]: {"model": m, "text": a["text"], "usage": a.get("usage") or {}}
            for q in old.get("questions", []) for m, a in q.get("answers", {}).items() if a.get("text") is not None}
    cache = Cache(cache_path, seed)
    recs = questions(domain)
    golds = scoring.gold(domain)
    facts = load_facts(domain)
    reader, judge_chat = chats or (scorer_chat(reader_model), scorer_chat(judge_model))
    per_model: dict[str, dict[str, dict[str, Any]]] = {}
    for m in models:
        log(f"{domain}: asking {m} ({len(recs)} questions)")
        answers = ask_all(recs, m, (sends or {}).get(m) or sender(m), cache, parallel, log)
        log(f"{domain}: scoring {m} with reader {reader.name}")
        scores = score_answers(domain, answers, m, reader, judge_chat, parallel)
        per_model[m] = {q: {**a, **scores.get(q, {"score": 0.0, "exact": False, "claims": 0})}
                        for q, a in answers.items()}
    mark = judge_mark(reader.name, models)
    qs = []
    for rec in recs:
        q = rec["qid"]
        entry: dict[str, Any] = {"qid": q, "type": rec["type"], "question": rec["question"], "answers": {}}
        for m in models:
            a = per_model[m][q]
            a["strict_right"] = strict_right(rec["type"], a["class"], a)
            a.update(mark)
            entry["answers"][m] = a
        if q in golds:
            entry["typical_baseline"] = typical_baseline(golds[q], facts)
        qs.append(entry)
    tokens = Counter()
    for m in models:
        for a in per_model[m].values():
            for k, v in (a.get("usage") or {}).items():
                if isinstance(v, int):
                    tokens[f"{m}:{k}"] += v
    report = {"version": VERSION, "prompt_sha256": PROMPT_SHA, "domain": domain, "split": "test",
              "created": time.strftime("%Y-%m-%d %H:%M:%S"), "models": models, "reader": reader.name,
              "judge": judge_chat.name, **({"note": mark["note"]} if mark else {}), "answer_calls_made": cache.calls, "reader_calls_made": reader.calls,
              "tokens": dict(tokens), "guess": {t: {"rate": None if math.isnan(g) else g, "why": w}
                                                for t, (g, w) in GUESS.items()},
              "summary": summarize(qs, models, mark), "typical_baseline": baseline_rows(qs), "questions": qs}
    out_path.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def table(report: dict[str, Any]) -> str:
    note = f", {report['note']}" if report.get("note") else ""
    lines = [f"{report['domain']} (reader {report['reader']}{note})",
             "model | type | n | right | rate | CI95 | guess | above | scorer mean | scorer right | unknown | NR"]
    for r in report["summary"]:
        lines.append(f"{r['model']} | {r['type']} | {r['n']} | {r['right']} | {r['rate']:.2f} | "
                     f"[{r['ci95'][0]:.2f}, {r['ci95'][1]:.2f}] | {r['guess']:.2f} | {'yes' if r['above_guess'] else 'no'}"
                     f" | {r['scorer_mean']:.2f} | {r['scorer_right']} | {r['abstain']} | {r['not_reported']}")
    for b in report["typical_baseline"]:
        lines.append(f"typical-value baseline | {b['type']} | {b['n']} | {b['right']} | {b['rate']:.2f} | "
                     f"[{b['ci95'][0]:.2f}, {b['ci95'][1]:.2f}] | mean {b['mean_score']:.2f}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--domains", nargs="+", default=list(DOMAINS))
    ap.add_argument("--models", nargs="+", default=[CLAUDE, QWEN])
    ap.add_argument("--data", type=Path, default=None, help="data folder (default: the repo's data submodule)")
    ap.add_argument("--parallel", type=int, default=8)
    ap.add_argument("--cache", type=Path, default=Path(os.environ["SHORTCUT_CACHE"])
                    if os.environ.get("SHORTCUT_CACHE") else None)
    a = ap.parse_args(argv)
    if a.data:
        use_data(a.data)
    models = list(a.models)
    qwen = [m for m in models if not m.startswith("claude-")]
    reader = judge = QWEN
    if qwen:
        ok, info = qwen_reachable()
        print(f"Qwen gateway {_base_url()}: {'reachable, ' + info if ok else 'NOT reachable (' + info + ')'}")
        if not ok:
            models = [m for m in models if m.startswith("claude-")]
    if not qwen or not qwen_reachable()[0]:
        reader = judge = next((m for m in models if m.startswith("claude-")), CLAUDE)
        print(f"scorer reader and judge: {reader} (Qwen not used)")
    for d in a.domains:
        rep = run_domain(d, models, reader, judge, a.parallel, a.cache)
        print(table(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())

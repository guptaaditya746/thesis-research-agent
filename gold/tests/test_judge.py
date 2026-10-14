"""gold/judge.py with pydantic-ai FunctionModels: verdicts, the cache (a rescore costs no model call),
prompt hashes, the calibration sample from runs' pairs.jsonl, and the calibration report."""
from __future__ import annotations

import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from agent import anchor
from agent.canonical import sha256_hex
from agent.pairs import write_pairs
from agent.tests.runs import baseline_run, research_run
from gold import judge, llm, review

from .fixtures import NQ, Env, env, pulled  # noqa: F401

SPIDER = {"s": "p1", "p": "evaluatesOn", "o": "Spider"}
QUOTE = "deployable LLMs using benchmark datasets like Spider and Bird"


def prompt_of(messages: list[ModelMessage]) -> str:
    return "\n".join(str(p.content) for m in messages for p in m.parts if isinstance(p, UserPromptPart))


def respond(info: AgentInfo, args: dict[str, Any]) -> ModelResponse:
    """The reply in the output mode structured() chose: an output tool call, or JSON text (native output)."""
    if info.output_tools:
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])
    return ModelResponse(parts=[TextPart(json.dumps(args))])


def scripted(calls: list[str], name: str = "scripted-judge") -> FunctionModel:
    """supports when the object is in the quote, partial for 'Bird', else no; matches when both sides
    name HotpotQA."""
    def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        prompt = prompt_of(messages)
        calls.append(prompt)
        if "Run fact" in prompt or "Run row" in prompt:
            args: dict[str, Any] = {"rationale": "compared", "match": prompt.count("HotpotQA") >= 2}
        else:
            obj = prompt.split("object: ", 1)[1].split("\n", 1)[0]
            quote = prompt.split('Quote:\n"""\n', 1)[1].split('\n"""', 1)[0]
            label = "partial" if obj == "Bird" else "supports" if obj in quote else "no"
            args = {"rationale": f"the quote {'names' if label != 'no' else 'lacks'} {obj}", "label": label}
        return respond(info, args)

    return FunctionModel(reply, model_name=name)


def test_support_verdict_and_cache(tmp_path: Path) -> None:
    calls: list[str] = []
    j = judge.Judge(tmp_path, [scripted(calls)])
    first = j.support(SPIDER, QUOTE)
    prompt = (judge.PROMPT_DIR / "judge-support.txt").read_text(encoding="utf-8")
    assert first == {"label": "supports", "rationale": "the quote names Spider", "model": "scripted-judge",
                     "served_model": "scripted-judge", "prompt_sha256": llm.prompt_sha256(prompt, judge.SupportReply),
                     "cached": False}
    assert j.support(SPIDER, QUOTE) == {**first, "cached": True} and len(calls) == 1
    line = json.loads((tmp_path / judge.CACHE_FILE).read_text(encoding="utf-8"))["value"]  # what was asked, of whom
    assert line["task"] == "support" and line["input"] == {"fact": SPIDER, "quote": QUOTE, "context": None}
    assert line["settings"] == {"temperature": 0.0, "seed": 0, "max_tokens": judge.MAX_TOKENS}
    assert line["user_prompt_sha256"] == sha256_hex(calls[0].encode("utf-8"))
    assert line["served_model"] == "scripted-judge" and line["usage"]["input_tokens"] > 0 and line["created_at"]
    again = judge.Judge(tmp_path, [scripted(calls)])  # a rescore reads the cache file
    assert again.support(SPIDER, QUOTE)["cached"] and again.calls == 0 and len(calls) == 1
    assert j.support(SPIDER, QUOTE, context="Paper p1")["cached"] is False  # the context is input
    other = judge.Judge(tmp_path, [scripted(calls, "another-model")])
    assert other.support(SPIDER, QUOTE)["cached"] is False  # another model never reuses an answer
    assert j.support({**SPIDER, "o": "HellaSwag"}, QUOTE)["label"] == "no"
    assert j.support({**SPIDER, "o": "Bird"}, QUOTE)["label"] == "partial"
    assert len((tmp_path / judge.CACHE_FILE).read_text(encoding="utf-8").splitlines()) == 5


def test_cache_only_judge_never_calls(tmp_path: Path) -> None:
    calls: list[str] = []
    assert judge.Judge(tmp_path, [scripted(calls)], cache_only=True).support(SPIDER, QUOTE) is None
    judge.Judge(tmp_path, [scripted(calls)]).support(SPIDER, QUOTE)
    assert judge.Judge(tmp_path, [scripted(calls)], cache_only=True).support(SPIDER, QUOTE)["label"] == "supports"
    assert len(calls) == 1


def test_same_fact_and_same_row(tmp_path: Path) -> None:
    from agent.tests.conftest import fixture

    concept = fixture("concept_graph.json")
    calls: list[str] = []
    j = judge.Judge(tmp_path, [scripted(calls)])
    run_fact = {"id": "f1", "s": "p6", "p": "evaluates on", "o": "HotpotQA", "claims": [], "origin": "research"}
    assert j.same_fact(run_fact, {"s": "p6", "p": "evaluatesOn", "o": "HotpotQA"}, concept)["match"] is True
    assert j.same_fact(run_fact, {"s": "p6", "p": "evaluatesOn", "o": "NQ"}, concept)["match"] is False
    row = {"id": "r1", "source": "p6", "target": "HotpotQA", "facts": [run_fact]}
    verdict = judge.same_row(row, {"id": "r9", "source": "p6", "target": "Hotpot QA"}, concept, judge=j)
    assert verdict["match"] is False and verdict["prompt_sha256"] == j.prompt_hashes()["same-row"]
    assert "facts" not in calls[-1] and "Benchmarks used by RAG papers" in calls[-1]
    assert j.same_fact(run_fact, {"s": "p6", "p": "evaluatesOn", "o": "HotpotQA"}, concept)["cached"]
    assert len(set(j.prompt_hashes().values())) == 3


def test_sync_calls_work_inside_a_running_loop(tmp_path: Path) -> None:
    j = judge.Judge(tmp_path, [scripted([])])

    async def endpoint() -> dict:  # e.g. a FastAPI handler calling the sync API
        return j.support(SPIDER, QUOTE)

    assert asyncio.run(endpoint())["label"] == "supports"


class FakeOpenAI(ThreadingHTTPServer):
    """An OpenAI-compatible chat endpoint with HTTP/1.1 keep-alive (as LiteLLM): every reply is a
    SupportReply JSON, `supports` when the object is in the prompt's quote, else `no`."""

    daemon_threads = True

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"  # keep the connection open between requests

            def do_POST(self) -> None:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                server.requests.append(body)
                prompt = body["messages"][-1]["content"]
                obj = prompt.split("object: ", 1)[1].split("\n", 1)[0]
                label = "supports" if obj in prompt.split("Quote:", 1)[1] else "no"
                content = json.dumps({"rationale": f"about {obj}", "label": label})
                data = json.dumps({
                    "id": f"chatcmpl-{len(server.requests)}", "object": "chat.completion", "created": 0,
                    "model": "Qwen/Qwen3-30B-A3B-Instruct-2507",
                    "choices": [{"index": 0, "finish_reason": "stop",
                                 "message": {"role": "assistant", "content": content}}],
                    "usage": {"prompt_tokens": 50, "completion_tokens": 7, "total_tokens": 57}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args: Any) -> None:
                pass

        super().__init__(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.serve_forever, daemon=True).start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}/v1"


@pytest.fixture
def openai_server() -> Any:
    server = FakeOpenAI()
    yield server
    server.shutdown()
    server.server_close()


def test_sync_calls_reuse_the_http_client(tmp_path: Path, openai_server: FakeOpenAI) -> None:
    """The real model class over keep-alive HTTP: one sync call after another, from this thread and
    from inside other event loops, all reach the server and all succeed (a pooled connection is only
    ever used by the loop that opened it)."""
    j = judge.Judge(tmp_path, [llm.openai_model("sub-model-1", url=openai_server.url)])
    verdicts = [j.support({**SPIDER, "o": o}, QUOTE) for o in ("Spider", "Bird", "WikiSQL", "Spider")]
    assert [v["label"] for v in verdicts] == ["supports", "supports", "no", "supports"]
    assert len(openai_server.requests) == 3 and j.calls == 3  # the last one came from the cache
    assert verdicts[0]["model"] == "sub-model-1" and verdicts[0]["served_model"] == "Qwen/Qwen3-30B-A3B-Instruct-2507"

    async def handler(o: str) -> dict:  # a sync call inside a running loop (a FastAPI handler)
        return j.support({**SPIDER, "o": o}, QUOTE)

    assert asyncio.run(handler("CoSQL"))["label"] == "no"
    assert asyncio.run(j.asupport({**SPIDER, "o": "SParC"}, QUOTE))["label"] == "no"  # another caller loop
    assert judge.support({**SPIDER, "o": "KaggleDBQA"}, QUOTE, judge=j)["label"] == "no"
    assert len(openai_server.requests) == 6
    sent = openai_server.requests[0]
    assert sent["model"] == "sub-model-1" and sent["temperature"] == 0.0 and sent["seed"] == 0


def test_gather_bounds_concurrency(tmp_path: Path) -> None:
    state = {"now": 0, "peak": 0}

    async def slow(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        state["now"] += 1
        state["peak"] = max(state["peak"], state["now"])
        await asyncio.sleep(0.01)
        state["now"] -= 1
        return respond(info, {"rationale": "r", "label": "no"})

    j = judge.Judge(tmp_path, [FunctionModel(slow, model_name="slow")], concurrency=2)
    out = asyncio.run(j.gather([j.asupport({**SPIDER, "o": f"D{n}"}, QUOTE) for n in range(7)]))
    assert [v["label"] for v in out] == ["no"] * 7 and state["peak"] == 2 and j.calls == 7
    state["peak"] = 0  # the bound holds across sync callers in threads too (scoring's workers)
    with ThreadPoolExecutor(5) as pool:
        labels = list(pool.map(lambda n: j.support({**SPIDER, "o": f"E{n}"}, QUOTE)["label"], range(5)))
    assert labels == ["no"] * 5 and state["peak"] == 2 and j.calls == 12


def test_identical_inputs_in_flight_make_one_call(tmp_path: Path) -> None:
    calls: list[int] = []

    async def slow(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append(1)
        await asyncio.sleep(0.02)  # the others arrive while this one waits for the model
        return respond(info, {"rationale": "r", "label": "supports"})

    j = judge.Judge(tmp_path, [FunctionModel(slow, model_name="slow")])
    out = asyncio.run(j.gather([j.asupport(SPIDER, QUOTE) for _ in range(4)]))
    assert len(calls) == 1 and j.calls == 1 and [v["cached"] for v in out] == [False, True, True, True]
    assert len((tmp_path / judge.CACHE_FILE).read_text(encoding="utf-8").splitlines()) == 1
    assert {v["label"] for v in out} == {"supports"}


def test_support_pair_gives_the_paper_and_context(env: Env) -> None:
    calls: list[str] = []
    j = judge.Judge(env.root, [scripted(calls)])
    sel = anchor.find(anchor.read_text(env.corpus / "p6.md"), NQ.text, file="p6.md")
    pair = {"s": "p6", "p": "evaluatesOn", "o": "NQ", "quote": sel.exact, "file": "p6.md", "start": sel.start, "end": sel.end}
    assert j.support_pair(pair, review.Corpus(env.corpus))["label"] == "supports"
    assert "Context:" in calls[0] and "Paper p6 (p6.md):" in calls[0] and "HotpotQA (Yang et al., 2018)" in calls[0]
    assert j.support_pair({**pair, "quote": None}, review.Corpus(env.corpus)) is None
    with pytest.raises(review.Rejected, match="unknown_file"):  # never judged without the context people saw
        j.support_pair({**pair, "file": "p77.md"}, review.Corpus(env.corpus))
    assert len(calls) == 1


def test_people_see_the_passage_the_judge_sees(env: Env) -> None:
    """The calibration compares people with the judge on the same input: the Argilla record's passage is
    context_for's window (CONTEXT_CHARS each side, cut at the same line ends), not the review's wider one."""
    corpus = review.Corpus(env.corpus)
    text = anchor.read_text(env.corpus / "p6.md")
    sel = anchor.find(text, NQ.text, file="p6.md")
    row = {"id": "judge-x", "fact": {"s": "p6", "p": "evaluatesOn", "o": "NQ"}, "quote": sel.exact, "file": "p6.md",
           "start": sel.start, "end": sel.end}
    [record] = judge.records([row], corpus)
    context = judge.context_for(corpus, "p6.md", sel.start, sel.end).split(":\n", 1)[1]
    a, b = judge.argilla_io.window(text, sel.start, sel.end, judge.CONTEXT_CHARS)
    assert context == text[a:b]
    shown = judge.argilla_io.passage_markdown(text, sel.start, sel.end, chars=judge.CONTEXT_CHARS)
    assert record["passage"] == shown and text[a:sel.start] + "<mark>" in shown and "</mark>" + text[sel.end:b] in shown
    wide = judge.argilla_io.passage_markdown(text, sel.start, sel.end)
    assert wide != shown  # the review's wider window: the fixture tells the two apart


def test_sample_from_the_scored_runs_only(tmp_path: Path) -> None:
    """With report/batch.json under --runs the calibration population is the runs `score batch` scored, not
    a cut attempt or a web run that lies under the same root; without it, every run (and the manifest says)."""
    fake_runs(tmp_path / "runs")
    scored = sorted(p.parent for p in (tmp_path / "runs").rglob("pairs.jsonl"))[:-1]  # q03-claim_on left out
    items = [{"run_id": d.name, "run_dir": str(d.resolve()), "scored": True} for d in scored]
    items.append({"run_id": "q09-claim_on-r1-a1", "run_dir": str(tmp_path / "gone"), "scored": False})
    (tmp_path / "runs" / "report").mkdir()
    (tmp_path / "runs" / "report" / "batch.json").write_text(json.dumps({"items": items}), encoding="utf-8")
    rows, manifest = judge.sample_pairs(tmp_path / "runs", size=500, seed="s")
    assert manifest["population"] == {"claim_on": 80, "claim_off": 20} and manifest["runs"] == 4
    assert manifest["scored_runs"] == sorted(str(d.resolve()) for d in scored)
    assert manifest["context_chars"] == judge.CONTEXT_CHARS
    every = judge.sample_pairs(tmp_path / "runs", size=500, seed="s", all_runs=True)[1]
    assert every["population"] == {"claim_on": 120, "claim_off": 20} and every["scored_runs"] is None


def test_allocate() -> None:
    assert judge.allocate({"claim_on": 300, "claim_off": 50}, 240) == {"claim_on": 190, "claim_off": 50}
    assert judge.allocate({"a": 10, "b": 10}, 240) == {"a": 10, "b": 10}
    assert judge.allocate({"a": 5, "b": 5, "c": 5}, 7) == {"a": 3, "b": 2, "c": 2}
    assert judge.allocate({"a": 0, "b": 4}, 3) == {"a": 0, "b": 3}


def fake_runs(root: Path) -> None:
    """Three claim_on runs with 40 quoted pairs and 5 unsourced facts each, two claim_off runs with 10."""
    for condition, runs, pairs in (("claim_on", 3, 40), ("claim_off", 2, 10)):
        for r in range(runs):
            run = root / "m4-72" / f"q0{r + 1}-{condition}-r1-a1"
            run.mkdir(parents=True)
            (run / "config.json").write_text(json.dumps({"condition": condition}), encoding="utf-8")
            lines = [{"run_id": run.name, "row_id": f"r{n}", "fact_id": f"f{n}", "s": "p1", "p": "evaluatesOn",
                      "o": f"D{n}", "origin": "research", "claim_id": f"claim-{n:06d}", "file": "p1.md",
                      "start": 0, "end": 5, "quote": f"quote {n}"} for n in range(pairs)]
            lines += [{"run_id": run.name, "row_id": "r99", "fact_id": f"f{100 + n}", "s": "p1", "p": "x", "o": "y",
                       "origin": "research", "claim_id": None, "file": None, "start": None, "end": None, "quote": None}
                      for n in range(5)]
            review.write_jsonl(run / "pairs.jsonl", lines)


def test_sample_pairs_stratified_by_condition(tmp_path: Path) -> None:
    fake_runs(tmp_path / "runs")
    rows, manifest = judge.sample_pairs(tmp_path / "runs", size=60, seed="s")
    assert manifest["population"] == {"claim_on": 120, "claim_off": 20}
    assert manifest["sampled"] == {"claim_on": 40, "claim_off": 20} and manifest["runs"] == 5
    assert len(rows) == 60 and len({r["id"] for r in rows}) == 60 and all(r["quote"] for r in rows)
    assert {r["qid"] for r in rows} == {"q01", "q02", "q03"}
    assert [r["id"] for r in judge.sample_pairs(tmp_path / "runs", size=60, seed="s")[0]] == [r["id"] for r in rows]
    assert [r["id"] for r in judge.sample_pairs(tmp_path / "runs", size=60, seed="t")[0]] != [r["id"] for r in rows]
    assert manifest["run_ids"] == sorted(p.parent.name for p in (tmp_path / "runs").rglob("pairs.jsonl"))
    assert set(manifest["pairs_files"]) == {f"m4-72/{r}/pairs.jsonl" for r in manifest["run_ids"]}
    judge.write_sample(tmp_path / "gold", rows, manifest)
    with pytest.raises(judge.SampleExists):  # drawn once: answers in Argilla belong to this sample
        judge.write_sample(tmp_path / "gold", rows[:10], manifest)
    judge.write_sample(tmp_path / "gold", rows[:10], manifest, force=True)
    assert len(judge.load_sample(tmp_path / "gold")[0]) == 10


def test_population_from_real_runs(tmp_path: Path, corpus_env: tuple[Path, Path]) -> None:
    for built in (research_run(tmp_path, *corpus_env), baseline_run(tmp_path, *corpus_env)):
        write_pairs(built.run)
    rows = judge.population(tmp_path / "runs")
    by_condition = {c: sorted(r["fact"]["o"] for r in rows if r["condition"] == c) for c in ("claim_on", "claim_off")}
    assert by_condition == {"claim_on": ["BIRD", "GSM8K", "HotpotQA", "Spider"],  # f5 has no claim
                            "claim_off": ["GSM8K", "HotpotQA", "Spider"]}  # f4: no source found
    text = anchor.read_text(corpus_env[0] / "p6.md")
    assert all(text[r["start"]:r["end"]] == r["quote"] for r in rows if r["file"] == "p6.md")


@pytest.fixture
def corpus_env(tmp_path: Path) -> tuple[Path, Path]:
    from agent.tests.conftest import write_corpus

    return write_corpus(tmp_path)


def calibration_case(judged: dict[str, str]) -> tuple[list[dict], dict, dict, dict]:
    """40 pairs over two conditions; people say supports on even pairs and no on odd ones."""
    sample = [{"id": f"j{n:02d}", "condition": "claim_on" if n % 2 else "claim_off"} for n in range(40)]
    answered = {r["id"]: {"label": "supports" if n % 2 == 0 else "no", "user": "ann",
                          "answers": {"ann": "supports" if n % 2 == 0 else "no"}} for n, r in enumerate(sample)}
    verdicts = {r["id"]: {"label": judged["even" if n % 2 == 0 else "odd"]} for n, r in enumerate(sample)}
    return sample, {"population": {"claim_on": 300, "claim_off": 100}}, answered, verdicts


def test_calibration_picks_the_partial_mapping_on_one_half() -> None:
    sample, manifest, answered, verdicts = calibration_case({"even": "partial", "odd": "no"})
    report = judge.calibrate(sample, manifest, answered, verdicts, seed="s")
    assert report["split"] == {"seed": "s", "calibration": 20, "test": 20}
    assert report["calibration"]["partial_counts_as"] == "yes"
    assert report["calibration"]["if_partial_no"]["kappa"] == 0.0  # the judge would say no to everything
    t = report["test"]
    assert t["kappa"] == 1.0 and t["weighted_kappa"] == 1.0 and t["raw_agreement"] == 1.0
    yes = t["precision_judge_yes"]
    assert yes["rate"] == 1.0 and yes["n"] == sum(t["confusion_judge_by_person"]["partial"].values())
    assert sum(sum(row.values()) for row in t["confusion_judge_by_person"].values()) == 20
    assert report["use_judge"] is True and t["per_person"]["ann"]["kappa"] == 1.0


def test_calibration_below_the_bar_says_to_report_without_the_judge() -> None:
    sample, manifest, answered, verdicts = calibration_case({"even": "supports", "odd": "supports"})
    report = judge.calibrate(sample, manifest, answered, verdicts, seed="s")
    assert report["calibration"]["partial_counts_as"] == "no"  # a tie keeps partial as no
    assert report["test"]["kappa"] == 0.0 and report["use_judge"] is False
    assert "without the judge" in report["advice"]
    assert report["test"]["person_yes_given_judge_no"]["n"] == 0


def test_calibration_report_end_to_end(env: Env) -> None:
    corpus = review.Corpus(env.corpus)
    rows = []
    for n, (fact, quote_file, quote) in enumerate([
            ({"s": "p6", "p": "evaluatesOn", "o": "NQ"}, "p6.md", NQ.text),
            ({"s": "p1", "p": "evaluatesOn", "o": "Spider"}, "p1.md", QUOTE),
            ({"s": "p1", "p": "evaluatesOn", "o": "WikiSQL"}, "p1.md", QUOTE),
            ({"s": "p1", "p": "evaluatesOn", "o": "Bird"}, "p1.md", QUOTE)]):
        sel = anchor.find(corpus.index(quote_file), quote, file=quote_file)
        rows.append({"id": f"judge-{n}", "run_id": "q01-claim_on-r1-a1", "qid": "q01",
                     "condition": "claim_on" if n % 2 else "claim_off", "fact": fact, "file": quote_file,
                     "start": sel.start, "end": sel.end, "quote": sel.exact})
    judge.write_sample(env.root, rows, {"population": {"claim_on": 10, "claim_off": 10}, "seed": "s"})
    labels = ["supports", "supports", "no", "partial"]
    review.write_jsonl(env.root / "judge" / "responses.jsonl",
                       [pulled(r["id"], "judge", {"ann": {"support": label}}) for r, label in zip(rows, labels)])
    calls: list[str] = []
    report = judge.calibration_report(env.root, corpus, judge=judge.Judge(env.root, [scripted(calls)]), seed="s")
    assert report["answered"] == report["judged"] == 4 and report["model_calls"] == 4 and len(calls) == 4
    assert report["model"] == "scripted-judge" and report["prompt_file"] == "gold/prompts/judge-support.txt"
    assert report["prompt_sha256"] == judge.load_prompt("support").sha256
    assert report["served_models"] == ["scripted-judge"] and report["settings"]["max_tokens"] == judge.MAX_TOKENS
    assert report["render_sha256"] == judge.render_sha256()["support"]
    assert review.read_json(env.root / judge.REPORT_FILE) == report
    again = judge.calibration_report(env.root, corpus, judge=judge.Judge(env.root, [scripted(calls)]), seed="s")
    assert again["model_calls"] == 0 and again["test"] == report["test"]

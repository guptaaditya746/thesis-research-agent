"""A small evidence-level world for the viewer's tests and for frontend work, made by the real tools.

The layout is the one a live run writes (docs/slurm-evidence-runbook.md), under one root `$EV`:

    corpora/        `synth build --renderer template` (two studies' worth of knobs) and a `synth variant`
    runs/           `evidence run`: regex-only, cascade (all), cascade-gaps (gaps), agentic-gaps (gaps, the
                    agentic protocol), plus rag-baseline/ and agent-baseline/ answers
    cache/engine/   the engine's record cache (extractor_calls.jsonl)
    agent-work/     the agentic extractor's agent run directories
    scores/         `evaluate score` per selection and corpus, `compare`, `shift`, `benchmark`
    proposals/      `evidence propose` frame -> draft -> critic -> cards -> (a person's decision) -> freeze -> amend

Every model is scripted (pydantic-ai FunctionModels as evidence/tests and evaluation/tests script them; the
research agent's orchestrator as evaluation/tests/test_agentic_agent.py does, unsandboxed, POSIX only), so
nothing reaches a network. The LLM extractors find nothing beyond the regex (an honest empty reply), so the
funnel's gaps stay visible. Without bash (Windows) the agentic run and the agent baseline are left out.

    uv run python -m webapp.tests.evidence_world OUT     # write the world to OUT (e.g. for `webapp serve`)
    uv run python -m webapp.tests.evidence_world OUT --mocks webapp/web/src/mocks/ev-fixtures.json
                                                         # and the frontend's mock responses from it, with
                                                         # write-contract.json beside them (write_contract.py)
"""
from __future__ import annotations

import dataclasses
import json
import os
import re
import shutil
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
PROTOCOL = REPO / "domains" / "rag" / "protocols" / "rag-factuality.yaml"
AGENTIC = REPO / "domains" / "rag" / "protocols" / "rag-factuality-agentic.yaml"
NAME = "rag-tpl-w1"
FENCE = "`" * 3
POSIX = os.name == "posix" and shutil.which("bash") is not None and shutil.which("timeout") is not None


@dataclass(frozen=True)
class EvidenceWorld:
    root: Path
    agent: bool  # whether the agentic run and the agent baseline are in it

    @property
    def corpora(self) -> Path:
        return self.root / "corpora"

    @property
    def runs(self) -> Path:
        return self.root / "runs"

    @property
    def scores(self) -> Path:
        return self.root / "scores"

    @property
    def proposals(self) -> Path:
        return self.root / "proposals"

    @property
    def cache(self) -> Path:
        return self.root / "cache" / "engine"

    @property
    def agent_work(self) -> Path:
        return self.root / "agent-work"

    def copy(self, target: Path) -> EvidenceWorld:
        shutil.copytree(self.root, target)
        return dataclasses.replace(self, root=target)

    def write_losses(self, losses: dict[str, Any]) -> Path:
        """losses.json and losses.md under scores/losses, where `evaluate losses` writes them (plan 3 Task 6)."""
        out = self.scores / "losses"
        out.mkdir(parents=True, exist_ok=True)
        (out / "losses.json").write_text(json.dumps(losses, indent=2) + "\n", encoding="utf-8", newline="\n")
        lines = ["# Losses first", "", "## Comparison", "", TIM_SENTENCE + ".", ""]
        for domain, rows in losses["domains"].items():
            lines += [f"### {domain}", "", "| question | report | engine loss | cause |", "|---|---|---|---|"]
            lines += [f"| {r['question_id']} | {r['report']} | {'yes' if r['engine_loss'] else 'no'} | {r['cause'] or ''} |"
                      for r in rows]
            lines.append("")
        (out / "losses.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
        return out


TIM_SENTENCE = "We should not assume that the evidence-level approach will necessarily perform better"


def stand_in_losses(world: EvidenceWorld) -> dict[str, Any]:
    """losses.json in the shape plan 3 Task 6's `losses(reports)` gives (the plan's Shared names), made from the
    world's own score reports until Task 6 adds `evaluate losses` (preflight F6), which then replaces this:
    the headline is direction accuracy over all levels; the cost is the engine run's, or the baseline answer's
    model and mapping calls; the engine loses when its headline is below the best baseline's or its label is
    wrong; the cause is "missed" when the extraction missed facts, else "wrong rule"."""
    rows = []
    for path in sorted(world.scores.glob("*/*/report.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        selection, corpus = path.parent.parent.name, path.parent.name
        run = json.loads((world.runs / selection / corpus / "run.json").read_text(encoding="utf-8"))
        systems: dict[str, float | None] = {}
        cost: dict[str, dict[str, int | None]] = {}
        for s in report["synthesis"]:
            systems[s["system"]] = next((r["direction_accuracy"] for r in s["rows"] if r["level"] == "all"), None)
            if s["system"] == "evidence-engine":
                c = run.get("cost") or {}
                calls, i, o = c.get("model_calls"), c.get("input_tokens"), c.get("output_tokens")
            else:
                answer = json.loads((world.runs / s["system"] / corpus / "answer.json").read_text(encoding="utf-8"))
                made = [m for m in (answer.get("model_call"), answer.get("mapping_call")) if m]
                calls, i, o = len(made), sum(m["input_tokens"] for m in made), sum(m["output_tokens"] for m in made)
            cost[s["system"]] = {"model_calls": calls, "input_tokens": i, "output_tokens": o,
                                 "tokens": i + o if i is not None and o is not None else None}
        engine = next(s for s in report["synthesis"] if s["system"] == "evidence-engine")
        best = max((v for k, v in systems.items() if k != "evidence-engine" and v is not None), default=None)
        loss = engine["label_correct"] is False or (best is not None and (systems["evidence-engine"] or 0) < best)
        cause = None if not loss else "missed" if (report.get("extraction") or {}).get("missed") else "wrong rule"
        rows.append({"question_id": run["protocol"]["id"], "kind": "effect", "systems": systems, "cost": cost,
                     "engine_loss": loss, "cause": cause, "report": f"{selection}~{corpus}"})
    rows.sort(key=lambda r: (not r["engine_loss"], r["question_id"], r["report"]))
    return {"domains": {"rag": rows}}


# --- scripted models -------------------------------------------------------------------------------------

def extractor_script(kind: str, doc: str, prompt: str) -> dict[str, Any]:
    """The LLM extractors' scripted reader: the screen says relevant (quoting the title), extraction finds nothing."""
    from evidence.tests.conftest import screen_yes
    if kind == "screen":
        return screen_yes(prompt, "the paper compares a retrieval-augmented model with the model without retrieval")
    return {"quotes": []} if kind == "retry" else {"items": []}


def extractor_provider() -> Any:
    from evidence.tests.conftest import provider_of, scripted
    return provider_of(scripted(extractor_script, [], name="scripted-orch"))


def paper_ids(corpus: Path) -> list[str]:
    return [p["id"] for p in json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))["papers"]]


def mapping_model(corpus: Path) -> Any:
    """The baselines' mapping call (and the RAG baseline's answering call): cite every passage shown, then map to
    'supported' with every cited paper supporting."""
    from evaluation.tests.helpers import Scripted
    header = re.compile(r"\[(\S+), (\d+)-(\d+)\]")
    known = set(paper_ids(corpus))

    def reply(prompt: str) -> dict[str, Any]:
        if "\n\nPassages:\n\n" in prompt:
            shown = [{"document": d, "start": int(a), "end": int(b)} for d, a, b in header.findall(prompt)]
            cited = shown[:3]
            refs = ", ".join(f"[{c['document']}, {c['start']}-{c['end']}]" for c in cited)
            return {"answer_text": f"The retrieved passages report higher accuracy with retrieval {refs}.",
                    "citations": cited}
        papers = sorted({d for d, _, _ in header.findall(prompt)} & known) or sorted(known)[:2]
        return {"label": "supported", "answer_text": "Retrieval improves factual accuracy in the papers cited.",
                "studies": [{"document": p, "stance": "supports"} for p in papers]}
    return Scripted(reply).model("scripted-orch")


def orchestrator(replies: list[Any]) -> Any:
    """The research agent's model with fixed replies (evaluation/tests/test_agentic_agent.py); a reply is a
    string ("{file}" becomes the paper the brief names) or a function of the messages so far."""
    from agent.loop import OrchestratorModel

    class Scripted(OrchestratorModel):
        abort_exceptions = [*OrchestratorModel.abort_exceptions, IndexError]

        def __init__(self) -> None:
            super().__init__(base_url="http://mock.invalid/v1", temperature=0.7, seed=1234)
            self.replies = list(replies)

        def _query(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
            reply = self.replies.pop(0)
            text = reply(messages) if callable(reply) else reply
            if "{file}" in text:
                found = re.search(r"\b(S\d+\.md)\b", json.dumps(messages))
                text = text.replace("{file}", found.group(1) if found else "S001.md")
            return {"model": "orch-model", "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 1200, "completion_tokens": 60, "total_tokens": 1260}}
    return Scripted()


AGENTIC_REPLIES = [
    "Read the results section of the paper first.\n" + FENCE + "bash\nls \"$CORPUS\"; grep -n -i 'accuracy' \"$CORPUS/{file}\" | head -20\n" + FENCE,
    "Record the value I am unsure of.\n" + FENCE + "bash\necho '{\"s\": \"r1\", \"p\": \"value\", \"o\": 0.5, \"file\": \"{file}\", "
    "\"quote\": \"an accuracy of 50 percent\"}' | claim\n" + FENCE,
    "The quote was not in the paper; nothing more to add.\n" + FENCE + "json\n{\"rows\": [], \"notes\": \"no further "
    "measurement found\"}\n" + FENCE,
]
def _claim_first_line(messages: list[dict[str, Any]]) -> str:
    """Claim the first line the grep of the step before printed (`S001.md:<line>`), as it stands."""
    shown = str(messages[-1].get("content", ""))
    hit = re.search(r"(S\d+\.md):([^\n]*\S)", shown)
    file, quote = (hit.group(1), hit.group(2).strip()) if hit else ("S001.md", "retrieval")
    request = json.dumps({"s": "r1", "p": "reports", "o": "higher accuracy with retrieval", "file": file, "quote": quote})
    return f"Claim what the first paper says.\n{FENCE}bash\necho '{request.replace(chr(39), '')}' | claim\n{FENCE}"


BASELINE_REPLIES = [
    "Find the papers that report accuracy.\n" + FENCE + "bash\nls \"$CORPUS\"; grep -H -m1 -i 'accuracy' \"$CORPUS\"/S001.md\n"
    + FENCE,
    _claim_first_line,
    "Done.\n" + FENCE + "json\n" + json.dumps({"rows": [{"id": "r1", "cells": {"conclusion": "Retrieval improves "
                                                                              "accuracy", "papers": ["S001"]},
                                                         "facts": [{"id": "f1", "s": "r1", "p": "reports",
                                                                    "o": "higher accuracy with retrieval",
                                                                    "claims": ["claim-000001"]}]}],
                                               "notes": "the paper that compares retrieval reports higher accuracy"})
    + "\n" + FENCE,
]


def agent_settings() -> Any:
    from evidence.agentic.runner import AgentSettings
    return AgentSettings(sandbox_mode="unsandboxed", broker="inprocess")


@contextmanager
def scripted_agentic(work: Path) -> Iterator[None]:
    """The agentic extractor's runner with the scripted orchestrator, unsandboxed, its runs kept in `work`."""
    from evidence.agentic import extractor as agentic
    from evidence.agentic.runner import ResearchAgentRunner

    def runner(settings: Any, work_dir: Any = None) -> ResearchAgentRunner:
        return ResearchAgentRunner(dataclasses.replace(settings, sandbox_mode="unsandboxed", broker="inprocess"),
                                   model_factory=lambda s: orchestrator(AGENTIC_REPLIES), work_dir=work)
    with mock.patch.object(agentic, "ResearchAgentRunner", runner):
        yield


# --- the world -------------------------------------------------------------------------------------------

def build(root: Path, *, agent: bool | None = None) -> EvidenceWorld:
    from evaluation import cli as evaluate
    from evaluation.baselines.agent import agent_baseline
    from evaluation.baselines.rag import rag_baseline
    from evidence import engine
    from evidence.agentic.runner import ResearchAgentRunner
    from modelcall import JsonlCache
    from synth import cli as synth

    agent = POSIX if agent is None else agent
    world = EvidenceWorld(Path(root), agent)
    corpora, runs, scores = world.corpora, world.runs, world.scores
    # Corpora: two levels and the mixed set, with a duplicate, a missing value and an irrelevant paper; a variant.
    assert synth.main(["build", "--name", NAME, "--seed", "7", "--studies", "4", "--levels", "explicit,paraphrased",
                       "--duplicates", "1", "--missing", "1", "--irrelevant", "1", "--renderer", "template",
                       "--out", str(corpora)]) == 0
    mixed = corpora / f"{NAME}-mixed"
    truth = json.loads((mixed / "ground_truth.json").read_text(encoding="utf-8"))
    study = next(s["study_id"] for s in truth["studies"]
                 if s.get("relevant", True) and not s.get("duplicate_of") and not s.get("missing")
                 and (s.get("effect") or {}).get("direction") == "supports")
    assert synth.main(["variant", "--corpus", str(mixed), "--study", study, "--direction", "contradicts"]) == 0
    variant = corpora / f"{NAME}-mixed-cf-{study}-contradicts"
    names = [f"{NAME}-explicit", f"{NAME}-mixed", variant.name]

    provider = extractor_provider()
    os.environ.pop("EVIDENCE_AGENT_WORK_DIR", None)
    for name in names:
        corpus = corpora / name
        engine.run(PROTOCOL, corpus, runs / "regex-only", cache=world.cache, selection="regex-only", run_id=name,
                   provider=provider)
        engine.run(PROTOCOL, corpus, runs / "cascade", cache=world.cache, selection="cascade", strategy="all",
                   model="orch-model", run_id=name, provider=provider)
        engine.run(PROTOCOL, corpus, runs / "cascade-gaps", cache=world.cache, selection="cascade", strategy="gaps",
                   model="orch-model", run_id=name, provider=provider)
        out = runs / "rag-baseline" / name
        answer = rag_baseline(corpus, model=mapping_model(corpus), model_id="scripted-orch",
                              cache=JsonlCache(world.root / "cache" / "rag-baseline.jsonl"))
        write_answer(answer, out)
    if agent:
        mixed_name = f"{NAME}-mixed"
        with scripted_agentic(world.agent_work):
            engine.run(AGENTIC, mixed, runs / "agentic-gaps", cache=world.cache, selection="cascade",
                       strategy="gaps", model="orch-model", run_id=mixed_name, provider=provider)
        out = runs / "agent-baseline" / mixed_name
        runner = ResearchAgentRunner(agent_settings(), model_factory=lambda s: orchestrator(BASELINE_REPLIES),
                                     work_dir=out / "agent-runs")
        write_answer(agent_baseline(mixed, runner=runner, model=mapping_model(mixed), model_id="scripted-orch",
                                    run_id=mixed_name, cache=JsonlCache(world.root / "cache" / "agent-baseline.jsonl")),
                     out)

    selections = ["regex-only", "cascade", "cascade-gaps"] + (["agentic-gaps"] if agent else [])
    for selection in selections:
        for name in names:
            run = runs / selection / name
            if not (run / "answer.json").is_file():
                continue
            args = ["score", "--run", str(run), "--corpus", str(corpora / name), "--out", str(scores / selection / name)]
            for system in ("rag-baseline", "agent-baseline"):
                if (runs / system / name / "answer.json").is_file():
                    args += ["--baseline", str(runs / system / name / "answer.json")]
            assert evaluate.main(args) == 0
    for selection in ("regex-only", "cascade", "cascade-gaps"):
        assert evaluate.main(["compare", "--out", str(scores / f"compare-{selection}"),
                              *[str(scores / selection / n) for n in names]]) == 0
    for name in names:
        assert evaluate.main(["compare", "--out", str(scores / "compare-funnel" / name),
                              str(scores / "cascade" / name), str(scores / "cascade-gaps" / name)]) == 0
    for selection in ("regex-only", "cascade", "cascade-gaps"):
        assert evaluate.main(["shift", "--base", str(scores / selection / mixed.name), "--variant",
                              str(scores / selection / variant.name), "--variant-json", str(variant / "variant.json"),
                              "--out", str(scores / f"shift-{selection}" / variant.name)]) == 0
    assert evaluate.main(["benchmark", str(scores / "cascade" / f"{NAME}-explicit"),
                          "--out", str(scores / "benchmark-tpl")]) == 0
    world.write_losses(stand_in_losses(world))
    proposal(world.proposals / "rag-factuality")
    return world


def write_answer(answer: dict[str, Any], out: Path) -> None:
    """As `evaluate rag-baseline` / `agent-baseline` write it (evaluation/cli._write_answer)."""
    from evaluation.cli import _write_answer
    _write_answer(answer, out)


def proposal(directory: Path) -> Path:
    """The proposal flow with the scripted model (evidence/tests/propose_support.py), one card decided by a
    person with a reason, frozen, then one amendment."""
    import yaml

    from evidence.propose import amend, cards, critic, draft, frame, freeze
    from evidence.tests.propose_support import QUESTION, Scripted

    model = Scripted()
    frame.run(QUESTION, directory, model=model.model)
    draft.run(directory)
    critic.run(directory, model=model.model)
    cards.run(directory, model=model.model)
    decisions_file = directory / "decisions.yaml"
    decisions = yaml.safe_load(decisions_file.read_text(encoding="utf-8"))
    for d in decisions["decisions"]:
        if d["card"] == "min_effect":
            option = next(o["id"] for o in json.loads((directory / "cards.json").read_text(encoding="utf-8"))["cards"]
                          [list(cards.HANDLERS).index("min_effect")]["options"] if o["id"] != d["choice"])
            d.update(choice=option, reason="a 1-point difference is within run-to-run noise on these benchmarks",
                     by="aditya")
    decisions_file.write_text(yaml.safe_dump(decisions, sort_keys=False), encoding="utf-8", newline="\n")
    freeze.run(directory, created="2026-10-17T12:00:00+00:00")
    protocol = directory / "protocol.yaml"
    text = protocol.read_text(encoding="utf-8")
    protocol.write_text(text.replace("factor: 3.0", "factor: 2.5"), encoding="utf-8", newline="\n")
    amend.run(directory, "large effects at 2.5 times the median, as in the pre-registration", before_main_run=True)
    return directory


MOCK_ROOT = "/srv/ev"   # what the world's own path becomes in the frontend's mock responses
BASE = "http://127.0.0.1"   # a Host the app answers (webapp/guard.py)


def mock_paths(world: EvidenceWorld) -> list[str]:
    """The /api/ev responses the frontend's mocks hold (webapp/web/src/mocks/ev-fixtures.json): every list,
    and the details of a few runs, papers, calls and scores, enough for every page and its tests."""
    from fastapi.testclient import TestClient

    from webapp.app import create_app
    from webapp.settings import Settings

    mixed, explicit = f"{NAME}-mixed", f"{NAME}-explicit"
    variant = next(p.name for p in sorted(world.corpora.iterdir()) if "-cf-" in p.name)
    paths = ["/api/ev/config", "/api/ev/questions", "/api/ev/questions/rag-factuality", "/api/ev/corpora",
             f"/api/ev/corpora/{mixed}", f"/api/ev/corpora/{variant}",
             f"/api/ev/corpora/{mixed}/papers/S001", "/api/ev/protocols", "/api/ev/protocols/rag-factuality",
             "/api/ev/proposals", "/api/ev/proposals/rag-factuality", "/api/ev/runs", "/api/ev/scores",
             f"/api/ev/scores/reports/cascade-gaps~{mixed}", f"/api/ev/scores/reports/cascade~{explicit}",
             "/api/ev/scores/compares/compare-cascade", f"/api/ev/scores/compares/compare-funnel~{mixed}",
             f"/api/ev/scores/shifts/shift-cascade~{variant}", "/api/ev/scores/benchmarks/benchmark-tpl",
             "/api/ev/losses"]
    paths += [f"/api/ev/run-group?source=repo&name={protocol}&extractors={extractors}&strategy={strategy}"
              for protocol in ("rag-factuality", "rag-factuality-agentic")
              for extractors in ("regex-only", "cascade") for strategy in ("all", "gaps")]   # the app's key order
    paths += [f"/api/ev/run-group?source=proposal&name={proposal}&extractors={extractors}&strategy={strategy}"
              for proposal in sorted(p.name for p in world.proposals.iterdir() if p.is_dir())
              for extractors in ("regex-only", "cascade") for strategy in ("all", "gaps")]
    runs = [f"cascade~{explicit}", f"cascade-gaps~{mixed}", f"rag-baseline~{mixed}"]
    runs += [f"agentic-gaps~{mixed}", f"agent-baseline~{mixed}"] if world.agent else []
    with TestClient(create_app(Settings(EV=world.root, WEBAPP_USER="aditya", agent_root=None)), base_url=BASE) as client:  # type: ignore[arg-type]
        for run in runs:
            detail = client.get(f"/api/ev/runs/{run}").json()
            paths.append(f"/api/ev/runs/{run}")
            if detail["kind"] == "engine":
                paths += [f"/api/ev/runs/{run}/graph"] + ([f"/api/ev/runs/{run}/protocol"] if run == runs[0] else [])
            elif detail["has_trace"]:
                paths.append(f"/api/ev/runs/{run}/agent-trace")
            for doc in detail["documents"][:2 if run == runs[0] else 1]:
                paths.append(f"/api/ev/runs/{run}/papers/{doc}")
                calls = client.get(f"/api/ev/runs/{run}/papers/{doc}").json()["calls"]
                picked = {c["kind"]: c for c in reversed(calls)}          # one call of each kind
                for call in picked.values():
                    paths.append(f"/api/ev/runs/{run}/calls/{call['call_id']}")
                    for agent_run in client.get(paths[-1]).json()["agent_runs"]:
                        paths.append(f"/api/ev/runs/{run}/calls/{call['call_id']}/trace/{agent_run}")
    return list(dict.fromkeys(paths))


def dump_mocks(world: EvidenceWorld, out: Path) -> Path:
    """{path: response JSON} for `mock_paths`, with the world's directory written as MOCK_ROOT."""
    from fastapi.testclient import TestClient

    from webapp.app import create_app
    from webapp.settings import Settings

    responses = {}
    with TestClient(create_app(Settings(EV=world.root, WEBAPP_USER="aditya", agent_root=None)), base_url=BASE) as client:  # type: ignore[arg-type]
        for path in mock_paths(world):
            response = client.get(path)
            assert response.status_code == 200, (path, response.text)
            responses[path] = response.json()
    text = json.dumps(responses, ensure_ascii=False, separators=(",", ":"))   # key order as served
    text = text.replace(str(world.root), MOCK_ROOT).replace(str(REPO), "/srv/repo")
    out.write_text(text + "\n", encoding="utf-8", newline="\n")
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    mocks = Path(args[args.index("--mocks") + 1]) if "--mocks" in args else None
    target = Path(next((a for a in args if not a.startswith("--") and Path(a) != mocks), "ev-world"))
    if target.exists():
        raise SystemExit(f"{target} exists; give a new directory")
    built = build(target)
    if mocks:
        from .write_contract import write
        dump_mocks(built, mocks)
        write(built, mocks.parent / "write-contract.json")
    print(built.root)

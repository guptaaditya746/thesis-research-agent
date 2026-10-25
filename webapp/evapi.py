"""The evidence-level viewer's API under /api/ev (the supervisor's flow, STATE.md §4 "Web app"): corpora,
protocols and proposals, engine and baseline runs (funnel, items with their spans, graph, answer, calls with
their model records and agent traces), and the scores A/B/C with the baselines beside the engine.

Read-only GETs over the files webapp/evfiles.py reads, and the proposal form's check (a POST that only reads);
nothing here starts a run or calls a model.
"""
from __future__ import annotations

from fastapi import APIRouter

from . import evcheck
from .evfiles import EvidenceFiles
from .evmodels import (
    AgentTrace,
    BenchmarkView,
    CallDetail,
    CheckRequest,
    CheckResult,
    CompareTable,
    CorpusDetail,
    CorpusPaperDetail,
    CorpusSummary,
    EvConfig,
    EvGraph,
    EvRunDetail,
    EvRunSummary,
    PreviewResult,
    ProposalDetail,
    ProposalSummary,
    ProtocolEntry,
    ProtocolView,
    ReportView,
    RunPaper,
    ScoresIndex,
    ShiftView,
    TracePage,
)


def evidence_router(files: EvidenceFiles) -> APIRouter:  # noqa: C901 (one route per endpoint)
    api = APIRouter(generate_unique_id_function=lambda route: route.name, tags=["evidence"])

    @api.get("/config", response_model=EvConfig)
    def ev_config() -> EvConfig:
        return files.config()

    # --- corpora -----------------------------------------------------------------------------------

    @api.get("/corpora", response_model=list[CorpusSummary])
    def ev_corpora() -> list[CorpusSummary]:
        return files.corpora()

    @api.get("/corpora/{name}", response_model=CorpusDetail)
    def ev_corpus(name: str) -> CorpusDetail:
        return files.corpus(name)

    @api.get("/corpora/{name}/papers/{paper}", response_model=CorpusPaperDetail)
    def ev_corpus_paper(name: str, paper: str) -> CorpusPaperDetail:
        return files.corpus_paper(name, paper)

    # --- protocols and proposals ---------------------------------------------------------------------

    @api.get("/protocols", response_model=list[ProtocolEntry])
    def ev_protocols() -> list[ProtocolEntry]:
        return files.protocols()

    @api.get("/protocols/{name}", response_model=ProtocolView)
    def ev_protocol(name: str) -> ProtocolView:
        return files.protocol(name)

    @api.get("/proposals", response_model=list[ProposalSummary])
    def ev_proposals() -> list[ProposalSummary]:
        return files.proposals()

    @api.get("/proposals/{name}", response_model=ProposalDetail)
    def ev_proposal(name: str) -> ProposalDetail:
        return files.proposal(name)

    @api.post("/proposals/{name}/check", response_model=CheckResult)
    def ev_proposal_check(name: str, request: CheckRequest) -> CheckResult:
        """The deterministic checks of the draft with these decisions applied (no model call)."""
        return evcheck.check(files, name, request)

    @api.get("/proposals/{name}/preview", response_model=PreviewResult)
    def ev_proposal_preview(name: str, corpus: str, paper: str) -> PreviewResult:
        """One paper's text with the hits of the draft's screen terms, the frame's names and the method kinds."""
        return evcheck.preview(files, name, corpus, paper)

    # --- runs --------------------------------------------------------------------------------------

    @api.get("/runs", response_model=list[EvRunSummary])
    def ev_runs() -> list[EvRunSummary]:
        return files.runs()

    @api.get("/runs/{run_id}", response_model=EvRunDetail)
    def ev_run(run_id: str) -> EvRunDetail:
        return files.run(run_id)

    @api.get("/runs/{run_id}/papers/{document}", response_model=RunPaper)
    def ev_run_paper(run_id: str, document: str) -> RunPaper:
        return files.run_paper(run_id, document)

    @api.get("/runs/{run_id}/graph", response_model=EvGraph)
    def ev_run_graph(run_id: str) -> EvGraph:
        return files.run_graph(run_id)

    @api.get("/runs/{run_id}/protocol", response_model=ProtocolView)
    def ev_run_protocol(run_id: str) -> ProtocolView:
        return files.run_protocol(run_id)

    @api.get("/runs/{run_id}/calls/{call_id}", response_model=CallDetail)
    def ev_run_call(run_id: str, call_id: str) -> CallDetail:
        return files.run_call(run_id, call_id)

    @api.get("/runs/{run_id}/calls/{call_id}/trace/{agent_run}", response_model=AgentTrace)
    def ev_call_trace(run_id: str, call_id: str, agent_run: str) -> AgentTrace:
        return files.call_trace(run_id, call_id, agent_run)

    @api.get("/runs/{run_id}/trace", response_model=TracePage)
    def ev_run_trace(run_id: str, after: int = 0) -> TracePage:
        """The live run trace: warm-pass calls, then the engine events, rows numbered from 1; `after` is the last row number held."""
        return files.run_trace(run_id, after)

    @api.get("/runs/{run_id}/agent-trace", response_model=AgentTrace)
    def ev_baseline_trace(run_id: str) -> AgentTrace:
        """The agent baseline's own run (its agent-runs/ directory)."""
        return files.baseline_trace(run_id)

    # --- scores ------------------------------------------------------------------------------------

    @api.get("/scores", response_model=ScoresIndex)
    def ev_scores() -> ScoresIndex:
        return files.scores()

    @api.get("/scores/reports/{score_id}", response_model=ReportView)
    def ev_report(score_id: str) -> ReportView:
        return files.report(score_id)

    @api.get("/scores/compares/{score_id}", response_model=CompareTable)
    def ev_compare(score_id: str) -> CompareTable:
        return files.compare(score_id)

    @api.get("/scores/shifts/{score_id}", response_model=ShiftView)
    def ev_shift(score_id: str) -> ShiftView:
        return files.shift(score_id)

    @api.get("/scores/benchmarks/{score_id}", response_model=BenchmarkView)
    def ev_benchmark(score_id: str) -> BenchmarkView:
        return files.benchmark(score_id)

    return api

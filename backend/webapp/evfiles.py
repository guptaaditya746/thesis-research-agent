"""The evidence-level files as the viewer shows them (webapp/evapi.py; docs/evidence-system.md Parts A-G).

Read-only: nothing here writes, starts a run or calls a model (the jobs of webapp/evjobs.py do, with the same
commands as the command line and Slurm, docs/runbook-slurm.md); the viewer reads what they leave, in the
layout the runbook makes:

- corpora: `$CORPORA/<name>/` (`synth build`, `synth variant`, `evidence fetch`): manifest.json, papers/, corpus.json,
  ground_truth.json, fidelity.json, decoys.json, variant.json; source.json for real papers (no ground truth);
- runs: `$EV_RUNS/<group>/<name>/`, an engine run (run.json, answer.json, funnel.json, evidence.jsonl,
  graph.json, events.jsonl, calls/) or a baseline's answer.json (`evaluate rag-baseline|agent-baseline
  --out`, the agent baseline's own run directories in its agent-runs/); a run's id is `<group>~<name>`;
- the engine's record cache `$EV_CACHE/extractor_calls.jsonl`, which holds every call's task, its model
  calls (request, response, usage) and, for an agentic call, the agent run's record; the agent's run
  directories under `$EV_AGENT_WORK` (`<agent run id>-<random>/runs/<agent run id>/`);
- scores: `$SCORES/<group>/[<name>/]` with report.json, compare.json, shift.json or a benchmark directory
  (benchmark.md and `<extractor id>/benchmark.json`); an id joins the directory names with `~`;
- proposals: `$EV_PROPOSALS/<name>/` (`evidence propose`); protocols: `domains/rag/protocols/*.yaml`.

Ids from URLs are plain names (webapp/files.py `ID`) and every path is checked to stay inside its root
(`inside`); a path written inside a file (run.json `settings.corpus`, `settings.cache`) is never opened: the
run's corpus is found under the corpora root by its manifest's sha256 (else its corpus id), its cache is
`$EV_CACHE`. Files are re-read when their size or mtime change (`signature`).

Paper texts are cut into segments on the server (`segments`): selectors count code points, JavaScript
strings UTF-16 units, so the page never converts an offset.
"""
from __future__ import annotations

import json
import logging
import re
import threading
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from agent.anchor import read_text
from jsonio import file_sha256, sha256_hex
from agent.rundir import RunDir as AgentRunDir
from evidence.calls import cache_key
from evidence.contract import ExtractionResult, ExtractorSpec, Item
from evidence.propose.common import CARDS, CRITIC, DRAFT, FRAME, PROPOSAL
from evidence.protocol import parse
from evidence.rundir import (ANSWER_FILE, CACHE_FILE, CALLS_DIR, EVENTS_FILE, EVIDENCE_FILE, FUNNEL_FILE, GRAPH_FILE, PROTOCOL_FILE,
                             REASON_FILE, RECORDS_FILE, RUN_FILE, PaperIndex, RunDir)

from .agenttrace import claim_of, steps_of
from .evmodels import (
    AgentTrace,
    Amendment,
    BenchmarkView,
    CallDetail,
    CallSummary,
    Card,
    Check,
    CompareTable,
    CorpusDetail,
    CorpusPaper,
    CorpusPaperDetail,
    CorpusSource,
    CorpusSummary,
    Decision,
    EV_ANSWER,
    EvConfig,
    EvGraph,
    EvRunDetail,
    EvRunSummary,
    FunnelDoc,
    Losses,
    LossesView,
    ModelCallRecord,
    Placement,
    ProposalDetail,
    ProposalSummary,
    ProtocolEntry,
    ProtocolView,
    Report,
    ReportView,
    Root,
    RunPaper,
    ScoreRef,
    ScoresIndex,
    Segment,
    ShiftView,
    Study,
    TracePage,
    TruthAnswer,
    VariantInfo,
)
from modelcall.cache import KEY_LINE
from .evtrace import TraceReader
from .files import ID, RUN_SEP, Damaged, NotFound, check_id, inside, read_json, read_jsonl, signature
from .models import Claim, ClaimRef, ModelCall, Step
from .settings import Settings

LOG = logging.getLogger(__name__)
STEPS = ("frame", "draft", "critic", "cards", "freeze")
STEP_FILES = {"frame": FRAME, "draft": DRAFT, "critic": CRITIC, "cards": CARDS, "freeze": PROPOSAL}
REVISION_FILE = re.compile(r"^protocol\.v(\d+)\.yaml$")
OUTPUT_HEAD = 4096


def parts(value: str, what: str, most: int = 3) -> list[str]:
    """`a~b~c` -> its plain names; NotFound for anything else."""
    names = (value or "").split(RUN_SEP)
    if not 1 <= len(names) <= most:
        raise NotFound(f"no such {what}: {value!r}")
    return [check_id(n, what) for n in names]


def subdirs(root: Path | None) -> list[Path]:
    """The plainly named directories in `root`; symlinks are left out (`inside` would refuse one leading out)."""
    if root is None or not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if ID.fullmatch(p.name) and not p.is_symlink() and p.is_dir())


def inside_or_none(root: Path, path: Path) -> Path | None:
    """`path` (built under `root`) checked to stay inside it, or None: one bad child never fails a listing."""
    try:
        return inside(root, *path.relative_to(root).parts)
    except (NotFound, ValueError):
        return None


def segments(text: str, spans: Iterable[tuple[int, int, str, str]]) -> list[Segment]:
    """The text cut at every span boundary; each segment lists the marks (ids) and roles of the spans over it.
    Spans outside the text are clipped, empty ones dropped."""
    spans = [(max(0, a), min(len(text), b), mark, role) for a, b, mark, role in spans]
    spans = [s for s in spans if s[0] < s[1]]
    cuts = sorted({0, len(text), *(s[0] for s in spans), *(s[1] for s in spans)})
    out = []
    for a, b in zip(cuts, cuts[1:]):
        over = [s for s in spans if s[0] < b and s[1] > a]
        out.append(Segment(text=text[a:b], start=a, end=b, marks=sorted({s[2] for s in over}),
                           roles=sorted({s[3] for s in over})))
    return out


class RecordCache:
    """Random access to a modelcall.JsonlCache file without loading every value: one scan for the byte offset of
    each key's last line (a later line wins, as JsonlCache.load does), redone when the file changes. The engine's
    cache holds every model call's messages and every agent record, so loading it whole per request (what
    JsonlCache does) would not do; no library indexes JSON lines by key, hence this small scanner.

    The cache only grows (JsonlCache appends), so a file that grew is scanned from the end of the last complete
    line indexed; one that shrank, or whose bytes before that point changed (the last indexed line's tail is
    compared), is scanned again from the start. A torn last line is left for the next scan."""

    TAIL = 64

    def __init__(self) -> None:
        # path -> (signature, index, end of the last complete line scanned, the bytes before that end)
        self._index: dict[Path, tuple[tuple[Any, ...], dict[str, tuple[int, int]], int, bytes]] = {}
        self._lock = threading.Lock()

    def offsets(self, path: Path) -> dict[str, tuple[int, int]]:
        sig = signature(path)
        with self._lock:
            hit = self._index.get(path)
        if hit and hit[0] == sig:
            return hit[1]
        found: dict[str, tuple[int, int]] = {}
        start = 0
        try:
            with open(path, "rb") as fh:
                if hit and sig[0] is not None and sig[0][0] >= hit[2]:
                    fh.seek(max(0, hit[2] - len(hit[3])))
                    if fh.read(len(hit[3])) == hit[3]:      # the same bytes up to where the last scan ended
                        found, start = dict(hit[1]), hit[2]
                fh.seek(start)
                pos, tail = start, hit[3] if start else b""
                for line in fh:
                    if not line.endswith(b"\n"):
                        break                                 # torn: indexed once complete
                    match = KEY_LINE.match(line)
                    if match:
                        found[match.group(1).decode()] = (pos, len(line))
                    pos += len(line)
                    tail = (tail + line)[-self.TAIL:]
        except OSError:
            return {}
        with self._lock:
            self._index[path] = (sig, found, pos, tail)
        return found

    def get(self, path: Path, key: str) -> Any | None:
        where = self.offsets(path).get(key)
        if where is None:
            return None
        try:
            with open(path, "rb") as fh:
                fh.seek(where[0])
                row = json.loads(fh.read(where[1]))
        except (OSError, ValueError):
            return None
        return row.get("value") if isinstance(row, dict) and row.get("key") == key else None


class EvidenceFiles:
    """Every read of the viewer; one per app."""

    def __init__(self, settings: Settings) -> None:
        self.s = settings
        self.cache = RecordCache()
        self.trace = TraceReader()
        self._lock = threading.Lock()
        self._memo: dict[Any, tuple[tuple[Any, ...], Any]] = {}

    def _cached(self, key: Any, files: tuple[Path, ...], make: Any) -> Any:
        """make() again only when one of `files` changed (size or mtime)."""
        sig = signature(*files)
        with self._lock:
            hit = self._memo.get(key)
            if hit and hit[0] == sig:
                return hit[1]
        value = make()
        with self._lock:
            self._memo[key] = (sig, value)
        return value

    @staticmethod
    def _need(root: Path | None, what: str, variable: str) -> Path:
        if root is None:
            raise NotFound(f"no {what} directory configured (set ${variable} or $EV)")
        if not root.is_dir():
            raise NotFound(f"the {what} directory {root} does not exist")
        return root

    def config(self) -> EvConfig:
        def root(path: Path | None) -> Root:
            return Root(path=str(path) if path else None, exists=bool(path and path.is_dir()))
        from evidence.cli import DEFAULT_MODEL
        from synth.levels import LEVELS

        from .settings import llm_key_set
        s = self.s
        return EvConfig(ev=str(s.ev) if s.ev else None, corpora=root(s.corpora_dir), runs=root(s.ev_runs_dir),
                        scores=root(s.scores_dir), proposals=root(s.proposals_dir), cache=root(s.ev_cache_dir),
                        agent_work=root(s.agent_work_dir), protocols=root(s.protocols),
                        questions=Root(path=str(s.questions), exists=s.questions.is_file()), jobs=root(s.jobs_dir),
                        user=s.user, default_model=DEFAULT_MODEL, llm_base_url=s.litellm_base_url,
                        llm_key_set=llm_key_set(), agent_root=str(s.agent_root) if s.agent_root else None,
                        model_jobs=s.model_jobs, levels=list(LEVELS))

    # --- corpora -------------------------------------------------------------------------------------

    def corpus_dir(self, name: str) -> Path:
        root = self._need(self.s.corpora_dir, "corpora", "CORPORA")
        path = inside(root, check_id(name, "corpus"))
        if not (path / "manifest.json").is_file():
            raise NotFound(f"no such corpus: {name!r}")
        return path

    def _corpus_summary(self, path: Path) -> CorpusSummary | None:
        manifest = read_json(path / "manifest.json")
        if not isinstance(manifest, dict):
            return None
        meta = read_json(path / "corpus.json") or {}
        truth = read_json(path / "ground_truth.json") or {}
        fidelity = read_json(path / "fidelity.json") or {}
        variant = read_json(path / "variant.json")
        source = read_json(path / "source.json")
        source = source if isinstance(source, dict) and isinstance(source.get("kind"), str) else None
        papers = manifest.get("papers") or []
        listed = {p.get("id") for p in papers}
        records = [r for r in fidelity.get("papers") or [] if r.get("id") in listed]
        base = None
        if isinstance(variant, dict):
            base = next((c.name for c in subdirs(path.parent) if c != path
                         and (read_json(c / "manifest.json") or {}).get("corpus_id") == variant.get("base_corpus_id")
                         and not (c / "variant.json").exists()), None)
        return CorpusSummary(
            name=path.name, corpus_id=str(manifest.get("corpus_id", "")), level=meta.get("level"),
            renderer=meta.get("renderer"), seed=meta.get("seed"), question=meta.get("question") or truth.get("question"),
            protocol=meta.get("protocol"), settings=meta.get("settings"), papers=len(papers),
            fidelity_ok=sum(bool(r.get("ok")) for r in records) if records else None,
            excluded=list(fidelity.get("excluded") or []),
            answer=TruthAnswer.model_validate(truth["answer"]) if isinstance(truth.get("answer"), dict) else None,
            variant=VariantInfo.model_validate(variant) if isinstance(variant, dict) else None, base=base,
            manifest_sha256=file_sha256(path / "manifest.json"),
            ground_truth=not (source is not None and source.get("ground_truth") is False),
            source=CorpusSource.model_validate(source) if source is not None else None)

    def corpora(self) -> list[CorpusSummary]:
        root = self.s.corpora_dir
        out = []
        for path in subdirs(root):
            summary = self._cached(("corpus", path), (path / "manifest.json", path / "corpus.json",
                                                      path / "ground_truth.json", path / "variant.json",
                                                      path / "source.json"),
                                   lambda p=path: self._corpus_summary(p))
            if summary is not None:
                out.append(summary)
        return out

    def corpus_by(self, *, manifest_sha256: str | None = None, corpus_id: str | None = None) -> str | None:
        """The corpus directory a run or an answer was made from: by manifest hash first, else by corpus id."""
        corpora = self.corpora()
        for c in corpora:
            if manifest_sha256 and c.manifest_sha256 == manifest_sha256:
                return c.name
        return next((c.name for c in corpora if corpus_id and c.corpus_id == corpus_id), None)

    def corpus(self, name: str) -> CorpusDetail:
        path = self.corpus_dir(name)
        summary = self._corpus_summary(path)
        if summary is None:
            raise NotFound(f"corpus {name!r} has no readable manifest.json")
        meta = read_json(path / "corpus.json") or {}
        truth = read_json(path / "ground_truth.json") or {}
        fidelity = {r.get("id"): r for r in (read_json(path / "fidelity.json") or {}).get("papers") or []}
        return CorpusDetail(**summary.model_dump(), models=meta.get("models"), generator=meta.get("generator"),
                            papers_list=self._papers(path, meta, truth, fidelity))

    @staticmethod
    def _papers(path: Path, meta: dict[str, Any], truth: dict[str, Any], fidelity: dict[str, Any]) -> list[CorpusPaper]:
        manifest = read_json(path / "manifest.json") or {}
        levels = {p.get("id"): p.get("level") for p in meta.get("papers") or []}
        studies = {s.get("paper", s.get("study_id")): s for s in truth.get("studies") or []}
        out = []
        for p in manifest.get("papers") or []:
            study = studies.get(p["id"]) or {}
            effect = study.get("effect") or {}
            record = fidelity.get(p["id"])
            out.append(CorpusPaper(id=p["id"], file=p["file"], sha256=p["sha256"], level=levels.get(p["id"]) or study.get("level"),
                                   relevant=study.get("relevant", True) is not False,
                                   direction=effect.get("direction") if study.get("relevant", True) is not False else None,
                                   delta=effect.get("delta"), flags=list(study.get("flags") or []),
                                   duplicate_of=study.get("duplicate_of"), missing=study.get("missing"),
                                   fidelity_ok=record.get("ok") if record else None))
        return out

    def _paper_text(self, corpus: Path, paper: str) -> tuple[dict[str, Any], str]:
        manifest = read_json(corpus / "manifest.json") or {}
        entry = next((p for p in manifest.get("papers") or [] if p.get("id") == paper), None)
        if entry is None:
            raise NotFound(f"no paper {paper!r} in {corpus.name}")
        file = inside(corpus, *Path(str(entry["file"])).parts)
        if not file.is_file():
            file = inside(corpus, "papers", Path(str(entry["file"])).name)
        try:
            return entry, read_text(file)
        except OSError as exc:
            raise NotFound(f"{entry['file']} of {corpus.name} cannot be read") from exc

    def corpus_paper(self, name: str, paper: str) -> CorpusPaperDetail:
        path = self.corpus_dir(name)
        entry, text = self._paper_text(path, check_id(paper, "paper"))
        meta = read_json(path / "corpus.json") or {}
        truth = read_json(path / "ground_truth.json") or {}
        fidelity = {r.get("id"): r for r in (read_json(path / "fidelity.json") or {}).get("papers") or []}
        listed = next(p for p in self._papers(path, meta, truth, fidelity) if p.id == paper)
        placements = [Placement.model_validate(p) for p in truth.get("placements") or [] if p.get("paper") == paper]
        study = next((s for s in truth.get("studies") or [] if s.get("paper", s.get("study_id")) == paper), None)
        decoys = [d for d in read_json(path / "decoys.json") or [] if isinstance(d, dict) and d.get("paper") == paper]
        marks = [(p.start, p.end, p.fact, p.role) for p in placements]
        marks += [(int(d["start"]), int(d["end"]), f"decoy:{d.get('measurement')}", "decoy") for d in decoys
                  if isinstance(d.get("start"), int) and isinstance(d.get("end"), int)]
        return CorpusPaperDetail(corpus=name, paper=listed, text=text, segments=segments(text, marks), study=study,
                                 placements=placements, fidelity=fidelity.get(paper), decoys=decoys)

    # --- protocols and proposals ------------------------------------------------------------------------

    @staticmethod
    def protocol_view(path: Path, source: str, name: str) -> ProtocolView:
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise NotFound(f"{name}: no protocol file") from exc
        text = data.decode("utf-8")
        try:
            protocol = parse(text)
        except (ValueError, yaml.YAMLError) as exc:   # pydantic's ValidationError is a ValueError
            return ProtocolView(source=source, name=name, path=str(path), sha256=sha256_hex(data), yaml=text, phases=[],
                                error=str(exc)[:2000])
        return ProtocolView(source=source, name=name, path=str(path), sha256=protocol.sha256, yaml=text,
                            phases=protocol.phases(), protocol=protocol)

    def protocols(self) -> list[ProtocolEntry]:
        root = self.s.protocols
        out = []
        for path in sorted(root.glob("*.yaml")) if root.is_dir() else []:
            view = self._cached(("protocol", path), (path,), lambda p=path: self.protocol_view(p, "repo", p.stem))
            p = view.protocol
            out.append(ProtocolEntry(name=path.stem, id=p.id if p else None, version=p.version if p else None,
                                     revision=p.revision if p else None, question=p.question if p else None,
                                     sha256=view.sha256, error=view.error))
        return out

    def protocol(self, name: str) -> ProtocolView:
        root = self.s.protocols
        path = inside(root, check_id(name, "protocol") + ".yaml")
        if not path.is_file():
            raise NotFound(f"no such protocol: {name!r}")
        return self.protocol_view(path, "repo", name)

    def _proposal_summary(self, path: Path) -> ProposalSummary:
        frame = read_json(path / "frame.json") or {}
        proposal = read_json(path / "proposal.json")
        amendments = read_jsonl(path / "amendments.jsonl")
        revision, sha = None, None
        if isinstance(proposal, dict):
            revision = (proposal.get("protocol") or {}).get("revision")
            sha = (proposal.get("protocol") or {}).get("sha256")
        if amendments:
            revision, sha = amendments[-1].get("revision", revision), amendments[-1].get("sha256", sha)
        return ProposalSummary(name=path.name, question=frame.get("question") or (proposal or {}).get("question"),
                               steps=[s for s in STEPS if (path / STEP_FILES[s]).is_file()],
                               frozen=isinstance(proposal, dict), revision=revision, protocol_sha256=sha,
                               decided_by=(proposal or {}).get("decided_by") or {}, amendments=len(amendments))

    def proposals(self) -> list[ProposalSummary]:
        return [self._proposal_summary(p) for p in subdirs(self.s.proposals_dir) if (p / "frame.json").is_file()]

    def proposal(self, name: str) -> ProposalDetail:
        root = self._need(self.s.proposals_dir, "proposals", "EV_PROPOSALS")
        path = inside(root, check_id(name, "proposal"))
        if not (path / "frame.json").is_file():
            raise NotFound(f"no such proposal: {name!r}")
        summary = self._proposal_summary(path)
        proposal = read_json(path / "proposal.json")
        critic = read_json(path / "critic.json")
        cards = read_json(path / "cards.json")
        card_list = [c for c in (cards.get("cards") or [] if isinstance(cards, dict) else []) if isinstance(c, dict) and "id" in c]
        frozen = {d.get("card"): d for d in (proposal or {}).get("decisions") or [] if isinstance(d, dict)} \
            if isinstance(proposal, dict) else {}
        pending, problems = self.decisions_of(path, card_list) if not frozen else ({}, [])
        out_cards = []
        for card in card_list:
            cid = str(card["id"])
            entry = frozen.get(cid) if frozen else pending.get(cid)
            try:
                decision = Decision.model_validate(entry) if isinstance(entry, dict) else None
            except ValidationError:
                decision = None
            mine = [p for p in problems if p.startswith(f"{cid}:")]
            out_cards.append(Card.model_validate({**card, "decision": decision,
                                                  "raw_decision": entry if entry is not None and decision is None else None,
                                                  "problems": mine}))
        protocol = self.protocol_view(path / "protocol.yaml", "proposal", name) if (path / "protocol.yaml").is_file() else None
        draft = path / "draft.yaml"
        revisions = sorted(int(m.group(1)) for p in path.iterdir() if (m := REVISION_FILE.match(p.name)))
        return ProposalDetail(**summary.model_dump(), frame=read_json(path / "frame.json"),
                              sources=read_json(path / "draft.sources.json"),
                              draft_yaml=draft.read_text(encoding="utf-8") if draft.is_file() else None,
                              critic=critic if isinstance(critic, dict) else None,
                              checks=[Check.model_validate(c) for c in (critic or {}).get("checks") or []]
                              if isinstance(critic, dict) else [],
                              # proposal.json repeats frame, sources and critic, which are given on their own
                              cards=out_cards, proposal={k: v for k, v in proposal.items() if k not in ("frame", "sources", "critic")}
                              if isinstance(proposal, dict) else None,
                              protocol=protocol, revisions=revisions, decision_problems=problems,
                              waivers=[] if frozen else self.waivers_of(path),
                              decisions_sha256=file_sha256(path / "decisions.yaml") if (path / "decisions.yaml").is_file() else None,
                              amendment_log=[Amendment.model_validate(a) for a in read_jsonl(path / "amendments.jsonl")])

    @staticmethod
    def waivers_of(path: Path) -> list[dict[str, str]]:
        """The waivers decisions.yaml holds, {check, reason, by} each (entries of another shape are left out)."""
        try:
            data = yaml.safe_load((path / "decisions.yaml").read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            return []
        entries = data.get("waivers") if isinstance(data, dict) else None
        return [{k: str(w[k]) for k in ("check", "reason", "by")} for w in entries or []
                if isinstance(w, dict) and all(isinstance(w.get(k), str) for k in ("check", "reason", "by"))]

    @staticmethod
    def decisions_of(path: Path, cards: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
        """decisions.yaml before freeze, as the person left it: the entry per card (whatever its shape) and
        what `evidence propose freeze` would refuse (cards.validate's own messages). The person edits this file
        by hand, so anything in it is shown, never a reason to fail the page."""
        from evidence.propose.cards import validate
        from evidence.propose.common import ProposalError
        try:
            data = yaml.safe_load((path / "decisions.yaml").read_text(encoding="utf-8"))
        except OSError:
            return {}, []
        except yaml.YAMLError as exc:
            return {}, [f"decisions.yaml is not YAML: {str(exc)[:300]}"]
        entries = data.get("decisions") if isinstance(data, dict) else None
        by_card = {str(e.get("card")): e for e in entries if isinstance(e, dict)} if isinstance(entries, list) else {}
        try:
            validate(cards, data)
            problems: list[str] = []
        except ProposalError as exc:
            lines = str(exc).splitlines()
            problems = [ln.strip() for ln in lines[1:] if ln.strip()] if len(lines) > 1 else [str(exc)]
        except Exception as exc:  # noqa: BLE001 - a hand-edited file must never fail the page
            problems = [f"decisions.yaml could not be checked: {type(exc).__name__}: {exc}"]
        return by_card, problems

    # --- runs ----------------------------------------------------------------------------------------

    def run_dir(self, run_id: str) -> Path:
        root = self._need(self.s.ev_runs_dir, "runs", "EV_RUNS")
        names = parts(run_id, "run", most=2)
        if len(names) != 2:
            raise NotFound(f"no such run: {run_id!r} (ids are <group>~<name>)")
        path = inside(root, *names)
        if RunDir(path).kind is None:
            raise NotFound(f"no such run: {run_id!r}")
        return path

    @staticmethod
    def _run_info(path: Path) -> tuple[EvRunSummary, str | None] | None:
        """The run's summary from its own files (without the corpus, which depends on the corpora root), and its
        manifest sha256. What an engine run or a baseline is, and when it is complete, is `RunDir.kind` and
        `RunDir.complete`: without a run.json an engine run is incomplete (crashed, or still running)."""
        rd = RunDir(path)
        kind = rd.kind
        if kind is None:
            return None
        run = rd.record or {}
        answer = rd.try_json(ANSWER_FILE)
        answer = answer if isinstance(answer, dict) else None
        run_id = f"{path.parent.name}{RUN_SEP}{path.name}"
        counts = answer.get("counts") if answer else None
        if kind == "engine":
            settings = rd.settings
            return EvRunSummary(id=run_id, group=path.parent.name, name=path.name, kind="engine", complete=rd.complete,
                                system=(answer or {}).get("system", "evidence-engine"), mode=run.get("mode"),
                                strategy=settings.strategy if settings else None,
                                selection=settings.selection if settings else None,
                                model=settings.model if settings else None, protocol=run.get("protocol"), corpus_id=run.get("corpus_id"),
                                label=(answer or {}).get("label") if run else None, counts=counts if run else None,
                                papers=len((answer or {}).get("studies") or []) or None, cost=run.get("cost"),
                                error_calls=rd.failed_calls()), \
                run.get("manifest_sha256")
        assert answer is not None
        settings = answer.get("settings") or {}
        return EvRunSummary(id=run_id, group=path.parent.name, name=path.name, kind="baseline", system=answer["system"],
                            strategy=settings.get("retrieval"), model=(answer.get("model_call") or answer.get("mapping_call")
                                                                       or {}).get("model"),
                            corpus_id=answer.get("corpus_id"), label=answer.get("label"), counts=counts,
                            papers=len(answer.get("studies") or []) or None), None

    def run_summary(self, path: Path) -> EvRunSummary | None:
        """The cached file part, then the corpus looked up now (the corpora root may have changed since)."""
        info = self._cached(("run", path), RunDir(path).watched(),
                            lambda: self._run_info(path))
        if info is None:
            return None
        summary, manifest = info
        return summary.model_copy(update={"corpus": self.corpus_by(manifest_sha256=manifest, corpus_id=summary.corpus_id)})

    def runs(self) -> list[EvRunSummary]:
        out = []
        for group in subdirs(self.s.ev_runs_dir):
            for path in subdirs(group):
                summary = self.run_summary(path)
                if summary is not None:
                    out.append(summary)
        return out

    def _calls(self, path: Path, run: dict[str, Any]) -> list[CallSummary]:
        """The extractor_call events of a run, as call summaries (events.jsonl, cached until it changes)."""
        kinds = {k: (v or {}).get("kind") for k, v in (run.get("extractor_specs") or {}).items()}

        def make() -> list[CallSummary]:
            out = []
            try:
                events = RunDir(path).events_of("extractor_call") or []
            except ValueError:   # damage in the middle of the chain: the calls it shows are none
                events = []
            for r in events:
                meta = r.get("custom_metadata") or {}
                out.append(CallSummary(call_id=r["task_id"], document=str(meta.get("document", r.get("group_id", ""))),
                                       evidence_type=str(meta.get("evidence_type", "")), extractor_id=r.get("agent_id", ""),
                                       kind=kinds.get(r.get("agent_id")), position=meta.get("position"),
                                       status=r.get("status", ""), source=meta.get("source"),
                                       attempt=int(meta.get("attempt") or 0), focus=meta.get("focus"),
                                       items=len(r.get("generated") or []), rejected=int(meta.get("rejected") or 0),
                                       model_calls=len(meta.get("model_calls") or [])))
            return out
        return self._cached(("calls", path), (RunDir(path).file(EVENTS_FILE),), make)

    def run(self, run_id: str) -> EvRunDetail:
        path = self.run_dir(run_id)
        summary = self.run_summary(path)
        if summary is None:
            raise NotFound(f"run {run_id!r} has neither a run.json nor a baseline's answer.json")
        rd = RunDir(path)
        run = rd.try_json(RUN_FILE)
        run = run if isinstance(run, dict) else {}
        answer = rd.try_json(ANSWER_FILE)
        funnel = rd.try_json(FUNNEL_FILE)
        reason = rd.try_json(REASON_FILE) if summary.kind == "engine" else None
        documents: list[str] = []
        if summary.corpus:
            manifest = read_json(self.corpus_dir(summary.corpus) / "manifest.json") or {}
            documents = [p["id"] for p in manifest.get("papers") or []]
        elif isinstance(answer, dict):
            documents = [s["document"] for s in answer.get("studies") or []]
        if not documents and summary.kind == "engine":   # incomplete: the papers it reached, from its events
            documents = list(dict.fromkeys(c.document for c in self._calls(path, run)))
        runs = self.runs()
        same = [r.id for r in runs if r.kind == "baseline" and r.id != summary.id
                and ((r.corpus and r.corpus == summary.corpus) or (r.corpus_id and r.corpus_id == summary.corpus_id))]
        reports = [r.id for r in self.scores().reports if r.run_id == summary.name and r.corpus_id == summary.corpus_id
                   and r.group == summary.group] if summary.kind == "engine" else []
        display = self._display(rd) if summary.kind == "engine" else {}   # registers the run's pack: specs need it
        specs = [ExtractorSpec.model_validate({k: v for k, v in spec.items() if k in ExtractorSpec.model_fields})
                 for spec in (run.get("extractor_specs") or {}).values()]
        return EvRunDetail(**summary.model_dump(), extractors=specs, settings=run.get("settings"),
                           chain_head=run.get("chain_head"), source_run=run.get("source_run"),
                           answer=EV_ANSWER.validate_python(answer) if isinstance(answer, dict) else None,
                           funnel={d: FunnelDoc.model_validate(v) for d, v in (funnel.get("documents") or {}).items()}
                           if isinstance(funnel, dict) else None,
                           documents=documents, baselines=same, reports=reports,
                           has_trace=summary.kind == "baseline" and self._baseline_run_dir(path) is not None,
                           link_flags=len(reason.get("link_flags") or []) if isinstance(reason, dict) else None,
                           display=display)

    @staticmethod
    def _display(rd: RunDir) -> dict[str, str]:
        """The display names of the run's pack (`Pack.display`): what the topic calls the two sides. Empty when
        the run has no protocol.yaml or its pack cannot be read (moved, or written by an older code)."""
        try:
            pack = rd.register_pack()
        except (OSError, ValueError, yaml.YAMLError) as exc:   # the page then names the sides treatment and control
            LOG.warning("run %s: the display names of its pack cannot be read: %s", rd.root, str(exc)[:200])
            return {}
        return dict(pack.display) if pack is not None else {}

    def _items(self, path: Path) -> list[Item]:
        """The run's evidence items; a damaged line (not the torn tail) is `Damaged`, named `group/run/file:line`
        relative to the runs root, never by its server path."""
        def make() -> list[Item]:
            rd = RunDir(path)
            try:
                return rd.items()
            except ValueError as exc:   # read_lines' `path:line: ...`, or an item that fails validation
                shown = f"{path.parent.name}/{path.name}/{EVIDENCE_FILE}"
                text = str(exc)
                full = str(rd.file(EVIDENCE_FILE))
                message = text.replace(full, shown) if full in text else f"{shown}: {text.splitlines()[0]}"
                raise Damaged(message[:500]) from None
        return self._cached(("items", path), (RunDir(path).file(EVIDENCE_FILE),), make)

    def run_paper(self, run_id: str, document: str) -> RunPaper:
        path = self.run_dir(run_id)
        document = check_id(document, "paper")
        summary = self.run_summary(path)
        rd = RunDir(path)
        run = rd.try_json(RUN_FILE)
        run = run if isinstance(run, dict) else {}
        answer = rd.try_json(ANSWER_FILE)
        answer = answer if isinstance(answer, dict) else {}
        funnel = rd.try_json(FUNNEL_FILE)
        funnel = (funnel.get("documents") if isinstance(funnel, dict) else None) or {}
        text, file = None, f"papers/{document}.md"
        papers = PaperIndex([(document, file)])   # without the corpus: the paper's usual file
        if summary and summary.corpus:
            entry, text = self._paper_text(self.corpus_dir(summary.corpus), document)
            file = str(entry["file"])
            papers = PaperIndex.of_corpus(self.corpus_dir(summary.corpus))
        items = [i for i in self._items(path) if papers.find(i) == document]
        study = next((s for s in answer.get("studies") or [] if s.get("document") == document), None)
        calls = [c for c in self._calls(path, run) if c.document == document] if summary and summary.kind == "engine" else []
        if text is None and study is None and not items and not calls:
            raise NotFound(f"run {run_id!r} has no document {document!r}")
        marks = [(int(sp.selector["start"]), int(sp.selector["end"]), i.item_id, sp.role)
                 for i in items for sp in i.spans]   # an item's spans are all in its paper
        if text is not None and answer.get("citations"):   # a baseline's cited passages
            marks += [(c["start"], c["end"], f"cited:{c['start']}-{c['end']}", "citation")
                      for c in answer["citations"] if c.get("document") == document]
        return RunPaper(run=run_id, document=document, text=text, segments=segments(text, marks) if text else [],
                        items=items, study=Study.model_validate(study) if study else None,
                        funnel=FunnelDoc.model_validate(funnel[document]) if document in funnel else None, calls=calls)

    def run_graph(self, run_id: str) -> EvGraph:
        """A plan run's records graph (records.nq: what its answer was computed from), else graph.json."""
        path = self.run_dir(run_id)
        rd = RunDir(path)
        if rd.file(RECORDS_FILE).is_file():
            from evidence.kg.view import view
            from evidence.planlines import load_records
            return self._cached(("graph", path), (rd.file(RECORDS_FILE),),
                                lambda: EvGraph(source="records", **view(load_records(path))))
        graph = rd.try_json(GRAPH_FILE)
        if not isinstance(graph, dict):
            raise NotFound(f"run {run_id!r} has no graph.json")
        return EvGraph.model_validate(graph)

    def run_protocol(self, run_id: str) -> ProtocolView:
        path = self.run_dir(run_id)
        protocol = RunDir(path).file(PROTOCOL_FILE)
        if not protocol.is_file():
            raise NotFound(f"run {run_id!r} has no protocol.yaml (a baseline runs without one)")
        return self.protocol_view(protocol, "run", run_id)

    def _cache_file(self) -> Path | None:
        root = self.s.ev_cache_dir
        return root / CACHE_FILE if root and (root / CACHE_FILE).is_file() else None

    @staticmethod
    def _unrecorded(run: dict[str, Any], call: CallSummary) -> str | None:
        """Why the record cache cannot hold this call, or None. A re-execution runs the bypassed extractors fresh
        and never stores them (evidence/calls.py), so the cache entry under the call's key is the ORIGINAL run's
        record, not this call's."""
        if run.get("mode") == "reexec" and call.source == "fresh":
            return "no record of this call: re-executed fresh, and a re-execution stores nothing in the cache"
        return None

    def _record(self, run: dict[str, Any], call: CallSummary, result: ExtractionResult,
                path: Path | None = None) -> dict[str, Any] | None:
        """The call's model-call record: the run's own copy (calls.jsonl) first, the shared cache second."""
        if self._unrecorded(run, call):
            return None
        key = cache_key(result.extractor_id, result.task_sha256, call.attempt)
        own = self.trace.call_row(path, key) if path is not None else None
        if own is not None:
            return own
        cache = self._cache_file()
        if cache is None:
            return None
        hit = self.cache.get(cache, key)
        if not isinstance(hit, dict) or hit.get("task_sha256") not in (None, result.task_sha256) \
                or hit.get("extractor_id") not in (None, result.extractor_id):
            return None
        return hit

    def _call(self, run_id: str, call_id: str) -> tuple[Path, dict[str, Any], CallSummary, ExtractionResult]:
        path = self.run_dir(run_id)
        call_id = check_id(call_id, "call")
        summary = self.run_summary(path)
        if summary is None or summary.kind != "engine":
            raise NotFound(f"run {run_id!r} is a baseline: it has no extractor calls")
        run = RunDir(path).try_json(RUN_FILE)
        run = run if isinstance(run, dict) else {}
        call = next((c for c in self._calls(path, run) if c.call_id == call_id), None)
        data = read_json(inside(path, CALLS_DIR, f"{call_id}.json"))
        if call is None or not isinstance(data, dict):
            raise NotFound(f"run {run_id!r} has no call {call_id!r}")
        return path, run, call, ExtractionResult.model_validate(data)

    def run_trace(self, run_id: str, after: int = 0) -> TracePage:
        path = self.run_dir(run_id)
        summary = self.run_summary(path)
        if summary is None or summary.kind != "engine":
            raise NotFound(f"run {run_id!r} is a baseline: it has no run trace")
        return self.trace.page(path, max(0, after))

    def _keyed_call(self, run_id: str, key: str) -> CallDetail | None:
        """A call named by its calls.jsonl key (a warm-pass row, which has no call id yet), from the run's own copy."""
        path = self.run_dir(run_id)
        row = self.trace.call_row(path, key)
        if row is None:
            return None
        run = RunDir(path).try_json(RUN_FILE)
        spec = ((run if isinstance(run, dict) else {}).get("extractor_specs") or {}).get(row.get("extractor_id"))
        result = ExtractionResult.model_validate(row.get("result") or {})
        model_calls = row.get("model_calls") or []
        call = CallSummary(call_id=key, document=str(row.get("document", "")), evidence_type=str(row.get("evidence_type", "")),
                           extractor_id=str(row.get("extractor_id", "")), kind=(spec or {}).get("kind") if isinstance(spec, dict) else None,
                           status=str(row.get("status", "")), source=row.get("source"), attempt=int(row.get("attempt") or 0),
                           items=len(result.items), rejected=len(result.rejected), model_calls=len(model_calls))
        return self._detail(run_id, call, result, spec, row, model_calls)

    def run_call(self, run_id: str, call_id: str) -> CallDetail:
        try:
            path, run, call, result = self._call(run_id, call_id)
        except NotFound:
            detail = self._keyed_call(run_id, check_id(call_id, "call"))
            if detail is None:
                raise
            return detail
        record = self._record(run, call, result, path)
        spec = (run.get("extractor_specs") or {}).get(result.extractor_id)
        return self._detail(run_id, call, result, spec, record, (record or {}).get("model_calls") or [],
                            self._unrecorded(run, call))

    def _detail(self, run_id: str, call: CallSummary, result: ExtractionResult, spec: Any, record: dict[str, Any] | None,
                records: list[Any], note: str | None = None) -> CallDetail:
        model_calls, agent_runs = [], []
        for m in records:
            agent = m.get("agent_run")
            agent_id = agent.get("run_id") if isinstance(agent, dict) else None
            if agent_id and agent_id not in agent_runs:
                agent_runs.append(agent_id)
            # `messages` (pydantic-ai's exchange, with timestamps) repeats request and response at length: left out
            model_calls.append(ModelCallRecord.model_validate({**{k: v for k, v in m.items() if k not in ("agent_run", "messages")},
                                                               "agent_run": agent_id}))
        if not agent_runs and call.kind == "agent":
            agent_runs = sorted({c.split("/", 1)[0] for c in result.model_calls if "/" in c})
        return CallDetail(run=run_id, call=call, result=result,
                          spec=ExtractorSpec.model_validate({k: v for k, v in spec.items() if k in ExtractorSpec.model_fields})
                          if isinstance(spec, dict) else None,
                          task=(record or {}).get("task"), cached=record is not None, model_calls=model_calls,
                          agent_runs=agent_runs, record_note=note)

    def call_trace(self, run_id: str, call_id: str, agent_run: str) -> AgentTrace:
        """The trace of one agent run behind an agentic call: its own run directory under $EV_AGENT_WORK (the
        attempt whose chain head is the record's), else the record the engine's cache keeps."""
        path, run, call, result = self._call(run_id, call_id)
        agent_run = check_id(agent_run, "agent run")
        if not any(c.split("/", 1)[0] == agent_run for c in result.model_calls):
            raise NotFound(f"call {call_id} of {run_id} made no agent run {agent_run!r}")
        record = self._record(run, call, result, path) or {}
        kept = next((m["agent_run"] for m in record.get("model_calls") or []
                     if isinstance(m.get("agent_run"), dict) and m["agent_run"].get("run_id") == agent_run), None)
        root = self.s.agent_work_dir
        candidates = [d / "runs" / agent_run for d in subdirs(root) if d.name.startswith(f"{agent_run}-")]
        candidates = [c for c in (inside_or_none(root, c) for c in candidates if root) if c and AgentRunDir(c).events.is_file()]
        if kept and kept.get("head"):
            candidates = [c for c in candidates if (read_jsonl(AgentRunDir(c).events) or [{}])[-1].get("hash") == kept["head"]]
        elif self._unrecorded(run, call):
            # a fresh re-executed call: its agent run is one of those made since the re-execution began (the
            # engine writes protocol.yaml first), never the original run's
            began = (path / "protocol.yaml").stat().st_mtime if (path / "protocol.yaml").exists() else 0.0
            candidates = [c for c in candidates if AgentRunDir(c).events.stat().st_mtime >= began]
        if candidates:
            return self._trace_of_dir(max(candidates, key=lambda c: AgentRunDir(c).events.stat().st_mtime), agent_run)
        if kept:
            return trace_of_record(kept)
        raise NotFound(f"no trace of {agent_run}: no run directory under the agent work root and no cache record")

    @staticmethod
    def _trace_of_dir(run_root: Path, run_id: str) -> AgentTrace:
        records = read_jsonl(AgentRunDir(run_root).events)
        claims = [claim_of(r) for r in read_jsonl(run_root / "claims.jsonl")]
        answer = read_json(run_root / "answer.json")
        concept = read_json(run_root / "concept.json")
        outcome = None
        trajectory = read_json(run_root / "trajectory.json")
        if isinstance(trajectory, dict):
            outcome = (trajectory.get("info") or {}).get("outcome") or {"exit_status": (trajectory.get("info") or {}).get("exit_status")}
        return AgentTrace(run_id=run_id, source="run_dir", outcome=outcome, concept=concept if isinstance(concept, dict) else None,
                          answer=answer if isinstance(answer, dict) else None, steps=steps_of(AgentRunDir(run_root), records),
                          claims=claims)

    def _baseline_run_dir(self, path: Path) -> Path | None:
        """The agent baseline's run directory: <out>/agent-runs/<run id>-<random>/runs/<run id>/ (newest)."""
        answer = read_json(path / "answer.json") or {}
        run_id = (answer.get("agent") or {}).get("run_id") if isinstance(answer, dict) else None
        if not run_id or not ID.fullmatch(str(run_id)):
            return None
        found = [d / "runs" / run_id for d in subdirs(path / "agent-runs") if d.name.startswith(f"{run_id}-")]
        found = [f for f in (inside_or_none(path, f) for f in found) if f and AgentRunDir(f).events.is_file()]
        return max(found, key=lambda f: AgentRunDir(f).events.stat().st_mtime) if found else None

    def baseline_trace(self, run_id: str) -> AgentTrace:
        path = self.run_dir(run_id)
        found = self._baseline_run_dir(path)
        if found is None:
            raise NotFound(f"run {run_id!r} has no agent run directory (agent-runs/)")
        return self._trace_of_dir(found, found.name)

    # --- scores --------------------------------------------------------------------------------------

    def _score_dirs(self) -> list[tuple[Path, list[str]]]:
        """Every directory up to two levels under the scores root, with its id parts."""
        out = []
        for group in subdirs(self.s.scores_dir):
            out.append((group, [group.name]))
            out += [(d, [group.name, d.name]) for d in subdirs(group)]
        return out

    def scores(self) -> ScoresIndex:
        index = ScoresIndex()
        for path, names in self._score_dirs():
            ref = ScoreRef(id=RUN_SEP.join(names), group=names[0], name=names[1] if len(names) > 1 else None)
            if (path / "report.json").is_file():
                report = self._cached(("report", path), (path / "report.json",), lambda p=path: read_json(p / "report.json"))
                if isinstance(report, dict):
                    index.reports.append(ref.model_copy(update={
                        "corpus_id": report.get("corpus_id"), "run_id": report.get("run_id"),
                        "levels": list(report.get("levels") or []),
                        "strategy": (report.get("funnel") or {}).get("strategy"),
                        "systems": [s.get("system") for s in report.get("synthesis") or [] if s.get("system")]}))
            if (path / "compare.json").is_file():
                index.compares.append(ref)
            if (path / "shift.json").is_file():
                shift = read_json(path / "shift.json") or {}
                index.shifts.append(ref.model_copy(update={"corpus_id": shift.get("corpus_id"),
                                                           "systems": [s.get("system") for s in shift.get("systems") or []]}))
            if (path / "benchmark.md").is_file():
                index.benchmarks.append(ref.model_copy(update={"systems": [d.name for d in path.iterdir() if d.is_dir()
                                                                           and (d / "benchmark.json").is_file()]}))
        return index

    def score_dir(self, score_id: str, file: str) -> tuple[Path, ScoreRef]:
        root = self._need(self.s.scores_dir, "scores", "SCORES")
        names = parts(score_id, "score", most=2)
        path = inside(root, *names)
        if not (path / file).is_file():
            raise NotFound(f"no {file} in {'/'.join(names)}")
        return path, ScoreRef(id=score_id, group=names[0], name=names[1] if len(names) > 1 else None)

    @staticmethod
    def _markdown(path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return None

    def report(self, score_id: str) -> ReportView:
        path, ref = self.score_dir(score_id, "report.json")
        report = Report.model_validate(read_json(path / "report.json"))
        ref = ref.model_copy(update={"corpus_id": report.corpus_id, "run_id": report.run_id, "levels": report.levels,
                                     "strategy": (report.funnel or {}).get("strategy"),
                                     "systems": [s.system for s in report.synthesis]})
        return ReportView(ref=ref, report=report, markdown=self._markdown(path / "report.md"))

    def compare(self, score_id: str) -> CompareTable:
        path, ref = self.score_dir(score_id, "compare.json")
        data = read_json(path / "compare.json") or {}
        return CompareTable(ref=ref, rows=list(data.get("rows") or []), intervals=list(data.get("intervals") or []),
                            markdown=self._markdown(path / "compare.md"))

    def shift(self, score_id: str) -> ShiftView:
        path, ref = self.score_dir(score_id, "shift.json")
        return ShiftView(ref=ref, shift=read_json(path / "shift.json") or {}, markdown=self._markdown(path / "shift.md"))

    def losses(self) -> LossesView:
        """`evaluate losses` output (plan 3 Task 6): <scores root>/losses/losses.json and losses.md; an empty view
        when there is none yet."""
        root = self.s.scores_dir
        path = root / "losses" if root is not None else None
        if path is None or not (path / "losses.json").is_file():
            return LossesView()
        data = read_json(path / "losses.json")
        try:
            losses = Losses.model_validate(data)
        except ValidationError as e:   # also not JSON (data None): a 422 naming the file, not a 500
            raise Damaged(f"losses/losses.json does not read as `evaluate losses` output: {str(e)[:400]}") from None
        return LossesView(losses=losses, markdown=self._markdown(path / "losses.md"))

    def benchmark(self, score_id: str) -> BenchmarkView:
        path, ref = self.score_dir(score_id, "benchmark.md")
        records = [r for d in sorted(path.iterdir()) if d.is_dir()
                   for r in [read_json(d / "benchmark.json")] if isinstance(r, dict)]
        return BenchmarkView(ref=ref, records=records, markdown=self._markdown(path / "benchmark.md"))


def trace_of_record(record: dict[str, Any]) -> AgentTrace:
    """An agent run as the engine's cache keeps it (evidence/agentic/runner.collect): commands with the output the
    agent saw (capped), model calls, claims, the answer; the replies themselves are in `trajectory` only."""
    steps: dict[int, dict[str, Any]] = {}

    def step(n: Any) -> dict[str, Any]:
        return steps.setdefault(int(n or 0), {"step": int(n or 0), "agent_id": "main", "origin": "research", "claims": []})
    for c in record.get("model_calls") or []:
        usage = c.get("usage") or {}
        step(c.get("step_id"))["model_call"] = ModelCall(task_id=str(c.get("task_id", "")), status=str(c.get("status") or "finished"),
                                                         tokens=usage.get("total_tokens"), prompt_tokens=usage.get("prompt_tokens"),
                                                         completion_tokens=usage.get("completion_tokens"))
    for c in record.get("commands") or []:
        output = str(c.get("output") or "")
        step(c.get("step_id")).update(command=c.get("command"), exit_code=c.get("exit_code"),
                                      output_head=output[:OUTPUT_HEAD], output_bytes=len(output.encode("utf-8")))
    claims = []
    for c in record.get("claims") or []:
        accepted = c.get("status") == "accepted"
        step(c.get("step_id"))["claims"].append(ClaimRef(claim_id=c.get("claim_id"), status="accepted" if accepted else "rejected",
                                                         reason=c.get("reason"), s=c.get("s"), p=c.get("p"), o=c.get("o")))
        anchor = c.get("anchor") or {}
        claims.append(Claim(claim_id=c.get("claim_id"), task_id="", status="accepted" if accepted else "rejected",
                            reason=c.get("reason"), s=c.get("s"), p=c.get("p"), o=c.get("o"), file=c.get("file"),
                            paper_id=Path(str(c.get("file") or "")).stem or None, quote=c.get("quote"),
                            quote_submitted=c.get("quote"), step=int(c.get("step_id") or 0), agent_id="main",
                            origin="research",
                            anchor={"start": anchor["start"], "end": anchor["end"]} if "start" in anchor else None))
    return AgentTrace(run_id=str(record.get("run_id", "")), source="cache", outcome=record.get("outcome"),
                      concept=record.get("concept"), answer=record.get("answer"),
                      steps=[Step(**steps[k]) for k in sorted(steps)], claims=claims)

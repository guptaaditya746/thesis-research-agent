"""The proposal flow by question kind: the frame guesses the kind, the draft starts from that kind's template,
and the person can override the guess (`propose frame --kind`)."""
from __future__ import annotations

import json
from pathlib import Path

import repo_paths

import pytest
import yaml

from evidence import cli
from evidence.propose import critic, draft, frame
from evidence.propose.common import KIND_TEMPLATES
from evidence.protocol import load, parse

from .propose_support import QUESTION, RAG_FRAME, Scripted

KINDS = ("effect", "consistency", "inventory", "best")


def _frame_reply(kind: str) -> dict:
    return {**RAG_FRAME, "kind": kind, "kind_reason": f"the question reads as {kind}"}


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_frame_reply_has_kind(tmp_path: Path) -> None:
    model = Scripted(frame_reply=_frame_reply("inventory"))
    frame.run("Which metrics do RAG papers report?", tmp_path, model=model.model)
    data = _json(tmp_path / "frame.json")
    assert (data["kind"], data["kind_by"]) == ("inventory", "model")
    assert data["kind_reason"] == "the question reads as inventory"


def test_frame_without_kind_is_effect() -> None:
    old = _json(repo_paths.REPO / "tests/EV2/proposal/frame.json")
    assert "kind" not in old and frame.Frame.model_validate(old).kind == "effect"


@pytest.mark.parametrize("kind", KINDS)
def test_draft_uses_kind_template(tmp_path: Path, kind: str) -> None:
    frame.run(QUESTION, tmp_path, model=Scripted(frame_reply=_frame_reply(kind)).model)
    draft.run(tmp_path)
    got = parse((tmp_path / "draft.yaml").read_text(encoding="utf-8"))
    template = load(KIND_TEMPLATES[kind])
    assert got.kind == template.kind == kind
    for block in ("synthesis", "inventory", "best", "consistency"):
        assert (getattr(got, block) is None) == (getattr(template, block) is None), block
    if kind != "effect":
        assert getattr(got, kind) == getattr(template, kind)   # the kind's own block is the template's
    assert got.question == QUESTION and got.screen.question == RAG_FRAME["population"]["screening_question"]
    sources = _json(tmp_path / "draft.sources.json")
    assert sources["template"]["path"] == KIND_TEMPLATES[kind].name


@pytest.mark.parametrize("kind", KINDS)
def test_critic_runs_on_every_kind(tmp_path: Path, kind: str) -> None:
    model = Scripted(frame_reply=_frame_reply(kind))
    frame.run(QUESTION, tmp_path, model=model.model)
    draft.run(tmp_path)
    critic.run(tmp_path, model=model.model)
    checks = {c["id"]: c for c in _json(tmp_path / "critic.json")["checks"]}
    assert checks["parses"]["ok"] and checks["label_complete"]["ok"] and checks["outcomes_complete"]["ok"]


def test_kind_override_redrafts(tmp_path: Path) -> None:
    model = Scripted(frame_reply=_frame_reply("effect"))
    frame.run(QUESTION, tmp_path, model=model.model)
    draft.run(tmp_path)
    assert parse((tmp_path / "draft.yaml").read_text(encoding="utf-8")).kind == "effect"
    frame.run(QUESTION, tmp_path, model=model.model, kind="best", force=True)
    data = _json(tmp_path / "frame.json")
    assert (data["kind"], data["kind_by"]) == ("best", "user")
    draft.run(tmp_path)
    assert parse((tmp_path / "draft.yaml").read_text(encoding="utf-8")).kind == "best"


def test_cli_kind_flag(tmp_path: Path) -> None:
    args = cli._parser().parse_args(["propose", "frame", "--question", "q", "--out", str(tmp_path), "--kind", "best"])
    assert args.kind == "best"
    with pytest.raises(SystemExit):
        cli._parser().parse_args(["propose", "frame", "--question", "q", "--out", str(tmp_path), "--kind", "nope"])


FUNNEL = ("regex_", "abbrev_", "gliner_", "number_", "llm_")   # the agreed order; a type has a subset of the steps


@pytest.mark.parametrize("kind", KINDS)
def test_draft_cascades_follow_the_funnel(tmp_path: Path, kind: str) -> None:
    """Every kind's draft offers the funnel steps its template has, in the order regex -> abbrev -> GLiNER ->
    number -> LLM (the effect template was rag-factuality.yaml, without abbrev, GLiNER and number)."""
    frame.run(QUESTION, tmp_path, model=Scripted(frame_reply=_frame_reply(kind)).model)
    draft.run(tmp_path)
    data = yaml.safe_load((tmp_path / "draft.yaml").read_text(encoding="utf-8"))
    names = {t: [e["name"] for e in spec.get("extractors", [])] for t, spec in data["evidence_types"].items()}
    steps = [n for cascade in names.values() for n in cascade]
    assert any(n.startswith("gliner_") for n in steps), names
    if kind in ("effect", "consistency"):
        assert names["condition"][:3] == ["regex_condition", "abbrev_condition", "gliner_condition"]
        assert names["metric"][:3] == ["regex_metric", "abbrev_metric", "gliner_metric"]
        assert "number_measurement" in names["measurement"]
    for cascade in names.values():
        ranks = [next(i for i, p in enumerate(FUNNEL) if n.startswith(p)) for n in cascade
                 if any(n.startswith(p) for p in FUNNEL)]
        assert ranks == sorted(ranks), cascade

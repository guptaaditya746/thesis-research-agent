"""The reasoner step (`Settings.reason`, spec 6.3, D25, D30): after the names step and before the answer, the pack's
ontology says which names count for a broader one the question asks about and which links point at something of
the wrong kind. The inferences are written into the run (reason.json, an output), so a replay reads them and never
reasons again. A run made before the setting (no `reason` in its settings) replays with it off: no file changes."""
from __future__ import annotations

import inspect
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from evidence import cli, kinds, reasoner
from evidence.extractors import gliner
from evidence.pack import DOMAINS, load_pack
from evidence.replay import replay
from evidence.rundir import REASON_FILE, RUN_FILE

from .conftest import PROTOCOL, answer_of, regex_run_dir, run_json

ONTO = Path(__file__).parent / "fixtures" / "onto" / "ontology.ttl"
# A dataset class beside the fixture's metric classes, so a metric link to "SQuAD" points at a material.
DATASET_CLASS = 'cskg:Material a owl:Class .\n:Squad rdfs:label "SQuAD" ; rdfs:subClassOf cskg:Material .\n'
# The plan's "System R reaches top-1 accuracy of 0.71; ..." loses 0.71 in regex_measurement: the digit of "top-1"
# between the condition and the value blocks the link. The metric named first keeps the same paper and numbers.
NARROWER = "Top-1 accuracy: System R reaches 0.71; the closed-book model 0.52."


@pytest.fixture(autouse=True)
def no_gliner(monkeypatch: pytest.MonkeyPatch) -> None:
    gliner.forget()
    monkeypatch.delenv("GLINER_URL", raising=False)


def onto_domains(tmp_path: Path) -> Path:
    """A domains folder whose rag pack has the fixture ontology (top-1 accuracy under accuracy, SQuAD a material)
    and metric words that keep those names (F1): "top-1 accuracy" -> canonical "top-1 accuracy", "accuracy" ->
    "accuracy"; "System R" is a treatment condition."""
    root = tmp_path / "domains"
    shutil.copytree(DOMAINS / "rag", root / "rag")
    (root / "rag" / "ontology.ttl").write_text(ONTO.read_text(encoding="utf-8") + DATASET_CLASS, encoding="utf-8")
    words = yaml.safe_load((root / "rag" / "words.yaml").read_text(encoding="utf-8"))
    words["metrics"] = [[r"(?i)\btop-1 accuracy\b", "top-1 accuracy", True], [r"(?i)\baccuracy\b", "accuracy", True]]
    words["fraction_metrics"] = ["accuracy", "top-1 accuracy"]
    words["conditions"]["rag"] = [r"\bSystem R\b", *words["conditions"]["rag"]]
    (root / "rag" / "words.yaml").write_text(yaml.safe_dump(words, sort_keys=False), encoding="utf-8")
    return root


def _protocol(tmp_path: Path, name: str, edit: Any) -> Path:
    """rag-factuality with its own metric enum (accuracy, top-1 accuracy, other), no screen, changed by `edit`."""
    data = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    data["id"] = name
    data.pop("screen")
    types = data["evidence_types"]
    types["metric"]["fields"]["properties"]["canonical"]["enum"] = ["accuracy", "top-1 accuracy", "other"]
    types["measurement"]["bounds"][0]["when"]["values"] = ["accuracy", "top-1 accuracy"]
    edit(data)
    path = tmp_path / "protocols" / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def question_metric_protocol(tmp_path: Path, metric: str) -> Path:
    """A protocol whose one question metric is `metric`."""
    def edit(data: dict[str, Any]) -> None:
        data["synthesis"]["metrics"] = [{"canonical": metric, "higher_is_better": True}]
    return _protocol(tmp_path, f"onto-{metric}", edit)


def metric_is_squad_protocol(tmp_path: Path) -> Path:
    """A protocol whose metric words read the dataset name "SQuAD" as a metric (a wrong link the reasoner flags)."""
    squad = [[r"\bSQuAD\b", "other", True]]

    def edit(data: dict[str, Any]) -> None:
        data["synthesis"]["metrics"] = [{"canonical": "accuracy", "higher_is_better": True}]
        for etype in ("metric", "measurement"):
            for ref in data["evidence_types"][etype]["extractors"]:
                if ref["name"] in ("regex_metric", "regex_measurement"):
                    ref["config"] = {"metrics": squad}
    return _protocol(tmp_path, "onto-squad", edit)


def strip_reason(out: Path) -> None:
    """Make run `out` a run made before this step: no reason.json, not in `outputs`, no `reason` setting."""
    (out / REASON_FILE).unlink()
    data = run_json(out)
    del data["outputs"][REASON_FILE]
    del data["settings"]["reason"]
    (out / RUN_FILE).write_text(json.dumps(data), encoding="utf-8")


def test_reason_off_writes_nothing_new(tmp_path, corpus):
    out = regex_run_dir(corpus, tmp_path, PROTOCOL, settings={"reason": "off"})
    assert not (out / "reason.json").exists() and "reason" not in run_json(out)["settings"]


def test_reason_on_writes_inferences_as_an_output(tmp_path, corpus):
    out = regex_run_dir(corpus, tmp_path, PROTOCOL)
    data = json.loads((out / "reason.json").read_text())
    assert set(data) == {"ontology_sha256", "broader", "link_flags"}
    assert data["ontology_sha256"] == reasoner.ontology_sha256(load_pack("rag"))
    assert "reason.json" in run_json(out)["outputs"] and run_json(out)["settings"]["reason"] == "on"


def test_narrower_metric_answers_a_broader_question(tmp_path):
    out = regex_run_dir([NARROWER], tmp_path,
                        question_metric_protocol(tmp_path, "accuracy"), domains=onto_domains(tmp_path))
    assert json.loads((out / "reason.json").read_text())["broader"]["top-1 accuracy"] == ["accuracy"]
    study = answer_of(out)["studies"][0]
    assert study["direction"] == "supports" and study["metric"] == "accuracy"


def test_narrower_metric_does_not_count_with_reason_off(tmp_path):
    out = regex_run_dir([NARROWER], tmp_path,
                        question_metric_protocol(tmp_path, "accuracy"), domains=onto_domains(tmp_path),
                        settings={"reason": "off"})
    assert answer_of(out)["studies"][0]["reason"]["code"] == "no_question_metric"


def test_value_linked_to_a_dataset_name_is_flagged(tmp_path):
    # the plan's "accuracy on SQuAD: 0.71" names no condition, and a value without both links is never reported
    out = regex_run_dir(["System R accuracy on SQuAD: 0.71"], tmp_path, metric_is_squad_protocol(tmp_path),
                        domains=onto_domains(tmp_path))
    flags = json.loads((out / "reason.json").read_text())["link_flags"]
    assert any(f[1] == "metric" and f[3] == "not a metric" for f in flags)
    assert all(f[0].startswith("m-") for f in flags)


def test_a_pack_without_an_ontology_writes_empty_inferences(tmp_path, corpus):
    domains = tmp_path / "domains"
    shutil.copytree(DOMAINS / "rag", domains / "rag")
    head = yaml.safe_load((domains / "rag" / "pack.yaml").read_text(encoding="utf-8"))
    del head["ontology"]
    (domains / "rag" / "pack.yaml").write_text(yaml.safe_dump(head), encoding="utf-8")
    out = regex_run_dir(corpus, tmp_path, PROTOCOL, domains=domains)
    assert json.loads((out / "reason.json").read_text()) == {"ontology_sha256": None, "broader": {}, "link_flags": []}


def test_replay_never_re_reasons(tmp_path, corpus, monkeypatch):
    out = regex_run_dir(corpus, tmp_path, PROTOCOL)
    monkeypatch.setattr(reasoner, "load_ontology", lambda *a, **k: pytest.fail("re-reasoned"))
    new, report = replay(out)
    assert report["ok"]
    assert (new / "reason.json").read_bytes() == (out / "reason.json").read_bytes()


def test_replay_reads_the_recorded_inferences(tmp_path):
    """The kinds get the recorded inferences: a replay whose ontology changed still answers as the run did."""
    domains = onto_domains(tmp_path)
    out = regex_run_dir([NARROWER], tmp_path,
                        question_metric_protocol(tmp_path, "accuracy"), domains=domains)
    (domains / "rag" / "ontology.ttl").write_text(ONTO.read_text(encoding="utf-8").replace(
        "rdfs:subClassOf :Accuracy", "rdfs:subClassOf cskg:Metric"), encoding="utf-8")
    new, report = replay(out)
    assert report["ok"] and answer_of(new)["studies"][0]["direction"] == "supports"


def test_replay_of_a_run_without_reason_keeps_every_hash(tmp_path, corpus):
    out = regex_run_dir(corpus, tmp_path, PROTOCOL)
    strip_reason(out)          # as a run made before this task (F24)
    new, report = replay(out)
    assert report["ok"] and not (new / "reason.json").exists()
    assert "reason" not in run_json(new)["settings"]


def test_every_kind_answer_takes_reason():
    """F31: the engine passes `reason=` to every kind's answer, plan 2's kinds included once merged."""
    for name, module in kinds.MODULES.items():
        param = inspect.signature(module.answer).parameters.get("reason")
        assert param is not None and param.kind is inspect.Parameter.KEYWORD_ONLY and param.default is None, name


def test_cli_reason_default_on():
    assert cli._parser().parse_args(["run", "--protocol", "p", "--corpus", "c"]).reason == "on"

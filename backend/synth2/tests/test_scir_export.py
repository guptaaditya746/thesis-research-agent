import json
from jsonio import canonical
from synth2.cli import main
from synth2.conclude import Answer
from synth2.corpus import Settings, build_base, load_truth
from synth2.family import make_family
from synth2.scir_export import export, task_of


def test_task_has_the_scir_keys_and_our_key(tmp_path):
    build_base(tmp_path / "base", Settings("rag", 11, 20, "opposed", "split", exact=True))
    t = task_of(tmp_path / "base")
    truth = load_truth(tmp_path / "base")
    assert set(t) == {"id", "domain", "problem_nl", "problem_obfuscated", "answer", "metadata"}
    assert t["id"] == truth["corpus_id"] and t["domain"] == "pooling"
    assert t["answer"] == canonical(truth["key"]) and Answer.parse(json.loads(t["answer"]))
    assert len(t["metadata"]["chunks"]["nl"]) == 20 == len(t["metadata"]["chunks"]["obfuscated"])
    assert "Subset A" in t["problem_obfuscated"] and "Subset A" not in t["problem_nl"]
    assert t["problem_nl"].startswith("Does retrieval-augmented generation")
    assert "Candidate conditions: fact_rarity (rare = rare-fact questions, common = common-fact questions); " in t["problem_nl"]
    assert t["problem_nl"].rstrip().endswith('"untested": ["<condition id>.<level id>"]}')


def test_the_text_does_not_leak_the_key(tmp_path):
    build_base(tmp_path / "base", Settings("rag", 11, 20, "opposed", "table", exact=True))
    t = task_of(tmp_path / "base")
    for text in (t["problem_nl"], t["problem_obfuscated"]):
        assert "key_matches_law" not in text and "mirrored" not in text and '"law"' not in text


def test_export_writes_one_task_per_corpus_and_cli_agrees(tmp_path):
    build_base(tmp_path / "g" / "opposed-table" / "s0" / "base", Settings("rag", 0, 20, "opposed", "table", exact=True))
    make_family(tmp_path / "g" / "opposed-table" / "s0" / "base")
    assert export(tmp_path / "g", tmp_path / "tasks.json") == 5
    data = json.loads((tmp_path / "tasks.json").read_text(encoding="utf-8"))
    assert data["metadata"]["tasks"] == 5 and len({t["id"] for t in data["tasks"]}) == len(data["tasks"])
    assert {t["metadata"]["generation_params"]["kind"] for t in data["tasks"]} == {"base", "twin", "twin_neutral", "spun", "duplicate"}
    assert main(["export-scir", "--root", str(tmp_path / "g"), "--out", str(tmp_path / "again.json")]) == 0
    assert (tmp_path / "again.json").read_bytes() == (tmp_path / "tasks.json").read_bytes()

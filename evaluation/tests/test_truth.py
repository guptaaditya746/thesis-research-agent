from evaluation.truth import Run


def test_run_load_survives_torn_events_line(tmp_path):
    good = '{"task_id": "t1", "subtype": "extractor_call"}\n{"task_id": "t2", "subtype": "screen"}\n'
    (tmp_path / "events.jsonl").write_text(good + '{"task_id": "t3", "sub', encoding="utf-8", newline="")
    run = Run.load(tmp_path)
    assert [e["task_id"] for e in run.events] == ["t1"]
    assert [e["task_id"] for e in run.screens] == ["t2"]

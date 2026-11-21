"""Qwen writer path and the v2 prompt set, with fake backends: no GPU, no network.

* `write_paper(model="qwen:orch-model", prompt_version="v2")` end to end through the vendored PaperOrchestra,
  against a fake LiteLLM gateway (a local HTTP server that answers like the fake `claude` of test_paperwriter);
* `evqa paper write ... --model qwen:orch-model --prompt-version v2` reaches write_domain with those settings;
* the S2 research tool: shared throttle, 429 retry, cache keyed by URL without the key, CC BY / CC0 filter, and
  a query that never names the brief's made-up drug;
* the v2 number audit (unsupported_numbers, exemplar_leaks).
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from evqa import cli, paperwriter
from evqa.research import s2, style
from evqa.tests.test_paperwriter import FAKE_CLAUDE, fc


# ---------- fake LiteLLM gateway ----------

@pytest.fixture
def fake_gateway(tmp_path, monkeypatch):
    script = tmp_path / "fake_claude"
    script.write_text(FAKE_CLAUDE.replace("{python}", sys.executable), encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("FAKE_RECORD", str(tmp_path / "record.jsonl"))
    seen = []

    class H(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            system, user = body["messages"][0]["content"], body["messages"][1]["content"]
            schema = body["response_format"]["json_schema"]["schema"]
            seen.append({"model": body["model"], "system": system, "user": user,
                         "thinking": body["chat_template_kwargs"]["enable_thinking"]})
            done = subprocess.run([str(script), "--json-schema", json.dumps(schema), "--system-prompt", system],
                                  input=user, capture_output=True, text=True, check=True)
            out = json.loads(done.stdout)["structured_output"]
            data = json.dumps({"model": "fake-qwen", "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                               "choices": [{"message": {"content": json.dumps(out)}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("LITELLM_BASE_URL", f"http://127.0.0.1:{srv.server_port}/v1")
    monkeypatch.setenv("LITELLM_MASTER_KEY", "test-key")
    yield seen
    srv.shutdown()


def _brief(root: Path, facts: list[dict]) -> Path:
    d = root / "medical" / "papers" / "P-med-01"
    d.mkdir(parents=True)
    (d / "idea_sparse.md").write_text("# Drugzor added to metformin\n\n- Problem: p\n", encoding="utf-8")
    rows = "".join(f"| {f['id']} | change in HbA1c | {f['value']} | pp | "
                   f"{'put in a table' if f['placement'] == 'table' else 'state in a sentence'} |\n" for f in facts)
    (d / "experimental_log.md").write_text(
        "# Log\n\n| Row id | Measure | Value | Unit | Placement |\n|---|---|---|---|---|\n" + rows, encoding="utf-8")
    return d


STYLE_EX = [{"id": "PMC1", "about": "realdrugin", "license": "cc by",
             "sections": {"Methods: participants": "A total of 701 patients were randomised.",
                          "Results: mean difference vs placebo": "HbA1c fell by 0.83% (95% CI 0.71 to 0.95)."}}]


def test_qwen_v2_end_to_end(tmp_path, fake_gateway, monkeypatch):
    facts = [{"id": f"R-med-01-0{i}", "value": v, "unit": "pp", "placement": p}
             for i, (v, p) in enumerate([("-0.46", "table"), ("-0.57", "text")], 1)]
    monkeypatch.setenv("FAKE_FACTS", json.dumps(facts))
    d = _brief(tmp_path, facts)
    monkeypatch.setattr(paperwriter, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(paperwriter, "WORK", tmp_path / "work")

    paper = paperwriter.write_paper(d, model="qwen:orch-model", prompt_version="v2", style_examples=STYLE_EX)

    assert "-0.57 pp" in paper.read_text()
    assert {s["model"] for s in fake_gateway} == {"orch-model"} and not any(s["thinking"] for s in fake_gateway)
    section = [s for s in fake_gateway if "value_checklist" in s["user"] and "style_examples" in s["system"]]
    assert len(section) == 1 and "701 patients" in section[0]["user"]          # v2 prompt + examples sent
    assert any("Related Work: 2 paragraphs" in s["system"] for s in fake_gateway)   # v2 intro/related prompt
    log = [json.loads(x) for x in (d / "writer_log.jsonl").read_text().splitlines()]
    assert next(r for r in log if r["event"] == "prompt_version")["version"] == "v2"
    final = next(r for r in log if r.get("stage") == "final")
    assert final["exemplar_leaks"] == {"numbers": [], "names": []} and final["unsupported_numbers"] == []
    assert log[-1]["prompt_version"] == "v2" and log[-1]["facts_failed"] == []


def test_v2_without_examples_fails_and_v1_prompt_unchanged(tmp_path, fake_gateway, monkeypatch):
    facts = [{"id": "R-med-01-01", "value": "-0.46", "unit": "pp", "placement": "table"}]
    monkeypatch.setenv("FAKE_FACTS", json.dumps(facts))
    d = _brief(tmp_path, facts)
    monkeypatch.setattr(paperwriter, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(paperwriter, "WORK", tmp_path / "work")
    with pytest.raises(paperwriter.PaperWriterError, match="style examples"):
        paperwriter.write_paper(d, model="qwen:orch-model", prompt_version="v2", style_examples=[])
    paperwriter.write_paper(d, model="qwen:orch-model")                       # v1 default
    assert not any("style_examples" in s["user"] for s in fake_gateway)


def test_cli_passes_model_and_prompt_version(monkeypatch):
    got = {}
    monkeypatch.setattr(paperwriter, "write_domain", lambda domain, paper, **kw: got.update(domain=domain, **kw)
                        or [{"paper": "P", "status": "ok"}])
    assert cli.main(["paper", "write", "medical", "--model", "qwen:orch-model", "--prompt-version", "v2"]) == 0
    assert got == {"domain": "medical", "model": "qwen:orch-model", "prompt_version": "v2"}


# ---------- S2 research tool ----------

def _fake_fetch(responses):
    calls = []

    def fetch(url, headers):
        calls.append((time.monotonic(), url, dict(headers)))
        return responses.pop(0)
    return fetch, calls


HIT = {"paperId": "abc", "title": "T", "year": 2020, "abstract": "word " * 130, "externalIds": {"DOI": "10/x"},
       "openAccessPdf": {"url": "https://x/pdf", "license": "CCBY"}, "url": "https://s2/abc"}
NC = {**HIT, "paperId": "nc", "openAccessPdf": {"url": "https://y", "license": "CCBYNC"}}


def test_s2_throttle_retry_cache_and_key_privacy(tmp_path, monkeypatch):
    monkeypatch.setenv("S2_API_KEY", "SECRET-KEY-123")
    body = json.dumps({"data": [NC, HIT]}).encode()
    fetch, calls = _fake_fetch([(429, b"slow down"), (200, body)])
    rows = s2.search("q", 5, fetch=fetch, cache_dir=tmp_path, gap=0.05)
    assert [r["paperId"] for r in rows] == ["abc"]                   # CC BY-NC dropped
    assert len(calls) == 2 and calls[1][0] - calls[0][0] >= 0.05     # retried after 429, throttled
    assert all(c[2]["x-api-key"] == "SECRET-KEY-123" and "SECRET" not in c[1] for c in calls)
    cached = list(tmp_path.glob("*.json"))
    assert len(cached) == 1 and "SECRET" not in cached[0].read_text()
    fetch2, calls2 = _fake_fetch([])
    assert s2.search("q", 5, fetch=fetch2, cache_dir=tmp_path, gap=0.05) == rows and calls2 == []   # cache hit


def test_s2_throttle_is_shared_across_threads(tmp_path):
    stamps = []
    lock = threading.Lock()

    def fetch(url, headers):
        with lock:
            stamps.append(time.monotonic())
        return 200, b'{"data": []}'
    ts = [threading.Thread(target=s2.get, args=("paper/search", {"query": f"q{i}"}),
                           kwargs={"fetch": fetch, "cache_dir": tmp_path, "gap": 0.1}) for i in range(4)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    stamps.sort()
    assert len(stamps) == 4 and min(b - a for a, b in zip(stamps, stamps[1:])) >= 0.095


def test_query_from_brief_never_names_the_drug():
    log = ("* **Design:** randomised controlled trial, parallel groups, Brenoxalin against placebo.\n"
           "* **Patients:** adults with type 2 diabetes on metformin.\n"
           "* **Evaluation Metrics:** change in HbA1c from baseline in percentage points and body weight.\n"
           "| R-med-01-01 | Brenoxalin | placebo | change in HbA1c from baseline | x |\n")
    q = s2.query_from_brief(log)
    assert "brenoxalin" not in q.lower() and "metformin" in q and "HbA1c" in q and "randomised" in q


def test_style_build_uses_stored_excerpts_and_retrieval(tmp_path):
    sdir = tmp_path / "style"
    (sdir / "PMC1").mkdir(parents=True)
    (sdir / "PMC1" / "excerpts.md").write_text("# c\n\n## Methods: participants\n\nP text.\n\n## Other\n\nx\n")
    (sdir / "PMC1" / "source.json").write_text(json.dumps({"drug": "realdrugin", "license": "cc by"}))
    d = _brief(tmp_path, [{"id": "R-med-01-01", "value": "-0.46", "unit": "pp", "placement": "table"}])
    out = style.build(d, "medical", sdir=sdir, search=lambda q, n: [s2._row(HIT)])
    assert out[0]["sections"] == {"Methods: participants": "P text."} and out[0]["about"] == "realdrugin"
    assert out[1]["id"] == "S2:abc" and "Abstract" in out[1]["sections"]


# ---------- v2 number audit ----------

def test_unsupported_numbers_and_exemplar_leaks():
    brief = "Doses 10 mg and 20 mg at week 12 and week 24. Value -0.46 percentage points."
    paper = ("## 3. Methods\n\nA total of 701 adults with type 2 diabetes were randomised in 2024. Table 1 and "
             "Table 2 show -0.46 at week 12; HbA1c fell by 0.83%.\n")
    assert fc.unsupported_numbers(paper, brief) == ["0.83", "701"]
    leaks = fc.exemplar_leaks(paper + " realdrugin", ["701 patients, 0.83% (95% CI 0.71 to 0.95)"], [brief],
                              ["realdrugin"])
    assert leaks == {"numbers": ["0.83", "701"], "names": ["realdrugin"]}

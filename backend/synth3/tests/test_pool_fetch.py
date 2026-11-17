import shutil
from pathlib import Path

import httpx

from synth3.pmc import DELAY_S, EUTILS, TOOL, USER_AGENT, Polite, fetch_pool
from synth3.pool import import_files, load_index
from synth3.tests.conftest import fake_paper

FIX = Path(__file__).parent / "fixtures" / "jats"


def handler(seen):
    trial = (FIX / "trial.xml").read_text(encoding="utf-8").split("?>", 1)[1].replace("PMC1234567", "PMC101")
    review = (FIX / "review.xml").read_text(encoding="utf-8").split("?>", 1)[1].replace("PMC7654321", "PMC102")

    def run(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if "esearch" in str(request.url):
            ids = "".join(f"<Id>{i}</Id>" for i in (101, 102, 103))
            return httpx.Response(200, content=f"<eSearchResult><IdList>{ids}</IdList></eSearchResult>".encode())
        return httpx.Response(200, content=f"<pmc-articleset>{review}{trial}</pmc-articleset>".encode())
    return run


def test_fetch_is_polite_and_sends_no_personal_detail(tmp_path, REAL_PMC):
    seen, waits = [], []
    client = Polite(transport=httpx.MockTransport(handler(seen)), sleep=waits.append, clock=lambda: 0.0)
    out = fetch_pool(REAL_PMC, tmp_path / "pool", client)
    assert all(r.url.params["tool"] == TOOL and "email" not in r.url.params for r in seen)
    assert all(r.headers["user-agent"] == USER_AGENT for r in seen)
    assert waits == [DELAY_S] * (len(seen) - 1)
    assert out["kept"] == 1 and out["unfit"] == {"article type review-article": 1, "not returned": 1}
    assert "Placebo" in (tmp_path / "pool" / "raw" / "PMC101.xml").read_text(encoding="utf-8")


def test_second_fetch_uses_saved_xml_and_keeps_one_row_per_paper(tmp_path, REAL_PMC):
    fetch_pool(REAL_PMC, tmp_path / "pool", Polite(transport=httpx.MockTransport(handler([])),
                                                  sleep=lambda s: None))
    seen = []
    out = fetch_pool(REAL_PMC, tmp_path / "pool", Polite(transport=httpx.MockTransport(handler(seen)),
                                                         sleep=lambda s: None))
    assert out["fetched"] == 0 and out["cached"] == 2 and not any("efetch" in str(r.url) for r in seen)
    assert len(load_index(tmp_path / "pool")) == 3


def test_429_waits_for_retry_after(tmp_path):
    answers = iter([httpx.Response(429, headers={"Retry-After": "2"}), httpx.Response(200, content=b"<x/>")])
    waits = []
    client = Polite(transport=httpx.MockTransport(lambda r: next(answers)), sleep=waits.append, clock=lambda: 0.0)
    assert client.get(EUTILS + "esearch.fcgi", {}) == b"<x/>" and 2.0 in waits


def test_import_reads_markdown_xml_and_pdf(tmp_path, REAL):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.md").write_text(fake_paper(1), encoding="utf-8")
    shutil.copy(FIX / "trial.xml", src / "b.xml")
    (src / "c.pdf").write_bytes(b"%PDF")
    out = import_files(src, tmp_path / "pool", REAL, convert_pdf=lambda data: fake_paper(2))
    assert out["kept"] == 3 and {r["id"] for r in load_index(tmp_path / "pool")} == {"a", "b", "c"}


def test_cli_pool_import_prints_counts_and_bad_folder_returns_2(tmp_path, capsys):
    from synth3.cli import main
    from synth3.tests.conftest import real_good, write_real
    root = write_real(tmp_path / "real", real_good())
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.md").write_text(fake_paper(1), encoding="utf-8")
    base = ["pool-import", "--domain", "demo", "--real-root", str(root), "--pools", str(tmp_path / "pools")]
    assert main([*base, "--from", str(src)]) == 0
    assert "kept 1 of 1" in capsys.readouterr().out
    assert main([*base, "--from", str(tmp_path / "nope")]) == 2

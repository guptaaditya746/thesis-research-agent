"""paperfactory: invented world -> seed + gold -> PaperOrchestra papers -> tagging, checks, QA, style-leak test.

  uv run paperfactory run --config backend/paperfactory/configs/law.json [--steps world,seed,materials,write,eval]
  uv run paperfactory check-world --config ... --world FILE

Every step writes into the run folder (settings "out") and reuses what is already there, so a stopped run can be
started again. Model calls are cached; their costs are in calls.jsonl.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from repo_paths import REPO

from paperfactory import SCORING_VERSION, config, files, materials, packs, repair, seed, world, write
from paperfactory.evaluate import Eval
from paperfactory.llm import Caller

STEPS = ("world", "seed", "materials", "write", "check", "eval")


def run(s: config.Settings, steps: list[str], use_cache: bool = True) -> None:
    f, g = packs.field(s.field), packs.genre(s.genre)
    out = s.out_dir
    out.mkdir(parents=True, exist_ok=True)
    call = Caller(s, use_cache=use_cache)
    wfile = out / "world.json"
    if "world" in steps and not wfile.is_file():
        if s.world_file:
            w = json.loads((REPO / s.world_file).read_text(encoding="utf-8"))
        else:
            w = world.draft(s, f, g, call)
        errs = world.check(w, f, g)
        if errs:
            sys.exit("world failed the checks:\n" + "\n".join(errs[:40]))
        files.write_json(wfile, w)
        print(f"world: {len(w['entities'])} entities, {len(w['papers'])} papers")
    w = json.loads(wfile.read_text(encoding="utf-8"))
    if "seed" in steps:
        graph, gold = seed.make(w, f, s.qa_papers_per_question, s.seed)
        graph.serialize(out / "seed.ttl", format="turtle")
        files.write_json(out / "gold.json", {"scoring_version": SCORING_VERSION} | gold)
        print(f"seed: SHACL ok, {len(gold['facts'])} facts, {len(gold['questions'])} questions")
    if "materials" in steps:
        print("materials:", len(materials.write_all(w, f, g, out)), "papers")
    if "write" in steps:
        res = write.write_all(s, w, f, g)
        print("write:", json.dumps(res))
    if "check" in steps:                 # papers must agree with the world (repair.py)
        template = packs.render_template(f, g, s.pages, out / f"template_{g.name}_{s.pages}p")

        def redo(pid: str) -> str | None:
            r = write.write_one(s, pid, template, attempt=2)
            p = out / "work" / pid / "redo-2" / "paper.md"
            return p.read_text(encoding="utf-8") if r["status"] in ("ok", "exists") and p.is_file() else None
        chk = repair.Checker(s, w, f, call)
        todo = [p for p in w["papers"] if (out / "work" / p / "paper.md").is_file()
                and not (out / "work" / p / "paper.repairs.json").is_file()]
        print("check:", json.dumps(write.pmap_papers(lambda p: chk.repair_paper(p, redo), todo)))
    if "eval" in steps:
        gold = json.loads((out / "gold.json").read_text(encoding="utf-8"))
        rep = Eval(s, w, f, gold, call, g.raw.get("max_mentions_per_fact", 3)).run()
        rep["cost"] = call.cost()
        files.write_json(out / "report.json", rep)
        print(json.dumps({k: rep[k] for k in ("papers_written", "verifier_test", "judge_validation", "qa_summary",
                                               "style_leak", "cost")}, indent=1))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="paperfactory", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--config", required=True)
    r.add_argument("--steps", default=",".join(STEPS))
    r.add_argument("--no-cache", action="store_true", help="never read cached model answers (they are replaced)")
    cc = sub.add_parser("clear-cache", help="delete the cached model answers of one step")
    cc.add_argument("--config", required=True)
    cc.add_argument("--step", required=True, help="step prefix as in calls.jsonl, e.g. 'verify:' or 'qa:LAW-01'")
    c = sub.add_parser("check-world")
    c.add_argument("--config", required=True)
    c.add_argument("--world", required=True)
    a = ap.parse_args(argv)
    s = config.load(a.config)
    if a.cmd == "run":
        steps = [x.strip() for x in a.steps.split(",") if x.strip()]
        unknown = set(steps) - set(STEPS)
        if unknown:
            sys.exit(f"unknown steps {sorted(unknown)}; steps: {STEPS}")
        run(s, steps, use_cache=not a.no_cache)
    elif a.cmd == "clear-cache":
        print(f"removed {Caller(s).clear(a.step)} cached answers for steps starting with {a.step!r}")
    else:
        errs = world.check(json.loads(Path(a.world).read_text()), packs.field(s.field), packs.genre(s.genre))
        print("\n".join(errs) or "ok")
        sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()

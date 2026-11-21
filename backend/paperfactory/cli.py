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
from typing import Any

from repo_paths import REPO

from paperfactory import SCORING_VERSION, config, files, meta, materials, packs, repair, seed, world, write
from paperfactory.evaluate import Eval
from paperfactory.llm import Caller

STEPS = ("world", "seed", "materials", "write", "check", "eval")


# ------------------------------------------------------------------ inputs of each step (#8, meta.py)
def world_inputs(s: config.Settings, f: packs.Field, g: packs.Genre) -> dict[str, Any]:
    d: dict[str, Any] = {"field_pack": f.raw, "genre_pack": g.raw, "papers": s.papers}
    if s.world_file:
        return d | {"world_file": (REPO / s.world_file).read_text(encoding="utf-8")}
    return d | {"seed": s.seed, "world_model": meta.role(s, "world"), "prompts": [world.ENT_SYS, world.PAPER_SYS]}


def write_inputs(s: config.Settings, pid: str, template: Path) -> dict[str, Any]:
    return {"notes": meta.dir_hash(s.out_dir / "papers" / pid), "template": meta.dir_hash(template),
            "pages": s.pages, "writer": meta.role(s, "writer"), "po_prompts": meta.dir_hash(meta.PO_PROMPTS),
            "po_prompt_version": write.PROMPT_VERSION}


def check_inputs(s: config.Settings, w: dict[str, Any], f: packs.Field, chk: repair.Checker, pid: str,
                 template: Path) -> dict[str, Any]:
    """The whole world counts (the check compares each sentence with what the WORLD says), and the writer's inputs
    count too (a failed repair writes the paper again)."""
    return {"world": w, "field_pack": f.raw, "verifier": meta.role(s, "verifier"), "repair": meta.role(s, "repair"),
            "prompts": [chk.system(), chk.REPAIR_SYS], "redo_writer": write_inputs(s, pid, template)}


# the inputs that every paper of one evaluation must share (paper-specific ones, like the notes, are left out)
SHARED = {"inputs": ["template", "pages", "writer", "po_prompts", "po_prompt_version"],
          "check": ["world", "field_pack", "verifier", "repair", "prompts"]}


def run(s: config.Settings, steps: list[str], use_cache: bool = True, allow_mixed: bool = False) -> None:
    f, g = packs.field(s.field), packs.genre(s.genre)
    out = s.out_dir
    out.mkdir(parents=True, exist_ok=True)
    call = Caller(s, use_cache=use_cache)
    wfile = out / "world.json"
    if "world" in steps:
        wi = world_inputs(s, f, g)
        if meta.stale(wfile, wi, allow_mixed, "world"):
            print("world: old world kept as", meta.set_aside(wfile).name)
        if not wfile.is_file():
            if s.world_file:
                w = json.loads((REPO / s.world_file).read_text(encoding="utf-8"))
            else:
                w = world.draft(s, f, g, call)
            errs = world.check(w, f, g)
            if errs:
                sys.exit("world failed the checks:\n" + "\n".join(errs[:40]))
            files.write_json(wfile, w)
            meta.write(wfile, wi)
            print(f"world: {len(w['entities'])} entities, {len(w['papers'])} papers")
    w = json.loads(wfile.read_text(encoding="utf-8"))
    if "seed" in steps:
        graph, gold = seed.make(w, f, s.qa_papers_per_question, s.seed)
        graph.serialize(out / "seed.ttl", format="turtle")
        files.write_json(out / "gold.json", {"scoring_version": SCORING_VERSION} | gold)
        print(f"seed: SHACL ok, {len(gold['facts'])} facts, {len(gold['questions'])} questions")
    if "materials" in steps:
        print("materials:", len(materials.write_all(w, f, g, out)), "papers")
    template = packs.render_template(f, g, s.pages, out / f"template_{g.name}_{s.pages}p")
    paper = lambda pid: out / "work" / pid / "paper.md"  # noqa: E731
    if "write" in steps:
        for pid in w["papers"]:
            if meta.write_stale(paper(pid), write_inputs(s, pid, template), allow_mixed, f"write {pid}"):
                print(f"write {pid}: old paper kept as", meta.set_aside(out / "work" / pid).name)
                for log in (out / "work").glob(f"{pid}.*"):       # its call logs go too (cost report, #13)
                    meta.set_aside(log)
        res = write.write_all(s, w, f, g)
        for r in res:
            if r["status"] == "ok":
                meta.write_done(paper(r["pid"]), write_inputs(s, r["pid"], template))
        print("write:", json.dumps(res))
    if "check" in steps:                 # papers must agree with the world (repair.py)
        def redo(pid: str) -> str | None:
            r = write.write_one(s, pid, template, attempt=2)
            p = out / "work" / pid / "redo-2" / "paper.md"
            return p.read_text(encoding="utf-8") if r["status"] in ("ok", "exists") and p.is_file() else None
        chk = repair.Checker(s, w, f, call)
        todo = []
        for pid in [p for p in w["papers"] if paper(p).is_file()]:
            state, why = meta.check_state(paper(pid), check_inputs(s, w, f, chk, pid, template), allow_mixed,
                                          f"check {pid}")
            if state == "redo":
                work = out / "work" / pid
                meta.set_aside(work / "paper.repairs.json")
                if (work / "paper.raw.md").is_file():       # start again from the paper as written
                    files.write_text(paper(pid), (work / "paper.raw.md").read_text(encoding="utf-8"))
                if "redo_writer" in why and (work / "redo-2").exists():
                    meta.set_aside(work / "redo-2")
            if state in ("todo", "redo"):
                todo.append(pid)

        def check_one(pid: str) -> dict[str, Any]:
            r = chk.repair_paper(pid, redo)
            meta.check_done(paper(pid), check_inputs(s, w, f, chk, pid, template))
            return r
        print("check:", json.dumps(write.pmap_papers(check_one, todo)))
    if "eval" in steps:
        gold = json.loads((out / "gold.json").read_text(encoding="utf-8"))
        from paperfactory.repair import failed
        pids = [p for p in w["papers"] if paper(p).is_file() and not failed(out, p)]
        allowed = meta.same_settings({p: meta.read(paper(p)) for p in pids}, SHARED, allow_mixed, "eval")
        rep = Eval(s, w, f, gold, call, g.raw.get("max_mentions_per_fact", 3)).run()
        rep["cost"] = call.cost()
        rep["mixed_settings_allowed"] = allowed
        files.write_json(out / "report.json", rep)
        meta.write(out / "report.json", {
            "gold": meta.file_hash(out / "gold.json"), "papers": {p: meta.file_hash(paper(p)) for p in pids},
            "roles": {r: meta.role(s, r) for r in ("tagger", "verifier", "judge", "rewriter", "qa", "leak")},
            "evidence": s.evidence, "leak_trials": s.leak_trials, "seed": s.seed,
            "qa_papers_per_question": s.qa_papers_per_question, "scoring_version": SCORING_VERSION,
            "code": {m: meta.file_hash(Path(__file__).with_name(m)) for m in ("evaluate.py", "text.py")}})
        print(json.dumps({k: rep[k] for k in ("papers_written", "verifier_test", "judge_validation", "qa_summary",
                                               "style_leak", "cost")}, indent=1))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="paperfactory", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--config", required=True)
    r.add_argument("--steps", default=",".join(STEPS))
    r.add_argument("--allow-mixed", action="store_true",
                   help="keep outputs made under other or unknown settings (no meta file) instead of stopping")
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
        try:
            run(s, steps, use_cache=not a.no_cache, allow_mixed=a.allow_mixed)
        except meta.MixedSettings as e:
            sys.exit(str(e))
    elif a.cmd == "clear-cache":
        print(f"removed {Caller(s).clear(a.step)} cached answers for steps starting with {a.step!r}")
    else:
        errs = world.check(json.loads(Path(a.world).read_text()), packs.field(s.field), packs.genre(s.genre))
        print("\n".join(errs) or "ok")
        sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()

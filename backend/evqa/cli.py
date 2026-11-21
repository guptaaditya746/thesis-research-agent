"""`evqa` command line.

  evqa seed vocab              download MeSH/ChEBI/QUDT (cache) and freeze the subsets the blueprints use
  evqa seed names  <domain>    LLM proposes made-up names, code checks them -> names.json (skipped if present)
  evqa seed build  <domain>    blueprint + names.json -> seed.ttl (no LLM)
  evqa seed check  <domain>    shapes, name clashes, split overlap -> check.json (exit 1 when it fails)
  evqa seed questions <domain> questions + intent cards (data/dataset) and gold (data/seed), frozen by sha256
  evqa seed bench <domain>     the 100-question benchmark (50 in-corpus, 50 "not reported"); LLM rewords only
                               (--dry-run: no LLM, nothing written; --force: replace the frozen set)
  evqa seed units              freeze backend/evqa/units.json (unit factors for norm.py) from the QUDT download
  evqa paper brief <domain>    seed -> idea_sparse.md + experimental_log.md per paper (data/seed/<domain>/papers/)
  evqa paper write <domain>    PaperOrchestra writes paper.md from each brief (Claude, at most 3 at once;
                               --model qwen:orch-model --prompt-version v2 for the Qwen writer)
  evqa paper check <domain>    L0: is every seed value in its paper, in the planned place? -> data/seed/<domain>/l0/
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from evqa.paths import SEED, domain_dir


def _blueprints() -> list[str]:
    return sorted(p.parent.name for p in SEED.glob("*/blueprint.yaml"))


def seed_vocab(_: argparse.Namespace) -> int:
    from evqa.seed import build, vocab
    vocab.fetch()
    mesh_ids, units = set(), set()
    for domain in _blueprints():
        bp = build.load_blueprint(domain)
        for group in ("items", "contexts", "measures"):
            mesh_ids |= {v["mesh"] for v in bp[group].values() if "mesh" in v}
        units |= {build.unit_iri(m["unit"]) for m in bp["measures"].values() if m["unit"].startswith("unit:")}
        units |= {build.unit_iri(f["unit"]) for f in bp["factors"].values()}
    units.add(build.UNIT.WK)
    print(json.dumps(vocab.freeze(mesh_ids, units), indent=2))
    return 0


def seed_names(a: argparse.Namespace) -> int:
    from evqa import llm
    from evqa.seed import build, names, vocab
    path = domain_dir(a.domain) / "names.json"
    bp = build.load_blueprint(a.domain)
    slots = {k: v["invent"] for k, v in bp["items"].items() if "invent" in v}
    old = json.loads(path.read_text(encoding="utf-8")) if path.is_file() and not a.force else None
    if old is not None:      # keep every picked name; invent only the slots the blueprint added since
        slots = {k: v for k, v in slots.items() if k not in old["slots"]}
        if not slots:
            print(f"{path} has every slot (use --force to make new names)")
            return 0
    keep = [s["name"] for s in old["slots"].values()] if old else []
    for other in bp.get("avoid_names_from", []):   # e.g. the hold-out seed must not reuse the medical seed's names
        keep += [s["name"] for s in json.loads((domain_dir(other) / "names.json").read_text("utf-8"))["slots"].values()]
    result = names.invent(llm.ClaudeCode(a.model), slots, vocab.label_index(), keep=keep)
    if old is not None:
        result = {**old, "slots": {**old["slots"], **result["slots"]}}
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print({k: v["name"] for k, v in result["slots"].items()})
    return 0


def seed_build(a: argparse.Namespace) -> int:
    from evqa.seed import build
    names = json.loads((domain_dir(a.domain) / "names.json").read_text(encoding="utf-8"))
    graph = build.build(build.load_blueprint(a.domain), names)
    print(f"{build.write(a.domain, graph)}: {len(graph)} triples")
    return 0


def seed_check(a: argparse.Namespace) -> int:
    from evqa.seed import check
    r = check.run(a.domain)
    print(f"shapes conform: {r['shapes']['conforms']}  name clashes: {r['name_clashes']['count']}  "
          f"split overlap: {r['split_overlap']['count']}")
    if r["shapes"]["report"]:
        print(r["shapes"]["report"])
    return 0 if r["pass"] else 1


def seed_questions(a: argparse.Namespace) -> int:
    from evqa.seed import questions
    try:
        print(json.dumps(questions.build(a.domain, force=a.force), indent=2, default=str))
    except questions.Frozen as e:
        print(f"refused: {e}")
        return 1
    return 0


def seed_bench(a: argparse.Namespace) -> int:
    from evqa import llm
    from evqa.seed import bench, questions
    gen = ver = None
    if not a.dry_run:   # generator and blind verifier: two separate calls, same cheapest model (Aditya, 21 Nov)
        gen, ver = llm.ClaudeCode(a.model), llm.ClaudeCode(a.model)
    try:
        out = bench.build(a.domain, gen=gen, ver=ver, force=a.force, dry_run=a.dry_run)
    except questions.Frozen as e:
        print(f"refused: {e}")
        return 1
    print(json.dumps(out, indent=2, default=str))
    return 0


def seed_units(_: argparse.Namespace) -> int:
    from evqa.seed import units
    print(units.freeze())
    return 0


def paper_brief(a: argparse.Namespace) -> int:
    from evqa.seed import brief
    for path in brief.write(a.domain):
        print(path)
    return 0


def paper_check(a: argparse.Namespace) -> int:
    from evqa.eval import dataset
    rows = dataset.check_domain(a.domain)
    for r in rows:
        print(json.dumps(r, default=str))
    return 0


def paper_write(a: argparse.Namespace) -> int:
    from evqa import paperwriter
    rows = paperwriter.write_domain(a.domain, a.paper, model=a.model, prompt_version=a.prompt_version)
    for r in rows:
        print(json.dumps(r, default=str))
    return 1 if any(r.get("status") == "failed" for r in rows) else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="evqa")
    sub = p.add_subparsers(required=True)
    seed = sub.add_parser("seed").add_subparsers(required=True)
    seed.add_parser("vocab").set_defaults(fn=seed_vocab)
    seed.add_parser("units").set_defaults(fn=seed_units)
    n = seed.add_parser("names")
    n.add_argument("domain")
    n.add_argument("--force", action="store_true")
    n.add_argument("--model", default="claude-haiku-5-5")
    n.set_defaults(fn=seed_names)
    q = seed.add_parser("questions")
    q.add_argument("domain")
    q.add_argument("--force", action="store_true")
    q.set_defaults(fn=seed_questions)
    b = seed.add_parser("bench")
    b.add_argument("domain")
    b.add_argument("--force", action="store_true")
    b.add_argument("--dry-run", action="store_true")
    b.add_argument("--model", default="claude-haiku-5-5")
    b.set_defaults(fn=seed_bench)
    rb = seed.add_parser("rebuild", help="rebuild a domain's seed, questions and gold from its blueprint (code only)")
    rb.add_argument("domain")
    rb.add_argument("rest", nargs=argparse.REMAINDER)
    rb.set_defaults(fn=seed_rebuild)
    for name, fn in (("build", seed_build), ("check", seed_check)):
        s = seed.add_parser(name)
        s.add_argument("domain")
        s.set_defaults(fn=fn)
    paper = sub.add_parser("paper").add_subparsers(required=True)
    w = paper.add_parser("write")
    w.add_argument("domain")
    w.add_argument("--paper")
    w.add_argument("--model", default="claude-haiku-5-5", help="claude-* or qwen:<alias> (e.g. qwen:orch-model)")
    w.add_argument("--prompt-version", default="v1", choices=["v1", "v2", "v2r"],
                   help="writer prompts: v1 = frozen benchmark set; v2 = style examples + plain writing; "
                        "v2r = v2 + Qwen research tool (Semantic Scholar search, citations)")
    w.set_defaults(fn=paper_write)
    for name, fn in (("brief", paper_brief), ("check", paper_check)):
        s = paper.add_parser(name)
        s.add_argument("domain")
        s.set_defaults(fn=fn)
    r = sub.add_parser("run", help="run the QA pipeline on a config (resumable), then score it")
    r.add_argument("--config", type=Path, required=True)
    r.add_argument("--no-eval", action="store_true", help="skip scoring the run folder")
    r.set_defaults(fn=pipeline_run)
    e = sub.add_parser("eval", help="score a run folder (writes eval.json)")
    e.add_argument("run_dir", type=Path)
    e.add_argument("--domain", default="medical")
    e.add_argument("--judge", action="store_true", help="also run the blind LLM label judge (eval/judge.py)")
    e.set_defaults(fn=eval_run)
    x = sub.add_parser("explain", help="why one question of a practice run is right or wrong, in plain words")
    x.add_argument("run_dir", type=Path)
    x.add_argument("qid")
    x.add_argument("--json", action="store_true")
    x.set_defaults(fn=explain_run)
    c = sub.add_parser("compare", help="side-by-side Markdown of run folders (per-question part: practice only)")
    c.add_argument("run_dirs", type=Path, nargs="+")
    c.add_argument("--out", type=Path, default=None, help="default runs/evqa/compare-<YYYY-MM-DD>.md")
    c.set_defaults(fn=compare_runs)
    a = p.parse_args(argv)
    return a.fn(a)


def pipeline_run(a: argparse.Namespace) -> int:
    from evqa import run as evqa_run          # lazy: loads dspy
    code = evqa_run.cli_run(a)
    if not a.no_eval:
        from evqa.contracts import RunConfig
        cfg = RunConfig.load(a.config)
        eval_run(argparse.Namespace(run_dir=evqa_run.ROOT / cfg.run_id(), domain=cfg.domain))
    return code


def seed_rebuild(a: argparse.Namespace) -> int:
    from evqa.seed import rebuild
    return rebuild.main([a.domain, *a.rest])


def explain_run(a: argparse.Namespace) -> int:
    from evqa import explain
    return explain.main([str(a.run_dir), a.qid, *(["--json"] if a.json else [])])


def compare_runs(a: argparse.Namespace) -> int:
    from evqa.compare import run_cli
    return run_cli(a)


def eval_run(a: argparse.Namespace) -> int:
    from evqa.eval.prism import score_run      # lazy: builds the seed graph
    out = score_run(a.run_dir, domain=a.domain)
    print(json.dumps(out["totals"], indent=2))
    if getattr(a, "judge", False):
        from evqa.eval.judge import judge_run
        got = judge_run(a.run_dir)
        print(json.dumps({k: v for k, v in got.items() if k != "details"}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

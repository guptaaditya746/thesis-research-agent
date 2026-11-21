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
                               (refused when data/seed/<domain>/FROZEN exists or a paper.md is in git; --force)
  evqa paper check <domain>    L0: is every seed value in its paper, in the planned place? -> data/seed/<domain>/l0/
  evqa doctor                  preflight before a long run: gateway, claude, Slurm time, disk, git (exit 1 on FAIL)
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


def _tracked(paths: list[Path]) -> list[Path]:
    """The paths among `paths` that git tracks."""
    import subprocess
    from repo_paths import REPO
    if not paths:
        return []
    out = subprocess.run(["git", "ls-files", "--", *map(str, paths)], capture_output=True, text=True, cwd=REPO)
    return [REPO / x for x in out.stdout.splitlines() if x.strip()]


def frozen_reason(domain: str, paper: str | None) -> str | None:
    """Why `paper write` must not overwrite this domain's papers, or None."""
    from evqa.paths import paper_file
    if (domain_dir(domain) / "FROZEN").is_file():
        return f"{domain_dir(domain) / 'FROZEN'} exists"
    root = domain_dir(domain) / "papers"
    names = [paper] if paper else (sorted(d.name for d in root.iterdir() if d.is_dir()) if root.is_dir() else [])
    kept = _tracked([f for f in (paper_file(domain, n) for n in names) if f.is_file()])
    return f"{len(kept)} paper.md file(s) are tracked by git, e.g. {kept[0]}" if kept else None


def paper_write(a: argparse.Namespace) -> int:
    from evqa import paperwriter
    why = None if a.force else frozen_reason(a.domain, a.paper)
    if why:
        print(f"refusing to overwrite frozen papers of {a.domain}: {why}. Use --force to write anyway.",
              file=sys.stderr)
        return 1
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
    w.add_argument("--force", action="store_true", help="overwrite frozen / git-tracked paper.md files")
    w.set_defaults(fn=paper_write)
    for name, fn in (("brief", paper_brief), ("check", paper_check)):
        s = paper.add_parser(name)
        s.add_argument("domain")
        s.set_defaults(fn=fn)
    r = sub.add_parser("run", help="run the QA pipeline on a config (resumable), then score it")
    r.add_argument("--config", type=Path, required=True)
    r.add_argument("--no-eval", action="store_true", help="skip scoring the run folder")
    r.add_argument("--text", action="store_true", help="also score the answer text (L3-text, LLM; see eval --text)")
    r.add_argument("--text-model", default=None, help="L3-text reader, backend:model (default qwen:orch-model)")
    r.add_argument("--judge-model", default=None, help="L3-text patient-group judge (default qwen:sub-model-1)")
    r.set_defaults(fn=pipeline_run)
    e = sub.add_parser("eval", help="score a run folder (writes eval.json)")
    e.add_argument("run_dir", type=Path)
    e.add_argument("--domain", default=None, help="default: domain in <run_dir>/config.yaml (must agree)")
    e.add_argument("--judge", action="store_true", help="also run the blind LLM label judge (eval/judge.py)")
    e.add_argument("--judge-population", action="store_true",
                   help="settle unverified patient groups with the blind LLM judge -> population_judge.json")
    e.add_argument("--text", action="store_true",
                   help="also score the answer text, the same way for evqa and baseline runs (L3-text, "
                        "eval/text_answer.py; LLM reader + blind judge, cached)")
    e.add_argument("--text-model", default=None, help="L3-text reader, backend:model (default qwen:orch-model)")
    e.add_argument("--judge-model", default=None, help="L3-text patient-group judge (default qwen:sub-model-1)")
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
    d = sub.add_parser("doctor", help="preflight checks before a long run (exit 1 on any FAIL)")
    d.add_argument("--config", type=Path, default=None, help="run config; its steps decide which backends to check")
    d.add_argument("--backend", choices=["qwen", "claude", "openrouter"], default=None,
                   help="check this backend instead of the config's (no config, no backend: qwen)")
    d.add_argument("--claude", action="store_true", help="also check the Claude CLI")
    d.add_argument("--min-hours", type=float, default=2.0, help="warn when the Slurm job has less time left")
    d.set_defaults(fn=doctor_run)
    a = p.parse_args(argv)
    return a.fn(a)


def pipeline_run(a: argparse.Namespace) -> int:
    from evqa import run as evqa_run          # lazy: loads dspy
    code = evqa_run.cli_run(a)
    if not a.no_eval:
        from evqa.contracts import RunConfig
        cfg = RunConfig.load(a.config)
        eval_run(argparse.Namespace(run_dir=evqa_run.ROOT / cfg.run_id(), domain=cfg.domain, text=a.text,
                                    text_model=a.text_model, judge_model=a.judge_model))
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


def doctor_run(a: argparse.Namespace) -> int:
    from evqa import doctor
    return doctor.main(a)


def run_domain(run_dir: Path, domain: str | None) -> str:
    """The run's domain from <run_dir>/config.yaml; an explicit `domain` must agree with it."""
    from evqa.contracts import RunConfig
    cfg_path = Path(run_dir) / "config.yaml"
    if not cfg_path.is_file():
        if domain is None:
            raise SystemExit(f"{cfg_path} is missing: pass --domain")
        return domain
    got = RunConfig.load(cfg_path).domain
    if domain is not None and domain != got:
        raise SystemExit(f"--domain {domain} disagrees with {cfg_path} (domain: {got}); drop --domain")
    return got


def eval_run(a: argparse.Namespace) -> int:
    from evqa.eval.prism import score_run      # lazy: builds the seed graph
    out = score_run(a.run_dir, domain=run_domain(a.run_dir, a.domain))
    print(json.dumps(out["totals"], indent=2))
    if getattr(a, "judge", False):
        from evqa.eval.judge import judge_run
        got = judge_run(a.run_dir)
        print(json.dumps({k: v for k, v in got.items() if k != "details"}, indent=2))
    if getattr(a, "judge_population", False):
        from evqa.eval.judge import judge_population
        got = judge_population(a.run_dir)
        print(json.dumps({k: v for k, v in got.items() if k != "details"}, indent=2))
    if getattr(a, "text", False):
        from evqa.eval import text_answer
        reader = step_llm(a.text_model) if getattr(a, "text_model", None) else text_answer.READER
        judge = step_llm(a.judge_model) if getattr(a, "judge_model", None) else text_answer.JUDGE
        got = text_answer.score_run(a.run_dir, reader=reader, judge_llm=judge)
        print(json.dumps({k: v for k, v in got["totals"].items() if k != "per_type"}, indent=2))
    return 0


def step_llm(spec: str):
    """'qwen:orch-model' -> StepLLM(backend='qwen', model='orch-model')."""
    from evqa.contracts import StepLLM
    backend, _, model = spec.partition(":")
    if not model:
        raise SystemExit(f"model {spec!r}: write backend:model, e.g. qwen:orch-model")
    return StepLLM(backend=backend, model=model)


if __name__ == "__main__":
    sys.exit(main())

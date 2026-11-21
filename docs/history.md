# History

One line per phase. Old docs (plans, specs, handoffs, runbooks, deck) live in git at tag `pre-restructure` (bb4accbd, 5 Nov) unless another ref is named.

| Phase | When | What | Old docs at |
|---|---|---|---|
| Earlier work | to 14 Oct | research agent (sandboxed loop, claim broker, graph, PROV-O, replay), gold D, claim on/off scoring, 12 questions; old web app removed 18 Oct | `backend/agent/tests/earlier-work.md` (kept: a test reads its question table); `docs/STATE.md` at `pre-restructure`; old app at `72da5dd` |
| EV1 | 14-21 Oct | Tim's design: protocol, extractor library, engine, synth benchmark, A/B/C scores, RAG + agent baselines; first Slurm run + diagnosis | tag `ev1`; `docs/ev1-review-diagnosis.md`, `docs/research/` |
| EV2 | 15-22 Oct | flags, benchmark knobs, variants, intervals; funnel engine; proposal flow; arch deepening (`modelcall.ask`, RunDir) | tag `ev2`, `ev2b-2026-10-22`; `docs/slurm-evidence-runbook.md`, `docs/evidence-system.md`, `docs/claude-ev2-handoff.md` |
| Question-first | 23-25 Oct | 10 questions / 4 kinds, trace tab, checker, GLiNER funnel, gaps default | tag `qf-v1`; `docs/runbook-question-first.md` |
| EV3 / EV3b | 26 Oct-1 Nov | Claude-written corpora, hard set, GLiNER confirm, per-paper RAG; engine 6/10 wins | tags `ev3`, `ev3-code`, `ev3b-code`, `archive/ev3-*`; `docs/runbook-ev3b.md`, `docs/presentation/` |
| EV4 | 1-2 Nov | general system plans 1-3: domain packs, drug trials, reasoner, sealed runs, real-paper checks | tags `ev4-code`, `ev4-pack-rag-v1`; `docs/runbook-ev4.md`, `docs/superpowers/` |
| General system | 3-4 Nov | LLM word list, ontology per field, planner + plan page, DSPy tuning, whole-run commands; 4 Nov fixes | `pre-restructure`; `docs/runbook-general-system.md`, `docs/handoff-claude-*.md` |
| Restructure | 5 Nov | backend/ frontend/ data/ docs/; services as modules | branch `restructure` |

Also at `pre-restructure`: `synth/README.md` (generator guide: knobs, variants, LLM renderer), `GLOSSARY.md` (now a table in `architecture.md`), `design-system/`, `thesis_pipeline.html`, `evaluation_dashboard.html`.

Code comments naming a deleted doc (`docs/evidence-system.md`, `docs/STATE.md`, `docs/earlier-work.md`, runbooks) mean that file at `pre-restructure`. Not rewritten: many sit in hashed files (`backend/README.md`, hashed files).

| evqa | 21 Nov | old system removed: `evidence`, `agent`, `gold`, `evaluation`, `scoring`, `synth` (synth2/3), `packbuilder`, the `/api/ev` app and its UI, `data/{domains,questions,concepts,corpus}`, old scripts and runbook; only evqa + Workbench remain | git before 21 Nov; `runs/backup/old-code-2026-11-21.tar.gz` |

# data/

Checked-in inputs. Bytes are hashed: always LF (`.gitattributes`); edit only by the pack/question process, never by hand during a run.

| Path | What | Read by |
|---|---|---|
| `domains/<pack>/` | domain pack: `pack.yaml`, `words.yaml`, `provenance.json` (hashed as `Pack.sha256`), `protocols/`, `questions.yaml`, `ontology.ttl`, `generator.yaml` (synth recipe), `propose.yaml` | `evidence.pack`, planner, synth, webapp |
| `domains/default.yaml` | names the default pack (frozen: protocols without `domain:` hash without it) | `evidence.protocol` |
| `domains/allowlist.yaml` | generic words code may use (`test_no_topic_words`) | tests |
| `domains/heldout.yaml` | papers held out of generator drafting (lists still owed) | `synth draft` |
| `questions/questions.json` | 12 questions of the earlier work | `agent concepts`, `gold` |
| `concepts/<qid>/` | frozen concept sessions (hash-chained) | `agent batch` manifests |
| `corpus/manifest.json` | frozen earlier-work corpus manifest (sha256 in every agent run config) | `agent`, e2e scripts |

Locations in code: `backend/repo_paths` (`DOMAINS`, `QUESTIONS_FILE`, `CONCEPTS`, `CORPUS_MANIFEST`).

Not here: `tests/` at repo root (EV corpora `tests/EV*/corpora`, results, M1/D1 records; ~7,000 files). Left in place because recorded reports and run records name `tests/EV2/...` paths and rescore/replay read them; moving would need rewriting `reports/`, which is not allowed.

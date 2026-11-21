# data/

Inputs of evqa (`backend/evqa/paths.py`).

| Path | What |
|---|---|
| `seed/` | the truth: `schema/`, frozen `vocab/` subsets, one folder per domain (blueprint, `seed.ttl`, briefs, gold); the QA pipeline never opens it |
| `dataset/<domain>/<paper>/paper.md` | written papers: the only files the QA system may read |
| `cache/` | big downloads and call caches (MeSH, ChEBI, QUDT, PaperOrchestra); not committed |

The old inputs (`domains/`, `questions/`, `concepts/`, `corpus/`) were removed on 21 Nov 2026; backup in
`runs/backup/old-code-2026-11-21.tar.gz`, history in git.

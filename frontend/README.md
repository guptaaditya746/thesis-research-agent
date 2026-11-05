# frontend/

Web UI: Vite + React + TanStack Query, shadcn components. Served by `webapp serve` from `dist/` (committed, so Slurm needs no npm).

| Command (in `frontend/`) | Does |
|---|---|
| `uv run --group frontend npm ci` | install; Node comes from the `frontend` uv group |
| `npm run dev` | Vite; proxies `/api` to `webapp serve` (127.0.0.1:8080, `WEBAPP_API` overrides) |
| `npm run dev:mock` | no backend; MSW answers `/api` from `src/mocks` |
| `npm test` | Vitest (jsdom, same MSW handlers) |
| `npm run build` | `tsc -b` + `dist/`; commit `dist/` |
| `npm run gen:api` | `src/api/schema.d.ts` from `openapi.json` |

After a backend model change (from repo root):

```bash
uv run webapp openapi -o frontend/openapi.json && (cd frontend && npm run gen:api)
uv run python -m webapp.tests.evidence_world <tmp> --mocks frontend/src/mocks/ev-fixtures.json   # refresh mock data
```

- Mock write contract: `src/mocks/write-contract.json`, checked by `backend/webapp/tests/test_write_contract.py` and `src/mocks/contract.test.ts`.
- `dist/` path for the server: `WEBAPP_DIST` (default `<repo>/frontend/dist`).

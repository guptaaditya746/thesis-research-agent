# frontend/

The Workbench: Vite + React + TanStack Query, shadcn components. Served by `webapp serve` from `dist/` (committed,
so Slurm needs no npm). The app opens on `/workbench`; it reads `/api/evqa/*`.

| Command (in `frontend/`) | Does |
|---|---|
| `uv run --group frontend npm ci` | install; Node comes from the `frontend` uv group |
| `npm run dev` | Vite; proxies `/api` to `webapp serve` (127.0.0.1:8080, `WEBAPP_API` overrides) |
| `npm test` | Vitest (jsdom; each test sets its `/api` answers with MSW) |
| `npm run build` | `tsc -b` + `dist/`; commit `dist/` |

- `dist/` path for the server: `WEBAPP_DIST` (default `<repo>/frontend/dist`).

# AEGIS frontend

Vite + React + TypeScript dashboard (Phase 22). Exposes real backend data across
14 screens — no mock data in the shipped app. See `../CONTRIBUTING.md` for setup.

```
npm install
cp .env.example .env
npm run dev
```

Point the dashboard at a running backend from **System Settings** (API base URL +
optional API key, stored in `localStorage`), or via `VITE_API_BASE_URL`.

## Scripts

| script | what |
|---|---|
| `npm run dev` | Vite dev server |
| `npm run build` | `tsc -b && vite build` |
| `npm run lint` | eslint (flat config) |
| `npm run typecheck` / `typecheck:test` | app project / test project |
| `npm run test` / `test:watch` | Vitest + RTL + MSW |
| `npm run gen:api` | regenerate `src/types/api-generated.ts` from `openapi/openapi.snapshot.json` |
| `npm run e2e` | Playwright smoke (manual — needs a live backend, not in CI) |

## Layout

- `src/services/` — `apiClient` (typed fetch + auth header injection), `queryClient`,
  `queryKeys`, `errorMessages`, `settingsStore`, `graphAdapter`
- `src/hooks/api/` — TanStack Query hooks, one module per endpoint group
- `src/types/api.ts` — curated aliases over the generated `api-generated.ts`
- `src/types/pipeline.ts` — mirrors `orchestrator.STAGE_ORDER` / `_STATE_RANK`
- `src/components/` — `primitives/`, `feedback/`, `layout/`, `state/`, `shared/`
- `src/features/` — `task-pipeline/` (stage-status derivation + panels),
  `diff/` (`react-diff-view` viewer), `graph/` (Cytoscape), `verification/` (HITL)
- `src/pages/` — the 14 screens + `TaskLayout`
- `src/test/` — MSW handlers, fixtures, `renderWithProviders`
- `e2e/` — Playwright smoke spec (manual)

## Regenerating the API types

Run a backend, then:

```
curl -s http://localhost:8000/openapi.json > openapi/openapi.snapshot.json
npm run gen:api
```

There is no CI gate asserting the snapshot matches a live `/openapi.json` — refresh
it by hand when the backend API changes.

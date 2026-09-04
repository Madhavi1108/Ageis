# AEGIS frontend

Vite + React + TypeScript scaffold (Phase 2). See `../CONTRIBUTING.md` for setup.

```
npm install
cp .env.example .env
npm run dev
```

- `src/router.tsx` -- route table (react-router-dom)
- `src/services/apiClient.ts` -- typed fetch wrapper against the backend's error envelope
- `src/services/queryClient.ts` -- TanStack Query client
- `src/pages/HealthPage.tsx` -- calls `GET /healthz` and `GET /version` through the client

`src/features/`, `src/components/`, `src/hooks/` are placeholders for later phases.

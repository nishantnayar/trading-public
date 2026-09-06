# Quantis dashboard (Next.js)

Five-screen quant terminal that talks to the FastAPI backend.

| Screen | Data |
|---|---|
| Overview `/` | Live — coverage, universe, sector mix, price chart |
| Signals `/signals` | Mockup until Phase 4 (model scores) |
| Positions `/positions` | Mockup until Phase 6 |
| Model `/model` | Mockup until Phase 4 |
| Monitoring `/monitoring` | Live — bar coverage; ingest-run audit is empty until flows write `ingest_runs` |

## Run

From the repo root, start API + UI + Prefect together:

```powershell
./scripts/start.ps1
```

Or this app alone (API must already be on `:8000`):

```bash
cp .env.example .env.local   # NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
npm install
npm run dev                  # http://localhost:3000
```

API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

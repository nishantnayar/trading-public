<div align="center">

# 📈 Quantis

### Cross-Sectional Equity ML Trading System

*Daily S&P 500 ranking: Alpaca bars → point-in-time features → LightGBM → FastAPI / Next.js.*

[![CI](https://github.com/nishantnayar/trading-public/actions/workflows/ci.yml/badge.svg)](https://github.com/nishantnayar/trading-public/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![uv](https://img.shields.io/badge/env-uv-DE5FE9)](https://github.com/astral-sh/uv)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![LightGBM](https://img.shields.io/badge/model-LightGBM-2E7D32)](https://lightgbm.readthedocs.io/)
[![Prefect](https://img.shields.io/badge/orchestration-Prefect-070E10?logo=prefect&logoColor=white)](https://www.prefect.io/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/dashboard-Next.js-000000?logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

</div>

---

## Overview

**Quantis** trains a LightGBM model to rank the S&P 500 on **forward cross-sectional
excess return** (per-date z-scored 5-day returns). Data, features, and the model live in
a local PostgreSQL database; a FastAPI backend and Next.js terminal surface coverage,
prices, and pipeline status.

> **Disclaimer** — Educational / portfolio project. **Paper trading only**, no real orders.
> Nothing here is investment advice.

---

## What is built

| Layer | What you can run today |
|---|---|
| **Prices** | ~757k Alpaca daily bars, 502 symbols, upserted into Postgres |
| **Features** | 11 point-in-time price features (~755k rows, leakage-tested) + 4 optional value/quality features from EDGAR fundamentals |
| **Model** | LightGBM + purged walk-forward CV, MLflow tracking, SHAP |
| **Backtest** | Dollar-neutral quintile L/S, cost sweep, Phase 6 construction levers |
| **Paper broker** | Simulated ledger (default) + Alpaca paper adapter; no live orders |
| **Ingest / schedules** | Prefect server + cron runner on `scripts/start.py` (weekday ingest, Sat research, Mon rebalance) |
| **API / UI** | FastAPI `:8000` + Next.js `:3000` — Overview, Signals, Positions, Model, Monitoring |

**Result so far — a real signal that costs eat.** Out-of-fold rank IC **0.018**; the
long/short book returns **5.3% CAGR at Sharpe 0.78 gross**, but **1.7% at Sharpe 0.28**
once 10 bps per side is charged, and turns negative by 20 bps. Break-even is **15.7 bps
per side**, and the constraint is **34x annualised turnover**, not the signal. A
no-trade buffer plus a 10-session hold cuts that to **13.4x** and lifts break-even to
**25.4 bps**; sector-neutralising the 5.3% IT tilt **destroys** the edge. Full
accounting: [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md#backtest-phase-5).

Fundamentals now come from **SEC EDGAR** (free, no API key): 503 symbols, 2006→2026,
real filing dates as the point-in-time anchor. Value/quality features are optional —
LightGBM handles the sparser coverage (78% of panel rows) natively rather than
requiring them complete like the price features. Whether they improve the model is
still an open question (one run isn't enough to tell) — see
[`docs/LIMITATIONS.md`](docs/LIMITATIONS.md#fundamentals-coverage--resolved-via-sec-edgar).
Positions in the UI are **target weights**; paper qty/cash is `GET /broker` after a
simulated rebalance.

Verified counts, tests, and design intent: [`docs/PROGRESS.md`](docs/PROGRESS.md),
[`docs/PLAN.md`](docs/PLAN.md).

---

## Architecture (current)

```mermaid
flowchart LR
    A[Alpaca<br/>daily bars] --> B[(PostgreSQL<br/>quantis)]
    F[SEC EDGAR<br/>fundamentals] --> B
    B --> C[Feature store<br/>11 price + 4 value/quality]
    C --> D[LightGBM<br/>purged walk-forward]
    D --> BT[Backtest<br/>quintile L/S · cost sweep]
    D -.-> M[MLflow]
    BT --> PB[Paper broker<br/>simulated / Alpaca paper]
    P[Prefect ingest] -.-> A
    Svc[Prefect schedules] -.-> P
    B --> API[FastAPI]
    API --> S[Next.js<br/>5 screens]
    PB -.-> API
```

---

## Stack

| Layer | Tools |
|---|---|
| **Language / env** | Python 3.11, [uv](https://github.com/astral-sh/uv) (no Docker) |
| **Data & storage** | Alpaca Market Data, SEC EDGAR (fundamentals), PostgreSQL, SQLAlchemy 2.0 |
| **Modeling** | scikit-learn, LightGBM, SHAP, MLflow |
| **Orchestration** | Prefect (isolated local profile) |
| **Backend / UI** | FastAPI + Uvicorn, Next.js (React + TypeScript) + Tailwind |
| **Quality** | pytest, black, flake8, ruff, mypy, pre-commit, GitHub Actions |

---

## Quickstart

```bash
# 1. Environment (uv fetches Python 3.11 automatically)
uv python install 3.11
uv sync --group data --group ml --group backtest --group orchestration --group api --group app --group dev

# 2. Configure
cp .env.example .env          # fill PGPASSWORD and Alpaca paper keys

# 3. Create the dedicated database, then validate the environment
uv run python scripts/init_db.py
uv run python scripts/env_check.py    # imports + Postgres ping → "ENV GATE: PASS"

# 4. Ingest daily bars for the S&P 500
uv run python -m quantis.orchestration.flows

# 4b. Fundamentals from SEC EDGAR (full universe by default, ~5 min; one-time)
uv run python scripts/ingest_fundamentals_edgar.py
uv run python scripts/migrate_add_fundamental_features.py   # one-time: adds 4 columns to `features`

# 4c. Point-in-time features: 11 price (writes `features`) + 4 value/quality from fundamentals
uv run python -m quantis.features.build
uv run python -m quantis.features.fundamental_build

# 4d. Train LightGBM (purged walk-forward; writes models/artifacts/)
uv run python -m quantis.models.train

# 4e. Backtest the out-of-fold predictions, net of costs
uv run python -m quantis.backtest.run
uv run python -m quantis.backtest.compare   # Phase 6 levers at 10 bps
uv run python -m quantis.backtest.publish   # scores + weights into Postgres for the UI

# 4f. Paper rebalance (simulated ledger; never live)
uv run python -m quantis.execution.broker

# 5. Local stack: FastAPI :8000, Next.js :3000, Prefect :4201 + cron deployments
uv run python scripts/start.py
```

One terminal, interleaved `[api]` / `[ui]` / `[prefect]` / `[schedules]` logs, Ctrl+C
stops everything. Use `--only api ui` or `--skip prefect` for a subset. `--skip schedules`
keeps the Prefect UI without registering cron. Postgres should already be running as a
system service.

Optional RL extra (not used by the current pipeline): `uv sync --group rl`.
Frontend deps: `cd frontend && npm install` (first time only; the launcher warns if
`node_modules` is missing).

---

## Quality checks

Lint and type checks run **before each commit** (pre-commit) and again on **GitHub Actions**
for every push and pull request.

```bash
uv sync --group dev                 # black, flake8, ruff, mypy, pre-commit
uv run pre-commit install           # once per clone — blocks bad commits
uv run pre-commit run --all-files   # same suite locally
```

| Check | What it covers |
|---|---|
| **black** | Python formatting (100-char lines) |
| **flake8** | pycodestyle + pyflakes |
| **ruff** | flake8-equivalent rules plus isort, pyupgrade, bugbear |
| **mypy** | static types on `src/`, `tests/`, `scripts/` |
| **ESLint** | Next.js / TypeScript in `frontend/` |
| **pytest** | unit suite (CI; DB ping skips without `PGPASSWORD`) |

CI also runs `npm run lint` in `frontend/`. The RL extra (`torch`) is not installed in CI.

---

## Dashboard

```bash
uv run python scripts/start.py
# API      http://127.0.0.1:8000/docs
# UI       http://localhost:3000
# Prefect  http://127.0.0.1:4201   (deployments register with the stack)
```

| Screen | Source |
|---|---|
| Overview `/` | Live — coverage, universe, sector mix, price chart |
| Monitoring `/monitoring` | Live — bar coverage, ingest-run audit |
| Signals `/signals` | Live — published OOF scores |
| Positions `/positions` | Live — target weights (`buffer=1`, 10-session hold) |
| Model `/model` | Live — IC, SHAP, cost-aware book metrics |

Paper fills: `GET /broker` (simulated ledger). See [`frontend/README.md`](frontend/README.md).

---

## Project structure

```
src/quantis/
├── config.py          # pydantic settings from .env
├── db/                # SQLAlchemy models + engine/session
├── data/              # universe, Alpaca/yfinance sources, upsert store
├── features/          # point-in-time feature store
├── models/            # labels, purged CV, LightGBM training, registry
├── backtest/          # weight construction, cost-aware P&L engine
├── execution/         # simulated ledger + Alpaca paper (no live path)
├── orchestration/     # Prefect ingest + cron runner (with start.py)
└── api/               # FastAPI backend
frontend/              # Next.js dashboard
scripts/               # start.py, env_check, init_db, ingest_fundamentals_edgar
tests/                 # env, features, leakage, labels, CV, backtest, API
docs/                  # PLAN · PROGRESS · LIMITATIONS
```

---

## Docs

How to run this repo is above. Everything else is under [`docs/`](docs/README.md):

- [`docs/PLAN.md`](docs/PLAN.md) — design and remaining phases
- [`docs/PROGRESS.md`](docs/PROGRESS.md) — what is verified (counts, tests, metrics)
- [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) — data and model caveats

---

## License

MIT — see [`LICENSE`](LICENSE).

<div align="center">

# 📈 Quantis

### US Equity Data Platform + Rule-Based Trend Signal

*Alpaca daily bars → PostgreSQL → SMA-crossover / momentum trend rule → FastAPI / Next.js.*

[![CI](https://github.com/nishantnayar/trading-public/actions/workflows/ci.yml/badge.svg)](https://github.com/nishantnayar/trading-public/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![uv](https://img.shields.io/badge/env-uv-DE5FE9)](https://github.com/astral-sh/uv)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Prefect](https://img.shields.io/badge/orchestration-Prefect-070E10?logo=prefect&logoColor=white)](https://www.prefect.io/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/dashboard-Next.js-000000?logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

</div>

---

## Overview

**Quantis** ingests daily equity bars and quarterly fundamentals into a local PostgreSQL
database, and evaluates a fully mechanical, backtestable trend-following rule (SMA
crossover confirmed by 12-1 momentum, debounced exit) over the full active universe. A
FastAPI backend and Next.js terminal surface data coverage, the current signal per
symbol, and pipeline status.

> **Disclaimer** — Educational / portfolio project. **Paper trading only**, no real orders.
> Nothing here is investment advice.

This repo previously carried a full LightGBM cross-sectional ranking pipeline
(features → model → backtest → paper execution). That layer was removed to rebuild the
signal side from a simpler, fully-rule-based baseline first — see
[`docs/PROGRESS.md`](docs/PROGRESS.md) for what that pipeline covered and why it was cut.

---

## What is built

| Layer | What you can run today |
|---|---|
| **Prices** | ~758k Alpaca daily bars, 503 symbols, upserted into Postgres |
| **Fundamentals** | Quarterly reports from SEC EDGAR, point-in-time `as_of` dates, 503 symbols back to 2006 |
| **Signal** | Rule-based trend-follower (`quantis.signals`) over the full ~503-name active universe — SMA(50/200) crossover, 12-1 momentum filter, 3-day debounced exit |
| **Backtest** | Per-symbol backtest with a flat-bps cost model + sector/regime breakdowns + a 3-variant debounce comparison |
| **Portfolio** | Equal-weight book, 15% GICS sector cap with water-filling reallocation, rebalanced daily (`quantis.signals.portfolio`) |
| **Execution** | Simulated paper broker (`quantis.execution.simulated`) — no live path anywhere in this repo |
| **Ingest / schedules** | Prefect server + cron runner on `scripts/start.py` (bar ingest → signal recompute → portfolio backtest recompute → paper rebalance, weekdays) |
| **API / UI** | FastAPI `:8000` + Next.js `:3000` — Overview, Signals, Positions, Broker, Monitoring |

The **Model** screen (a holdover from the deleted ML pipeline) has been removed from
the UI — there is currently no model in this system to show diagnostics for.

Per-symbol, net of a 10 bps/side cost model, the rule has no edge across the full
active universe — median net return is negative for every debounce variant tested
(-4.7% for the current default, `exit_only`, vs -19.0%/-6.1% for the other two). Digging
into *why* (`uv run python -m quantis.signals --sectors` / `--regime`) found it
concentrated: Energy and Information Technology carry the result, defensive sectors
(Health Care, Real Estate, Consumer Staples) drag it down, and the rule loses money in
every year except 2022. That pointed at portfolio construction rather than further
per-symbol tuning.

**The default portfolio construction** (`uv run python -m quantis.signals --portfolio`)
is an equal-weight book of every currently-long name, capped at 15% per GICS sector
with the freed weight from any over-cap sector reallocated to under-cap ones
("water-filling") rather than left uninvested. Over the full ingested history
(2017-11-15 → today): **70.2% total return / 7.7% CAGR at Sharpe 0.65**, max drawdown
**-18.9%**, ~25x annualized turnover — diversification recovers real value the
per-symbol view was hiding, and capping the sector concentration found above cuts the
uncapped book's -37% drawdown by half. These defaults were chosen by comparing cap
levels and reallocation on/off (`--no-cap`, `--no-reallocate`) against the live
universe — see [`docs/PROGRESS.md`](docs/PROGRESS.md) Phases 15-17 for the full
comparison. Volatility targeting (`--vol-target`, Phase 20) and a per-name cap
(`--name-cap`, Phase 21) both exist but are **off by default — both made every
metric tested slightly worse, never better**; kept available rather than hidden,
but not something to turn on by default. See
[`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) for why, and the other honest
caveats (no shorting).

That construction now actually trades — `quantis.execution.simulated` rebalances
an in-database paper ledger toward it daily, filled at each symbol's latest close.
`uv run python -c "from quantis.execution.simulated import rebalance; rebalance()"`
or `GET /broker` / the Broker screen to see it. A held symbol with no valid price
is excluded from equity and left untouched rather than silently valued at $0 or
force-sold — flagged via `unpriced_symbols` end to end (result, API, UI). Every
rebalance appends an equity snapshot, charted as a NAV history on the Broker
screen. No live or real-money path exists anywhere in this repo.

---

## Architecture (current)

```mermaid
flowchart LR
    A[Alpaca<br/>daily bars] --> B[(PostgreSQL<br/>quantis)]
    F[SEC EDGAR<br/>fundamentals] --> B
    B --> SIG[Trend rule<br/>SMA crossover + 12-1 momentum]
    SIG --> B
    B --> PF[Portfolio construction<br/>equal-weight + sector cap]
    PF --> B
    B --> EX[Simulated broker<br/>quantis.execution]
    EX --> B
    P[Prefect ingest] -.-> A
    Sc[Prefect schedules] -.-> P
    Sc -.-> SIG
    Sc -.-> PF
    Sc -.-> EX
    B --> API[FastAPI]
    API --> S[Next.js<br/>terminal]
```

---

## Stack

| Layer | Tools |
|---|---|
| **Language / env** | Python 3.11, [uv](https://github.com/astral-sh/uv) (no Docker) |
| **Data & storage** | Alpaca Market Data, SEC EDGAR (fundamentals), PostgreSQL, SQLAlchemy 2.0 |
| **Signal** | Pure pandas (`quantis.signals`) — no ML dependency today |
| **Orchestration** | Prefect (isolated local profile) |
| **Backend / UI** | FastAPI + Uvicorn, Next.js (React + TypeScript) + Tailwind |
| **Quality** | pytest, black, flake8, ruff, mypy, pre-commit, GitHub Actions |

---

## Quickstart

```bash
# 1. Environment (uv fetches Python 3.11 automatically)
uv python install 3.11
uv sync --group data --group orchestration --group api --group app --group dev

# 2. Configure
cp .env.example .env          # fill PGPASSWORD and Alpaca paper keys

# 3. Create the dedicated database, then validate the environment
uv run python scripts/init_db.py
uv run python scripts/env_check.py    # imports + Postgres ping → "ENV GATE: PASS"

# 4. Ingest daily bars for the S&P 500
uv run python -m quantis.orchestration.flows

# 4b. Fundamentals from SEC EDGAR (full universe by default, ~5 min; one-time)
uv run python scripts/ingest_fundamentals_edgar.py

# 4c. Compute and persist the trend signal over the full active universe
uv run python -m quantis.signals --persist

# Optional: backtest the rule, or compare debounce variants
uv run python -m quantis.signals --backtest
uv run python -m quantis.signals --compare

# 4d. Backtest / persist the portfolio construction, then paper-rebalance toward it
uv run python -m quantis.signals --portfolio
uv run python -c "from quantis.signals.portfolio import persist_portfolio_summary; persist_portfolio_summary()"
uv run python -c "from quantis.execution.simulated import rebalance; rebalance()"

# 5. Local stack: FastAPI :8000, Next.js :3000, Prefect :4201 + cron deployments
uv run python scripts/start.py
```

One terminal, interleaved `[api]` / `[ui]` / `[prefect]` / `[schedules]` logs, Ctrl+C
stops everything. Use `--only api ui` or `--skip prefect` for a subset. `--skip schedules`
keeps the Prefect UI without registering cron. Postgres should already be running as a
system service.

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

CI also runs `npm run lint` in `frontend/`.

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
| Signals `/signals` | Live — current trend rule signal per universe symbol |
| Positions `/positions` | Live — illustrative equal-weight book + the real backtested portfolio construction's performance (CAGR, Sharpe, drawdown, exposure, turnover) |
| Broker `/broker` | Live — simulated paper ledger: equity, cash, positions, recent fills |

See [`frontend/README.md`](frontend/README.md).

---

## Project structure

```
src/quantis/
├── config.py          # pydantic settings from .env
├── db/                # SQLAlchemy models + engine/session
├── data/              # universe, Alpaca/EDGAR sources, upsert store
├── signals/           # rule-based trend signal, portfolio construction, backtest
├── execution/         # simulated paper broker (no live path)
├── orchestration/      # Prefect ingest/signal/portfolio/rebalance flows (with start.py)
└── api/               # FastAPI backend
frontend/              # Next.js dashboard
scripts/               # start.py, env_check, init_db, ingest_fundamentals_edgar
tests/                 # env, signals, orchestration, API
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

# Cross-Sectional Equity ML Trading System — Design Plan

## Context

Nishant wants a **full end-to-end, AI/ML-driven trading system** to showcase quant + ML
engineering depth to recruiters. Constraints from the discussion:

- **No intraday** — daily/weekly rebalancing (swing/position horizon).
- **Heavy AI/ML** — the alpha signal is a supervised learning model, not hand-tuned rules.
- **Strategy**: cross-sectional US large-cap equity ranking (long top decile /
  short-or-cash bottom decile).
- **Scope**: full system — data ingestion → feature store → model training →
  backtesting → portfolio/risk construction → paper execution → dashboard.
- **Stack**: Python + LightGBM/XGBoost, **PostgreSQL** as the store, **Prefect** for
  scheduling, and a **Next.js (React) + FastAPI** dashboard (chosen over Streamlit).

The intended outcome is a portfolio-grade repo: clean architecture, reproducible
research, honest backtesting (no look-ahead / survivorship bias), and an MLOps story
(model registry, monitoring, scheduled retrain) — the things recruiters actually probe.

## The Strategy (one-paragraph pitch for the README)

Each week, for every stock in the S&P 500 universe, the system computes a feature
vector (momentum, value, quality, volatility, technical, and sentiment features) and
feeds it to a gradient-boosted model trained to predict **forward N-day cross-sectional
excess return**. Stocks are ranked by predicted return; the portfolio goes long the top
quintile and short (or flat, configurable) the bottom quintile, sized by a risk model
(inverse-vol / vol-targeting) with sector and position caps. Rebalanced weekly. The
ML problem is framed as **learning-to-rank across the cross-section on each date**,
which is the honest way to state the objective and avoids the classic "predict price"
naivety recruiters look for.

## Architecture

```
data/            raw + curated market data (yfinance/Stooq), fundamentals, calendar
  ingestion/     downloaders, universe (S&P 500 membership w/ point-in-time)
  store (Postgres): prices, fundamentals, features, predictions, trades, equity_curve
features/        feature engineering -> "feature store" table, all point-in-time
models/          training, cross-validation (purged/embargoed), registry (MLflow)
backtest/        event-driven-ish vectorized backtester, costs, slippage
portfolio/       ranking -> weights, risk model, constraints, rebalancer
rl/              (advanced) Gymnasium env + PPO/SAC portfolio agent behind construct()
execution/       simulated broker + optional Alpaca paper-trading adapter
orchestration/   Prefect flows: daily data pull, weekly retrain, weekly rebalance
api/             FastAPI backend: JSON endpoints for the Next.js UI
frontend/        Next.js (React+TS) dashboard: 5 screens (separate npm project)
dashboard/       Streamlit app: data-layer smoke test (temporary)
tests/           pytest: leakage checks, feature correctness, backtest invariants
```

### Key design decisions (the "showcase" points)

1. **Point-in-time correctness** — universe membership and fundamentals stored with
   `as_of` dates; features computed only from data available at prediction time. This is
   the single most important credibility signal.
2. **Purged K-Fold CV with embargo** (López de Prado style) so overlapping forward-return
   labels don't leak across train/test folds.
3. **Learning-to-rank / cross-sectional target** — label = forward return z-scored
   within each date (neutralizes market beta), so the model learns relative strength.
4. **Cost-aware backtest** — commission + spread/slippage + turnover penalty; report
   net-of-cost metrics only.
5. **Risk model + constraints** — vol-targeting, per-name and per-sector caps, so the
   portfolio isn't just "top 10 momentum names."
6. **MLOps loop** — MLflow experiment tracking + model registry; Prefect scheduled
   retrain; drift/decay monitoring (rolling IC, feature drift) surfaced on the dashboard.

## Tech stack

- **Environment**: **uv**-managed venv, no Docker anywhere. See the dedicated
  "Python environment (uv)" section below for the full, dependency-conflict-aware package
  set — decided once, up front.
- **Build location**: `D:\PythonProjects\trading-public`.
- **Data wrangling**: pandas (polars optional for the feature build).
- **Price data**: primary source is a **one-time copy of existing OHLC tables** from the
  user's other projects (e.g. `Trading-System` / `factor-stat-arb`) into THIS project's
  own Postgres via a bootstrap ETL — the system is self-contained, not coupled to those
  DBs. **Alpaca Market Data API** then supplies incremental daily bars going forward
  (same vendor as execution — consistent symbology/timestamps/auth). Both sit behind a
  `PriceSource` interface; `yfinance`/Stooq kept only as a documented fallback.
- **Fundamentals**: separate source (Alpaca does not provide them) — yfinance
  fundamentals or SimFin free tier. S&P 500 membership via a static point-in-time CSV to
  start (documented limitation).
- **Postgres**: installed natively/locally (no Docker); connection via `.env`.
- **ML**: scikit-learn pipeline + **LightGBM** (primary), XGBoost as a comparison;
  optional PyTorch MLP as a "stretch" model. SHAP for feature attribution.
- **Experiment tracking / registry**: MLflow on a local **SQLite** backend (`mlflow.db`),
  upgradeable to Postgres. The file backend (`./mlruns`) is in maintenance mode upstream
  and now raises rather than initialising.
- **Store**: **PostgreSQL** via SQLAlchemy; Alembic for migrations.
- **Backtest**: **vectorbt** (confirmed) — fits the cross-sectional ranked weight-matrix
  shape and runs fast parameter sweeps. **Tearsheets/analytics**: **quantstats** (primary)
  and/or **pyfolio-reloaded** (classic `pyfolio` is unmaintained on modern pandas — use
  the maintained forks).
- **Orchestration**: **Prefect** flows + deployments (daily ingest, weekly retrain/rebalance).
- **Execution**: `SimulatedBroker` (for backtests) and `AlpacaPaperClient` (paper only;
  no real orders) behind one `ExecutionClient` interface. Alpaca is the primary live/paper
  venue, matching the data source.
- **Dashboard**: **Next.js (React + TypeScript)** frontend consuming a **FastAPI**
  backend that exposes quantis data (coverage, universe, bars, signals, positions, model
  diagnostics) as JSON. Full-stack signal; matches the dark quant-terminal mockups
  pixel-for-pixel. (A basic Streamlit app exists as a data-layer smoke test and will be
  retired once the Next.js UI covers the same screens.)
- **Quality**: pytest, ruff, mypy, pre-commit, GitHub Actions CI. (No Docker — README
  documents native Postgres + `uv sync` setup instead.)
- **UI already designed**: dark quant-terminal dashboard, 5 screens (Overview, Signals,
  Positions & Risk, Model Diagnostics, Monitoring) — mocked and approved in Claude Design;
  the Next.js build matches those layouts.
- **Node toolchain**: Node 22 / npm 10 (present). Frontend deps via npm in `frontend/`;
  Python API deps via uv (`api` group). Ports: API 8000, frontend 3000 (distinct from
  Prefect 4201).

## Reinforcement learning module (advanced / stretch)

RL is included as a **portfolio-construction agent layered on top of the supervised
signal**, not as a replacement for it — this is the defensible use of RL in a
daily-horizon equity system and reads well to recruiters.

- **Framing**: a custom **Gymnasium** environment wraps the backtest. **State** = the
  LightGBM cross-sectional scores + current portfolio weights + risk/exposure features
  (vol, sector tilts, drawdown). **Action** = target portfolio weights (or a
  scale/tilt on the rank-based weights). **Reward** = next-period net-of-cost return
  penalized for turnover and vol-target breaches. **Agent** = PPO (or SAC) via
  **Stable-Baselines3**.
- **Why this shape**: predicting returns directly with RL on ~daily data is
  sample-starved and overfits; sizing/allocation from an already-informative signal is a
  well-posed sequential decision problem where RL can add value (cost-aware turnover,
  regime-adaptive sizing).
- **Honest evaluation**: train on the same purged/embargoed splits, evaluate
  out-of-sample against the rule-based construction baseline (vol-targeting + caps).
  Report whether RL actually beats the baseline net of costs — a negative result,
  clearly analyzed, is itself a strong signal of judgment.
- **Isolation**: lives behind the SAME `portfolio.construct` interface as the rule-based
  constructor, selectable by config, so it never destabilizes the core system. Depends on
  `torch`, so it ships in its own optional uv group.

## Python environment (uv)

**The env is decided once here to avoid dependency hell.** The one real constraint in
this stack: `vectorbt` depends on `numba`, and `numba` lags the newest Python and pins
`numpy`. So we standardize on **Python 3.11** and **numpy < 2.1**, which every library
below supports. uv resolves and locks exact versions (`uv lock`); the ranges below are
the compatibility intent.

**Setup:**
```
uv init  →  uv add <core deps>  →  uv add --group <name> <group deps>  →  uv sync
```
Run everything via `uv run <cmd>` (never a manually activated venv). Heavy/conflict-prone
libs go in **dependency groups** so a resolver issue in one area never blocks the rest.

**Core (`[project.dependencies]`)** — data + storage + config, no version friction:
- `python = "~=3.11.0"`
- `pandas>=2.1,<3`, `numpy>=1.26,<2.1`, `pyarrow`
- `sqlalchemy>=2.0`, `psycopg[binary]>=3.1`, `alembic`
- `pydantic>=2`, `pydantic-settings`, `python-dotenv`, `httpx`, `tenacity`, `loguru`

**`data` group** — market data sources:
- `alpaca-py` (bars + paper trading), `yfinance` (fundamentals + fallback), `pandas-datareader`

**`ml` group** — modeling + tracking:
- `scikit-learn>=1.4`, `lightgbm>=4.3`, `xgboost>=2.0`, `shap>=0.45`, `mlflow>=2.14`
- (PyTorch left out of the default lock as a "stretch" — add `torch` only if the MLP
  model is built, since it is a large, platform-specific wheel.)

**`backtest` group** — the numba-constrained corner, isolated on purpose:
- `vectorbt>=0.26` (pulls compatible `numba`/`llvmlite`), `quantstats>=0.0.62`,
  `pyfolio-reloaded` (optional; skip if it fights the pandas pin — quantstats covers
  tearsheets)

**`rl` group** (optional, advanced) — reinforcement-learning portfolio agent:
- `gymnasium>=0.29`, `stable-baselines3>=2.3`, `torch` (large platform-specific wheel —
  installed only when the RL module is worked on)

**`orchestration` group**: `prefect>=2.19`
**`api` group** (backend for the Next.js UI): `fastapi`, `uvicorn[standard]`
**`app` group** (Streamlit smoke test, temporary): `streamlit>=1.36`, `plotly`, `altair`
**Frontend** (not uv — npm in `frontend/`): Next.js, React, TypeScript, Tailwind CSS,
a charting lib (Recharts or lightweight-charts), TanStack Query
**`dev` group**: `pytest`, `pytest-cov`, `ruff`, `mypy`, `pre-commit`, `ipykernel`

**Fallback if numba/vectorbt ever blocks the resolve**: keep `vectorbt` in its own group
so `uv sync` (without `--group backtest`) still yields a working data+ML+app env, and the
backtest layer can drop to a pandas/numpy vectorized loop with quantstats for the tearsheet
— no numba dependency. This keeps the project installable no matter what.

## Build phases (implementation order)

0. **Repo setup (do first, on approval)** — create `D:\PythonProjects\trading-public`,
   `git init`, `.gitignore` (`.venv/`, `.env`, `__pycache__/`, `mlruns/`, data dumps),
   copy the approved design mockups into `design/`, write the initial `README.md` and
   `pyproject.toml`, and make the first commit.
1. **Scaffold + ENV GATE** — `uv init` + `uv add` the dependency set, package layout
   under `src/`, settings/config. **Then STOP and validate the environment before any
   further step** (explicit user gate):
   - `uv sync` resolves and locks with no conflicts.
   - `uv run python scripts/env_check.py` imports every key package and prints versions:
     pandas, numpy, sqlalchemy, psycopg, lightgbm, xgboost, shap, mlflow, **vectorbt**
     (+ numba/llvmlite — the risky corner), quantstats, prefect, streamlit, alpaca,
     and (if RL group installed) gymnasium/stable_baselines3/torch.
   - `env_check.py` also opens a Postgres connection from `.env` and runs `SELECT 1`.
   - `uv run pytest tests/test_env.py` — a tiny test asserting the imports + DB ping.
   - Report versions + pass/fail to the user and get the go-ahead before Phase 2.
   SQLAlchemy models + Alembic migrations land here too once the env is green.
2. **Data layer** — start fresh from Alpaca (the `factor_stat_arb` OHLC is hourly, a
   different granularity, so it is NOT reused): (a) Alpaca **daily** bars downloader
   (full history backfill + incremental); (b) fundamentals downloader (yfinance/SimFin);
   (c) universe loader; Postgres upserts + a Prefect `ingest` flow. Tests for schema +
   idempotent upsert.
   **Status:** (a) and (c) done. (b) partially done — `fundamentals` table + yfinance
   loader exist but only a **5-symbol pilot** is ingested. yfinance yields just ~5 usable
   quarters per ticker, so value/quality features are blocked on a better source
   (SimFin / EDGAR / Sharadar) and the full 502-name backfill is deferred. Phase 3
   therefore builds **price-only** features. See `docs/LIMITATIONS.md`.
3. **Feature store** — momentum/value/quality/vol/technical features, all point-in-time;
   `features` table; leakage unit tests.
   **Status:** DONE, price-only. 11 features (momentum 1m/3m/6m/12-1, `ret_5d`, vol
   20d/60d, RSI-14, distance from 52w high, 50/200 MA ratio, log dollar volume) built
   for 502 symbols / 754,809 rows. 18 tests cover hand-computed values plus four leakage
   guards (future-truncation invariance, last-bar shock isolation, cross-symbol
   independence, and an AST check rejecting `shift(-n)` / `center=True`). Value and
   quality are deferred — see the Phase 2 status note.
   **Status:** price-only features are implemented (`definitions.py`, `build.py`,
   `tests/test_features.py`, `tests/test_leakage.py`). Value/quality is deferred until
   fundamentals have real history — see `docs/LIMITATIONS.md`. Run with
   `uv run python -m quantis.features.build`.
4. **Labels + model** — ✅ **done.** Per-date z-scored 5-day forward-return labels
   (`models/labels.py`), purged walk-forward CV with embargo (`models/cv.py`), rank-IC
   metrics (`models/metrics.py`), LightGBM L2 regression + SHAP + MLflow
   (`models/train.py`). Objective is regression on the z-score rather than `lambdarank`:
   the z-score already strips the market move, so no query groups are needed. Complete
   feature vectors are **required, not imputed**. Result: rank IC 0.0178 gross over 5
   folds — see `docs/PROGRESS.md` and `docs/LIMITATIONS.md`. Run with
   `uv run python -m quantis.models.train`.
5. **Backtester** — vectorbt weight-matrix backtest with costs/slippage/turnover;
   tearsheet (CAGR, Sharpe, Sortino, max DD, hit rate, turnover, IC) via quantstats.
6. **Portfolio & risk** — ranking → weights, vol-targeting, sector/name caps, rebalancer
   behind a `portfolio.construct` interface (the seam the RL agent later plugs into).
7. **Execution** — SimulatedBroker + Alpaca paper adapter behind one interface.
8. **Orchestration** — Prefect deployments: daily ingest, weekly retrain, weekly rebalance.
9. **Dashboard** — (a) **FastAPI** backend (`src/quantis/api/`) exposing coverage,
   universe, bars, signals, positions, model diagnostics as JSON; (b) **Next.js** frontend
   (`frontend/`) with the 5 screens matching the mockups, consuming the API. Retire the
   Streamlit smoke test once parity is reached.
   **Status:** scaffold is live. `scripts/start.ps1` launches API `:8000`, UI `:3000`,
   and Prefect `:4201`. Overview and Monitoring read Postgres; Signals / Positions /
   Model are labeled mockups until Phases 4–7. Streamlit remains at
   `scripts/dashboard.ps1` (`:8502`) as a temporary smoke test.
10. **RL agent (advanced / stretch)** — Gymnasium env wrapping the backtest, PPO/SAC via
    Stable-Baselines3, plugged into `portfolio.construct`; benchmark vs the rule-based
    baseline out-of-sample.
11. **Polish** — CI, README with architecture diagram, results tearsheet,
    "known limitations & next steps" section.
    **Sphinx docs site (do last):** `docs/` today is working markdown. At the end,
    stand up Sphinx with autodoc/Napoleon (and MyST so existing `.md` pages are
    included) so the project ships a real API reference from docstrings — the
    engineering-practice signal, not just a recruiter README. Gate this on Phases
    4–7 existing; generating docs over empty packages is worse than waiting.

## Critical files to create (representative)

- `pyproject.toml`, `uv.lock`, `.env.example`, `.pre-commit-config.yaml`
- `src/config.py` (pydantic settings), `src/db/models.py`, `alembic/`
- `src/data/universe.py`, `src/data/prices.py` (`PriceSource` iface: `AlpacaPrices`,
  fallback `YFinancePrices`), `src/data/fundamentals.py`
- `src/features/build.py`, `src/features/definitions.py`
- `src/models/labels.py`, `src/models/cv.py`, `src/models/train.py`
- `src/backtest/engine.py`, `src/backtest/costs.py`, `src/backtest/metrics.py`
- `src/portfolio/construct.py`, `src/portfolio/risk.py`
- `src/rl/env.py`, `src/rl/train.py`, `src/rl/agent.py` (advanced module)
- `src/execution/base.py`, `src/execution/simulated.py`, `src/execution/alpaca.py`
- `src/orchestration/flows.py`
- `src/quantis/api/main.py` (FastAPI app), `src/quantis/api/routes/*.py`
- `frontend/` (Next.js app: `app/`, `components/`, `lib/api.ts`, Tailwind config)
- `dashboard/app.py` (Streamlit smoke test — temporary)
- `scripts/env_check.py`, `tests/test_env.py` (the environment gate)
- `tests/test_leakage.py`, `tests/test_backtest.py`, `tests/test_features.py`
- `docs/conf.py` + Sphinx autodoc (Phase 11 — not before the core packages exist)

## Verification

- `uv sync` installs deps; local Postgres reachable via `.env`; `prefect` flows run
  end-to-end on a small date range and populate all tables (bootstrap ETL first).
- `pytest` green — especially leakage and backtest-invariant tests.
- A **reproducible backtest** produces a saved tearsheet (HTML/PNG) checked into
  `results/` so recruiters see performance without running anything.
- `uv run uvicorn quantis.api.main:app` serves the JSON API; `npm run dev` in `frontend/`
  serves the Next.js UI showing equity curve, signals, positions, and model diagnostics
  against the populated Postgres DB. (Streamlit smoke test: `uv run streamlit run
  dashboard/app.py` on :8502.)
- README documents assumptions, limitations (survivorship bias in the starter universe,
  free-data quality), and next steps — demonstrating honest quant judgment.
- **Sphinx** (`uv run sphinx-build`) produces HTML under `docs/_build/` from package
  docstrings + the markdown in `docs/` (Phase 11 only).

## Open items to confirm at implementation time

- **Alpaca API keys**: needs a free Alpaca paper account (API key + secret in `.env`,
  never committed) for incremental data + paper execution. Confirm you have/will create one.
- **Source OHLC tables**: identify which other project(s) hold the OHLC data and their
  table schema (inspect at implementation time) so the bootstrap ETL can map columns.
- Rebalance cadence: weekly (default) vs monthly.

## Confirmed decisions

- Strategy: cross-sectional S&P 500 ML ranking, **long/short** (long Q5, short Q1).
- Backtest: **vectorbt**; analytics: quantstats / pyfolio-reloaded.
- Env: **uv**, native Postgres, **no Docker**. Build in `D:\PythonProjects\trading-public`.
- Data: one-time **copy** of existing OHLC into this project's DB; Alpaca for
  incremental bars + paper execution.
- UI: dark quant-terminal, 5 screens — mocked in Claude Design. **Stack: Next.js (React
  + TS) frontend + FastAPI backend** (chosen over Streamlit for full-stack signal +
  pixel-fidelity to the mockups). Streamlit kept only as a temporary data smoke test.
- RL: portfolio-construction agent (PPO/SAC, Gymnasium) as an optional module behind the
  `portfolio.construct` seam — benchmarked against the rule-based baseline, not a
  signal replacement.
- First action on approval: create the folder, `git init`, commit scaffold + design.
- **Execution is gated**: build the uv env first and validate it (import smoke test +
  Postgres ping + `test_env.py`); do NOT start the data layer until the env is confirmed
  green with the user.

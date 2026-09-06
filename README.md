# Quantis — Cross-Sectional Equity ML Trading System

A full end-to-end, ML-driven **long/short US large-cap equity** system on a
daily/weekly horizon (no intraday). Each week every S&P 500 name is scored by a
gradient-boosted **learning-to-rank** model predicting forward cross-sectional excess
return; the book goes **long the top quintile, short the bottom quintile**, sized by a
risk model (vol-targeting, sector/name caps) and rebalanced weekly — net of realistic
transaction costs.

> Portfolio/demo project. Paper trading only. Numbers in the design mockups are illustrative.

## Why it's built this way (the showcase points)

- **Point-in-time correctness** — universe & fundamentals stored with `as_of` dates.
- **Purged K-fold CV with embargo** — overlapping forward-return labels don't leak.
- **Cross-sectional learning-to-rank** — relative strength, market-beta neutralized.
- **Cost-aware backtest** — commission + slippage + turnover; net-of-cost metrics only.
- **MLOps loop** — MLflow registry, Prefect scheduled retrain, drift/IC-decay monitoring.
- **RL (advanced)** — an optional PPO/SAC portfolio-construction agent benchmarked
  against the rule-based baseline (not a signal replacement).

## Stack

Python 3.11 · **uv** (env) · PostgreSQL · SQLAlchemy/Alembic · LightGBM/XGBoost · SHAP ·
MLflow · **vectorbt** + quantstats (backtest) · Prefect (orchestration) · Streamlit
(dashboard) · Alpaca (data + paper execution). No Docker.

## Data

Self-contained: **daily** OHLC bars are pulled fresh from **Alpaca** into this project's
own `quantis` Postgres database (the existing `factor_stat_arb` data is hourly — a
different granularity — so it is intentionally not reused). Alpaca also handles paper
execution. The system has no runtime dependency on any other project's DB.

## Setup

```bash
uv python install 3.11        # uv fetches Python 3.11
uv sync --group data --group ml --group backtest --group orchestration --group app
cp .env.example .env          # then fill PGPASSWORD + Alpaca keys
# create the dedicated DB (run once, using your postgres superuser):
#   createdb -U postgres quantis
uv run python scripts/env_check.py   # environment gate: imports + DB ping
```

Add the RL module later with: `uv sync --group rl` (pulls torch).

## Layout

```
src/quantis/
  config.py            pydantic settings from .env
  db/                  SQLAlchemy models + engine
  data/                bootstrap ETL, Alpaca/yfinance sources, universe
  features/            point-in-time feature store
  models/              labels, purged CV, LightGBM training, registry
  backtest/            vectorbt engine, costs, metrics
  portfolio/           construct() -> weights, risk model, constraints
  rl/                  (advanced) Gymnasium env + PPO/SAC agent
  execution/           SimulatedBroker + Alpaca paper adapter
  orchestration/       Prefect flows
dashboard/             Streamlit app (5 screens)
scripts/env_check.py   environment gate
tests/                 leakage / feature / backtest / env tests
design/                approved dark quant-terminal UI mockups
```

## Status

Bootstrapping. See `design/` for the approved dashboard mockups the Streamlit app targets.

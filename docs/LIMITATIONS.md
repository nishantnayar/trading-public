# Known Limitations & Open Work

Honest accounting of where the data and modelling assumptions fall short, and what it
would take to fix each one. Kept current as phases land.

---

## Fundamentals coverage — **BLOCKING for value/quality features**

**Status:** pilot only — 5 symbols ingested (`AAPL, MSFT, JPM, XOM, LLY`), 25 rows,
`2025-06-30 → 2026-06-30`.

### 1. yfinance returns only ~5 usable quarters

The free yfinance quarterly statements expose roughly **5 usable quarters** per ticker
(it pads older columns with all-NaN, which the loader now drops). Daily bars go back to
**2017-11**, so fundamentals cover only about **1 of the ~9 available years**.

Consequence: **value and quality features cannot be trained on meaningful history.**
A cross-sectional model needs the feature present across the whole training window; one
year of fundamentals yields ~4 quarterly observations per name, which is far too few for
the purged-CV scheme in Phase 4.

Options, cheapest first:

| Option | Cost | History | Notes |
|---|---|---|---|
| Ship price-only features (momentum, vol, technical, liquidity) | free | full 2017→ | Phase 3 proceeds now; model is honest but has no value/quality leg |
| SimFin free tier | free, API key | ~5 years | Bulk CSV download, no per-symbol rate limit |
| Sharadar SF1 (Nasdaq Data Link) | paid | 20+ years | Point-in-time with real filing dates — the correct fix |
| SEC EDGAR `companyfacts` API | free | 10+ years | True filing dates; needs XBRL tag mapping work |

**Recommendation:** build Phase 3 price-only, and treat value/quality as a follow-up
gated on a better fundamentals source. Do not train on 5 quarters and pretend otherwise.

**Phase 3 status:** the price-only feature store is implemented (momentum, reversal,
vol, RSI, 52-week high, MA ratio, dollar volume). Value/quality columns are still
absent from `features` on purpose.

### 2. `as_of` is an approximation, not a filing date

yfinance gives the fiscal `period_end` but **not** the SEC filing date. The loader sets
`as_of = period_end + reporting_lag_days` (default **60**, stored per row).

Real 10-Qs are filed in 30–45 days, so 60 is deliberately **late** — the model sees
figures later than reality, which biases against look-ahead rather than toward it. Any
source with true filing dates (EDGAR, Sharadar) should overwrite `as_of` directly; the
column is per-row so no migration is needed.

**Features must filter on `as_of`, never `period_end`.** This is the single easiest place
to introduce a look-ahead bug.

### 3. TODO — full-universe backfill

The pilot deliberately covers 5 names. **Before Phase 4 the remaining ~497 symbols must
be ingested**, or value/quality features will silently be null for 99% of the universe.

```bash
uv run python scripts/ingest_fundamentals.py --all     # ~500 sequential calls, ~20 min
```

Blockers to resolve first:
- yfinance has **no batch fundamentals endpoint** — one HTTP call per symbol, paced at
  `THROTTLE_SECONDS = 1.0` in `scripts/ingest_fundamentals.py`.
- Rate limiting is likely on a 500-symbol run; the loader skips failures per symbol
  (logged, batch continues), so reruns are needed until coverage is complete.
- The upsert is idempotent, so reruns are safe and resumable.
- Given limitation #1, a full backfill is only worth doing **after** picking a source
  with real history — otherwise it is 500 calls for one year of data.

**Verify coverage before Phase 4:**
```python
from quantis.data.store import fundamental_coverage
fundamental_coverage()   # expect ~502 symbols, not 5
```

---

## Price data

### Effective history starts **2020-01**, not 2017-11

`min(date)` in `daily_bars` is 2017-11-15, but that is a *single* symbol. The
cross-section is effectively empty until 2020:

| Year | Bars | Symbols |
|---|---|---|
| 2017 | 1 | 1 |
| 2018 | 68 | 9 |
| 2019 | 201 | 10 |
| **2020** | **53,386** | **484** |
| 2021 | 122,157 | 489 |
| 2026 (partial) | 85,125 | 502 |

**Quote the usable span as ~6.5 years (2020→) — not 9.** A cross-sectional model needs a
populated universe on each date; 9 symbols in 2018 cannot support a quintile spread. The
2018–19 rows are harmless (features simply exist for one name) but must not be counted as
training history.

Consequence for Phase 4: the training window starts **2020**, which is dominated by the
COVID crash, the 2020–21 liquidity rally, the 2022 drawdown, and the 2023–26 recovery.
That is a narrow and unusual regime sample — worth stating explicitly next to any Sharpe
figure.

### Other price caveats

- **IEX feed volume** — the free Alpaca tier reports IEX-only volume, a fraction of
  consolidated tape. It is consistently understated across names, so *cross-sectional*
  volume/liquidity features remain usable, but absolute levels are wrong and
  dollar-volume filters must not use real-world thresholds.
- **No pre-2020 regimes** — no 2008-09 crisis and no 2015-16 drawdown, so the model has
  never seen a severe multi-quarter deleveraging.

## Feature store (Phase 3)

- **Price-only.** 11 features: momentum (1m, 3m, 6m, 12-1), short-term reversal (5d),
  realised vol (20d, 60d), RSI-14, distance from 52w high, 50/200 MA ratio, and log
  dollar volume. **No value or quality features** — blocked on the fundamentals gap above.
- **Features are raw, not cross-sectionally normalised.** Per-date z-scoring / ranking is
  deliberately left to the model layer (Phase 4) so the same stored feature can be
  neutralised different ways without a rebuild.
- **`ret_5d` needs only 5 sessions, `mom_12_1` needs 252.** Early rows therefore have
  some features populated and others null. Phase 4 must decide explicitly whether to
  require a complete feature vector (drops early history) or impute. From 2024 onward all
  11 features are 100% populated, so this only affects 2020–21.
- **Full rebuild is ~4 minutes** for 502 symbols / 754k rows. There is no incremental
  mode; `run(start=...)` bounds the *output* but still loads ~1 year of warm-up bars.

## Model (Phase 4)

### Requiring complete feature vectors costs 35% of rows — and 18 months

Phase 4 chose to **require all 11 features present** rather than impute (imputing a
fabricated `mom_12_1` would inject signal that never existed). The bill:

| | Value |
|---|---|
| Feature rows available | 754,561 |
| Complete rows kept | 491,928 (**65%**) |
| Final panel after label join | 489,429 rows · 499 symbols · 1,279 dates |
| Panel span | **2021-07-27 → 2026-08-28** (~5.1 years) |

The training window therefore starts **2021-07, not 2020** as originally assumed.
`mom_12_1` needs 252 sessions, and the universe only fills in across 2020, so the first
date where a full cross-section has complete vectors is mid-2021. This compounds the
narrow-regime problem above: **~5 years, no pre-COVID data, one major drawdown (2022).**

### Fold 1 is not a meaningful evaluation

| Fold | Train rows | Valid rows | Best iter | Rank IC |
|---|---|---|---|---|
| 1 | 51,302 | 74,168 | **1** | **-0.021** |
| 2 | 122,080 | 89,173 | 20 | 0.021 |
| 3 | 211,223 | 89,783 | 17 | 0.013 |
| 4 | 300,986 | 90,414 | 28 | 0.043 |
| 5 | 391,370 | 93,089 | 42 | 0.032 |

Fold 1 stopped at **iteration 1** — early stopping fired immediately, so it is close to a
constant predictor. Its 354 training dates carry only ~145 names each (the cross-section
is still filling in), while it is scored on dates averaging ~407 names. That is a
**coverage shift, not a discovered regime effect**, and it is why fold 1 trains on fewer
rows than it validates on. Treat the -0.021 as "insufficient data", not "the signal
inverts". Excluding it, folds 2–5 average IC ≈ 0.027; the honest headline is still the
all-fold 0.0178.

### `q_spread` is in z-score units, not percent

The label is a per-date z-scored forward return, so the reported quintile spread
(**0.050**) is dimensionless — it is **not** a 5% return. A real long/short return spread
needs raw forward returns net of costs, which is Phase 5's job. Do not quote `q_spread`
as a P&L figure.

### The signal is weak, and nothing is netted yet

Overall **rank IC 0.0178** (t-stat 3.97 over 915 validation dates, IC hit rate 56%). That
is inside the plausible band for price-only features on daily equities, and the
permutation control (`test_shuffled_labels_destroy_the_signal`) confirms it is not
leakage. But it is measured **gross**: no transaction costs, no turnover penalty, no
capacity or borrow constraints, and no market-impact model. A 0.018 IC can easily be
fully consumed by costs at weekly rebalance — Phase 5/6 decides whether anything survives.

Also still missing: **no value or quality leg** (fundamentals gap above), so SHAP
importance is dominated by `vol_60d` and `mom_12_1` largely by default.

### Other model caveats

- **Hyperparameters are hand-set, not tuned.** `LGBM_PARAMS` is deliberately conservative
  (31 leaves, `min_child_samples=200`, `lambda_l2=1.0`). Optuna is a declared dependency
  but unused; any tuning must happen *inside* the CV loop or the purge is wasted.
- **Single seed.** One `seed=42` run; fold-level IC ranges from -0.02 to +0.04, so
  seed/fold variance is on the same order as the signal itself.
- **The final model is fold 5's booster** — fit on data through 2025-08, not refit on the
  full panel. Live inference needs a deliberate refit policy.
- **Embargo is 5 days on a 5-day horizon.** Defensible, but feature autocorrelation
  (60-day vol, 200-day MA) is far longer-lived than 10 sessions; a longer embargo would
  be more conservative and would cost more history.

## Backtest (Phase 5)

### The strategy does not survive realistic costs

Break-even is **15.7 bps per side**. At 10 bps the net result is CAGR 1.74% / Sharpe 0.28
over 915 days; at 20 bps it is negative. Gross Sharpe is 0.78. **Do not quote the gross
figure without the cost curve** — the honest headline is "positive but not investable".

**Turnover (34.2x annualised) is the binding constraint.** A weekly full-quintile swap
has zero position inertia: a name that drifts one rank past the cutoff is liquidated. The
signal is thin per name, so almost all of it is spent on execution.

Phase 6 tested the obvious construction fixes. A **no-trade buffer plus a 10-session
hold** cuts turnover to 13.4x and lifts break-even to **25.4 bps**. That is better, not
solved: at 10 bps Sharpe is 0.31 (still inside sampling noise of the 0.28 baseline) and
the book still dies at a conservative 20 bps if you insist on the original weekly
schedule. **Sector-neutralising destroys the signal** (Sharpe -0.21) — the 5.3% IT tilt
was the edge, not leftover risk. See `docs/PROGRESS.md` Phase 6.

### What the cost model does and does not include

`cost = |w(t) - w(t-1)| * bps_per_side` covers commission plus half the bid-ask spread as
a flat rate. It **excludes**:

- **Market impact** — no participation-rate or square-root impact term. Fine at small
  size, wrong at scale, and the IEX-only volume data cannot support a real capacity
  estimate anyway (see Price data).
- **Borrow cost and short availability** — the short leg is assumed freely shortable at
  no fee. Hard-to-borrow names are neither excluded nor charged.
- **Financing** — Sharpe is excess-of-zero on the assumption that a dollar-neutral book
  roughly self-funds.
- **Slippage dispersion** — one flat rate for every name and every day, whereas real
  spreads widen precisely when the book most wants to trade.

### Other backtest caveats

- **Evaluable window is 2023-01 to 2026-08 (3.6 years)**, not the panel's full 5.1: the
  first CV fold was dropped for insufficient training data, and the backtest only
  consumes out-of-fold predictions. 915 days is a short sample for a Sharpe estimate —
  the standard error on Sharpe here is roughly 0.33, so 0.28 net is not
  distinguishable from zero.
- **The IT tilt *is* the alpha.** Mean net exposure of 5.3% in Information Technology
  was left unmanaged in Phase 5. Forcing sector-neutrality in Phase 6 zeroed the tilt
  and took Sharpe@10bps from +0.28 to **-0.21**. Live with the tilt and disclose it, or
  accept there is currently no sector-neutral version of this signal. Do not "fix" it
  and keep quoting the dollar-neutral Sharpe.
- **No beta neutralisation** — the two legs are equal-weight, not beta-matched, so the
  book carries residual market exposure.
- **Execution at the close is assumed to be free of timing risk.** Weights are formed
  from the same close that prices the trade; a real implementation fills over a window
  and would differ.
- **Fixed quintile count and schedule** were not tuned. Any sweep of them must be treated
  as parameter search on out-of-fold data, which is a second-order overfit.

## Universe

- **Survivorship bias** — `data/universe/sp500.csv` is the *current* S&P 500. Names that
  were dropped (delisted, acquired, fell out) are absent, so backtests inherit an upward
  bias. The `symbols` table carries `active` and `added_at`, and the `Fundamental` model
  is already point-in-time shaped, so the fix is a historical membership CSV with
  `valid_from` / `valid_to` — not a schema change.

## Infrastructure

- **No Alembic migrations** — schema is created with `Base.metadata.create_all()` via
  `scripts/init_db.py`. Alembic is a declared dependency but unconfigured; fine while
  tables are additive, needs doing before any destructive column change.
- **`ingest_runs` is written** by `ingest-daily-bars` and `publish-scores`. Older docs
  said it was empty by design; that is no longer true. Scheduled Prefect deployments
  (daily/weekly) are still Phase 8.
- **No `YFinancePrices` fallback** — `PriceSource` is a protocol with only
  `AlpacaDailyBars` implementing it, despite the plan naming a fallback.

## Feature store

- **Price-only by design.** Eleven columns on `features`, all from daily bars. No
  value/quality features until a fundamentals source with multi-year history is chosen.
- **Dollar volume is IEX-only.** `dollar_vol_20d` is usable for cross-sectional ranking,
  not for absolute liquidity screens. See Price data above.

## Dashboard

- **The dev stack is loopback-only and not deployable as-is.** All three services bind
  `127.0.0.1`, and the frontend reads `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`.
  Deploying the Next app to Vercel would therefore render the shell with **no data**: the
  visitor's browser would call *their own* localhost. A hosted dashboard needs three
  things first — the FastAPI service publicly reachable, **Postgres hosted** (it is
  currently a local install with no managed instance), and the deployed origin added to
  `api_cors_origins`. Vercel can host the frontend, but not the data layer behind it.
- **Positions are target weights, not fills.** The Positions screen shows the published
  working book (`buffer=1`, 10-session hold). There is no SimulatedBroker / Alpaca paper
  adapter yet, so there is no quantity, market value, or uPnL — those would be fiction.
  Restart the UI after `publish` so Next picks up API changes; uvicorn `--reload-dir src`
  covers the backend.

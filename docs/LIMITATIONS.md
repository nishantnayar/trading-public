# Known Limitations & Open Work

Honest accounting of where the data and modelling assumptions fall short, and what it
would take to fix each one. Kept current as phases land.

> **2026-09 rebuild.** The LightGBM cross-sectional ranking pipeline (feature store →
> model → backtest → paper execution, described in the "Feature store", "Model",
> "Backtest", and "Paper execution" sections below) was deleted to rebuild the signal
> side from a simpler, fully rule-based baseline (`quantis.signals`) first. Those
> sections are kept **as a historical record** of what was built and learned — none of
> that code exists in this repo anymore. The **Fundamentals coverage** and **Price
> data** sections below are still current: the ingestion layer they describe was kept.
> See the new **Signal (v1)** section for the current system's limitations.

---

## Fundamentals coverage — **RESOLVED via SEC EDGAR**

**Status (2026-09-06):** full-universe backfill from SEC EDGAR's XBRL `companyfacts`
API. 33,659 quarterly rows, **503 symbols**, spanning **2006-09 → 2026-08** — the
`YFinanceFundamentals` pilot (5 symbols, 25 rows, one year) is superseded and left in
`data/fundamentals.py` only as a documented fallback/reference implementation.

### Why EDGAR instead of yfinance

The free yfinance quarterly statements expose roughly **5 usable quarters** per
ticker (it pads older columns with all-NaN). That is far too little history for the
purged-CV scheme in Phase 4 — one year of fundamentals yields ~4 observations per
name. SEC EDGAR's `companyfacts` endpoint returns a filer's **entire XBRL history**
(often 15-20 years) in a single free, no-API-key call, and — the more important
property — every fact carries the SEC's own **`filed` date**, so `as_of` here is a
genuine point-in-time anchor rather than `period_end + an assumed lag`. See
`quantis/data/fundamentals.py::EdgarFundamentals`.

```bash
uv run python scripts/ingest_fundamentals_edgar.py            # full active universe, ~5 min
uv run python scripts/ingest_fundamentals_edgar.py AAPL MSFT  # subset
```

`scripts/migrate_add_fundamental_features.py` and `quantis.features.fundamental_build`
(which turned these rows into the 4 value/quality model features below) were deleted
with the ML pipeline. `fundamentals` is still ingested and stored point-in-time; nothing
currently reads it into a feature or a signal.

### Known EDGAR data quirks, and how they're handled

1. **Same quarter, different `end` dates across concepts.** A 52/53-week fiscal
   filer's balance-sheet facts (instant) are often tagged at the true fiscal
   Saturday-close (e.g. `2025-06-28`) while some duration facts use the nearby
   calendar quarter-end (`2025-06-30`). An exact-date join would silently split one
   quarter's data across two half-populated rows. `EdgarFundamentals._bucket_period_ends`
   clusters `end` dates within a 10-day tolerance into one canonical period.
2. **Cash-flow-statement items are often YTD-cumulative only.** Many 10-Qs tag
   `NetCashProvidedByUsedInOperatingActivities` as a 6-month or 9-month cumulative
   figure, never as a standalone quarter (Q1 is the exception — 3-months-cumulative
   IS the standalone quarter). `EdgarFundamentals._reconstruct_standalone_quarters`
   differences consecutive cumulative periods within a fiscal year (Q2 − Q1, Q3 − Q2,
   FY − Q3) using the `fy`/`fp` tags EDGAR provides on every fact, as a fallback that
   only fills gaps the as-reported (80–100 day span) facts didn't already cover. A
   fiscal year missing an earlier quarter simply breaks the differencing chain from
   that point rather than producing a wrong number.
3. **Restatements.** The same fiscal quarter is often re-tagged as a "prior period"
   comparative column in a later filing. The earliest-`filed` value wins per
   (period, column) — the point-in-time-honest choice, since a later restatement was
   not knowable at the time.
4. **No single reliable debt tag.** `LongTermDebt` vs `LongTermDebtNoncurrent` vs
   `DebtCurrent` vary by filer with no tag used consistently enough to trust without
   per-filer mapping. `total_debt` is fetched into `Fundamental` but left `NULL` —
   not used by any current feature.
5. **`total_debt` and `capex` are ingested but unused.** Both are raw columns on
   `Fundamental` for future use; no `FUND_FEATURE_NAMES` feature currently consumes
   them.

### `as_of` is a real filing date, not an approximation

Unlike the retired yfinance path (`as_of = period_end + 60 days`, an assumed lag),
EDGAR's `as_of` is the SEC's own `filed` timestamp on each fact — the actual date the
figure became public. **Features must still filter on `as_of`, never `period_end`** —
that discipline doesn't change, only the anchor's honesty does.

### Value/quality features are OPTIONAL, not required-complete

`quantis/features/fundamental_build.py` computes 4 point-in-time ratios and upserts
them onto the SAME `features` table as the 11 price columns:

| Feature | Formula | Family |
|---|---|---|
| `gross_margin` | TTM gross profit / TTM revenue | quality |
| `roe_ttm` | TTM net income / total equity | quality |
| `accruals_ttm` | (TTM net income − TTM operating cash flow) / total assets | quality |
| `book_to_market` | total equity / (shares outstanding × daily close) | value |

TTM = trailing 4 filed quarters (per-symbol rolling sum), so a name needs at least 4
quarters of history before any ratio appears. Unlike the 11 price features (which
`dataset.load_features` requires complete via `dropna`), these 4 are **left as NaN
when absent** — LightGBM handles missing values natively, so a row simply trains on
the price features alone when fundamentals aren't yet available. Coverage in the live
training panel (2021-07 → 2026-08): **78.3% of rows have at least one fundamental
feature populated** (`accruals_ttm` alone: ~67%, gated by both TTM-OCF availability
and the reconstruction fallback above).

### Does it help? Inconclusive from one run — treat as an open question

A single retrain with fundamentals wired in produced overall OOF rank IC **0.0117**
(5 folds), versus the price-only headline of **0.0178** documented below. `book_to_market`
did surface in the top-6 SHAP features, so the model is using it — but a single-seed,
single-split comparison cannot distinguish "fundamentals hurt" from ordinary fold
variance, which the price-only run below already shows is on the same order as the
signal itself (fold IC ranging −0.02 to +0.04). Properly answering "do fundamentals
help" needs a multi-seed run with and without `FUND_FEATURE_NAMES`, which has not been
done. Do not quote either IC as the fundamentals-vs-not verdict without that
comparison.

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

---

## Signal (v1) — `quantis.signals`

The current signal: SMA(50/200) crossover, confirmed by 12-1 momentum, single-bar
entry, 3-day debounced exit. See
[`src/quantis/signals/rules.py`](../src/quantis/signals/rules.py) for the full
rationale and the parameter comparison that picked these defaults.

- **Net of realistic costs, the median outcome is a loss — for all three variants
  tested, across the full universe.** At a 10 bps/side cost model over the full ~503
  active names (2020-07-27 → 2026-09-10): median net return is -4.7% for the current
  default (`exit_only`), -19.0% for a fully single-bar rule, and -6.1% for a symmetric
  debounced-entry-and-exit rule. `exit_only` is the best of the three (most wins,
  least-negative median, the only one with a barely-positive median Sharpe of 0.04) —
  but "best of three simple options" is not the same claim as "a proven edge." A rule
  this simple having no edge net of costs across the broad market is the expected,
  honest result. Reproduce: `uv run python -m quantis.signals --compare`.
- **No market impact, slippage dispersion, or borrow cost in the cost model.** It is a
  flat `cost_bps_per_side` charged on every position change — see
  `quantis.signals.backtest` module docstring. Real costs would be worse on the more
  illiquid names in a 500+-name universe, not better.
- **No edge on genuine multi-year decliners.** Names like CMCSA, ALGN, TROW, MDLZ lose
  money under every variant tested, including versus their own (weak/negative)
  buy-and-hold. Expected for a trend-follower — it has nothing to say about a name with
  no trend to follow — but worth stating plainly rather than only reporting the median.
- **The net-loss median is heavily sector-concentrated, not spread evenly.** Grouping
  the same full-universe backtest by GICS sector (`uv run python -m quantis.signals
  --sectors`): Energy (median net +49.1%, 90% of names net-positive) and Information
  Technology (+15.4%, 53% positive) carry the rule; Health Care (-19.9%, 22% positive),
  Real Estate (-23.3%, 17% positive), and Consumer Staples (-18.8%, 26% positive) drag
  it down hardest. Defensive/low-beta sectors chop sideways or move on rate-driven
  regime shifts rather than idiosyncratic trends, which an SMA crossover has nothing to
  grab onto — this is closer to "the rule doesn't apply to these sectors" than "the
  rule is broken."
- **Per-symbol median return and the portfolio-level backtest tell different
  stories, and the portfolio is the better number.** `quantis.signals.portfolio`
  backtests a book of every currently-long name, rebalanced daily
  (`uv run python -m quantis.signals --portfolio`). Its **default construction**
  is equal-weight, capped at **15% per GICS sector**, with an over-cap sector's
  freed weight **reallocated** to under-cap sectors via iterative proportional
  capping ("water-filling": `_water_fill_sector_weights`) rather than left
  uninvested. Over the full ingested history (2017-11-15 → 2026-09-10, 1,798
  trading days), that construction returns **70.2% total / 7.7% CAGR, Sharpe
  0.65, max drawdown -18.9%**, at ~25.2x annualized turnover — materially better
  than the negative per-symbol median net return. Cross-sectional diversification
  across many concurrently-long names smooths out the whipsaw/cost drag that
  dominates any single undiversified symbol, while the per-symbol median is
  pulled down by sectors with no exploitable trend (see above).
- **These defaults (15% cap, reallocated) were picked by comparing alternatives
  against the live universe, not assumed.** All four combinations, same period:

  | construction | CAGR | Sharpe | max drawdown | avg exposure |
  |---|---|---|---|---|
  | equal-weight, no cap | 8.2% | 0.59 | -37.0% | 78.3% |
  | 25% cap, not reallocated | 7.9% | 0.64 | -20.4% | 72.3% |
  | 25% cap, reallocated | 7.9% | 0.64 | -20.4% | 72.4% |
  | **15% cap, not reallocated** | 7.0% | 0.62 | **-19.2%** | 66.8% |
  | **15% cap, reallocated (default)** | **7.7%** | **0.65** | -18.9% | **71.6%** |

  Reallocation barely matters at the 25% cap (few sectors bind that hard with 11
  GICS sectors and ~175 names typically long) but clearly helps at 15% (several
  sectors bind simultaneously, leaving real freed weight to redistribute) — both
  results are genuine, not a bug, confirmed with isolated synthetic tests before
  trusting the live-DB numbers. Reproduce any row:
  `uv run python -m quantis.signals --portfolio --sector-cap 0.15` (add
  `--no-cap` or `--no-reallocate` for the other variants).
- **A per-name cap exists (`max_name_weight` / `--name-cap`) but is off by default —
  it also made things slightly worse, never better, at every level tried.** Applied
  after the sector cap: any name whose weight would exceed `max_name_weight` is
  scaled down to the cap, with the same `reallocate` choice (redistribute the
  excess to under-cap names via water-filling, or leave it uninvested) as the
  sector cap. At 3% and 1% caps on the live universe (avg breadth ~175 names, so
  equal weight is usually ~0.5-1% and rarely near even a 1% cap): CAGR 7.4-7.6% and
  Sharpe 0.63-0.64, both fractionally below the 0.65/7.7% baseline (15% sector cap,
  reallocated, no name cap). The cap does bind on real days — the breadth
  distribution has a long left tail (25th percentile is just 1 name long, both from
  the sparse pre-2020 universe and genuine low-breadth periods like the 2020 COVID
  crash) — but concentrating capital in the only 1-2 names actually in an uptrend
  during a genuine drawdown isn't something diversification can fix without also
  cutting exposure outright, so capping it here trims a little of what upside there
  was without meaningfully reducing risk. Kept off by default for the same reason as
  vol targeting: a knob that doesn't help shouldn't ship turned on. Reproduce:
  `uv run python -m quantis.signals --portfolio --name-cap 0.03`.
- **Volatility targeting exists (`vol_target` / `--vol-target`) but is off by
  default — it made every metric tested worse, not better, and that's a real result,
  not an unfinished feature.** It scales the whole book's daily return by
  `target_vol / trailing realized vol` (capped at `max_leverage`, using only
  information known the prior day — see `_vol_target_leverage`). Tried against the
  live universe at several target levels (10%/13%/15%), lookback windows
  (20/60/120 days), and leverage caps (up to 2.0x): every configuration landed at
  Sharpe 0.49-0.62, all below the 0.65 baseline (15% sector cap, reallocated, no vol
  target) — never an improvement. The likely mechanism: trailing realized vol lags
  a regime shift, so it cuts exposure *after* a trend has already turned choppy
  (too late to help) and can cut exposure *during* a strong trend simply because
  the trend itself was volatile (too early, missing the move) - the reverse of what
  a trend-following overlay wants. This is a case where a standard risk-management
  technique doesn't transfer cleanly onto this specific signal, worth stating
  plainly rather than quietly shipping a knob that doesn't help. Reproduce:
  `uv run python -m quantis.signals --portfolio --vol-target 0.13 --vol-lookback 60`.
- **The 25.2x annualized turnover estimate is an approximation**, not an exact
  portfolio accounting: it's total position-change events across the universe,
  divided by twice the average book size, annualized — treats every name as an equal
  1/N slice at all times rather than tracking actual weight drift as the book's size
  changes day to day. Directionally right, not to the decimal.
- **No shorting.** Long/flat only — a flat call just means "not in the book," never a
  short position.
- **A simulated paper broker exists (`quantis.execution.simulated`) — no live path
  anywhere in this repo.** It rebalances an in-database cash + position ledger
  toward `quantis.signals.portfolio.target_weights()` (today's construction), filled
  at each symbol's latest close. No slippage dispersion, no market impact, no
  borrow cost, no financing, and no next-day execution lag — the fill uses the same
  close the weights were computed from, not a later, realistic fill price. Fractional
  shares are allowed since this is a simulation, not a real brokerage. `GET /broker`
  and the Broker screen read the current ledger; `daily-rebalance` (17:40 weekdays)
  recomputes it. Positions traded down to ~0 (dropped from the book, or capped out)
  are removed rather than carried as dust.
- **A symbol with no current price is silently skipped, not liquidated.** If a
  held name stops getting bars (delisted, ingestion gap), the rebalance leaves its
  position untouched and excludes it from the equity mark until a price
  reappears — it neither trades nor is valued, rather than erroring or forcing a
  sale at a stale price. Rare in practice (the same universe backing the signal
  layer is what gets ingested), but a real gap this would need explicit handling
  for.

## Universe

- **Survivorship bias** — `data/universe/sp500.csv` is the *current* S&P 500. Names that
  were dropped (delisted, acquired, fell out) are absent, so anything backtested inherits
  an upward bias. The `symbols` table carries `active` and `added_at`, and the
  `Fundamental` model is already point-in-time shaped, so the fix is a historical
  membership CSV with `valid_from` / `valid_to` — not a schema change.

## Infrastructure

- **No Alembic migrations** — schema is created with `Base.metadata.create_all()` via
  `scripts/init_db.py`. Alembic is a declared dependency but unconfigured; fine while
  tables are additive, needs doing before any destructive column change.
- **`ingest_runs` is written** by `ingest-daily-bars` and `recompute-signals`.
  `scripts/start.py` starts the Prefect server and the cron runner together.
  `--skip schedules` disables cron.
- **Prefect 2.20 cannot run on AnyIO 4.14+.** `GatherTaskGroup` is missing `create_task`,
  so a finished ingest was marked Crashed. The env is pinned to `anyio>=4.4,<4.14`.
- **No `YFinancePrices` fallback** — `PriceSource` is a protocol with only
  `AlpacaDailyBars` implementing it, despite the plan naming a fallback.

## Dashboard

- **The dev stack is loopback-only and not deployable as-is.** All three services bind
  `127.0.0.1`, and the frontend reads `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`.
  Deploying the Next app to Vercel would therefore render the shell with **no data**: the
  visitor's browser would call *their own* localhost. A hosted dashboard needs three
  things first — the FastAPI service publicly reachable, **Postgres hosted** (it is
  currently a local install with no managed instance), and the deployed origin added to
  `api_cors_origins`. Vercel can host the frontend, but not the data layer behind it.
- **Positions is an illustrative equal-weighted book**, not a constructed portfolio —
  see Signal (v1) above. There is no rebalance history or broker fill data anywhere in
  this repo.

---

> **Everything below this line documents the deleted ML/backtest/execution pipeline**
> (feature store → LightGBM → backtest → paper broker). Kept as a record of what was
> built and learned; none of it reflects code currently in this repo.

## Feature store (Phase 3)

- **11 price features** (momentum 1m/3m/6m/12-1, short-term reversal 5d, realised vol
  20d/60d, RSI-14, distance from 52w high, 50/200 MA ratio, log dollar volume), all
  required-complete, plus **4 value/quality features** from EDGAR fundamentals
  (`gross_margin`, `roe_ttm`, `accruals_ttm`, `book_to_market`), which are optional /
  sparser-by-design — see "Fundamentals coverage" above.
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

This is the **price-only** baseline (11 features, no fundamentals) — the run this
whole Backtest section is built on. A later run with the 4 EDGAR value/quality
features added (see "Fundamentals coverage" above) produced a *different* overall IC
(0.0117, one seed) with `book_to_market` in the top-6 SHAP features; that run has not
been carried through Phase 5/6 or published, and the two single-run ICs are not a
valid fundamentals-vs-not comparison (see the note there). Everything below still
describes the original price-only baseline.

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

## Feature store

- **Price-only by design.** Eleven columns on `features`, all from daily bars. No
  value/quality features until a fundamentals source with multi-year history is chosen.
- **Dollar volume is IEX-only.** `dollar_vol_20d` is usable for cross-sectional ranking,
  not for absolute liquidity screens. See Price data above.

## Paper execution

- **No live trading.** `AlpacaPaperClient` refuses to construct unless `ALPACA_PAPER` is
  true, and the SDK client is always `paper=True`. There is no live endpoint in this
  repo.
- **Simulated is the default.** `QUANTIS_BROKER=simulated` so scheduled rebalance cannot
  submit Alpaca paper orders unless you change it on purpose.
- **Simulated fills at the mark**, normally yesterday's close — not a bid/ask, not
  latency, not a locate. Short qty is just negative inventory.
- **Alpaca paper fills are not written** to `broker_fills`; only the simulated ledger
  persists. `GET /broker` reads that ledger.

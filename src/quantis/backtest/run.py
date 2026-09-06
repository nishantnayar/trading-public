"""Backtest the out-of-fold predictions and sweep transaction costs.

Only **out-of-fold** predictions are used: every row was produced by a model that never
saw that date in training, so the equity curve is a genuine out-of-sample simulation
rather than an in-sample fit. P&L comes from **raw adjusted returns**, never the
z-scored label, which is dimensionless.

Run:  uv run python -m quantis.backtest.run
      uv run python -m quantis.backtest.run --every 5 --quantiles 5
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from loguru import logger
from sqlalchemy import select

from quantis.backtest import portfolio as pf
from quantis.backtest.engine import break_even_cost, daily_returns, run_backtest
from quantis.db.engine import session_scope
from quantis.db.models import Symbol
from quantis.models.dataset import load_close_wide

ARTIFACT_DIR = Path(__file__).resolve().parents[3] / "models" / "artifacts"
COST_SWEEP = (0.0, 5.0, 10.0, 20.0)


def latest_oof(directory: Path = ARTIFACT_DIR) -> Path:
    """Most recent out-of-fold prediction file written by training."""
    files = sorted(directory.glob("oof-*.parquet"))
    if not files:
        raise FileNotFoundError(
            f"no oof-*.parquet in {directory} - run: uv run python -m quantis.models.train"
        )
    return files[-1]


def load_sectors() -> pd.Series:
    with session_scope() as session:
        rows = session.execute(select(Symbol.symbol, Symbol.sector)).all()
    return pd.DataFrame(rows, columns=["symbol", "sector"]).set_index("symbol")["sector"]


def run(
    oof_path: Path | None = None,
    quantiles: int = pf.DEFAULT_QUANTILES,
    every: int = pf.REBALANCE_EVERY,
    costs: tuple[float, ...] = COST_SWEEP,
    buffer: int = 0,
    sector_neutral: bool = False,
) -> pd.DataFrame:
    """Build the portfolio, sweep costs, and report. Returns the sweep table."""
    path = oof_path or latest_oof()
    predictions = pd.read_parquet(path)
    predictions["date"] = pd.to_datetime(predictions["date"])
    logger.info(
        "predictions: {} rows, {} symbols, {} -> {} (from {})",
        len(predictions),
        predictions["symbol"].nunique(),
        predictions["date"].min().date(),
        predictions["date"].max().date(),
        path.name,
    )

    sectors = load_sectors() if sector_neutral else None
    weights = pf.target_weights(
        predictions, quantiles=quantiles, every=every, buffer=buffer, sectors=sectors
    )
    close = load_close_wide()
    close.index = pd.to_datetime(close.index)
    returns = daily_returns(close)

    exposure = pf.exposure_report(weights, sectors if sectors is not None else load_sectors())
    logger.info(
        "book: gross {:.2f}, net {:+.2e}, {} long / {} short, turnover {:.1f}x per year",
        exposure["gross"].mean(),
        exposure["net"].abs().max(),
        int(exposure["n_long"].median()),
        int(exposure["n_short"].median()),
        pf.annualised_turnover(weights),
    )

    rows = []
    for bps in costs:
        result = run_backtest(weights, returns, cost_bps_per_side=bps)
        rows.append(result.summary())
    sweep = pd.DataFrame(rows)

    breakeven = break_even_cost(weights, returns)
    logger.info("break-even cost: {:.2f} bps per side", breakeven)

    columns = ["cost_bps_per_side", "cagr", "ann_vol", "sharpe", "max_drawdown", "hit_rate"]
    logger.info("cost sweep:\n{}", sweep[columns].to_string(index=False))

    # Persist the tilts we chose not to neutralise, so Phase 6 has a baseline to beat.
    sector_columns = [c for c in exposure.columns if c.startswith("net_")]
    tilts = exposure[sector_columns].abs().mean().sort_values(ascending=False)
    if len(tilts):
        logger.info("largest mean |sector tilt|:\n{}", tilts.head(5).to_string())

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = path.stem.replace("oof-", "backtest-")
    sweep.to_csv(ARTIFACT_DIR / f"{stem}.csv", index=False)
    (ARTIFACT_DIR / f"{stem}.json").write_text(
        json.dumps(
            {
                "source": path.name,
                "quantiles": quantiles,
                "rebalance_every": every,
                "buffer": buffer,
                "sector_neutral": sector_neutral,
                "break_even_bps_per_side": breakeven,
                "annualised_turnover": pf.annualised_turnover(weights),
                "mean_gross": float(exposure["gross"].mean()),
                "max_abs_net": float(exposure["net"].abs().max()),
                "sweep": sweep.to_dict(orient="records"),
            },
            indent=2,
            default=str,
        )
    )
    return sweep


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backtest out-of-fold predictions.")
    parser.add_argument("--oof", type=Path, default=None, help="path to an oof parquet")
    parser.add_argument("--quantiles", type=int, default=pf.DEFAULT_QUANTILES)
    parser.add_argument("--every", type=int, default=pf.REBALANCE_EVERY)
    parser.add_argument("--buffer", type=int, default=0)
    parser.add_argument("--sector-neutral", action="store_true")
    args = parser.parse_args(argv)

    run(
        oof_path=args.oof,
        quantiles=args.quantiles,
        every=args.every,
        buffer=args.buffer,
        sector_neutral=args.sector_neutral,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

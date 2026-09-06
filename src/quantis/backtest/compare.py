"""Compare Phase 6 construction levers on the same out-of-fold predictions.

Variants are evaluated at a *fixed* 10 bps per side — the cost that made the Phase 5
book uninvestable — plus turnover and break-even, so a lever that "wins" on Sharpe by
assuming cheaper execution cannot hide.

Run:  uv run python -m quantis.backtest.compare
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from loguru import logger

from quantis.backtest import portfolio as pf
from quantis.backtest.engine import break_even_cost, daily_returns, run_backtest
from quantis.backtest.run import ARTIFACT_DIR, latest_oof, load_sectors
from quantis.models.dataset import load_close_wide

EVAL_COST_BPS = 10.0


@dataclass(frozen=True)
class Variant:
    name: str
    every: int
    buffer: int
    sector_neutral: bool


VARIANTS = (
    Variant("baseline (phase 5)", every=5, buffer=0, sector_neutral=False),
    Variant("no-trade buffer=1", every=5, buffer=1, sector_neutral=False),
    Variant("hold every 10", every=10, buffer=0, sector_neutral=False),
    Variant("buffer=1 + hold 10", every=10, buffer=1, sector_neutral=False),
    Variant("sector-neutral", every=5, buffer=0, sector_neutral=True),
    Variant("buffer=1 + sector-neutral", every=5, buffer=1, sector_neutral=True),
)


def evaluate(predictions: pd.DataFrame, returns: pd.DataFrame, sectors: pd.Series) -> pd.DataFrame:
    rows = []
    for variant in VARIANTS:
        weights = pf.target_weights(
            predictions,
            every=variant.every,
            buffer=variant.buffer,
            sectors=sectors if variant.sector_neutral else None,
        )
        result = run_backtest(weights, returns, cost_bps_per_side=EVAL_COST_BPS)
        exposure = pf.exposure_report(weights, sectors)
        sector_cols = [c for c in exposure.columns if c.startswith("net_")]
        max_tilt = float(exposure[sector_cols].abs().mean().max()) if sector_cols else 0.0
        rows.append(
            {
                "variant": variant.name,
                "every": variant.every,
                "buffer": variant.buffer,
                "sector_neutral": variant.sector_neutral,
                "turnover": pf.annualised_turnover(weights),
                "break_even_bps": break_even_cost(weights, returns),
                "sharpe_10bps": result.summary()["sharpe"],
                "cagr_10bps": result.summary()["cagr"],
                "max_dd_10bps": result.summary()["max_drawdown"],
                "max_sector_tilt": max_tilt,
            }
        )
        logger.info(
            "{:>28}: turnover {:5.1f}x  sharpe@10bps {:+.3f}  BE {:>5.1f} bps  tilt {:.3f}",
            variant.name,
            rows[-1]["turnover"],
            rows[-1]["sharpe_10bps"],
            rows[-1]["break_even_bps"],
            max_tilt,
        )
    return pd.DataFrame(rows)


def main() -> int:
    path = latest_oof()
    predictions = pd.read_parquet(path)
    predictions["date"] = pd.to_datetime(predictions["date"])
    close = load_close_wide()
    close.index = pd.to_datetime(close.index)
    logger.info("comparing levers on {} ({} rows)", path.name, len(predictions))

    table = evaluate(predictions, daily_returns(close), load_sectors())
    out = ARTIFACT_DIR / "phase6-levers.csv"
    table.to_csv(out, index=False)
    logger.info("wrote {}", out)
    print(table.to_string(index=False, float_format=lambda x: f"{x: .4f}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

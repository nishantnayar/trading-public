"""Publish OOF scores and the working book into Postgres for the dashboard.

The Signals / Positions / Model screens read these tables, not parquet files. This is
a deliberate snapshot: it publishes the **working construction** (no-trade buffer +
10-session hold), labelled as such, without silently changing the Phase 5 default in
`backtest.run`.

Run:  uv run python -m quantis.backtest.publish
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from loguru import logger

from quantis.backtest import portfolio as pf
from quantis.backtest.engine import break_even_cost, daily_returns, run_backtest
from quantis.backtest.run import ARTIFACT_DIR, latest_oof
from quantis.data.scores import replace_model_run, upsert_positions, upsert_predictions
from quantis.data.store import finish_ingest_run, start_ingest_run
from quantis.db.engine import get_engine
from quantis.db.models import Base
from quantis.models import metrics
from quantis.models.dataset import load_close_wide
from quantis.models.train import LGBM_PARAMS

# The book the UI shows. Phase 5 defaults stay in `backtest.run`.
WORKING_BUFFER = 1
WORKING_EVERY = 10
WORKING = f"buffer={WORKING_BUFFER},every={WORKING_EVERY},quantiles=5"
EVAL_COST_BPS = 10.0


def _shap_from_booster(directory: Path = ARTIFACT_DIR) -> list[dict]:
    files = sorted(directory.glob("lgbm-*.txt"))
    if not files:
        return []
    try:
        import lightgbm as lgb

        booster = lgb.Booster(model_file=str(files[-1]))
        gain = booster.feature_importance(importance_type="gain")
        names = booster.feature_name()
        total = float(sum(gain)) or 1.0
        rows = [
            {"feature": name, "gain": float(value) / total}
            for name, value in zip(names, gain, strict=True)
        ]
        return sorted(rows, key=lambda r: r["gain"], reverse=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("could not read booster importance ({})", exc)
        return []


def publish(oof_path: Path | None = None) -> dict:
    Base.metadata.create_all(get_engine())
    path = oof_path or latest_oof()
    run_id = start_ingest_run("publish-scores")
    try:
        return _publish(path, run_id)
    except Exception as exc:
        finish_ingest_run(run_id, status="failed", detail=str(exc))
        raise


def _publish(path, run_id: int) -> dict:
    predictions = pd.read_parquet(path)
    predictions["date"] = pd.to_datetime(predictions["date"])

    n_pred = upsert_predictions(predictions[["symbol", "date", "pred", "label"]], path.name)

    weights = pf.target_weights(
        predictions, every=WORKING_EVERY, buffer=WORKING_BUFFER, sectors=None
    )
    n_pos = upsert_positions(weights, WORKING)

    close = load_close_wide()
    close.index = pd.to_datetime(close.index)
    returns = daily_returns(close)
    result = run_backtest(weights, returns, cost_bps_per_side=EVAL_COST_BPS)
    ic = metrics.summarise(predictions)

    as_of = predictions["date"].max().date()
    payload = {
        "oof_source": path.name,
        "construction": WORKING,
        "as_of": as_of,
        "n_dates": int(predictions["date"].nunique()),
        "n_symbols": int(predictions["symbol"].nunique()),
        "rank_ic": ic.get("rank_ic"),
        "icir": ic.get("icir"),
        "ic_hit_rate": ic.get("ic_hit_rate"),
        "q_spread": ic.get("q_spread"),
        "sharpe_10bps": result.summary()["sharpe"],
        "turnover": pf.annualised_turnover(weights),
        "break_even_bps": break_even_cost(weights, returns),
        "shap": _shap_from_booster(),
        "params": {**LGBM_PARAMS, "horizon": 5, "embargo": 5, "working": WORKING},
        "predictions": n_pred,
        "positions": n_pos,
    }
    replace_model_run(payload)
    finish_ingest_run(
        run_id,
        status="success",
        symbols_processed=int(predictions["symbol"].nunique()),
        rows_written=n_pred + n_pos,
        detail=WORKING,
    )
    logger.info(
        "published {} preds, {} positions, as_of={}, construction={}",
        n_pred,
        n_pos,
        as_of,
        WORKING,
    )
    return payload


def main() -> int:
    publish()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Train the cross-sectional LightGBM ranker under purged walk-forward CV.

Objective is L2 regression on the per-date z-scored forward return. The z-score already
removes the market move, so a regression fit ranks the cross-section without needing
`lambdarank` query groups — simpler and more stable, and the metric that matters
(rank IC) is measured directly.

Run:  uv run python -m quantis.models.train
      uv run python -m quantis.models.train --folds 3 --horizon 5
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger

from quantis.features.definitions import FEATURE_NAMES
from quantis.models import metrics
from quantis.models.cv import PurgedWalkForwardCV
from quantis.models.dataset import DEFAULT_START, build_panel, panel_summary
from quantis.models.labels import DEFAULT_HORIZON

REPO_ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_DIR = REPO_ROOT / "models" / "artifacts"
# MLflow put its filesystem backend into maintenance mode and now refuses `./mlruns`, so
# tracking goes to a local SQLite file. Artifacts still land under `mlartifacts/`.
MLFLOW_DB = REPO_ROOT / "mlflow.db"

# Conservative defaults: shallow trees and heavy regularisation, because a 6.5-year
# panel with 11 features overfits readily.
LGBM_PARAMS = {
    "objective": "regression",
    "metric": "l2",
    "learning_rate": 0.03,
    "num_leaves": 31,
    "min_child_samples": 200,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 1.0,
    "verbosity": -1,
    "num_threads": 0,
    "seed": 42,
}
NUM_ROUNDS = 400


def fit_fold(train: pd.DataFrame, valid: pd.DataFrame, params: dict, num_rounds: int = NUM_ROUNDS):
    """Fit one fold and return (booster, validation frame with predictions)."""
    import lightgbm as lgb

    train_set = lgb.Dataset(train[FEATURE_NAMES], label=train["label"])
    valid_set = lgb.Dataset(valid[FEATURE_NAMES], label=valid["label"], reference=train_set)

    booster = lgb.train(
        params,
        train_set,
        num_boost_round=num_rounds,
        valid_sets=[valid_set],
        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)],
    )

    scored = valid.copy()
    scored["pred"] = booster.predict(valid[FEATURE_NAMES], num_iteration=booster.best_iteration)
    return booster, scored


def shap_importance(booster, sample: pd.DataFrame, max_rows: int = 20_000) -> pd.DataFrame:
    """Mean |SHAP| per feature. Sampled — full-panel SHAP is needlessly slow."""
    import shap

    if len(sample) > max_rows:
        sample = sample.sample(max_rows, random_state=42)

    explainer = shap.TreeExplainer(booster)
    values = explainer.shap_values(sample[FEATURE_NAMES])
    mean_abs = np.abs(values).mean(axis=0)

    return (
        pd.DataFrame({"feature": FEATURE_NAMES, "mean_abs_shap": mean_abs})
        .sort_values("mean_abs_shap", ascending=False)
        .reset_index(drop=True)
    )


def run(
    folds: int = 6,
    horizon: int = DEFAULT_HORIZON,
    embargo: int = 5,
    start: dt.date | None = DEFAULT_START,
    num_rounds: int = NUM_ROUNDS,
    log_mlflow: bool = True,
) -> dict:
    """Full purged-CV training run. Returns the aggregated metric summary."""
    panel = build_panel(start=start, horizon=horizon)
    if panel.empty:
        raise RuntimeError("training panel is empty — build features first")

    shape = panel_summary(panel)
    logger.info("panel: {}", shape)

    cv = PurgedWalkForwardCV(n_splits=folds, horizon=horizon, embargo=embargo)
    params = {**LGBM_PARAMS}

    fold_metrics: list[dict] = []
    oof: list[pd.DataFrame] = []
    booster = None

    for fold, (train_idx, valid_idx) in enumerate(cv.split(panel), start=1):
        train, valid = panel.iloc[train_idx], panel.iloc[valid_idx]
        booster, scored = fit_fold(train, valid, params, num_rounds)

        summary = metrics.summarise(scored)
        summary |= {
            "fold": fold,
            "train_rows": len(train),
            "valid_rows": len(valid),
            "best_iteration": booster.best_iteration,
        }
        fold_metrics.append(summary)
        oof.append(scored[["symbol", "date", "label", "pred"]])
        logger.info(
            "fold {}: rank_ic={:.4f} icir={:.2f} q_spread={:.4f} ({} dates)",
            fold,
            summary["rank_ic"],
            summary["icir"],
            summary["q_spread"],
            summary["n_dates"],
        )

    oof_frame = pd.concat(oof, ignore_index=True)
    overall = metrics.summarise(oof_frame)
    overall["folds"] = len(fold_metrics)

    if booster is None:
        raise RuntimeError("no CV folds produced a model")

    importance = shap_importance(booster, oof_frame.merge(panel, on=["symbol", "date"]))
    logger.info("top features:\n{}", importance.head(6).to_string(index=False))

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    oof_frame.to_parquet(ARTIFACT_DIR / f"oof-{stamp}.parquet", index=False)
    booster.save_model(str(ARTIFACT_DIR / f"lgbm-{stamp}.txt"))
    (ARTIFACT_DIR / f"metrics-{stamp}.json").write_text(
        json.dumps(
            {"overall": overall, "folds": fold_metrics, "panel": shape}, indent=2, default=str
        )
    )

    if log_mlflow:
        # Artifacts and metrics are already on disk above; a tracking-server problem must
        # not discard a finished run.
        try:
            _log_to_mlflow(params, shape, overall, fold_metrics, importance, horizon, embargo)
        except Exception as exc:  # noqa: BLE001
            logger.warning("MLflow logging failed ({}) — artifacts still written", exc)

    logger.info("OVERALL rank_ic={rank_ic:.4f} icir={icir:.2f}".format(**overall))
    return overall


def _log_to_mlflow(
    params: dict,
    shape: dict,
    overall: dict,
    fold_metrics: list[dict],
    importance: pd.DataFrame,
    horizon: int,
    embargo: int,
) -> None:
    import mlflow

    mlflow.set_tracking_uri(f"sqlite:///{MLFLOW_DB.as_posix()}")
    mlflow.set_experiment("quantis-xs-equity")

    with mlflow.start_run():
        mlflow.log_params(
            {**params, "horizon": horizon, "embargo": embargo, "features": len(FEATURE_NAMES)}
        )
        mlflow.log_params({f"panel_{k}": v for k, v in shape.items()})
        mlflow.log_metrics({k: v for k, v in overall.items() if isinstance(v, int | float)})
        for row in fold_metrics:
            mlflow.log_metrics(
                {f"fold{row['fold']}_{k}": v for k, v in row.items() if isinstance(v, int | float)}
            )
        mlflow.log_text(importance.to_string(index=False), "shap_importance.txt")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train the Quantis cross-sectional model.")
    parser.add_argument("--folds", type=int, default=6)
    parser.add_argument("--horizon", type=int, default=DEFAULT_HORIZON)
    parser.add_argument("--embargo", type=int, default=5)
    parser.add_argument("--rounds", type=int, default=NUM_ROUNDS)
    parser.add_argument("--no-mlflow", action="store_true")
    args = parser.parse_args(argv)

    run(
        folds=args.folds,
        horizon=args.horizon,
        embargo=args.embargo,
        num_rounds=args.rounds,
        log_mlflow=not args.no_mlflow,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

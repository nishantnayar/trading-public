"""Training-pipeline tests on synthetic panels — no database required.

The important one is `test_shuffled_labels_destroy_the_signal`: if a model can still
score an IC after the labels are shuffled within each date, the pipeline is leaking
somewhere, and every metric it reports is fiction.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantis.features.definitions import FEATURE_NAMES
from quantis.models import metrics
from quantis.models.cv import PurgedWalkForwardCV
from quantis.models.train import LGBM_PARAMS, fit_fold, shap_importance


@pytest.fixture
def synthetic() -> pd.DataFrame:
    """Panel where the label is a noisy linear function of two features."""
    rng = np.random.default_rng(0)
    dates = pd.bdate_range("2022-01-03", periods=400)
    symbols = [f"S{i:03d}" for i in range(60)]

    rows = []
    for date in dates:
        frame = pd.DataFrame(
            rng.normal(size=(len(symbols), len(FEATURE_NAMES))), columns=FEATURE_NAMES
        )
        frame["symbol"] = symbols
        frame["date"] = date
        signal = 1.0 * frame["mom_12_1"] - 0.7 * frame["vol_60d"]
        noise = rng.normal(scale=1.5, size=len(symbols))
        raw = signal + noise
        frame["label"] = (raw - raw.mean()) / raw.std(ddof=0)
        rows.append(frame)

    return pd.concat(rows, ignore_index=True)


@pytest.fixture
def fast_params() -> dict:
    return {**LGBM_PARAMS, "learning_rate": 0.1, "num_leaves": 15, "min_child_samples": 50}


def test_model_recovers_a_planted_signal(synthetic: pd.DataFrame, fast_params: dict) -> None:
    cutoff = synthetic["date"].quantile(0.7)
    train = synthetic[synthetic["date"] <= cutoff]
    valid = synthetic[synthetic["date"] > cutoff]

    _, scored = fit_fold(train, valid, fast_params, num_rounds=120)
    assert metrics.summarise(scored)["rank_ic"] > 0.15


def test_shuffled_labels_destroy_the_signal(synthetic: pd.DataFrame, fast_params: dict) -> None:
    """Permutation control: shuffling labels within each date must collapse IC to ~0."""
    rng = np.random.default_rng(7)
    shuffled = synthetic.copy()
    shuffled["label"] = shuffled.groupby("date")["label"].transform(
        lambda values: rng.permutation(values.to_numpy())
    )

    cutoff = shuffled["date"].quantile(0.7)
    train = shuffled[shuffled["date"] <= cutoff]
    valid = shuffled[shuffled["date"] > cutoff]

    _, scored = fit_fold(train, valid, fast_params, num_rounds=120)
    assert abs(metrics.summarise(scored)["rank_ic"]) < 0.05


def test_predictions_cover_every_validation_row(synthetic: pd.DataFrame, fast_params: dict) -> None:
    cutoff = synthetic["date"].quantile(0.8)
    valid = synthetic[synthetic["date"] > cutoff]
    _, scored = fit_fold(synthetic[synthetic["date"] <= cutoff], valid, fast_params, 60)

    assert len(scored) == len(valid)
    assert scored["pred"].notna().all()


def test_cv_folds_train_and_score_end_to_end(synthetic: pd.DataFrame, fast_params: dict) -> None:
    cv = PurgedWalkForwardCV(n_splits=3, horizon=5, embargo=5, min_train_dates=120)
    results = []

    for train_idx, valid_idx in cv.split(synthetic):
        _, scored = fit_fold(synthetic.iloc[train_idx], synthetic.iloc[valid_idx], fast_params, 60)
        results.append(metrics.summarise(scored)["rank_ic"])

    assert len(results) >= 2
    assert all(np.isfinite(results))


def test_shap_ranks_the_planted_features_highest(
    synthetic: pd.DataFrame, fast_params: dict
) -> None:
    booster, _ = fit_fold(
        synthetic[synthetic["date"] <= synthetic["date"].quantile(0.7)],
        synthetic[synthetic["date"] > synthetic["date"].quantile(0.7)],
        fast_params,
        120,
    )
    importance = shap_importance(booster, synthetic, max_rows=5_000)

    assert list(importance.columns) == ["feature", "mean_abs_shap"]
    assert len(importance) == len(FEATURE_NAMES)
    assert set(importance["feature"].head(2)) == {"mom_12_1", "vol_60d"}

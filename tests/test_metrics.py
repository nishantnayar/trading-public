"""Cross-sectional metric behaviour under known signal conditions."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantis.models import metrics


def panel(n_dates: int = 30, n_names: int = 40, noise: float = 0.0, seed: int = 0):
    """Panel whose prediction equals the label plus optional noise."""
    rng = np.random.default_rng(seed)
    frames = []
    for d in range(n_dates):
        label = rng.normal(size=n_names)
        pred = label + rng.normal(scale=noise, size=n_names) if noise else label
        frames.append(
            pd.DataFrame(
                {
                    "date": pd.Timestamp("2024-01-01") + pd.Timedelta(days=d),
                    "symbol": [f"S{i}" for i in range(n_names)],
                    "label": label,
                    "pred": pred,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def test_perfect_prediction_gives_ic_one() -> None:
    ics = metrics.rank_ic_by_date(panel())
    assert ics.mean() == pytest.approx(1.0)


def test_inverted_prediction_gives_ic_minus_one() -> None:
    frame = panel()
    frame["pred"] = -frame["label"]
    assert metrics.rank_ic_by_date(frame).mean() == pytest.approx(-1.0)


def test_random_prediction_gives_ic_near_zero() -> None:
    frame = panel(n_dates=200, seed=1)
    rng = np.random.default_rng(99)
    frame["pred"] = rng.normal(size=len(frame))

    mean_ic = metrics.rank_ic_by_date(frame).mean()
    assert abs(mean_ic) < 0.05


def test_ic_is_computed_per_date_not_pooled() -> None:
    """Two dates with opposite in-date signal must average to ~0, not correlate globally.

    A pooled correlation would be fooled by cross-date level differences; this pins the
    per-date behaviour.
    """
    good = panel(n_dates=1, seed=2)
    bad = panel(n_dates=1, seed=3)
    bad["date"] = bad["date"] + pd.Timedelta(days=1)
    bad["pred"] = -bad["label"]

    ics = metrics.rank_ic_by_date(pd.concat([good, bad], ignore_index=True))
    assert len(ics) == 2
    assert ics.mean() == pytest.approx(0.0, abs=1e-9)


def test_thin_dates_are_skipped() -> None:
    frame = panel(n_dates=5, n_names=5)
    assert len(metrics.rank_ic_by_date(frame, min_names=20)) == 0


def test_quantile_spread_positive_for_good_signal() -> None:
    assert metrics.quantile_spread(panel()) > 0


def test_quantile_spread_negative_for_inverted_signal() -> None:
    frame = panel()
    frame["pred"] = -frame["label"]
    assert metrics.quantile_spread(frame) < 0


def test_summarise_reports_expected_keys() -> None:
    out = metrics.summarise(panel(n_dates=40, noise=1.0, seed=5))
    assert set(out) >= {
        "n_dates",
        "rank_ic",
        "ic_std",
        "icir",
        "ic_t_stat",
        "ic_hit_rate",
        "q_spread",
    }
    assert out["n_dates"] == 40
    assert 0.0 <= out["ic_hit_rate"] <= 1.0


def test_summarise_handles_empty_input() -> None:
    empty = pd.DataFrame({"date": [], "pred": [], "label": []})
    out = metrics.summarise(empty)
    assert out["n_dates"] == 0


def test_noise_degrades_ic_monotonically() -> None:
    clean = metrics.summarise(panel(n_dates=60, noise=0.5, seed=7))["rank_ic"]
    noisy = metrics.summarise(panel(n_dates=60, noise=4.0, seed=7))["rank_ic"]
    assert clean > noisy

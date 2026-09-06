"""Purged walk-forward CV — the guard against overlapping-label leakage."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantis.models.cv import PurgedWalkForwardCV, gap_report


@pytest.fixture
def dates() -> pd.Series:
    return pd.Series(pd.bdate_range("2020-01-01", periods=1500))


@pytest.fixture
def panel(dates: pd.Series) -> pd.DataFrame:
    """Long frame: 3 symbols per date."""
    return pd.DataFrame(
        {
            "date": np.repeat(dates.to_numpy(), 3),
            "symbol": np.tile(["AAA", "BBB", "CCC"], len(dates)),
        }
    )


def test_train_always_precedes_validation(dates: pd.Series) -> None:
    cv = PurgedWalkForwardCV(n_splits=5, horizon=5, embargo=5)
    for train_dates, val_dates in cv.date_splits(dates):
        assert train_dates.max() < val_dates.min()


def test_gap_is_at_least_horizon_plus_embargo(dates: pd.Series) -> None:
    """The core purge guarantee: no train label window can reach the validation block."""
    horizon, embargo = 5, 5
    cv = PurgedWalkForwardCV(n_splits=5, horizon=horizon, embargo=embargo)
    unique = np.array(sorted(pd.unique(dates)))

    for train_dates, val_dates in cv.date_splits(dates):
        train_end_pos = int(np.where(unique == train_dates[-1])[0][0])
        val_start_pos = int(np.where(unique == val_dates[0])[0][0])
        assert val_start_pos - train_end_pos >= horizon + embargo


def test_a_train_label_window_never_touches_validation(dates: pd.Series) -> None:
    """Stated in label terms: last train date + horizon must land before validation."""
    horizon = 10
    cv = PurgedWalkForwardCV(n_splits=4, horizon=horizon, embargo=3)
    unique = np.array(sorted(pd.unique(dates)))

    for train_dates, val_dates in cv.date_splits(dates):
        last_train = int(np.where(unique == train_dates[-1])[0][0])
        label_ends_at = last_train + horizon
        val_start = int(np.where(unique == val_dates[0])[0][0])
        assert label_ends_at < val_start


def test_validation_blocks_do_not_overlap(dates: pd.Series) -> None:
    cv = PurgedWalkForwardCV(n_splits=5, horizon=5)
    seen: set = set()
    for _, val_dates in cv.date_splits(dates):
        current = set(val_dates)
        assert not (current & seen)
        seen |= current


def test_training_window_expands(dates: pd.Series) -> None:
    cv = PurgedWalkForwardCV(n_splits=5, horizon=5)
    sizes = [len(train) for train, _ in cv.date_splits(dates)]
    assert sizes == sorted(sizes)
    assert sizes[0] < sizes[-1]


def test_split_returns_disjoint_row_indices(panel: pd.DataFrame) -> None:
    cv = PurgedWalkForwardCV(n_splits=3, horizon=5)
    for train_idx, val_idx in cv.split(panel):
        assert len(train_idx) > 0
        assert len(val_idx) > 0
        assert not set(train_idx) & set(val_idx)


def test_split_keeps_whole_dates_together(panel: pd.DataFrame) -> None:
    """A date must land entirely in train or entirely in validation, never split.

    Splitting a date would let the model see part of a cross-section it is scored on.
    """
    cv = PurgedWalkForwardCV(n_splits=3, horizon=5)
    for train_idx, val_idx in cv.split(panel):
        train_dates = set(panel.iloc[train_idx]["date"])
        val_dates = set(panel.iloc[val_idx]["date"])
        assert not train_dates & val_dates


def test_larger_horizon_widens_the_gap(dates: pd.Series) -> None:
    small = PurgedWalkForwardCV(n_splits=3, horizon=5, embargo=0)
    large = PurgedWalkForwardCV(n_splits=3, horizon=60, embargo=0)

    small_train = small.date_splits(dates)[0][0]
    large_train = large.date_splits(dates)[0][0]
    assert len(large_train) < len(small_train)


def test_rejects_invalid_configuration() -> None:
    with pytest.raises(ValueError, match="n_splits must be >= 2"):
        PurgedWalkForwardCV(n_splits=1)
    with pytest.raises(ValueError, match="horizon must be >= 1"):
        PurgedWalkForwardCV(horizon=0)
    with pytest.raises(ValueError, match="embargo must be >= 0"):
        PurgedWalkForwardCV(embargo=-1)


def test_raises_when_history_too_short_for_any_fold() -> None:
    short = pd.Series(pd.bdate_range("2024-01-01", periods=100))
    cv = PurgedWalkForwardCV(n_splits=3, horizon=5, min_train_dates=252)
    with pytest.raises(ValueError, match="no usable folds"):
        cv.date_splits(short)


def test_gap_report_shape(dates: pd.Series) -> None:
    cv = PurgedWalkForwardCV(n_splits=4, horizon=5, embargo=5)
    report = gap_report(cv, dates)

    assert len(report) == len(cv.date_splits(dates))
    assert (report["gap_sessions"] >= 10).all()
    assert report["train_dates"].is_monotonic_increasing

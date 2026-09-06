"""Label correctness and the label/feature leakage boundary."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantis.models import labels as lb


@pytest.fixture
def close() -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-01", periods=40)
    return pd.DataFrame(
        {
            "AAA": np.linspace(100, 139, 40),
            "BBB": np.linspace(50, 50, 40),
            "CCC": np.linspace(200, 161, 40),
        },
        index=dates,
    )


def test_forward_return_looks_exactly_horizon_ahead(close: pd.DataFrame) -> None:
    out = lb.forward_return(close, horizon=5)
    expected = close["AAA"].iloc[10] / close["AAA"].iloc[5] - 1
    assert out["AAA"].iloc[5] == pytest.approx(expected)


def test_trailing_rows_are_unlabelled(close: pd.DataFrame) -> None:
    """The last `horizon` dates have no observed future — must stay NaN, not 0."""
    out = lb.forward_return(close, horizon=5)
    assert out.iloc[-5:].isna().all().all()
    assert out.iloc[-6].notna().all()


def test_flat_price_has_zero_forward_return(close: pd.DataFrame) -> None:
    out = lb.forward_return(close, horizon=5)
    assert out["BBB"].iloc[10] == pytest.approx(0.0)


def test_horizon_must_be_positive(close: pd.DataFrame) -> None:
    """A zero or negative horizon would make the label a same-day or past return."""
    for bad in (0, -5):
        with pytest.raises(ValueError, match="horizon must be >= 1"):
            lb.forward_return(close, horizon=bad)


def test_zscore_is_centred_and_scaled() -> None:
    frame = pd.DataFrame({f"S{i}": [float(i)] for i in range(30)})
    out = lb.cross_sectional_zscore(frame, min_names=5, clip=None)

    assert out.iloc[0].mean() == pytest.approx(0.0, abs=1e-12)
    assert out.iloc[0].std(ddof=0) == pytest.approx(1.0)


def test_zscore_is_per_date_not_pooled() -> None:
    """Each row is standardised independently; a row-wide level shift must vanish."""
    base = {f"S{i}": [float(i), float(i) + 100.0] for i in range(30)}
    out = lb.cross_sectional_zscore(pd.DataFrame(base), min_names=5, clip=None)
    pd.testing.assert_series_equal(out.iloc[0], out.iloc[1], check_names=False, check_index=False)


def test_thin_dates_are_dropped() -> None:
    """Fewer than `min_names` observations yields NaN rather than a noisy z-score."""
    frame = pd.DataFrame({"AAA": [1.0], "BBB": [2.0], "CCC": [3.0]})
    out = lb.cross_sectional_zscore(frame, min_names=20)
    assert out.isna().all().all()


def test_zscore_clips_outliers() -> None:
    values = {f"S{i}": [1.0] for i in range(30)}
    values["S0"] = [1e6]  # a halted/acquired name
    out = lb.cross_sectional_zscore(pd.DataFrame(values), min_names=5, clip=5.0)
    assert out.iloc[0].max() == pytest.approx(5.0)
    assert out.iloc[0].abs().max() <= 5.0


def test_zero_variance_date_is_nan() -> None:
    """If every name returns the same, relative strength is undefined — not 0."""
    frame = pd.DataFrame({f"S{i}": [7.0] for i in range(30)})
    out = lb.cross_sectional_zscore(frame, min_names=5)
    assert out.iloc[0].isna().all()


def test_make_labels_ranks_within_date(close: pd.DataFrame) -> None:
    """AAA rises, CCC falls, so AAA's label must exceed CCC's on the same date."""
    wide = lb.make_labels(close, horizon=5, min_names=3)
    row = wide.iloc[10]
    assert row["AAA"] > row["CCC"]


def test_to_long_drops_unlabelled_rows(close: pd.DataFrame) -> None:
    wide = lb.make_labels(close, horizon=5, min_names=3)
    long = lb.to_long(wide)

    assert set(long.columns) == {"date", "symbol", "label"}
    assert long["label"].notna().all()
    # The final `horizon` dates are unlabelled and must not appear.
    assert long["date"].max() <= close.index[-6]

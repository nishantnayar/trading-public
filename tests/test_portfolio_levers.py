"""Phase 6 construction levers: no-trade buffer and sector neutralization."""

from __future__ import annotations

import pandas as pd
import pytest

from quantis.backtest import portfolio as pf


def _panel(n_dates: int, n_names: int, flip_at: int | None = None) -> pd.DataFrame:
    """Scores rise with symbol index; optionally reverse the ranking after `flip_at`."""
    dates = pd.bdate_range("2024-01-01", periods=n_dates)
    rows = []
    for d, date in enumerate(dates):
        for i in range(n_names):
            pred = float(n_names - 1 - i) if flip_at is not None and d >= flip_at else float(i)
            rows.append({"date": date, "symbol": f"S{i:02d}", "pred": pred})
    return pd.DataFrame(rows)


def test_zero_buffer_matches_phase5_constructor() -> None:
    """buffer=0 must not quietly change the Phase 5 book, even with a prior book."""
    scores = pd.Series({f"S{i:02d}": float(i) for i in range(40)})
    phase5 = pf.leg_weights(scores)
    assert pf.buffered_legs(scores, buffer=0).equals(phase5)
    assert pf.buffered_legs(scores, previous=phase5, buffer=0).equals(phase5)


def test_buffer_keeps_an_incumbent_just_outside_the_quintile() -> None:
    """S31 is long on day 0 (ranks 32-39 are the top 8 of 40). After a 1-rank drop it
    is out of the top quintile but still in the top two — buffer=1 must keep it."""
    scores = pd.Series({f"S{i:02d}": float(i) for i in range(40)})
    opened = pf.buffered_legs(scores, buffer=1)
    assert opened["S32"] > 0  # edge of the top quintile (ranks 33-40)

    slipped = scores.copy()
    slipped["S32"] = 31.4  # now ranks just below the top-8 cutoff
    slipped["S31"] = 32.0  # takes its place in the raw quintile
    kept = pf.buffered_legs(slipped, previous=opened, buffer=1)
    assert kept["S32"] > 0
    # Fresh construction with no memory would have sold S32.
    fresh = pf.leg_weights(slipped)
    assert fresh["S32"] == 0.0


def test_buffer_evicts_once_the_name_leaves_the_band() -> None:
    scores = pd.Series({f"S{i:02d}": float(i) for i in range(40)})
    opened = pf.buffered_legs(scores, buffer=1)
    crashed = scores.copy()
    crashed["S39"] = -1.0  # worst name now
    evicted = pf.buffered_legs(crashed, previous=opened, buffer=1)
    assert evicted["S39"] == 0.0


def test_buffer_does_not_grow_the_book() -> None:
    scores = pd.Series({f"S{i:02d}": float(i) for i in range(40)})
    opened = pf.buffered_legs(scores, buffer=1)
    slipped = scores.copy()
    slipped["S32"] = 28.0
    kept = pf.buffered_legs(slipped, previous=opened, buffer=1)
    assert (kept > 0).sum() == 8
    assert (kept < 0).sum() == 8
    assert kept.sum() == pytest.approx(0.0)
    assert kept.abs().sum() == pytest.approx(1.0)


def test_buffer_reduces_turnover_when_ranks_jitter() -> None:
    """A one-rank reshuffle at the cutoff churns the Phase 5 book and should not
    churn the buffered book."""
    dates = pd.bdate_range("2024-01-01", periods=15)
    rows = []
    for d, date in enumerate(dates):
        for i in range(40):
            pred = float(i)
            if d >= 5 and i == 31:
                pred = 32.5  # crosses into the top quintile
            if d >= 5 and i == 32:
                pred = 31.5  # slips just below the cutoff
            rows.append({"date": date, "symbol": f"S{i:02d}", "pred": pred})
    preds = pd.DataFrame(rows)

    base = pf.target_weights(preds, every=5, buffer=0)
    buffered = pf.target_weights(preds, every=5, buffer=1)
    assert pf.annualised_turnover(buffered) < pf.annualised_turnover(base)


def test_rejects_negative_buffer() -> None:
    scores = pd.Series({f"S{i:02d}": float(i) for i in range(40)})
    with pytest.raises(ValueError, match="buffer must be >= 0"):
        pf.buffered_legs(scores, buffer=-1)


def test_sector_neutral_zeroes_each_sector_net() -> None:
    scores = pd.Series({f"S{i:02d}": float(i) for i in range(40)})
    sectors = pd.Series({f"S{i:02d}": "Tech" if i < 20 else "Health" for i in range(40)})
    weights = pf.sector_neutral_weights(scores, sectors, min_names=10)
    assert weights[sectors[sectors == "Tech"].index].sum() == pytest.approx(0.0)
    assert weights[sectors[sectors == "Health"].index].sum() == pytest.approx(0.0)
    assert weights.sum() == pytest.approx(0.0)
    assert weights.abs().sum() == pytest.approx(1.0)


def test_thin_sector_is_left_flat() -> None:
    scores = pd.Series({f"S{i:02d}": float(i) for i in range(24)})
    sectors = pd.Series({f"S{i:02d}": "Big" if i < 20 else "Tiny" for i in range(24)})
    weights = pf.sector_neutral_weights(scores, sectors, min_names=10)
    assert weights[sectors[sectors == "Tiny"].index].abs().sum() == 0.0
    assert weights[sectors[sectors == "Big"].index].abs().sum() == pytest.approx(1.0)

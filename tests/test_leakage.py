"""Leakage guards — the credibility tests for the whole system.

A feature dated `t` must depend only on bars up to and including `t`. If any of these
fail, every downstream backtest number is fiction.
"""

from __future__ import annotations

import ast
import inspect

import numpy as np
import pandas as pd
import pytest

from quantis.features import definitions as fd
from quantis.features.build import build_features, to_wide


@pytest.fixture
def close() -> pd.DataFrame:
    dates = pd.bdate_range("2023-01-02", periods=320)
    rng = np.random.default_rng(42)
    data = {
        sym: 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.012, 320)))
        for sym in ("AAA", "BBB", "CCC")
    }
    return pd.DataFrame(data, index=dates)


@pytest.fixture
def volume(close: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    return pd.DataFrame(
        rng.uniform(1e6, 5e6, close.shape), index=close.index, columns=close.columns
    )


def test_future_bars_cannot_change_past_features(close: pd.DataFrame, volume: pd.DataFrame) -> None:
    """The core guard: truncating the future must not alter any earlier feature value.

    Computed on the full history, then on history truncated at `cut`. Every overlapping
    value must match exactly. A `shift(-n)` or centred window anywhere breaks this.
    """
    cut = 250
    full = fd.compute_all(close, volume)
    truncated = fd.compute_all(close.iloc[:cut], volume.iloc[:cut])

    for name in fd.FEATURE_NAMES:
        a = full[name].iloc[:cut]
        b = truncated[name]
        pd.testing.assert_frame_equal(a, b, check_freq=False, obj=name)


def test_mutating_the_last_bar_leaves_earlier_features_untouched(
    close: pd.DataFrame, volume: pd.DataFrame
) -> None:
    """A shock on the final day must not propagate backwards."""
    shocked = close.copy()
    shocked.iloc[-1] *= 5.0

    base = fd.compute_all(close, volume)
    after = fd.compute_all(shocked, volume)

    for name in fd.FEATURE_NAMES:
        pd.testing.assert_frame_equal(
            base[name].iloc[:-1], after[name].iloc[:-1], check_freq=False, obj=name
        )


def test_no_negative_shift_or_centred_window_in_source() -> None:
    """Static guard so a future edit cannot quietly reintroduce look-ahead.

    Walks the AST rather than the raw text, so prose in docstrings that *describes* the
    forbidden patterns doesn't trip it.
    """
    tree = ast.parse(inspect.getsource(fd))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.attr if isinstance(node.func, ast.Attribute) else None

        if name == "shift":
            for arg in node.args:
                negative = (
                    isinstance(arg, ast.UnaryOp)
                    and isinstance(arg.op, ast.USub)
                    and isinstance(arg.operand, ast.Constant)
                )
                assert not negative, "shift() with a negative offset looks into the future"

        for keyword in node.keywords:
            if keyword.arg == "center":
                is_true = isinstance(keyword.value, ast.Constant) and keyword.value.value
                assert not is_true, f"{name}(center=True) peeks forward"


def test_features_never_reference_another_symbol(close: pd.DataFrame, volume: pd.DataFrame) -> None:
    """Per-name features must be independent across the cross-section.

    Rolling windows on a wide frame are column-wise, but this pins the behaviour: changing
    BBB's whole history must leave AAA's features identical.
    """
    altered = close.copy()
    altered["BBB"] *= 3.0

    base = fd.compute_all(close, volume)
    after = fd.compute_all(altered, volume)

    for name in fd.FEATURE_NAMES:
        pd.testing.assert_series_equal(base[name]["AAA"], after[name]["AAA"], obj=name)


def test_build_features_preserves_symbol_date_alignment(
    close: pd.DataFrame, volume: pd.DataFrame
) -> None:
    """The long-format reshape must not transpose symbols against dates."""
    bars = (
        close.stack(future_stack=True)
        .rename("close")
        .reset_index()
        .rename(columns={"level_0": "date", "level_1": "symbol"})
    )
    vols = (
        volume.stack(future_stack=True)
        .rename("volume")
        .reset_index()
        .rename(columns={"level_0": "date", "level_1": "symbol"})
    )
    bars = bars.merge(vols, on=["date", "symbol"])

    wide_close, wide_volume = to_wide(bars)
    out = build_features(wide_close, wide_volume)

    probe = out[(out["symbol"] == "AAA") & (out["date"] == close.index[300])]
    expected = fd.compute_all(wide_close, wide_volume)["mom_1m"]["AAA"].iloc[300]
    assert probe["mom_1m"].iloc[0] == pytest.approx(expected)

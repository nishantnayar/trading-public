"""Purged walk-forward cross-validation (López de Prado style).

## Why plain K-fold is wrong here

The label at date `t` spans `t → t + horizon`. With a 5-day horizon, the label for Monday
overlaps the labels for Tue–Fri. A random K-fold split puts Monday in train and Wednesday
in validation, and those two labels share four days of returns — the model is scored on
information it already saw. Reported IC comes out inflated, and the strategy dies live.

Two mechanisms fix it:

- **Purge** — drop training dates whose label window reaches into the validation block.
  With horizon `h`, any train date in `[val_start - h, val_start)` is contaminated.
- **Embargo** — additionally drop training dates immediately *before* the purge zone.
  Serial correlation in features means a bar adjacent to the validation window still
  carries information about it, even when the label windows do not literally overlap.

Splits are **walk-forward** (train always precedes validation), which also respects the
arrow of time: the model is never fit on the future to predict the past.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np
import pandas as pd

DEFAULT_EMBARGO = 5


@dataclass
class PurgedWalkForwardCV:
    """Expanding-window splitter with purge + embargo between train and validation.

    Args:
        n_splits: number of validation blocks.
        horizon: label horizon in trading days — sets the purge width.
        embargo: extra trading days dropped before the purge zone.
        min_train_dates: a fold is skipped if training would be shorter than this.
    """

    n_splits: int = 5
    horizon: int = 5
    embargo: int = DEFAULT_EMBARGO
    min_train_dates: int = 252

    def __post_init__(self) -> None:
        if self.n_splits < 2:
            raise ValueError(f"n_splits must be >= 2, got {self.n_splits}")
        if self.horizon < 1:
            raise ValueError(f"horizon must be >= 1, got {self.horizon}")
        if self.embargo < 0:
            raise ValueError(f"embargo must be >= 0, got {self.embargo}")

    def date_splits(self, dates: pd.Series) -> list[tuple[np.ndarray, np.ndarray]]:
        """Split the *unique sorted dates* into (train_dates, val_dates) blocks."""
        unique = np.array(sorted(pd.unique(dates)))
        n = len(unique)
        if n < self.n_splits + 1:
            raise ValueError(f"need > {self.n_splits} distinct dates, got {n}")

        # Validation blocks tile the tail of the timeline; the first block leaves room for
        # an initial training window.
        block = n // (self.n_splits + 1)
        splits: list[tuple[np.ndarray, np.ndarray]] = []

        for fold in range(self.n_splits):
            val_start = block * (fold + 1)
            val_end = val_start + block if fold < self.n_splits - 1 else n
            val_dates = unique[val_start:val_end]

            # Purge + embargo: cut back from the validation start.
            train_end = val_start - self.horizon - self.embargo
            if train_end < self.min_train_dates:
                continue
            splits.append((unique[:train_end], val_dates))

        if not splits:
            raise ValueError(
                "no usable folds — reduce min_train_dates/n_splits or supply more history"
            )
        return splits

    def split(self, frame: pd.DataFrame, date_column: str = "date") -> Iterator:
        """Yield (train_idx, val_idx) positional indices into a long DataFrame."""
        dates = frame[date_column]
        positions = np.arange(len(frame))

        for train_dates, val_dates in self.date_splits(dates):
            train_mask = dates.isin(set(train_dates)).to_numpy()
            val_mask = dates.isin(set(val_dates)).to_numpy()
            yield positions[train_mask], positions[val_mask]

    def get_n_splits(self, *_args, **_kwargs) -> int:
        """Actual fold count, which may be below `n_splits` if history is short."""
        return self.n_splits


def gap_report(cv: PurgedWalkForwardCV, dates: pd.Series) -> pd.DataFrame:
    """Per-fold summary — sizes and the realised train/validation gap.

    Useful as evidence in the dashboard and as a sanity check that the gap is never
    smaller than `horizon + embargo`.
    """
    unique = np.array(sorted(pd.unique(dates)))
    position = {date: index for index, date in enumerate(unique)}

    rows = []
    for fold, (train_dates, val_dates) in enumerate(cv.date_splits(dates), start=1):
        gap = position[val_dates[0]] - position[train_dates[-1]]
        rows.append(
            {
                "fold": fold,
                "train_dates": len(train_dates),
                "train_end": train_dates[-1],
                "val_start": val_dates[0],
                "val_end": val_dates[-1],
                "val_dates": len(val_dates),
                "gap_sessions": int(gap),
            }
        )
    return pd.DataFrame(rows)

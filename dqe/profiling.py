"""Build a :class:`DatasetProfile` — descriptive stats every check can reuse.

Profiling once, up front, keeps checks fast and consistent: they read from the
profile rather than each recomputing null counts and cardinalities.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pandas.api import types as ptypes

from dqe.types import ColumnProfile, DatasetProfile


def profile_dataset(df: pd.DataFrame, sample_size: int = 5) -> DatasetProfile:
    """Compute structural and per-column statistics for ``df``."""
    columns = [_profile_column(df[name], sample_size) for name in df.columns]
    return DatasetProfile(
        n_rows=len(df),
        n_columns=df.shape[1],
        memory_bytes=int(df.memory_usage(deep=True).sum()),
        columns=columns,
    )


def _profile_column(series: pd.Series, sample_size: int) -> ColumnProfile:
    n = len(series)
    null_count = int(series.isna().sum())
    non_null = series.dropna()
    unique_count = int(non_null.nunique())

    profile = ColumnProfile(
        name=str(series.name),
        dtype=str(series.dtype),
        count=n - null_count,
        null_count=null_count,
        null_fraction=(null_count / n) if n else 0.0,
        unique_count=unique_count,
        unique_fraction=(unique_count / (n - null_count)) if (n - null_count) else 0.0,
        sample_values=_sample(non_null, sample_size),
    )

    if ptypes.is_numeric_dtype(series) and not ptypes.is_bool_dtype(series) and not non_null.empty:
        profile.min = _clean_float(non_null.min())
        profile.max = _clean_float(non_null.max())
        profile.mean = _clean_float(non_null.mean())
        profile.std = _clean_float(non_null.std())

    return profile


def _sample(non_null: pd.Series, k: int) -> list:
    """Return up to ``k`` example values, JSON-safe."""
    head = non_null.head(k).tolist()
    return [_jsonable(v) for v in head]


def _jsonable(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return _clean_float(float(value))
    if isinstance(value, (pd.Timestamp,)):
        return str(value)
    return value


def _clean_float(value: float | None):
    """Convert NaN/inf to None so the value survives JSON serialisation."""
    if value is None:
        return None
    f = float(value)
    if np.isnan(f) or np.isinf(f):
        return None
    return f

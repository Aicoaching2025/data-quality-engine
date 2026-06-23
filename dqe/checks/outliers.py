"""Accuracy — outlier detection on numeric columns.

Uses the IQR (Tukey) rule by default: values beyond ``k`` interquartile ranges
of the first/third quartile are flagged. It's distribution-agnostic and robust,
which makes it a safe default for unknown data. A z-score method is available
via config for roughly-normal columns.

The score is the percentage of in-range values, so a column with a handful of
extreme values still scores high — outliers are a warning signal, not an
automatic failure.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pandas.api import types as ptypes

from dqe.checks.base import Check, register
from dqe.types import CheckResult, DatasetProfile, Dimension


@register
class OutlierCheck(Check):
    name = "outliers"
    dimension = Dimension.ACCURACY
    default_config = {
        "method": "iqr",        # "iqr" or "zscore"
        "iqr_k": 1.5,           # Tukey fence multiplier
        "zscore_threshold": 3.0,
        "min_rows": 20,         # don't bother on tiny columns
        "warn_below": 99.0,
        "fail_below": 95.0,
    }

    def run(self, df: pd.DataFrame, profile: DatasetProfile) -> list[CheckResult]:
        results: list[CheckResult] = []
        method = self.config.get("method", "iqr")
        min_rows = self.config.get("min_rows", 20)

        for col in profile.columns:
            series = df[col.name]
            if not ptypes.is_numeric_dtype(series) or ptypes.is_bool_dtype(series):
                continue
            values = series.dropna()
            if len(values) < min_rows:
                continue

            if method == "zscore":
                outlier_mask, bounds = self._zscore(values)
            else:
                outlier_mask, bounds = self._iqr(values)

            n_outliers = int(outlier_mask.sum())
            frac = n_outliers / len(values)
            score = (1.0 - frac) * 100.0
            if n_outliers == 0:
                message = f"'{col.name}' has no outliers ({method.upper()})."
            else:
                message = (
                    f"'{col.name}' has {n_outliers:,} outlier(s) "
                    f"({frac:.1%}) outside [{bounds[0]:.3g}, {bounds[1]:.3g}]."
                )
            results.append(
                self._result(
                    score=score,
                    message=message,
                    column=col.name,
                    metric=frac,
                    method=method,
                    n_outliers=n_outliers,
                    lower_bound=float(bounds[0]),
                    upper_bound=float(bounds[1]),
                )
            )
        return results

    def _iqr(self, values: pd.Series) -> tuple[pd.Series, tuple[float, float]]:
        q1, q3 = values.quantile(0.25), values.quantile(0.75)
        iqr = q3 - q1
        k = self.config.get("iqr_k", 1.5)
        lower, upper = q1 - k * iqr, q3 + k * iqr
        return (values < lower) | (values > upper), (lower, upper)

    def _zscore(self, values: pd.Series) -> tuple[pd.Series, tuple[float, float]]:
        mean, std = values.mean(), values.std()
        thr = self.config.get("zscore_threshold", 3.0)
        if std == 0 or np.isnan(std):
            return pd.Series(False, index=values.index), (mean, mean)
        lower, upper = mean - thr * std, mean + thr * std
        return (values < lower) | (values > upper), (lower, upper)

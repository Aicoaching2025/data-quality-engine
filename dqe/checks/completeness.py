"""Completeness — are values actually present?

Missing data is the single most common reason a model can't train, so this is
the highest-weighted dimension. One result is emitted per column, scored as the
percentage of non-null values.
"""
from __future__ import annotations

import pandas as pd

from dqe.checks.base import Check, register
from dqe.types import CheckResult, DatasetProfile, Dimension


@register
class CompletenessCheck(Check):
    name = "completeness"
    dimension = Dimension.COMPLETENESS
    # Score is "% present", so default cut points are high: a column that's 5%
    # null already warrants a warning.
    default_config = {"warn_below": 99.0, "fail_below": 90.0}

    def run(self, df: pd.DataFrame, profile: DatasetProfile) -> list[CheckResult]:
        results: list[CheckResult] = []
        n = len(df)
        for col in profile.columns:
            present = 1.0 - col.null_fraction
            score = present * 100.0
            if col.null_count == 0:
                message = f"'{col.name}' has no missing values."
            else:
                message = (
                    f"'{col.name}' is {present:.1%} complete "
                    f"({col.null_count:,} of {n:,} values missing)."
                )
            results.append(
                self._result(
                    score=score,
                    message=message,
                    column=col.name,
                    metric=col.null_fraction,
                    null_count=col.null_count,
                    present_fraction=round(present, 6),
                )
            )
        return results

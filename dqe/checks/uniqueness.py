"""Uniqueness — duplicate rows and primary-key collisions.

Two checks live here:
  * fully duplicated rows (table-level), and
  * uniqueness of a configured primary key (one or more columns).
"""
from __future__ import annotations

import pandas as pd

from dqe.checks.base import Check, register
from dqe.types import CheckResult, DatasetProfile, Dimension, Status


@register
class DuplicateRowsCheck(Check):
    name = "duplicate_rows"
    dimension = Dimension.UNIQUENESS
    default_config = {"warn_below": 100.0, "fail_below": 98.0}

    def run(self, df: pd.DataFrame, profile: DatasetProfile) -> list[CheckResult]:
        n = len(df)
        if n == 0:
            return [self._result(100.0, "Empty dataset — no rows to deduplicate.",
                                 status=Status.WARN)]
        dup_mask = df.duplicated(keep="first")
        dup_count = int(dup_mask.sum())
        unique_fraction = 1.0 - (dup_count / n)
        score = unique_fraction * 100.0
        if dup_count == 0:
            message = "No fully-duplicated rows."
        else:
            message = (
                f"{dup_count:,} duplicated row(s) found "
                f"({dup_count / n:.1%} of the dataset)."
            )
        return [
            self._result(
                score=score,
                message=message,
                metric=dup_count / n,
                duplicate_rows=dup_count,
            )
        ]


@register
class PrimaryKeyCheck(Check):
    name = "primary_key"
    dimension = Dimension.UNIQUENESS
    # Only runs when a key is configured: checks.primary_key.key: [col, ...]
    default_config = {"key": None, "warn_below": 100.0, "fail_below": 100.0}

    def run(self, df: pd.DataFrame, profile: DatasetProfile) -> list[CheckResult]:
        key = self.config.get("key")
        if not key:
            return []  # no key declared → nothing to assert
        if isinstance(key, str):
            key = [key]

        missing_cols = [c for c in key if c not in df.columns]
        if missing_cols:
            return [
                self._result(
                    score=0.0,
                    message=f"Primary-key column(s) not found: {missing_cols}.",
                    status=Status.FAIL,
                    key=key,
                    missing_columns=missing_cols,
                )
            ]

        n = len(df)
        dup_mask = df.duplicated(subset=key, keep="first")
        dup_count = int(dup_mask.sum())
        score = (1.0 - dup_count / n) * 100.0 if n else 100.0
        label = ", ".join(key)
        if dup_count == 0:
            message = f"Primary key ({label}) is unique across all rows."
        else:
            message = f"Primary key ({label}) has {dup_count:,} collision(s)."
        return [
            self._result(
                score=score,
                message=message,
                metric=dup_count / n if n else 0.0,
                key=key,
                collisions=dup_count,
            )
        ]

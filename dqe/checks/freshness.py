"""Timeliness — is the data recent enough to be useful?

Runs only when a date column and a reference "now" are configured. Because the
engine forbids hidden clock reads for reproducibility, the reference time is
passed in explicitly (the CLI stamps it once at run start).

Config::

    checks:
      freshness:
        column: event_date
        max_age_days: 30
        warn_age_days: 7
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from dqe.checks.base import Check, register
from dqe.types import CheckResult, DatasetProfile, Dimension, Status


@register
class FreshnessCheck(Check):
    name = "freshness"
    dimension = Dimension.TIMELINESS
    default_config = {
        "column": None,
        "max_age_days": None,
        "warn_age_days": None,
        # reference_time is injected by the engine, not set in config files.
        "reference_time": None,
    }

    def run(self, df: pd.DataFrame, profile: DatasetProfile) -> list[CheckResult]:
        col = self.config.get("column")
        max_age = self.config.get("max_age_days")
        if not col or max_age is None:
            return []
        if col not in df.columns:
            return [
                self._result(
                    0.0, f"Freshness column '{col}' not found.",
                    column=col, status=Status.FAIL,
                )
            ]

        ts = pd.to_datetime(df[col], errors="coerce")
        if ts.notna().sum() == 0:
            return [
                self._result(
                    0.0, f"Column '{col}' has no parseable dates.",
                    column=col, status=Status.FAIL,
                )
            ]

        reference = self.config.get("reference_time") or datetime.now()
        reference = pd.Timestamp(reference)
        latest = ts.max()
        age_days = (reference - latest).total_seconds() / 86400.0

        warn_age = self.config.get("warn_age_days") or (max_age / 2)
        if age_days <= warn_age:
            status, score = Status.PASS, 100.0
        elif age_days <= max_age:
            status, score = Status.WARN, 75.0
        else:
            status, score = Status.FAIL, 30.0

        message = (
            f"Most recent '{col}' is {age_days:.1f} day(s) old "
            f"(threshold: {max_age} days)."
        )
        return [
            self._result(
                score=score, message=message, column=col,
                metric=age_days, status=status,
                latest=str(latest), max_age_days=max_age,
            )
        ]

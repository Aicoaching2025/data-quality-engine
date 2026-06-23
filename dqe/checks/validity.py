"""Validity — configured business rules: value ranges and allowed sets.

These checks only run when rules are declared in config, so they impose no
opinion on unknown data but become powerful once you encode domain knowledge.

Config::

    checks:
      range:
        rules:
          age: {min: 0, max: 120}
          revenue: {min: 0}
      allowed_values:
        rules:
          status: ["active", "churned", "trial"]
          country: {values: ["US", "CA", "GB"], case_insensitive: true}
"""
from __future__ import annotations

import pandas as pd
from pandas.api import types as ptypes

from dqe.checks.base import Check, register
from dqe.types import CheckResult, DatasetProfile, Dimension


@register
class RangeCheck(Check):
    name = "range"
    dimension = Dimension.CONSISTENCY
    default_config = {"rules": None, "warn_below": 100.0, "fail_below": 99.0}

    def run(self, df: pd.DataFrame, profile: DatasetProfile) -> list[CheckResult]:
        rules: dict | None = self.config.get("rules")
        if not rules:
            return []
        results: list[CheckResult] = []
        for col, rule in rules.items():
            if col not in df.columns:
                continue
            series = df[col].dropna()
            if series.empty or not ptypes.is_numeric_dtype(series):
                continue
            lo, hi = rule.get("min"), rule.get("max")
            mask = pd.Series(False, index=series.index)
            if lo is not None:
                mask |= series < lo
            if hi is not None:
                mask |= series > hi
            violations = int(mask.sum())
            score = (1.0 - violations / len(series)) * 100.0
            bound_txt = self._describe_bounds(lo, hi)
            if violations == 0:
                message = f"All '{col}' values fall within {bound_txt}."
            else:
                message = (
                    f"'{col}' has {violations:,} value(s) outside {bound_txt}."
                )
            results.append(
                self._result(
                    score=score,
                    message=message,
                    column=col,
                    metric=violations / len(series),
                    violations=violations,
                    min=lo,
                    max=hi,
                )
            )
        return results

    @staticmethod
    def _describe_bounds(lo, hi) -> str:
        if lo is not None and hi is not None:
            return f"[{lo}, {hi}]"
        if lo is not None:
            return f">= {lo}"
        if hi is not None:
            return f"<= {hi}"
        return "the allowed range"


@register
class AllowedValuesCheck(Check):
    name = "allowed_values"
    dimension = Dimension.VALIDITY
    default_config = {"rules": None, "warn_below": 100.0, "fail_below": 99.0}

    def run(self, df: pd.DataFrame, profile: DatasetProfile) -> list[CheckResult]:
        rules: dict | None = self.config.get("rules")
        if not rules:
            return []
        results: list[CheckResult] = []
        for col, rule in rules.items():
            if col not in df.columns:
                continue
            allowed, case_insensitive = self._parse_rule(rule)
            series = df[col].dropna().astype(str)
            if case_insensitive:
                allowed_set = {v.lower() for v in allowed}
                bad_mask = ~series.str.lower().isin(allowed_set)
            else:
                bad_mask = ~series.isin(set(allowed))
            violations = int(bad_mask.sum())
            score = (1.0 - violations / len(series)) * 100.0 if len(series) else 100.0
            if violations == 0:
                message = f"All '{col}' values are within the allowed set."
            else:
                unexpected = sorted(series[bad_mask].unique())[:5]
                message = (
                    f"'{col}' has {violations:,} value(s) outside the allowed "
                    f"set (e.g. {unexpected})."
                )
            results.append(
                self._result(
                    score=score,
                    message=message,
                    column=col,
                    metric=violations / len(series) if len(series) else 0.0,
                    violations=violations,
                    allowed=list(allowed),
                )
            )
        return results

    @staticmethod
    def _parse_rule(rule) -> tuple[list, bool]:
        if isinstance(rule, dict):
            return rule.get("values", []), bool(rule.get("case_insensitive", False))
        return list(rule), False

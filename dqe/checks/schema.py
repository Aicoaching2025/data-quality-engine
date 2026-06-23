"""Schema validity — does the data match the expected contract?

When an expected schema is configured, this verifies that required columns are
present, that no unexpected columns have crept in, and that dtypes match. With
no schema configured the check is a no-op (it returns nothing), so the engine
still runs cleanly on unknown data.

Config::

    checks:
      schema:
        expected:
          customer_id: int
          signup_date: datetime
          revenue: float
        allow_extra_columns: true
"""
from __future__ import annotations

import pandas as pd
from pandas.api import types as ptypes

from dqe.checks.base import Check, register
from dqe.types import CheckResult, DatasetProfile, Dimension, Status


def _is_text(series: pd.Series) -> bool:
    """Treat object and the (pandas 2.x/3.x) string dtypes uniformly as text.

    pandas 3.0 infers a dedicated ``StringDtype`` for text columns, for which
    ``is_object_dtype`` is False — so we accept either.
    """
    return ptypes.is_string_dtype(series) or ptypes.is_object_dtype(series)


# Map friendly type names in config to predicate functions over a pandas Series.
_TYPE_PREDICATES = {
    "int": ptypes.is_integer_dtype,
    "integer": ptypes.is_integer_dtype,
    "float": ptypes.is_float_dtype,
    "number": ptypes.is_numeric_dtype,
    "numeric": ptypes.is_numeric_dtype,
    "bool": ptypes.is_bool_dtype,
    "boolean": ptypes.is_bool_dtype,
    "datetime": ptypes.is_datetime64_any_dtype,
    "date": ptypes.is_datetime64_any_dtype,
    "str": _is_text,
    "string": _is_text,
    "object": _is_text,
    "category": isinstance,  # handled specially below
}


@register
class SchemaCheck(Check):
    name = "schema"
    dimension = Dimension.VALIDITY
    default_config = {"expected": None, "allow_extra_columns": True}

    def run(self, df: pd.DataFrame, profile: DatasetProfile) -> list[CheckResult]:
        expected: dict[str, str] | None = self.config.get("expected")
        if not expected:
            return []  # no contract declared → skip

        results: list[CheckResult] = []
        actual_cols = set(df.columns)

        # 1) Missing required columns — a hard failure per column.
        for col, expected_type in expected.items():
            if col not in actual_cols:
                results.append(
                    self._result(
                        score=0.0,
                        message=f"Required column '{col}' is missing.",
                        column=col,
                        status=Status.FAIL,
                        expected_type=expected_type,
                    )
                )
                continue

            # 2) dtype conformance for present columns.
            ok, actual = self._dtype_matches(df[col], expected_type)
            if ok:
                results.append(
                    self._result(
                        score=100.0,
                        message=f"'{col}' matches expected type ({expected_type}).",
                        column=col,
                        status=Status.PASS,
                        expected_type=expected_type,
                        actual_dtype=actual,
                    )
                )
            else:
                results.append(
                    self._result(
                        score=0.0,
                        message=(
                            f"'{col}' has type '{actual}', expected "
                            f"'{expected_type}'."
                        ),
                        column=col,
                        status=Status.FAIL,
                        expected_type=expected_type,
                        actual_dtype=actual,
                    )
                )

        # 3) Unexpected columns — a warning unless explicitly disallowed.
        if not self.config.get("allow_extra_columns", True):
            for col in actual_cols - set(expected):
                results.append(
                    self._result(
                        score=0.0,
                        message=f"Unexpected column '{col}' not in schema.",
                        column=col,
                        status=Status.FAIL,
                    )
                )
        return results

    @staticmethod
    def _dtype_matches(series: pd.Series, expected_type: str) -> tuple[bool, str]:
        actual = str(series.dtype)
        predicate = _TYPE_PREDICATES.get(str(expected_type).lower())
        if predicate is None:
            # Unknown type name → fall back to a literal dtype-string compare.
            return actual == str(expected_type), actual
        if expected_type.lower() == "category":
            return isinstance(series.dtype, pd.CategoricalDtype), actual
        return bool(predicate(series)), actual


@register
class ConstantColumnCheck(Check):
    """Flag columns that carry no information (a single value, or all null).

    Constant columns are usually a loading bug or a leak of a filter that was
    applied upstream, and they're useless as model features.
    """

    name = "constant_columns"
    dimension = Dimension.CONSISTENCY
    default_config = {"warn_below": 100.0, "fail_below": 100.0}

    def run(self, df: pd.DataFrame, profile: DatasetProfile) -> list[CheckResult]:
        results: list[CheckResult] = []
        for col in profile.columns:
            non_null_unique = col.unique_count
            if col.count == 0:
                results.append(
                    self._result(
                        0.0,
                        f"'{col.name}' is entirely null.",
                        column=col.name,
                        status=Status.FAIL,
                    )
                )
            elif non_null_unique <= 1:
                results.append(
                    self._result(
                        0.0,
                        f"'{col.name}' is constant (single distinct value).",
                        column=col.name,
                        status=Status.WARN,
                        distinct_values=non_null_unique,
                    )
                )
        # No news is good news: emit a single pass result so the dimension scores.
        if not results:
            results.append(
                self._result(100.0, "No constant or empty columns.", status=Status.PASS)
            )
        return results

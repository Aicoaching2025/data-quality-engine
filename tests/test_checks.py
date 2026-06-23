"""Unit tests for the checks and the scoring pipeline.

These run on small in-memory DataFrames so they're fast and deterministic, and
they double as executable documentation of what each check asserts.
"""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from dqe.engine import QualityEngine
from dqe.profiling import profile_dataset
from dqe.checks.completeness import CompletenessCheck
from dqe.checks.uniqueness import DuplicateRowsCheck, PrimaryKeyCheck
from dqe.checks.schema import SchemaCheck, ConstantColumnCheck
from dqe.checks.outliers import OutlierCheck
from dqe.checks.validity import RangeCheck, AllowedValuesCheck
from dqe.types import Status


@pytest.fixture
def df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id": [1, 2, 3, 4, 5],
            "age": [25, 30, None, 41, 200],          # one null, one impossible value
            "status": ["active", "churned", "active", "trial", "bogus"],
            "const": ["x", "x", "x", "x", "x"],      # constant column
        }
    )


def _run(check, df):
    return check.run(df, profile_dataset(df))


def test_completeness_flags_nulls(df):
    results = {r.column: r for r in _run(CompletenessCheck(), df)}
    assert results["id"].status == Status.PASS
    assert results["age"].status in (Status.WARN, Status.FAIL)
    assert results["age"].metric == pytest.approx(0.2)


def test_duplicate_rows_detected():
    d = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})
    (result,) = _run(DuplicateRowsCheck(), d)
    assert result.details["duplicate_rows"] == 1
    assert result.status != Status.PASS


def test_primary_key_collision():
    d = pd.DataFrame({"id": [1, 1, 2]})
    (result,) = _run(PrimaryKeyCheck({"key": ["id"]}), d)
    assert result.details["collisions"] == 1
    assert result.status == Status.FAIL


def test_primary_key_noop_without_config(df):
    assert _run(PrimaryKeyCheck(), df) == []


def test_schema_type_mismatch(df):
    check = SchemaCheck({"expected": {"id": "int", "age": "int"}})
    results = {r.column: r for r in _run(check, df)}
    assert results["id"].status == Status.PASS
    # age has nulls -> stored as float -> mismatch against expected int
    assert results["age"].status == Status.FAIL


def test_schema_missing_column(df):
    check = SchemaCheck({"expected": {"missing_col": "int"}})
    (result,) = _run(check, df)
    assert result.status == Status.FAIL
    assert "missing" in result.message.lower()


def test_constant_column_flagged(df):
    flagged = [r for r in _run(ConstantColumnCheck(), df) if r.column == "const"]
    assert flagged and flagged[0].status == Status.WARN


def test_range_check_catches_impossible_age(df):
    (result,) = _run(RangeCheck({"rules": {"age": {"min": 0, "max": 120}}}), df)
    assert result.details["violations"] == 1
    assert result.status != Status.PASS


def test_allowed_values_catches_bogus(df):
    check = AllowedValuesCheck({"rules": {"status": ["active", "churned", "trial"]}})
    (result,) = _run(check, df)
    assert result.details["violations"] == 1


def test_outliers_on_numeric():
    d = pd.DataFrame({"x": list(range(50)) + [10_000]})  # one extreme outlier
    (result,) = _run(OutlierCheck(), d)
    assert result.details["n_outliers"] >= 1


def test_outliers_skip_small_columns(df):
    # Default min_rows is 20; the 5-row fixture should produce no outlier results.
    assert _run(OutlierCheck(), df) == []


def test_engine_end_to_end_scores_and_grades(df):
    engine = QualityEngine(
        {
            "checks": {
                "primary_key": {"key": ["id"]},
                "range": {"rules": {"age": {"min": 0, "max": 120}}},
                "allowed_values": {"rules": {"status": ["active", "churned", "trial"]}},
            }
        }
    )
    report = engine.assess_dataframe(df, dataset_name="test", reference_time=datetime(2024, 6, 1))
    assert 0 <= report.scorecard.overall_score <= 100
    assert report.scorecard.grade
    assert report.scorecard.verdict in ("READY", "REVIEW", "NOT READY")
    # The fixture is intentionally messy, so there should be findings.
    assert len(report.findings) > 0
    # Round-trips to JSON-safe dict.
    assert isinstance(report.to_dict(), dict)


def test_reference_time_is_reproducible(df):
    """Same data + same reference time -> identical score (no hidden clock)."""
    engine = QualityEngine()
    ref = datetime(2024, 1, 1)
    a = engine.assess_dataframe(df, reference_time=ref)
    b = QualityEngine().assess_dataframe(df, reference_time=ref)
    assert a.scorecard.overall_score == b.scorecard.overall_score

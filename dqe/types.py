"""Core data structures shared across the engine.

Keeping these in one place gives every check, the scorer, and the reporters a
single vocabulary: a check produces a :class:`CheckResult`, results roll up into
:class:`Dimension` scores, and the dataset itself is described by a
:class:`DatasetProfile` of :class:`ColumnProfile` entries.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


class Status(str, Enum):
    """Outcome of a single quality check.

    Inherits from ``str`` so it serialises cleanly to JSON and compares to plain
    strings (``status == "pass"``).
    """

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"

    @property
    def rank(self) -> int:
        """Severity ordering — higher is worse. Useful for sorting findings."""
        return {Status.PASS: 0, Status.WARN: 1, Status.FAIL: 2}[self]


class Dimension(str, Enum):
    """The quality dimension a check contributes to.

    These map to the classic data-quality dimensions used in governance
    frameworks, which makes the final report legible to non-technical
    stakeholders.
    """

    COMPLETENESS = "completeness"   # are values present?
    UNIQUENESS = "uniqueness"       # are rows/keys free of duplication?
    VALIDITY = "validity"           # do values conform to the expected schema/format?
    CONSISTENCY = "consistency"     # are values internally coherent (ranges, constants)?
    ACCURACY = "accuracy"           # are values plausible (outliers)?
    TIMELINESS = "timeliness"       # is the data fresh enough?


# Relative weight of each dimension in the overall readiness score. Completeness
# and validity matter most for whether a model can even train; timeliness only
# applies when a date column is configured, so it carries less default weight.
DIMENSION_WEIGHTS: dict[Dimension, float] = {
    Dimension.COMPLETENESS: 1.0,
    Dimension.UNIQUENESS: 0.8,
    Dimension.VALIDITY: 1.0,
    Dimension.CONSISTENCY: 0.6,
    Dimension.ACCURACY: 0.7,
    Dimension.TIMELINESS: 0.5,
}


@dataclass
class CheckResult:
    """The outcome of one check, optionally scoped to a single column.

    Attributes:
        check: machine name of the check (e.g. ``"completeness"``).
        dimension: which quality dimension this contributes to.
        status: pass / warn / fail.
        score: 0–100 quality contribution (100 = perfect).
        column: the column assessed, or ``None`` for table-level checks.
        message: human-readable, stakeholder-facing summary.
        metric: the headline measured value (e.g. null fraction).
        details: any extra structured context for drill-down.
    """

    check: str
    dimension: Dimension
    status: Status
    score: float
    column: Optional[str] = None
    message: str = ""
    metric: Optional[float] = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["dimension"] = self.dimension.value
        d["status"] = self.status.value
        d["score"] = round(self.score, 2)
        if self.metric is not None:
            d["metric"] = round(float(self.metric), 6)
        return d


@dataclass
class ColumnProfile:
    """Descriptive statistics for a single column."""

    name: str
    dtype: str
    count: int
    null_count: int
    null_fraction: float
    unique_count: int
    unique_fraction: float
    sample_values: list[Any] = field(default_factory=list)
    # Numeric-only fields (None for non-numeric columns)
    min: Optional[float] = None
    max: Optional[float] = None
    mean: Optional[float] = None
    std: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for k in ("null_fraction", "unique_fraction", "min", "max", "mean", "std"):
            if d[k] is not None:
                d[k] = round(float(d[k]), 6)
        return d


@dataclass
class DatasetProfile:
    """A structural snapshot of the dataset under assessment."""

    n_rows: int
    n_columns: int
    memory_bytes: int
    columns: list[ColumnProfile] = field(default_factory=list)

    @property
    def total_cells(self) -> int:
        return self.n_rows * self.n_columns

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_rows": self.n_rows,
            "n_columns": self.n_columns,
            "total_cells": self.total_cells,
            "memory_bytes": self.memory_bytes,
            "columns": [c.to_dict() for c in self.columns],
        }

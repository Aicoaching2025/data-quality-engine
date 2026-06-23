"""Roll individual check results up into a single data-readiness score.

The aggregation is deliberately transparent so a stakeholder can follow it:

    check score  ->  (mean within a dimension)  ->  dimension score
    dimension scores  ->  (weighted mean)  ->  overall readiness (0–100)  ->  grade

Weights live in :data:`dqe.types.DIMENSION_WEIGHTS`. Only dimensions that
actually produced results are included, so configuring no freshness check
doesn't drag the score down.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dqe.types import CheckResult, Dimension, DIMENSION_WEIGHTS, Status


@dataclass
class DimensionScore:
    dimension: Dimension
    score: float
    weight: float
    n_checks: int
    n_pass: int
    n_warn: int
    n_fail: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension.value,
            "score": round(self.score, 2),
            "weight": self.weight,
            "checks": self.n_checks,
            "pass": self.n_pass,
            "warn": self.n_warn,
            "fail": self.n_fail,
        }


@dataclass
class Scorecard:
    overall_score: float
    grade: str
    dimensions: list[DimensionScore] = field(default_factory=list)
    n_pass: int = 0
    n_warn: int = 0
    n_fail: int = 0

    @property
    def verdict(self) -> str:
        """One-word gate decision derived from the grade."""
        if self.overall_score >= 90:
            return "READY"
        if self.overall_score >= 75:
            return "REVIEW"
        return "NOT READY"

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_score": round(self.overall_score, 2),
            "grade": self.grade,
            "verdict": self.verdict,
            "totals": {"pass": self.n_pass, "warn": self.n_warn, "fail": self.n_fail},
            "dimensions": [d.to_dict() for d in self.dimensions],
        }


def _grade(score: float) -> str:
    cutoffs = [(97, "A+"), (93, "A"), (90, "A-"), (87, "B+"), (83, "B"),
               (80, "B-"), (77, "C+"), (73, "C"), (70, "C-"), (60, "D"), (0, "F")]
    for cutoff, letter in cutoffs:
        if score >= cutoff:
            return letter
    return "F"


def score_results(results: list[CheckResult]) -> Scorecard:
    """Aggregate check results into a :class:`Scorecard`."""
    by_dim: dict[Dimension, list[CheckResult]] = {}
    for r in results:
        by_dim.setdefault(r.dimension, []).append(r)

    dimension_scores: list[DimensionScore] = []
    for dim, dim_results in by_dim.items():
        mean_score = sum(r.score for r in dim_results) / len(dim_results)
        dimension_scores.append(
            DimensionScore(
                dimension=dim,
                score=mean_score,
                weight=DIMENSION_WEIGHTS.get(dim, 1.0),
                n_checks=len(dim_results),
                n_pass=sum(r.status == Status.PASS for r in dim_results),
                n_warn=sum(r.status == Status.WARN for r in dim_results),
                n_fail=sum(r.status == Status.FAIL for r in dim_results),
            )
        )

    total_weight = sum(d.weight for d in dimension_scores)
    overall = (
        sum(d.score * d.weight for d in dimension_scores) / total_weight
        if total_weight else 100.0
    )

    # Order dimensions worst-first so the report leads with what needs attention.
    dimension_scores.sort(key=lambda d: d.score)

    return Scorecard(
        overall_score=overall,
        grade=_grade(overall),
        dimensions=dimension_scores,
        n_pass=sum(r.status == Status.PASS for r in results),
        n_warn=sum(r.status == Status.WARN for r in results),
        n_fail=sum(r.status == Status.FAIL for r in results),
    )

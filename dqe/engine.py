"""The orchestrator: load → profile → check → score → report.

This is the heart of the engine and the one module most code will touch.
``QualityEngine.assess`` runs the full pipeline and returns a
:class:`QualityReport` that the reporters serialise to JSON/HTML.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import pandas as pd

from dqe.checks import build_checks
from dqe.connectors import get_connector
from dqe.profiling import profile_dataset
from dqe.scoring import Scorecard, score_results
from dqe.types import CheckResult, DatasetProfile, Status


@dataclass
class QualityReport:
    """Everything produced by one assessment run."""

    dataset_name: str
    source: str
    generated_at: str
    profile: DatasetProfile
    results: list[CheckResult]
    scorecard: Scorecard
    config: dict[str, Any] = field(default_factory=dict)

    @property
    def findings(self) -> list[CheckResult]:
        """Non-passing results, worst-first — the report's call to action."""
        flagged = [r for r in self.results if r.status != Status.PASS]
        return sorted(flagged, key=lambda r: (-r.status.rank, r.score))

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "source": self.source,
            "generated_at": self.generated_at,
            "scorecard": self.scorecard.to_dict(),
            "profile": self.profile.to_dict(),
            "results": [r.to_dict() for r in self.results],
            "findings": [r.to_dict() for r in self.findings],
            "config": self.config,
        }


class QualityEngine:
    """Runs a configured set of checks against a dataset."""

    def __init__(self, config: Optional[dict[str, Any]] = None) -> None:
        self.config = config or {}
        self.checks = build_checks(self.config)

    def assess(
        self,
        source: str,
        *,
        source_type: Optional[str] = None,
        dataset_name: Optional[str] = None,
        reference_time: Optional[datetime] = None,
        connector_options: Optional[dict[str, Any]] = None,
    ) -> QualityReport:
        """Run the full pipeline against ``source`` and return a report.

        Args:
            source: file path, SQL query/table, or API URL.
            source_type: override the inferred connector type.
            dataset_name: label used in the report (defaults to the source).
            reference_time: "now" for freshness checks; stamped once so runs are
                reproducible. Defaults to the wall clock at call time.
            connector_options: passed through to the connector.
        """
        connector = get_connector(source, source_type, **(connector_options or {}))
        df = connector.load()
        return self.assess_dataframe(
            df,
            source=connector.description,
            dataset_name=dataset_name or _default_name(source),
            reference_time=reference_time,
        )

    def assess_dataframe(
        self,
        df: pd.DataFrame,
        *,
        source: str = "<dataframe>",
        dataset_name: str = "dataset",
        reference_time: Optional[datetime] = None,
    ) -> QualityReport:
        """Assess an already-loaded DataFrame (useful for tests and pipelines)."""
        reference_time = reference_time or datetime.now()
        self._inject_reference_time(reference_time)

        profile = profile_dataset(df)
        results: list[CheckResult] = []
        for check in self.checks:
            results.extend(check.run(df, profile))

        scorecard = score_results(results)
        return QualityReport(
            dataset_name=dataset_name,
            source=source,
            generated_at=reference_time.isoformat(timespec="seconds"),
            profile=profile,
            results=results,
            scorecard=scorecard,
            config=self.config,
        )

    def _inject_reference_time(self, reference_time: datetime) -> None:
        """Hand the freshness check a fixed clock for reproducible runs."""
        for check in self.checks:
            if "reference_time" in check.config:
                check.config["reference_time"] = reference_time


def _default_name(source: str) -> str:
    from pathlib import Path
    stem = Path(source).stem
    return stem or source


def assess(
    source: str,
    *,
    config: Optional[dict[str, Any]] = None,
    source_type: Optional[str] = None,
    dataset_name: Optional[str] = None,
) -> QualityReport:
    """Convenience one-shot: build an engine and assess a source.

    >>> from dqe import assess
    >>> report = assess("data.csv")
    >>> report.scorecard.overall_score
    """
    return QualityEngine(config).assess(
        source, source_type=source_type, dataset_name=dataset_name
    )

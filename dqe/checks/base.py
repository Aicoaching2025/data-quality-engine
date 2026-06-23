"""Base class and registry for quality checks.

A check is a small, self-contained unit that looks at a DataFrame (plus its
precomputed profile) and emits zero or more :class:`CheckResult` objects. Checks
declare a ``dimension`` and read their thresholds from a config dict, so tuning
the engine never means touching check logic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Type

import pandas as pd

from dqe.types import CheckResult, DatasetProfile, Dimension, Status


class Check(ABC):
    """Abstract base for every quality check.

    Subclasses set :attr:`name` and :attr:`dimension` and implement
    :meth:`run`. Threshold config is merged over :attr:`default_config` so a
    check always has sane defaults even with an empty config file.
    """

    name: str = "unnamed"
    dimension: Dimension = Dimension.VALIDITY
    default_config: dict[str, Any] = {}

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = {**self.default_config, **(config or {})}

    @abstractmethod
    def run(self, df: pd.DataFrame, profile: DatasetProfile) -> list[CheckResult]:
        """Assess ``df`` and return the resulting check results."""

    # -- helpers shared by subclasses ---------------------------------------

    def _status_from_score(self, score: float) -> Status:
        """Map a 0–100 score to pass/warn/fail using configured cut points."""
        warn_at = self.config.get("warn_below", 99.0)
        fail_at = self.config.get("fail_below", 90.0)
        if score < fail_at:
            return Status.FAIL
        if score < warn_at:
            return Status.WARN
        return Status.PASS

    def _result(
        self,
        score: float,
        message: str,
        column: str | None = None,
        metric: float | None = None,
        status: Status | None = None,
        **details: Any,
    ) -> CheckResult:
        score = max(0.0, min(100.0, score))
        return CheckResult(
            check=self.name,
            dimension=self.dimension,
            status=status or self._status_from_score(score),
            score=score,
            column=column,
            message=message,
            metric=metric,
            details=details,
        )


# -- registry ---------------------------------------------------------------

_REGISTRY: dict[str, Type[Check]] = {}


def register(cls: Type[Check]) -> Type[Check]:
    """Class decorator that adds a check to the global registry by name."""
    _REGISTRY[cls.name] = cls
    return cls


def available_checks() -> dict[str, Type[Check]]:
    """Return a copy of the name → check-class registry."""
    return dict(_REGISTRY)


def build_checks(config: dict[str, Any] | None = None) -> list[Check]:
    """Instantiate all enabled checks given a top-level config dict.

    Config shape::

        checks:
          completeness:
            enabled: true
            warn_below: 99
          outliers:
            enabled: false

    A check absent from config is enabled with its defaults.
    """
    config = config or {}
    checks_cfg = config.get("checks", {})
    built: list[Check] = []
    for name, cls in _REGISTRY.items():
        cfg = checks_cfg.get(name, {})
        if cfg.get("enabled", True):
            built.append(cls(cfg))
    return built

"""Data Quality Engine — automated assessment of dataset readiness for ML/analytics.

Public API:
    from dqe import assess
    report = assess("data.csv")
"""
from dqe.engine import assess, QualityEngine
from dqe.types import CheckResult, Status, Dimension

__version__ = "0.1.0"
__all__ = ["assess", "QualityEngine", "CheckResult", "Status", "Dimension", "__version__"]

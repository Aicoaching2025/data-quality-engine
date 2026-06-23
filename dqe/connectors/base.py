"""Connector interface and the factory that picks one for a given source."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

import pandas as pd


class Connector(ABC):
    """Turns some external source into a pandas DataFrame.

    Subclasses implement exactly one thing — :meth:`load`. The contract is
    deliberately tiny so new sources (SQL, API, S3, …) are cheap to add.
    """

    def __init__(self, source: str, **options: Any) -> None:
        self.source = source
        self.options = options

    @abstractmethod
    def load(self) -> pd.DataFrame:
        """Read the source and return it as a DataFrame."""

    @property
    def description(self) -> str:
        """Human-readable label for the report (overridable)."""
        return f"{self.__class__.__name__}: {self.source}"


# Map a file extension to its connector type name. Kept as strings to avoid
# importing optional-dependency connectors until they're actually requested.
_EXTENSION_MAP: dict[str, str] = {
    ".csv": "csv",
    ".tsv": "csv",
    ".txt": "csv",
    ".xlsx": "excel",
    ".xls": "excel",
    ".parquet": "parquet",
    ".pq": "parquet",
}


def get_connector(
    source: str,
    source_type: Optional[str] = None,
    **options: Any,
) -> Connector:
    """Return the right connector for ``source``.

    Args:
        source: a file path, SQL query/table, or API URL.
        source_type: force a connector ("csv", "excel", "parquet", "sql",
            "api"). If omitted, it's inferred from the file extension.
        **options: passed through to the connector (e.g. ``sep`` for CSV,
            ``connection`` for SQL).

    Raises:
        ValueError: if the type can't be inferred or isn't supported.
    """
    kind = (source_type or _infer_type(source)).lower()

    # Local imports keep optional dependencies (sqlalchemy, requests, pyarrow)
    # out of the import path unless the corresponding connector is used.
    if kind == "csv":
        from dqe.connectors.file_connectors import CSVConnector
        return CSVConnector(source, **options)
    if kind == "excel":
        from dqe.connectors.file_connectors import ExcelConnector
        return ExcelConnector(source, **options)
    if kind == "parquet":
        from dqe.connectors.file_connectors import ParquetConnector
        return ParquetConnector(source, **options)
    if kind == "sql":
        from dqe.connectors.sql_connector import SQLConnector
        return SQLConnector(source, **options)
    if kind == "api":
        from dqe.connectors.api_connector import APIConnector
        return APIConnector(source, **options)

    raise ValueError(
        f"Unsupported source type {kind!r}. "
        f"Use one of: csv, excel, parquet, sql, api."
    )


def _infer_type(source: str) -> str:
    ext = Path(source).suffix.lower()
    if ext in _EXTENSION_MAP:
        return _EXTENSION_MAP[ext]
    if source.lower().startswith(("http://", "https://")):
        return "api"
    raise ValueError(
        f"Could not infer source type from {source!r}. "
        f"Pass source_type explicitly (e.g. --source-type sql)."
    )

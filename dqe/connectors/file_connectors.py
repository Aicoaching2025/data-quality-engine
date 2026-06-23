"""File-based connectors: CSV/TSV, Excel, and Parquet."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from dqe.connectors.base import Connector


class CSVConnector(Connector):
    """Read delimited text files. Auto-detects tab separation for ``.tsv``."""

    def load(self) -> pd.DataFrame:
        path = Path(self.source)
        if not path.exists():
            raise FileNotFoundError(f"CSV source not found: {path}")
        opts = dict(self.options)
        if "sep" not in opts and path.suffix.lower() == ".tsv":
            opts["sep"] = "\t"
        return pd.read_csv(path, **opts)


class ExcelConnector(Connector):
    """Read an Excel workbook. Pass ``sheet_name`` via options to pick a sheet."""

    def load(self) -> pd.DataFrame:
        path = Path(self.source)
        if not path.exists():
            raise FileNotFoundError(f"Excel source not found: {path}")
        try:
            return pd.read_excel(path, **self.options)
        except ImportError as exc:  # pragma: no cover - depends on env
            raise ImportError(
                "Reading Excel requires openpyxl. Install with: pip install openpyxl"
            ) from exc


class ParquetConnector(Connector):
    """Read a Parquet file (requires pyarrow)."""

    def load(self) -> pd.DataFrame:
        path = Path(self.source)
        if not path.exists():
            raise FileNotFoundError(f"Parquet source not found: {path}")
        try:
            return pd.read_parquet(path, **self.options)
        except ImportError as exc:  # pragma: no cover - depends on env
            raise ImportError(
                "Reading Parquet requires pyarrow. Install with: pip install pyarrow"
            ) from exc

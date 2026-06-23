"""SQL connector — an extension point, implemented but kept dependency-light.

CSV is the primary path for the first build, but the interface is real: point it
at any SQLAlchemy-supported database and hand it a table name or query.

    get_connector("SELECT * FROM customers", source_type="sql",
                  connection="postgresql://user:pass@host/db")
"""
from __future__ import annotations

import pandas as pd

from dqe.connectors.base import Connector


class SQLConnector(Connector):
    """Load a table or query result from a SQL database.

    Options:
        connection: a SQLAlchemy URL or an existing connection/engine (required).
        is_table: if True (default when ``source`` is a bare identifier), treat
            ``source`` as a table name; otherwise treat it as a SQL query.
    """

    def load(self) -> pd.DataFrame:
        connection = self.options.get("connection")
        if connection is None:
            raise ValueError(
                "SQLConnector requires a 'connection' option "
                "(SQLAlchemy URL or engine)."
            )

        try:
            from sqlalchemy import create_engine, text  # noqa: F401
        except ImportError as exc:  # pragma: no cover - depends on env
            raise ImportError(
                "The SQL connector requires SQLAlchemy. "
                "Install with: pip install sqlalchemy"
            ) from exc

        engine = create_engine(connection) if isinstance(connection, str) else connection
        source = self.source.strip()
        looks_like_query = " " in source or source.lower().startswith("select")

        if looks_like_query:
            return pd.read_sql_query(source, engine)
        return pd.read_sql_table(source, engine)

    @property
    def description(self) -> str:
        return f"SQL: {self.source}"

"""API connector — an extension point for JSON REST endpoints.

    get_connector("https://api.example.com/records", source_type="api",
                  records_path="data.items")

Flattens nested JSON into a tabular frame so the same checks apply.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from dqe.connectors.base import Connector


class APIConnector(Connector):
    """Fetch JSON from an HTTP endpoint and normalise it into a DataFrame.

    Options:
        records_path: dotted path to the list of records inside the response
            (e.g. ``"data.items"``). If omitted, the top-level JSON is used.
        params, headers, timeout: forwarded to ``requests.get``.
    """

    def load(self) -> pd.DataFrame:
        try:
            import requests
        except ImportError as exc:  # pragma: no cover - depends on env
            raise ImportError(
                "The API connector requires requests. "
                "Install with: pip install requests"
            ) from exc

        resp = requests.get(
            self.source,
            params=self.options.get("params"),
            headers=self.options.get("headers"),
            timeout=self.options.get("timeout", 30),
        )
        resp.raise_for_status()
        payload: Any = resp.json()

        records_path = self.options.get("records_path")
        if records_path:
            for key in records_path.split("."):
                payload = payload[key]

        return pd.json_normalize(payload)

    @property
    def description(self) -> str:
        return f"API: {self.source}"

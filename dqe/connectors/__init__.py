"""Data source connectors.

Every source — a CSV on disk, a SQL table, a JSON API — is reduced to the same
thing: a :class:`~dqe.connectors.base.Connector` that returns a pandas
DataFrame. The rest of the engine never knows or cares where the data came from,
which is what makes adding SQL/API a drop-in rather than a rewrite.
"""
from dqe.connectors.base import Connector, get_connector

__all__ = ["Connector", "get_connector"]

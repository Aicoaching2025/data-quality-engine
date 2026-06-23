"""Quality checks package.

Importing this package imports every check module, which triggers the
``@register`` decorators and populates the registry. The engine then calls
:func:`build_checks` to instantiate the enabled ones.
"""
from dqe.checks.base import Check, available_checks, build_checks, register

# Import for side effect: each module registers its check(s) on import.
from dqe.checks import completeness  # noqa: F401
from dqe.checks import uniqueness    # noqa: F401
from dqe.checks import schema        # noqa: F401
from dqe.checks import outliers      # noqa: F401
from dqe.checks import validity      # noqa: F401
from dqe.checks import freshness     # noqa: F401

__all__ = ["Check", "available_checks", "build_checks", "register"]

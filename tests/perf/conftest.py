"""Pytest hooks for the perf suite.

Perf tests are slow and noisy on shared CI runners. They are skipped by
default and only run when the user opts in with ``--run-perf``, or when
the environment variable ``CFA_RUN_PERF=1`` is set.
"""

from __future__ import annotations

import os

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-perf",
        action="store_true",
        default=False,
        help="Run the perf benchmark suite under tests/perf/",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--run-perf") or os.environ.get("CFA_RUN_PERF") == "1":
        return
    skip_perf = pytest.mark.skip(reason="perf tests skipped (pass --run-perf or set CFA_RUN_PERF=1)")
    for item in items:
        if "tests/perf" in str(item.fspath) or "tests\\perf" in str(item.fspath):
            item.add_marker(skip_perf)

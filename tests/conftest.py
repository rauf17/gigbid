"""Global pytest fixtures and hooks for GigBid test suites."""
from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register custom CLI flags for test execution."""
    parser.addoption(
        "--update-snapshot",
        action="store_true",
        default=False,
        help="Update contract snapshot files deliberately",
    )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Ensure pytest does not exit with code 5 when a directory has no tests."""
    if exitstatus == 5:
        session.exitstatus = pytest.ExitCode.OK

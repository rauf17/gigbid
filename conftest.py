"""Root pytest configuration and hooks for GigBid."""
from __future__ import annotations

import pytest


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Ensure pytest does not exit with code 5 when a directory has no tests."""
    if exitstatus == 5:
        session.exitstatus = pytest.ExitCode.OK

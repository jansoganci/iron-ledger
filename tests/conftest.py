"""Shared fixtures. Every test starts with every period open."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from tests.period_fakes import FakePeriodClosesRepo


@pytest.fixture(autouse=True)
def period_closes_repo():
    """Default: no period is closed, no database is touched.

    Lock tests use this same fake (request it by name) to close a month.
    """
    repo = FakePeriodClosesRepo()
    with patch("backend.api.period_lock.get_period_closes_repo", return_value=repo):
        with patch(
            "backend.api.routers.periods.get_period_closes_repo", return_value=repo
        ):
            yield repo

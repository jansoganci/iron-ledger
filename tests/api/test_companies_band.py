"""API tests for monthly_revenue_band on company create / GET / PATCH."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.auth import (
    _company_cache,
    get_cached_company,
    get_current_user,
    invalidate_company_cache,
)
from backend.domain.errors import RLSForbiddenError
from backend.main import app

USER_ID = "user-band-1"
COMPANY_ID = "co-band-1"

client = TestClient(app, raise_server_exceptions=False)


def _company_row(band: str | None = None) -> dict:
    return {
        "id": COMPANY_ID,
        "name": "Acme Alarm",
        "sector": "security",
        "currency": "USD",
        "monthly_revenue_band": band,
    }


@pytest.fixture(autouse=True)
def _override_auth():
    previous_user = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: USER_ID
    yield
    if previous_user is not None:
        app.dependency_overrides[get_current_user] = previous_user
    else:
        app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_cached_company, None)
    _company_cache.pop(USER_ID, None)


def test_post_companies_omitting_band_is_422() -> None:
    resp = client.post("/companies", json={"name": "Acme", "sector": "security"})
    assert resp.status_code == 422


def test_post_companies_invalid_band_is_422() -> None:
    resp = client.post(
        "/companies",
        json={
            "name": "Acme",
            "sector": "security",
            "monthly_revenue_band": "annual",
        },
    )
    assert resp.status_code == 422


@patch("backend.api.routes.get_companies_repo")
def test_post_companies_idempotent_does_not_update_band(mock_repo) -> None:
    repo = MagicMock()
    repo.get_by_owner.return_value = _company_row("under_100k")
    mock_repo.return_value = repo

    resp = client.post(
        "/companies",
        json={
            "name": "Acme",
            "sector": "security",
            "monthly_revenue_band": "500k_plus",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["monthly_revenue_band"] == "under_100k"
    repo.update.assert_not_called()
    repo.create.assert_not_called()


@patch("backend.api.routes.get_companies_repo")
def test_patch_companies_me_sets_band(mock_repo) -> None:
    app.dependency_overrides[get_cached_company] = lambda: _company_row(None)
    repo = MagicMock()
    repo.update.return_value = _company_row("100k_250k")
    mock_repo.return_value = repo

    resp = client.patch(
        "/companies/me",
        json={"monthly_revenue_band": "100k_250k"},
    )
    assert resp.status_code == 200
    assert resp.json()["monthly_revenue_band"] == "100k_250k"
    repo.update.assert_called_once_with(COMPANY_ID, monthly_revenue_band="100k_250k")


@patch("backend.api.routes.get_companies_repo")
def test_patch_invalidates_company_cache(mock_repo) -> None:
    app.dependency_overrides[get_cached_company] = lambda: _company_row(None)
    repo = MagicMock()
    repo.update.return_value = _company_row("250k_500k")
    mock_repo.return_value = repo

    _company_cache[USER_ID] = (_company_row(None), time.monotonic() + 300)
    resp = client.patch(
        "/companies/me",
        json={"monthly_revenue_band": "250k_500k"},
    )
    assert resp.status_code == 200
    assert USER_ID not in _company_cache


def test_invalidate_company_cache_is_safe_when_empty() -> None:
    invalidate_company_cache("nobody")


@patch("backend.api.routes.get_companies_repo")
def test_get_companies_me_includes_null_band(mock_repo) -> None:
    app.dependency_overrides[get_cached_company] = lambda: _company_row(None)

    resp = client.get("/companies/me")
    assert resp.status_code == 200
    assert resp.json()["monthly_revenue_band"] is None


@patch("backend.api.routes.get_companies_repo")
def test_post_companies_create_passes_band(mock_repo) -> None:
    repo = MagicMock()
    repo.get_by_owner.side_effect = RLSForbiddenError("none")
    repo.create.return_value = _company_row("100k_250k")
    mock_repo.return_value = repo

    resp = client.post(
        "/companies",
        json={
            "name": "Acme Alarm",
            "sector": "security",
            "monthly_revenue_band": "100k_250k",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["monthly_revenue_band"] == "100k_250k"
    repo.create.assert_called_once()
    assert repo.create.call_args.kwargs["monthly_revenue_band"] == "100k_250k"

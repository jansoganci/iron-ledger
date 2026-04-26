"""Tests for POST /runs/{run_id}/confirm-mappings endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.auth import get_company_id, get_current_user
from backend.domain.run_state_machine import RunStatus
from backend.main import app

# Override auth dependencies globally for all tests in this module.
app.dependency_overrides[get_current_user] = lambda: "user-1"
app.dependency_overrides[get_company_id] = lambda: "co-1"

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _mock_run(status: str, parse_preview: dict | None = None) -> dict:
    return {
        "id": "run-123",
        "status": status,
        "period": "2026-03-01",
        "parse_preview": parse_preview or {},
    }


def _preview_with_pool(pool: list[str]) -> dict:
    return {
        "mapping_draft": {"items": [], "gl_account_pool": pool},
        "file_keys": {"payroll.xlsx": "user/2026-03-01/payroll.xlsx"},
        "is_multi_file": True,
    }


# ---------------------------------------------------------------------------
# Test 1: wrong state → 409
# ---------------------------------------------------------------------------


@patch("backend.api.routes.get_runs_repo")
def test_confirm_mappings_wrong_state_returns_409(mock_repo):
    runs_repo = MagicMock()
    runs_repo.get_by_id.return_value = _mock_run(RunStatus.AWAITING_CONFIRMATION.value)
    mock_repo.return_value = runs_repo

    resp = client.post(
        "/runs/run-123/confirm-mappings",
        json={"decisions": {"AlarmTech": "Equipment COGS"}},
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Test 2: gl_account not in pool → 400
# ---------------------------------------------------------------------------


@patch("backend.api.routes.get_runs_repo")
def test_confirm_mappings_bad_gl_account_returns_400(mock_repo):
    runs_repo = MagicMock()
    runs_repo.get_by_id.return_value = _mock_run(
        RunStatus.AWAITING_MAPPING_CONFIRMATION.value,
        parse_preview=_preview_with_pool(["Equipment COGS", "Salaries & Wages"]),
    )
    mock_repo.return_value = runs_repo

    resp = client.post(
        "/runs/run-123/confirm-mappings",
        json={"decisions": {"AlarmTech": "Made Up Account"}},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Test 3: empty decisions → 400
# ---------------------------------------------------------------------------


@patch("backend.api.routes.get_runs_repo")
def test_confirm_mappings_empty_decisions_returns_400(mock_repo):
    runs_repo = MagicMock()
    runs_repo.get_by_id.return_value = _mock_run(
        RunStatus.AWAITING_MAPPING_CONFIRMATION.value,
        parse_preview=_preview_with_pool(["Equipment COGS"]),
    )
    mock_repo.return_value = runs_repo

    resp = client.post(
        "/runs/run-123/confirm-mappings",
        json={"decisions": {}},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Test 4: success → 200 + background task scheduled
# ---------------------------------------------------------------------------


@patch("backend.api.routes.apply_mapping_and_consolidate")
@patch("backend.api.routes.get_runs_repo")
def test_confirm_mappings_success_returns_200(mock_repo, mock_apply):
    runs_repo = MagicMock()
    runs_repo.get_by_id.return_value = _mock_run(
        RunStatus.AWAITING_MAPPING_CONFIRMATION.value,
        parse_preview=_preview_with_pool(["Equipment COGS", "Salaries & Wages"]),
    )
    mock_repo.return_value = runs_repo

    resp = client.post(
        "/runs/run-123/confirm-mappings",
        json={
            "decisions": {
                "AlarmTech": "Equipment COGS",
                "T. Rivera": "Salaries & Wages",
            }
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "applying_mappings"
    assert data["run_id"] == "run-123"

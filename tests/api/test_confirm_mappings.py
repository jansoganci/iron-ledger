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
        "company_id": "co-1",
        "parse_preview": parse_preview or {},
    }


def _preview_with_pool(pool: list[str]) -> dict:
    return {
        "mapping_draft": {
            "items": [
                {
                    "source_pattern": "AlarmTech",
                    "source_file": "vendor.xlsx",
                    "file_type": "supplier_invoices",
                    "suggested_gl_account": "Equipment COGS",
                    "confident": True,
                    "origin": "new",
                }
            ],
            "gl_account_pool": pool,
        },
        "file_keys": {"vendor.xlsx": "user/2026-03-01/vendor.xlsx"},
        "is_multi_file": True,
    }


# ---------------------------------------------------------------------------
# Test 1: wrong state → 409
# ---------------------------------------------------------------------------


@patch("backend.api.routers.uploads.get_runs_repo")
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


@patch("backend.api.routers.uploads.get_runs_repo")
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


@patch("backend.api.routers.uploads.get_runs_repo")
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


@patch("backend.api.routers.uploads.get_source_mappings_repo")
@patch("backend.api.routers.uploads.apply_mapping_and_consolidate")
@patch("backend.api.routers.uploads.get_runs_repo")
def test_confirm_mappings_success_returns_200(mock_repo, mock_apply, mock_maps):
    runs_repo = MagicMock()
    runs_repo.get_by_id.return_value = _mock_run(
        RunStatus.AWAITING_MAPPING_CONFIRMATION.value,
        parse_preview=_preview_with_pool(["Equipment COGS", "Salaries & Wages"]),
    )
    mock_repo.return_value = runs_repo
    maps_repo = MagicMock()
    mock_maps.return_value = maps_repo

    resp = client.post(
        "/runs/run-123/confirm-mappings",
        json={
            "decisions": {
                "AlarmTech": "Equipment COGS",
            }
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "applying_mappings"
    assert data["run_id"] == "run-123"
    maps_repo.upsert.assert_called_once_with(
        "co-1", "supplier_invoices", "AlarmTech", "Equipment COGS"
    )


@patch("backend.api.routers.uploads.get_runs_repo")
def test_confirm_mappings_foreign_company_returns_403(mock_repo):
    runs_repo = MagicMock()
    run = _mock_run(RunStatus.AWAITING_MAPPING_CONFIRMATION.value)
    run["company_id"] = "other-co"
    runs_repo.get_by_id.return_value = run
    mock_repo.return_value = runs_repo

    resp = client.post(
        "/runs/run-123/confirm-mappings",
        json={"decisions": {"AlarmTech": "Equipment COGS"}},
    )
    assert resp.status_code == 403


@patch("backend.api.routers.uploads.get_source_mappings_repo")
@patch("backend.api.routers.uploads.apply_mapping_and_consolidate")
@patch("backend.api.routers.uploads.get_runs_repo")
def test_confirm_mappings_does_not_persist_payroll(mock_repo, mock_apply, mock_maps):
    preview = _preview_with_pool(["Equipment COGS", "Salaries & Wages"])
    preview["mapping_draft"]["items"].append(
        {
            "source_pattern": "Alice Johnson",
            "source_file": "payroll.xlsx",
            "file_type": "payroll",
            "suggested_gl_account": "Salaries & Wages",
            "confident": True,
            "origin": "new",
        }
    )
    runs_repo = MagicMock()
    runs_repo.get_by_id.return_value = _mock_run(
        RunStatus.AWAITING_MAPPING_CONFIRMATION.value,
        parse_preview=preview,
    )
    mock_repo.return_value = runs_repo
    maps_repo = MagicMock()
    mock_maps.return_value = maps_repo

    resp = client.post(
        "/runs/run-123/confirm-mappings",
        json={
            "decisions": {
                "AlarmTech": "Equipment COGS",
                "Alice Johnson": "Salaries & Wages",
            }
        },
    )
    assert resp.status_code == 200
    maps_repo.upsert.assert_called_once_with(
        "co-1", "supplier_invoices", "AlarmTech", "Equipment COGS"
    )

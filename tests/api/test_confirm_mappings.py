"""Tests for POST /runs/{run_id}/confirm-mappings endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.auth import get_company_id, get_current_user
from backend import messages
from backend.domain.run_state_machine import RunStatus
from backend.main import app

# Override auth dependencies globally for all tests in this module.
app.dependency_overrides[get_current_user] = lambda: "user-1"
app.dependency_overrides[get_company_id] = lambda: "co-1"

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _override_auth():
    previous_user = app.dependency_overrides.get(get_current_user)
    previous_company = app.dependency_overrides.get(get_company_id)
    app.dependency_overrides[get_current_user] = lambda: "user-1"
    app.dependency_overrides[get_company_id] = lambda: "co-1"
    yield
    if previous_user is not None:
        app.dependency_overrides[get_current_user] = previous_user
    else:
        app.dependency_overrides.pop(get_current_user, None)
    if previous_company is not None:
        app.dependency_overrides[get_company_id] = previous_company
    else:
        app.dependency_overrides.pop(get_company_id, None)


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
    runs_repo.get_by_id.return_value = _mock_run(
        RunStatus.AWAITING_MAPPING_CONFIRMATION.value,
        parse_preview=_preview_with_pool(["Equipment COGS"]),
    )

    resp = client.post(
        "/runs/run-123/confirm-mappings",
        json={"decisions": {}},
    )
    assert resp.status_code == 400


@pytest.mark.parametrize(
    "decisions,totals,detail",
    [
        (
            {"AlarmTech": "Equipment COGS"},
            {"contracts.xlsx": ""},
            messages.MAPPING_CONFIRMATION_REQUIRED,
        ),
        (
            {"AlarmTech": "Equipment COGS"},
            {"contracts.xlsx": "   "},
            messages.MAPPING_CONFIRMATION_REQUIRED,
        ),
        ({"AlarmTech": "Equipment COGS"}, {}, messages.MAPPING_CONFIRMATION_REQUIRED),
        (
            {},
            {"contracts.xlsx": "Service Revenue"},
            messages.MAPPING_CONFIRMATION_REQUIRED,
        ),
        (
            {"AlarmTech": "Equipment COGS", "extra": "Service Revenue"},
            {"contracts.xlsx": "Service Revenue"},
            messages.MAPPING_DRAFT_INVALID,
        ),
        (
            {"AlarmTech": "Other tenant account"},
            {"contracts.xlsx": "Service Revenue"},
            messages.MAPPING_INVALID_GL_ACCOUNT,
        ),
    ],
)
def test_incomplete_or_invalid_confirmation_has_no_side_effects(
    decisions, totals, detail
):
    preview = _preview_with_pool(["Service Revenue", "Equipment COGS"])
    preview["mapping_draft"]["items"].append(
        {
            "source_pattern": "(entire file)",
            "source_file": "contracts.xlsx",
            "file_type": "contracts",
            "mapping_mode": "file_total",
            "suggested_gl_account": "Service Revenue",
            "confident": True,
        }
    )
    with patch("backend.api.routers.uploads.get_runs_repo") as get_runs, patch(
        "backend.api.routers.uploads.get_source_mappings_repo"
    ) as get_maps, patch(
        "backend.api.routers.uploads.apply_mapping_and_consolidate"
    ) as apply:
        runs = get_runs.return_value
        runs.get_by_id.return_value = _mock_run(
            RunStatus.AWAITING_MAPPING_CONFIRMATION.value, parse_preview=preview
        )
        resp = client.post(
            "/runs/run-123/confirm-mappings",
            json={
                "decisions": decisions,
                "file_total_decisions": totals,
            },
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == detail
        runs.update_status.assert_not_called()
        runs.set_parse_preview.assert_not_called()
        get_maps.assert_not_called()
        apply.assert_not_called()


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
def test_confirm_mappings_file_total_validates_gl_and_is_not_persisted(
    mock_repo, mock_apply, mock_maps
):
    preview = _preview_with_pool(["Service Revenue", "Equipment COGS"])
    preview["mapping_draft"]["items"].append(
        {
            "source_pattern": "(entire file)",
            "source_file": "contracts.xlsx",
            "file_type": "contracts",
            "suggested_gl_account": "Service Revenue",
            "confident": True,
            "mapping_mode": "file_total",
            "amount_scope": "Monthly Fee",
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

    bad = client.post(
        "/runs/run-123/confirm-mappings",
        json={
            "decisions": {},
            "file_total_decisions": {"contracts.xlsx": "Made Up Account"},
        },
    )
    assert bad.status_code == 400

    other_file = client.post(
        "/runs/run-123/confirm-mappings",
        json={
            "decisions": {},
            "file_total_decisions": {"not-in-draft.xlsx": "Service Revenue"},
        },
    )
    assert other_file.status_code == 400

    ok = client.post(
        "/runs/run-123/confirm-mappings",
        json={
            "decisions": {"AlarmTech": "Equipment COGS"},
            "file_total_decisions": {"contracts.xlsx": "Service Revenue"},
        },
    )
    assert ok.status_code == 200
    maps_repo.upsert.assert_called_once_with(
        "co-1", "supplier_invoices", "AlarmTech", "Equipment COGS"
    )
    stored_preview = runs_repo.set_parse_preview.call_args[0][1]
    assert stored_preview["file_total_decisions"]["contracts.xlsx"] == "Service Revenue"


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

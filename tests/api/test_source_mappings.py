"""API tests for saved vendor/expense mappings. company_id comes from auth."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.api.auth import get_company_id, get_current_user
from backend.domain.entities import SourceAccountMapping
from backend.main import app

app.dependency_overrides[get_current_user] = lambda: "user-1"
app.dependency_overrides[get_company_id] = lambda: "co-1"

client = TestClient(app, raise_server_exceptions=False)


def _row(**kwargs) -> SourceAccountMapping:
    payload = {
        "id": "map-1",
        "company_id": "co-1",
        "file_type": "supplier_invoices",
        "source_pattern": "AlarmTech Industries",
        "gl_account": "Equipment COGS",
        "updated_at": "2026-09-16T12:00:00",
    }
    payload.update(kwargs)
    return SourceAccountMapping(**payload)


@patch("backend.api.routers.source_mappings.get_accounts_repo")
@patch("backend.api.routers.source_mappings.get_source_mappings_repo")
def test_list_source_mappings_uses_auth_company(mock_maps, mock_accounts):
    repo = MagicMock()
    repo.list_for_company.return_value = [_row()]
    mock_maps.return_value = repo
    accounts = MagicMock()
    accounts.list_for_company.return_value = {"Equipment COGS": "COGS"}
    mock_accounts.return_value = accounts

    resp = client.get("/source-mappings?company_id=other-co")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mappings"][0]["source_pattern"] == "AlarmTech Industries"
    assert "company_id" not in body["mappings"][0]
    repo.list_for_company.assert_called_once_with("co-1")
    accounts.list_for_company.assert_called_once_with("co-1")


@patch("backend.api.routers.source_mappings.get_source_mappings_repo")
def test_patch_rejects_foreign_company_id_in_body(mock_maps):
    repo = MagicMock()
    repo.update.return_value = _row(gl_account="Utilities")
    mock_maps.return_value = repo

    resp = client.patch(
        "/source-mappings/map-1",
        json={"gl_account": "Utilities", "company_id": "other-co"},
    )
    assert resp.status_code == 422
    repo.update.assert_not_called()


@patch("backend.api.routers.source_mappings.get_source_mappings_repo")
def test_patch_missing_row_is_404(mock_maps):
    repo = MagicMock()
    repo.update.return_value = None
    mock_maps.return_value = repo

    resp = client.patch(
        "/source-mappings/missing",
        json={"gl_account": "Utilities"},
    )
    assert resp.status_code == 404
    repo.update.assert_called_once_with("co-1", "missing", "Utilities")


@patch("backend.api.routers.source_mappings.get_source_mappings_repo")
def test_patch_success_scopes_to_company(mock_maps):
    repo = MagicMock()
    repo.update.return_value = _row(gl_account="Utilities")
    mock_maps.return_value = repo

    resp = client.patch(
        "/source-mappings/map-1",
        json={"gl_account": "Utilities"},
    )
    assert resp.status_code == 200
    assert resp.json()["gl_account"] == "Utilities"
    repo.update.assert_called_once_with("co-1", "map-1", "Utilities")


@patch("backend.api.routers.source_mappings.get_source_mappings_repo")
def test_delete_missing_row_is_404(mock_maps):
    repo = MagicMock()
    repo.delete.return_value = False
    mock_maps.return_value = repo

    resp = client.delete("/source-mappings/missing")
    assert resp.status_code == 404
    repo.delete.assert_called_once_with("co-1", "missing")


@patch("backend.api.routers.source_mappings.get_source_mappings_repo")
def test_delete_success(mock_maps):
    repo = MagicMock()
    repo.delete.return_value = True
    mock_maps.return_value = repo

    resp = client.delete("/source-mappings/map-1")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"
    repo.delete.assert_called_once_with("co-1", "map-1")

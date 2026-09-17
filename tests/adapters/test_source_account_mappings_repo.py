"""Unit tests for source-mapping repo company scoping."""

from __future__ import annotations

from unittest.mock import MagicMock

from backend.adapters.supabase_repos import SupabaseSourceAccountMappingsRepo
from backend.domain.entities import SourceAccountMapping


def _builder(row: dict | None) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.data = [row] if row else []
    builder = MagicMock()
    builder.select.return_value = builder
    builder.eq.return_value = builder
    builder.order.return_value = builder
    builder.upsert.return_value = builder
    builder.update.return_value = builder
    builder.delete.return_value = builder
    builder.execute.return_value = mock_resp
    return builder


def test_update_always_filters_company_id() -> None:
    row = {
        "id": "map-1",
        "company_id": "co-1",
        "file_type": "supplier_invoices",
        "source_pattern": "Phone",
        "gl_account": "Utilities",
        "created_at": None,
        "updated_at": None,
    }
    builder = _builder(row)
    client = MagicMock()
    client.table.return_value = builder
    repo = SupabaseSourceAccountMappingsRepo(client)

    result = repo.update("co-1", "map-1", "Utilities")
    assert isinstance(result, SourceAccountMapping)
    eq_args = [call.args for call in builder.eq.call_args_list]
    assert ("company_id", "co-1") in eq_args
    assert ("id", "map-1") in eq_args


def test_update_missing_row_returns_none() -> None:
    builder = _builder(None)
    client = MagicMock()
    client.table.return_value = builder
    repo = SupabaseSourceAccountMappingsRepo(client)
    assert repo.update("co-1", "missing", "Utilities") is None


def test_delete_filters_company_id() -> None:
    builder = _builder(
        {
            "id": "map-1",
            "company_id": "co-1",
            "file_type": "supplier_invoices",
            "source_pattern": "Phone",
            "gl_account": "Utilities",
        }
    )
    client = MagicMock()
    client.table.return_value = builder
    repo = SupabaseSourceAccountMappingsRepo(client)
    assert repo.delete("co-1", "map-1") is True
    eq_args = [call.args for call in builder.eq.call_args_list]
    assert ("company_id", "co-1") in eq_args
    assert ("id", "map-1") in eq_args


def test_list_for_company_scopes_query() -> None:
    builder = _builder(None)
    client = MagicMock()
    client.table.return_value = builder
    repo = SupabaseSourceAccountMappingsRepo(client)
    assert repo.list_for_company("co-1") == []
    eq_args = [call.args for call in builder.eq.call_args_list]
    assert ("company_id", "co-1") in eq_args

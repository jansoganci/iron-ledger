"""Integration test: AccountMapper full flow.

Mocked external dependencies:
- Anthropic API (LLMClient) → canned responses per prompt file
- Supabase repos → in-memory shared state dict
- Supabase Storage → in-memory bytes dict
- run_comparison_and_report → stub that writes fake Report + sets COMPLETE

NOT mocked (real logic exercised):
- Orchestrator state machine transitions
- parse_file_silently (parser + normalizer + validator)
- AccountMapper.build_draft() (runs against mocked LLM)
- _run_consolidation (consolidate + hint_computer)

Flow verified:
  Step 1: Upload GL + payroll → run created (AWAITING_MAPPING_CONFIRMATION after BG task)
  Step 2: status == awaiting_mapping_confirmation
  Step 3: mapping_draft contains employee names from payroll file
  Step 4: POST confirm-mappings with employee→GL account decisions
  Step 5: status == awaiting_confirmation (Phase B complete)
  Step 6: POST confirm
  Step 7: status == complete (comparison stub ran)
  Step 8: report reconciliations use GL account names, not employee names
"""

from __future__ import annotations

import io
import uuid
from contextlib import ExitStack
from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from backend.api.auth import get_company_id, get_current_user
from backend.domain.contracts import (
    AccountMappingDecision,
    AccountMappingResponse,
    DiscoveryPlan,
    MappingOutput,
    MappingResponse,
    NarrativeJSON,
)
from backend.domain.entities import Report
from backend.domain.run_state_machine import RunStatus
from backend.main import app

# ---------------------------------------------------------------------------
# Auth override (module-scoped — applied once, reset in teardown)
# ---------------------------------------------------------------------------

app.dependency_overrides[get_current_user] = lambda: "user-test"
app.dependency_overrides[get_company_id] = lambda: "co-test"

client = TestClient(app, raise_server_exceptions=False)

_COMPANY = "co-test"
_PERIOD = date(2026, 3, 1)

# ---------------------------------------------------------------------------
# Shared in-memory state (reset between tests)
# ---------------------------------------------------------------------------

_state: dict[str, Any] = {
    "runs": {},
    "files": {},
    "accounts": {},
    "entries": [],
    "reports": {},
}


def _reset() -> None:
    for k in _state:
        if isinstance(_state[k], dict):
            _state[k].clear()
        else:
            _state[k].clear()


# ---------------------------------------------------------------------------
# Minimal Excel file builders — header at row 0, simple 2-column data
# ---------------------------------------------------------------------------


def _xlsx(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# GL: two accounts with known totals
GL_BYTES = _xlsx(
    [
        ["Account", "Amount", "Date"],
        ["Salaries & Wages", 10000.0, "2026-03-01"],
        ["Equipment COGS", 5000.0, "2026-03-01"],
    ]
)

# Payroll: employee names (raw, messy) — AccountMapper maps these to GL names
PAYROLL_BYTES = _xlsx(
    [
        ["Account", "Amount", "Date"],
        ["Alice Johnson", 9500.0, "2026-03-01"],  # → Salaries & Wages
        ["Bob Smith", 1000.0, "2026-03-01"],  # → Salaries & Wages (creates delta)
    ]
)

# ---------------------------------------------------------------------------
# Fake repository implementations
# ---------------------------------------------------------------------------


class _FakeRunsRepo:
    """In-memory runs repo — all instances share _state["runs"]."""

    def create(self, company_id: str, period: date) -> dict:
        run_id = str(uuid.uuid4())
        run: dict = {
            "id": run_id,
            "status": RunStatus.PENDING.value,
            "company_id": company_id,
            "period": str(period),
            "parse_preview": None,
            "report_id": None,
            "storage_key": None,
            "file_count": 0,
            "low_confidence_columns": [],
        }
        _state["runs"][run_id] = run
        return run

    def get_by_id(self, run_id: str) -> dict:
        return _state["runs"][run_id]

    def update_status(self, run_id: str, status, extra: dict | None = None) -> None:
        run = _state["runs"][run_id]
        run["status"] = status.value if hasattr(status, "value") else str(status)
        if extra:
            run.update(extra)

    def set_parse_preview(self, run_id: str, preview: dict) -> None:
        _state["runs"][run_id]["parse_preview"] = preview

    def set_file_count(self, run_id: str, count: int) -> None:
        _state["runs"][run_id]["file_count"] = count

    def set_storage_key(self, run_id: str, key: str) -> None:
        _state["runs"][run_id]["storage_key"] = key

    def set_low_confidence_columns(self, run_id: str, cols) -> None:
        _state["runs"][run_id]["low_confidence_columns"] = []


class _FakeFileStorage:
    """In-memory file storage — all instances share _state["files"]."""

    def upload(self, user_id: str, period: str, filename: str, data: bytes) -> str:
        key = f"{user_id}/{period}/{filename}"
        _state["files"][key] = data
        return key

    def download(self, key: str) -> bytes:
        return _state["files"][key]

    def delete(self, keys) -> None:
        if isinstance(keys, str):
            keys = [keys]
        for k in keys:
            _state["files"].pop(k, None)


class _FakeAccountsRepo:
    """In-memory accounts repo."""

    def list_for_company(self, company_id: str) -> dict[str, str]:
        return _state["accounts"].get(company_id, {})

    def bulk_upsert_mappings(self, company_id: str, mappings) -> dict:
        d = _state["accounts"].setdefault(company_id, {})
        for m in mappings:
            d[m.column] = m.category
        return {
            "inserted": len(mappings),
            "already_existed": 0,
            "total_requested": len(mappings),
        }

    def get_accounts_by_id(self, company_id: str) -> dict:
        existing = _state["accounts"].get(company_id, {})
        return {
            f"acc-{name}": {"name": name, "category": cat}
            for name, cat in existing.items()
        }

    def batch_get_or_create(
        self, company_id: str, items: list[tuple[str, str]]
    ) -> dict[str, str]:
        d = _state["accounts"].setdefault(company_id, {})
        result = {}
        for name, cat in items:
            if name not in d:
                d[name] = cat
            result[name] = f"acc-{name}"
        return result


class _FakeEntriesRepo:
    def list_for_period(self, company_id, period):
        return []

    def list_history(self, company_id, period, lookback_months=6):
        return []

    def replace_period(self, company_id, period, entries):
        _state["entries"] = list(entries)
        return len(_state["entries"])


class _FakeAnomaliesRepo:
    def write_batch(self, anomalies):
        pass

    def list_for_period(self, company_id, period):
        return []


class _FakeReportsRepo:
    def write(self, report: Report) -> Report:
        _state["reports"][report.id] = report
        return report

    def get(self, company_id: str, period: date):
        for report in _state["reports"].values():
            if str(report.company_id) == company_id and report.period == period:
                return report
        return None


# ---------------------------------------------------------------------------
# LLM canned responses
# ---------------------------------------------------------------------------

# Discovery: header at row 0, Account/Amount/Date columns
_PLAN = DiscoveryPlan(
    header_row_index=0,
    skip_row_indices=[],
    column_mapping={"Account": "account", "Amount": "amount", "Date": "date"},
    hierarchy_hints=[],
    discovery_confidence=0.95,
    notes="",
)

# Category mapping (mapping_prompt.txt) — called for every parsed file
_CAT_RESP = MappingResponse(
    mappings=[
        MappingOutput(column="Salaries & Wages", category="OPEX", confidence=0.95),
        MappingOutput(column="Equipment COGS", category="COGS", confidence=0.95),
        MappingOutput(column="Alice Johnson", category="OTHER", confidence=0.30),
        MappingOutput(column="Bob Smith", category="OTHER", confidence=0.30),
    ]
)

# AccountMapper (account_mapping_prompt.txt)
_AMAP_RESP = AccountMappingResponse(
    mappings={
        "Alice Johnson": AccountMappingDecision(
            gl_account="Salaries & Wages", confident=True
        ),
        "Bob Smith": AccountMappingDecision(
            gl_account="Salaries & Wages", confident=True
        ),
    }
)

# Narrative (narrative_prompt.txt)
_NARR_RESP = NarrativeJSON(
    narrative="March 2026 close: payroll vs GL reconciliation.",
    numbers_used=[10000.0, 10500.0, 5000.0, 500.0, 0.0],
    reconciliation_classifications={
        "Salaries & Wages": "stale_reference",
        "Equipment COGS": "missing_je",
    },
)


def _make_llm_mock() -> MagicMock:
    mock = MagicMock()

    def _call(prompt: str, model: str, context: dict, schema):
        if "discovery" in prompt:
            return _PLAN
        if "account_mapping" in prompt:
            return _AMAP_RESP
        if "mapping_prompt" in prompt:
            return _CAT_RESP
        if "narrative" in prompt:
            return _NARR_RESP
        raise ValueError(f"Unexpected prompt: {prompt}")

    mock.call.side_effect = _call
    return mock


# ---------------------------------------------------------------------------
# Fake comparison stub (replaces run_comparison_and_report background task)
# ---------------------------------------------------------------------------


def _fake_comparison(run_id: str, company_id: str, period: date, **_kwargs) -> None:
    """Write a fake report + transition run to COMPLETE."""
    run = _state["runs"].get(run_id, {})
    pp = run.get("parse_preview") or {}
    recon = pp.get("reconciliations", [])

    report = Report(
        id=str(uuid.uuid4()),
        company_id=company_id,
        period=period,
        summary="Fake report for integration test.",
        anomaly_count=0,
        error_count=0,
        reconciliations=recon,
    )
    _state["reports"][report.id] = report
    _state["runs"][run_id]["status"] = RunStatus.COMPLETE.value
    _state["runs"][run_id]["report_id"] = report.id


# ---------------------------------------------------------------------------
# Patch factory
# ---------------------------------------------------------------------------


def _make_patches(llm_mock: MagicMock) -> list:
    return [
        # Orchestrator deps (used by background task functions)
        patch(
            "backend.agents.orchestrator.get_runs_repo", return_value=_FakeRunsRepo()
        ),
        patch(
            "backend.agents.orchestrator.get_file_storage",
            return_value=_FakeFileStorage(),
        ),
        patch(
            "backend.agents.orchestrator.get_accounts_repo",
            return_value=_FakeAccountsRepo(),
        ),
        patch("backend.agents.orchestrator.get_llm_client", return_value=llm_mock),
        # Routes deps (used by HTTP handlers)
        patch("backend.api.routes.get_runs_repo", return_value=_FakeRunsRepo()),
        patch("backend.api.routes.get_file_storage", return_value=_FakeFileStorage()),
        patch("backend.api.routes.get_accounts_repo", return_value=_FakeAccountsRepo()),
        patch("backend.api.routes.get_entries_repo", return_value=_FakeEntriesRepo()),
        patch(
            "backend.api.routes.get_anomalies_repo", return_value=_FakeAnomaliesRepo()
        ),
        patch("backend.api.routes.get_reports_repo", return_value=_FakeReportsRepo()),
        # Stub out the heavy comparison+report pipeline
        patch(
            "backend.api.routes.run_comparison_and_report",
            side_effect=_fake_comparison,
        ),
    ]


# ---------------------------------------------------------------------------
# Integration test
# ---------------------------------------------------------------------------


def test_account_mapper_full_flow() -> None:
    """Walk all 8 steps of the AccountMapper flow end-to-end."""
    _reset()
    llm_mock = _make_llm_mock()

    with ExitStack() as stack:
        for p in _make_patches(llm_mock):
            stack.enter_context(p)

        # ── Step 1: Upload GL + payroll ──────────────────────────────────
        resp = client.post(
            "/upload",
            data={"period": "2026-03-01"},
            files=[
                ("files", ("gl.xlsx", GL_BYTES, "application/octet-stream")),
                ("files", ("payroll.xlsx", PAYROLL_BYTES, "application/octet-stream")),
            ],
        )
        assert resp.status_code == 200, f"Upload failed: {resp.text}"
        run_id = resp.json()["run_id"]
        assert run_id in _state["runs"], "Run not found in state after upload"

        # ── Step 2: Background task ran → AWAITING_MAPPING_CONFIRMATION ──
        run = _state["runs"][run_id]
        assert (
            run["status"] == RunStatus.AWAITING_MAPPING_CONFIRMATION.value
        ), f"Expected AWAITING_MAPPING_CONFIRMATION, got {run['status']}"

        # ── Step 3: mapping_draft has payroll employee names ───────────
        pp = run["parse_preview"]
        assert pp is not None, "parse_preview is None"
        assert "mapping_draft" in pp, "mapping_draft missing from parse_preview"
        draft = pp["mapping_draft"]
        patterns = {item["source_pattern"] for item in draft["items"]}
        assert (
            "Alice Johnson" in patterns
        ), f"Alice Johnson missing from draft: {patterns}"
        assert "Bob Smith" in patterns, f"Bob Smith missing from draft: {patterns}"
        gl_pool = draft["gl_account_pool"]
        assert "Salaries & Wages" in gl_pool, f"Salaries & Wages not in pool: {gl_pool}"

        # Verify status endpoint exposes mapping_draft
        status_resp = client.get(f"/runs/{run_id}/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["mapping_draft"] is not None

        # ── Step 4: POST confirm-mappings ─────────────────────────────
        decisions = {
            "Alice Johnson": "Salaries & Wages",
            "Bob Smith": "Salaries & Wages",
        }
        map_resp = client.post(
            f"/runs/{run_id}/confirm-mappings",
            json={"decisions": decisions},
        )
        assert map_resp.status_code == 200, f"confirm-mappings failed: {map_resp.text}"
        assert map_resp.json()["status"] == "applying_mappings"

        # ── Step 5: Phase B ran → AWAITING_CONFIRMATION ───────────────
        run = _state["runs"][run_id]
        assert (
            run["status"] == RunStatus.AWAITING_CONFIRMATION.value
        ), f"Expected AWAITING_CONFIRMATION after Phase B, got {run['status']}"

        # ── Step 6: POST /confirm → triggers comparison stub ─────────
        confirm_resp = client.post(
            f"/runs/{run_id}/confirm",
            json={"overrides": []},
        )
        assert confirm_resp.status_code == 200, f"confirm failed: {confirm_resp.text}"

        # ── Step 7: COMPLETE ──────────────────────────────────────────
        run = _state["runs"][run_id]
        assert (
            run["status"] == RunStatus.COMPLETE.value
        ), f"Expected COMPLETE, got {run['status']}"
        assert run["report_id"] is not None

        # ── Step 8: reconciliations use GL account names ──────────────
        report_id = run["report_id"]
        report = _state["reports"].get(report_id)
        assert report is not None, "Report not found in state"

        recon = report.reconciliations or []
        assert len(recon) > 0, "No reconciliation items in report"

        account_names = {item["account"] for item in recon}
        assert (
            "Alice Johnson" not in account_names
        ), f"Employee name leaked into reconciliations: {account_names}"
        assert (
            "Bob Smith" not in account_names
        ), f"Employee name leaked into reconciliations: {account_names}"
        # GL account names should be present
        gl_names = {"Salaries & Wages", "Equipment COGS", "Bonuses"}
        assert (
            account_names & gl_names
        ), f"No GL account names found in reconciliations: {account_names}"

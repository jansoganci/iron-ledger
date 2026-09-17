"""delete_monthly is tenant-scoped and does not go through write()."""

from __future__ import annotations

from datetime import date

from backend.adapters.supabase_repos import SupabaseReportsRepo
from backend.domain.entities import Report


class _RecordingTable:
    def __init__(self, log: list[tuple]) -> None:
        self._log = log

    def insert(self, row):
        self._log.append(("insert", row))
        self._resp = type("R", (), {"data": [dict(row)]})()
        return self

    def delete(self):
        self._log.append(("delete",))
        return self

    def eq(self, key, value):
        self._log.append(("eq", key, value))
        return self

    def execute(self):
        return getattr(self, "_resp", type("R", (), {"data": []})())


class _RecordingClient:
    def __init__(self) -> None:
        self.ops: list[tuple] = []

    def table(self, name: str):
        self.ops.append(("table", name))
        return _RecordingTable(self.ops)


def test_delete_monthly_filters_company_period_and_monthly_type() -> None:
    client = _RecordingClient()
    SupabaseReportsRepo(client).delete_monthly("co-a", date(2026, 3, 1))

    assert ("table", "reports") in client.ops
    assert ("delete",) in client.ops
    assert ("eq", "company_id", "co-a") in client.ops
    assert ("eq", "report_type", "monthly") in client.ops
    assert ("eq", "period", "2026-03-01") in client.ops
    assert ("eq", "company_id", "co-b") not in client.ops


def test_write_still_does_not_delete() -> None:
    client = _RecordingClient()
    SupabaseReportsRepo(client).write(
        Report(
            id="r1",
            company_id="co-a",
            period=date(2026, 3, 1),
            summary="ok",
            anomaly_count=0,
            error_count=0,
        )
    )
    assert ("delete",) not in client.ops
    assert any(op[0] == "insert" for op in client.ops)

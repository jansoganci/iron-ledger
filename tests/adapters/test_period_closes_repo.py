"""SupabasePeriodClosesRepo — query shape and error mapping. No network."""

from __future__ import annotations

from datetime import date

import pytest

from backend.adapters.supabase_repos import SupabasePeriodClosesRepo
from backend.domain.errors import DuplicateEntryError


class _Q:
    def __init__(self, db: "_DB", table: str) -> None:
        self.db, self.table, self.ops = db, table, []

    def __getattr__(self, name):
        def rec(*args):
            self.ops.append((name, args))
            return self

        return rec

    def execute(self):
        self.db.calls.append((self.table, self.ops))
        fail = self.db.fail.get(self.table)
        if fail:
            raise fail
        return type("R", (), {"data": self.db.data.get(self.table, [])})()


class _Admin:
    def get_user_by_id(self, user_id):
        return type("U", (), {"user": type("X", (), {"email": "a@b.test"})()})()


class _DB:
    def __init__(self) -> None:
        self.calls, self.data, self.fail = [], {}, {}
        self.auth = type("A", (), {"admin": _Admin()})()

    def table(self, name):
        return _Q(self, name)


ROW = {"id": "c1", "company_id": "co-a", "period": "2026-03-01"}


def test_close_inserts_for_the_given_company_and_logs() -> None:
    db = _DB()
    db.data["period_closes"] = [ROW]
    repo = SupabasePeriodClosesRepo(db)
    assert repo.close("co-a", date(2026, 3, 1), "u1") == ROW
    (table, ops), (log_table, log_ops) = db.calls
    assert table == "period_closes" and log_table == "period_close_log"
    payload = ops[0][1][0]
    assert payload["company_id"] == "co-a" and payload["closed_by"] == "u1"
    assert payload["closed_by_email"] == "a@b.test"
    assert log_ops[0][1][0]["event"] == "closed"


def test_second_active_close_maps_to_duplicate() -> None:
    db = _DB()
    db.fail["period_closes"] = Exception("23505 uq_period_closes_active")
    with pytest.raises(DuplicateEntryError):
        SupabasePeriodClosesRepo(db).close("co-a", date(2026, 3, 1), "u1")


def test_reopen_updates_only_the_active_row_of_that_company_and_never_deletes() -> None:
    db = _DB()
    db.data["period_closes"] = [ROW]
    repo = SupabasePeriodClosesRepo(db)
    assert repo.reopen("co-a", date(2026, 3, 1), "u1") == ROW
    names = [n for _, ops in db.calls for n, _ in ops]
    assert "delete" not in names
    ops = dict((n, a) for n, a in db.calls[0][1])
    assert ops["eq"] in (("company_id", "co-a"), ("period", "2026-03-01"))
    assert ("is_", ("reopened_at", "null")) in db.calls[0][1]
    assert db.calls[1][0] == "period_close_log"


def test_reopen_of_an_open_month_returns_none_and_logs_nothing() -> None:
    db = _DB()
    db.data["period_closes"] = []
    assert SupabasePeriodClosesRepo(db).reopen("co-a", date(2026, 3, 1), "u1") is None
    assert [t for t, _ in db.calls] == ["period_closes"]


def test_a_failed_log_write_does_not_undo_the_close() -> None:
    db = _DB()
    db.data["period_closes"] = [ROW]
    db.fail["period_close_log"] = Exception("boom")
    assert SupabasePeriodClosesRepo(db).close("co-a", date(2026, 3, 1), "u1") == ROW

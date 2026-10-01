"""In-memory PeriodClosesRepo with the same rules as the SQL (one active close
per company+period, reopen keeps the row, append-only log). No I/O."""

from __future__ import annotations

from datetime import date, datetime, timezone

from backend.domain.errors import DuplicateEntryError


class FakePeriodClosesRepo:
    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.log: list[dict] = []

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def get_active(self, company_id: str, period: date) -> dict | None:
        for r in self.rows:
            if (
                r["company_id"] == company_id
                and r["period"] == str(period)
                and r["reopened_at"] is None
            ):
                return r
        return None

    def close(self, company_id: str, period: date, user_id: str) -> dict:
        if self.get_active(company_id, period):
            raise DuplicateEntryError("23505 uq_period_closes_active")
        row = {
            "id": f"close-{len(self.rows) + 1}",
            "company_id": company_id,
            "period": str(period),
            "closed_by": user_id,
            "closed_by_email": f"{user_id}@example.test",
            "closed_at": self._now(),
            "reopened_by": None,
            "reopened_by_email": None,
            "reopened_at": None,
        }
        self.rows.append(row)
        self._add_log(row, "closed", user_id)
        return row

    def reopen(self, company_id: str, period: date, user_id: str) -> dict | None:
        row = self.get_active(company_id, period)
        if row is None:
            return None
        row.update(
            reopened_by=user_id,
            reopened_by_email=f"{user_id}@example.test",
            reopened_at=self._now(),
        )
        self._add_log(row, "reopened", user_id)
        return row

    def _add_log(self, row: dict, event: str, user_id: str) -> None:
        self.log.append(
            {
                "company_id": row["company_id"],
                "period": row["period"],
                "event": event,
                "actor_email": f"{user_id}@example.test",
                "created_at": self._now(),
            }
        )

    def list_log(self, company_id: str, period: date) -> list[dict]:
        return [
            {k: e[k] for k in ("event", "actor_email", "created_at")}
            for e in self.log
            if e["company_id"] == company_id and e["period"] == str(period)
        ]

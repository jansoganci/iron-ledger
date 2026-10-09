"""Consolidation keeps every uploaded file so a later Retry can re-run them."""

from __future__ import annotations

from datetime import date

import pandas as pd

from backend.agents.orchestrator import _run_consolidation
from backend.tools.retry_files import files_for_retry

USER = "3f2b8c1e-9a4d-4e6f-8b2a-1c3d5e7f9a0b"
PERIOD = date(2026, 3, 1)
KEYS = [f"{USER}/2026-03-01/payroll.xlsx", f"{USER}/2026-03-01/gl.xlsx"]


class _Runs:
    def __init__(self) -> None:
        self.preview: dict | None = None

    def get_by_id(self, run_id: str) -> dict:
        return {"parse_preview": {}}

    def update_status(self, *args, **kwargs) -> None:
        return None

    def set_parse_preview(self, run_id: str, preview: dict) -> None:
        self.preview = preview

    def set_file_count(self, run_id: str, file_count: int) -> None:
        return None


def test_consolidation_stores_the_list_the_next_retry_reads(monkeypatch) -> None:
    frame = pd.DataFrame(
        [
            {
                "account": "Rent",
                "amount": 10.0,
                "category": "OPEX",
                "source_breakdown": [],
            }
        ]
    )
    monkeypatch.setattr(
        "backend.agents.orchestrator.consolidate",
        lambda *args, **kwargs: (frame, []),
    )
    runs = _Runs()
    per_file = [
        ("payroll.xlsx", [{"account": "Wages", "amount": 1.0}], "amount", frame),
        ("gl.xlsx", [{"account": "Rent", "amount": 10.0}], "amount", frame, True),
    ]

    _run_consolidation("run-1", "co-1", PERIOD, per_file, runs, KEYS)

    assert runs.preview is not None
    assert runs.preview["storage_keys"] == KEYS
    decision = files_for_retry(
        {
            "file_count": 2,
            "storage_key": KEYS[0],
            "parse_preview": runs.preview,
        },
        USER,
        PERIOD,
    )
    assert decision.refusal is None
    assert decision.keys == tuple(KEYS)

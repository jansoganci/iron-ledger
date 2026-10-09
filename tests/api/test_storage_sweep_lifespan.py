"""The daily sweep starts with the app, waits before its first run, stops cleanly."""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from backend import main


def test_app_start_and_stop_do_not_sweep_immediately(monkeypatch) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(main, "sweep_abandoned_uploads", lambda *a: calls.append(a))

    with TestClient(main.app) as client:
        assert client.get("/health").status_code == 200

    assert calls == []
    assert main._SWEEP_FIRST_DELAY_SECONDS >= 60
    assert main._SWEEP_INTERVAL_SECONDS == 24 * 60 * 60


def test_loop_keeps_running_after_a_failed_sweep(monkeypatch) -> None:
    calls: list[int] = []

    def sweep(*_):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("storage down")

    monkeypatch.setattr(main, "sweep_abandoned_uploads", sweep)
    monkeypatch.setattr(main, "get_runs_repo", object)
    monkeypatch.setattr(main, "get_file_storage", object)
    monkeypatch.setattr(main, "_SWEEP_FIRST_DELAY_SECONDS", 0)
    monkeypatch.setattr(main, "_SWEEP_INTERVAL_SECONDS", 0)

    async def scenario() -> None:
        task = asyncio.create_task(main._storage_sweep_loop())
        for _ in range(200):
            if len(calls) >= 2:
                break
            await asyncio.sleep(0.01)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(scenario())
    assert len(calls) >= 2

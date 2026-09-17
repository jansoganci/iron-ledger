from __future__ import annotations

from backend.domain.regenerate import (
    REGENERATE_PREVIEW_KEY,
    attach_regenerate_flag,
    run_wants_regenerate,
    strip_regenerate_flag,
)


def test_attach_and_strip_round_trip() -> None:
    preview = {"rows": [1]}
    flagged = attach_regenerate_flag(preview, regenerate=True)
    assert flagged[REGENERATE_PREVIEW_KEY] is True
    assert flagged["rows"] == [1]
    assert run_wants_regenerate({"parse_preview": flagged}) is True
    stripped = strip_regenerate_flag(flagged)
    assert REGENERATE_PREVIEW_KEY not in stripped
    assert stripped["rows"] == [1]


def test_run_without_flag_is_false() -> None:
    assert run_wants_regenerate({"parse_preview": {"rows": []}}) is False
    assert run_wants_regenerate({}) is False
    assert run_wants_regenerate(None) is False

from __future__ import annotations

from backend.tools.pii_sanitizer import sanitize_sample


def _row(row_index: int, values: list, is_bold: bool = False) -> dict:
    return {
        "row_index": row_index,
        "values": values,
        "is_bold": is_bold,
        "indent_level": 0.0,
        "is_merged": False,
    }


# -----------------------------------------------------------------------------
# Redaction — the three categories we commit to catching
# -----------------------------------------------------------------------------


def test_redacts_ssn_embedded_in_memo():
    rows = [_row(0, ["03/31/2026", "Refund per ticket SSN 123-45-6789", 500.0])]
    out = sanitize_sample(rows)
    assert out[0]["values"][0] == "03/31/2026"
    assert out[0]["values"][1] == "[REDACTED]"
    assert out[0]["values"][2] == 500.0


def test_redacts_email_in_vendor_cell():
    rows = [_row(0, ["03/31/2026", "Invoice from alice@example.com", 1200.0])]
    out = sanitize_sample(rows)
    assert out[0]["values"][1] == "[REDACTED]"


def test_redacts_credit_card_with_separators():
    rows = [
        _row(0, ["Refund to card 4111-1111-1111-1111", 50.0]),
        _row(1, ["Refund to card 4111 1111 1111 1111", 50.0]),
        _row(2, ["Refund to card 4111111111111111", 50.0]),
    ]
    out = sanitize_sample(rows)
    for i in range(3):
        assert (
            out[i]["values"][0] == "[REDACTED]"
        ), f"row {i} not redacted: {out[i]['values'][0]!r}"


def test_no_op_on_clean_sample():
    rows = [
        _row(0, ["Date", "Account", "Amount"], is_bold=True),
        _row(1, ["03/31/2026", "Revenue", 1000.0]),
        _row(2, ["03/31/2026", "COGS", -400.0]),
    ]
    out = sanitize_sample(rows)
    assert out == rows  # every cell value passes through unchanged


# -----------------------------------------------------------------------------
# The critical test — over-redaction regression guard (R-006 flip side)
# -----------------------------------------------------------------------------


def test_legitimate_accounting_values_survive_unchanged():
    """The non-negotiable: redaction must NOT match DRONE-shape accounting data."""
    rows = [
        _row(
            0,
            [
                "03/31/2026",  # per-transaction date
                "4000 - HobiFly X1 — E-commerce",  # account code + name + em-dash
                "5010 - Component Costs",  # account code + name
                45000,  # integer amount
                -18000.50,  # float amount
                "Qty: 34",  # memo
                "Trade show spike in March",  # free-text description
                "0.394",  # percentage-as-decimal
                "2026",  # year
                "1234",  # short numeric (invoice? PO?)
            ],
        ),
    ]
    out = sanitize_sample(rows)
    # Every cell survives byte-identical — not a single false positive.
    assert out[0]["values"] == rows[0]["values"]


# -----------------------------------------------------------------------------
# Non-destructiveness — structure + flags + None pattern preserved
# -----------------------------------------------------------------------------


def test_row_structure_and_flags_preserved():
    rows = [
        _row(5, ["Date", "Account", "Amount"], is_bold=True),
        _row(6, [None, "REVENUE", None], is_bold=True),
        _row(7, ["03/31/2026", "4000 - HobiFly", 45000]),
    ]
    # Inject one PII cell so the path that redacts runs at least once
    rows[2]["values"][1] = "from alice@example.com"
    out = sanitize_sample(rows)

    # Row count unchanged
    assert len(out) == 3
    # Per-row column width unchanged
    for orig, new in zip(rows, out):
        assert len(new["values"]) == len(orig["values"])
    # Flags pass through untouched
    assert out[0]["is_bold"] is True
    assert out[1]["is_bold"] is True
    assert out[2]["is_bold"] is False
    # None cells stay None (Discovery's blank-row detection relies on this)
    assert out[1]["values"][0] is None
    assert out[1]["values"][2] is None
    # Non-PII cells keep their original type (not coerced to string)
    assert out[2]["values"][0] == "03/31/2026"
    assert out[2]["values"][2] == 45000
    assert isinstance(out[2]["values"][2], int)


# -----------------------------------------------------------------------------
# Audit guarantee — no cell values in logs
# -----------------------------------------------------------------------------


def test_values_never_appear_in_log_payload(caplog):
    secret_ssn = "999-88-7777"
    secret_email = "victim@example.com"
    rows = [_row(0, [secret_ssn, secret_email, 500.0])]
    with caplog.at_level("INFO"):
        sanitize_sample(rows, run_id="run-audit")
    log_text = "\n".join(
        r.getMessage() + str(getattr(r, "__dict__", "")) for r in caplog.records
    )
    # Neither secret should appear in any log line
    assert secret_ssn not in log_text
    assert secret_email not in log_text
    # But the summary count should
    ssn_count = sum(
        r.__dict__.get("categories", {}).get("ssn", 0) for r in caplog.records
    )
    assert ssn_count >= 1

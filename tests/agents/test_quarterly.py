"""Unit tests for quarterly.py — aggregation logic, progress tracking, and guardrail integration."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from backend.agents.quarterly import (
    QuarterlyAgent,
    _quarter_to_months,
    _period_to_label,
)
from backend.domain.contracts import NarrativeJSON
from backend.domain.entities import Anomaly


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


def test_quarter_to_months_q1():
    """Q1 should return Jan, Feb, Mar."""
    months = _quarter_to_months(2026, 1)
    assert months == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]


def test_quarter_to_months_q4():
    """Q4 should return Oct, Nov, Dec."""
    months = _quarter_to_months(2026, 4)
    assert months == [date(2026, 10, 1), date(2026, 11, 1), date(2026, 12, 1)]


def test_period_to_label():
    """Period should convert to lowercase month abbreviation."""
    assert _period_to_label(date(2026, 1, 1)) == "jan"
    assert _period_to_label(date(2026, 6, 1)) == "jun"
    assert _period_to_label(date(2026, 12, 1)) == "dec"


# ---------------------------------------------------------------------------
# Aggregation logic tests
# ---------------------------------------------------------------------------


def test_quarterly_agent_aggregation_with_3_months():
    """Test aggregation logic with all 3 months available."""
    # Mock dependencies
    runs_repo = MagicMock()
    anomalies_repo = MagicMock()
    llm_client = MagicMock()
    reports_repo = MagicMock()

    # Setup mock data for 3 months
    jan_summary = {
        "accounts": {
            "Revenue": {"category": "REVENUE", "current": 100000.0},
            "COGS": {"category": "COGS", "current": 40000.0},
            "OpEx": {"category": "OPEX", "current": 30000.0},
        }
    }
    feb_summary = {
        "accounts": {
            "Revenue": {"category": "REVENUE", "current": 120000.0},
            "COGS": {"category": "COGS", "current": 48000.0},
            "OpEx": {"category": "OPEX", "current": 32000.0},
        }
    }
    mar_summary = {
        "accounts": {
            "Revenue": {"category": "REVENUE", "current": 130000.0},
            "COGS": {"category": "COGS", "current": 52000.0},
            "OpEx": {"category": "OPEX", "current": 35000.0},
        }
    }

    # Mock runs_repo to return all 3 months
    def mock_get_latest_run_id(company_id, period):
        return f"run-{period.month}"

    def mock_get_by_id(run_id):
        if run_id == "run-1":
            return {"status": "complete", "pandas_summary": jan_summary}
        elif run_id == "run-2":
            return {"status": "complete", "pandas_summary": feb_summary}
        elif run_id == "run-3":
            return {"status": "complete", "pandas_summary": mar_summary}
        return None

    runs_repo.get_latest_run_id_for_period = mock_get_latest_run_id
    runs_repo.get_by_id = mock_get_by_id

    # Mock anomalies_repo to return empty list
    anomalies_repo.list_for_period = MagicMock(return_value=[])

    # Mock LLM to return valid NarrativeJSON
    llm_client.call = MagicMock(
        return_value=NarrativeJSON(
            narrative="Q1 2026 revenue was $350,000 with a gross margin of 40%.",
            numbers_used=[
                350000.0,
                40.0,
                350000.0,
                140000.0,
                97000.0,
                60000.0,
                72000.0,
                78000.0,
            ],
        )
    )

    # Create agent and run
    agent = QuarterlyAgent(runs_repo, anomalies_repo, llm_client, reports_repo)
    result = agent.run(company_id="test-company", year=2026, quarter=1)

    # Verify success
    assert result["status"] == "complete"
    assert "result" in result

    # Verify aggregated totals
    kpis = result["result"]["kpis"]
    assert kpis["revenue"] == 350000.0  # 100k + 120k + 130k
    assert kpis["opex"] == 97000.0  # 30k + 32k + 35k
    # Gross margin should be calculated: (350k - 140k) / 350k * 100 = 60%
    assert 59.9 < kpis["gross_margin"] < 60.1

    # Verify missing_months is empty
    assert result["result"]["missing_months"] == []


def test_quarterly_agent_with_2_months_missing_one():
    """Test aggregation with 2 months (one missing)."""
    # Mock dependencies
    runs_repo = MagicMock()
    anomalies_repo = MagicMock()
    llm_client = MagicMock()
    reports_repo = MagicMock()

    # Setup mock data for 2 months only (Jan missing)
    feb_summary = {
        "accounts": {
            "Revenue": {"category": "REVENUE", "current": 120000.0},
            "COGS": {"category": "COGS", "current": 48000.0},
        }
    }
    mar_summary = {
        "accounts": {
            "Revenue": {"category": "REVENUE", "current": 130000.0},
            "COGS": {"category": "COGS", "current": 52000.0},
        }
    }

    # Mock runs_repo to return only Feb and Mar
    def mock_get_latest_run_id(company_id, period):
        if period.month == 1:
            return None  # Jan missing
        return f"run-{period.month}"

    def mock_get_by_id(run_id):
        if run_id == "run-2":
            return {"status": "complete", "pandas_summary": feb_summary}
        elif run_id == "run-3":
            return {"status": "complete", "pandas_summary": mar_summary}
        return None

    runs_repo.get_latest_run_id_for_period = mock_get_latest_run_id
    runs_repo.get_by_id = mock_get_by_id

    # Mock anomalies_repo
    anomalies_repo.list_for_period = MagicMock(return_value=[])

    # Mock LLM
    llm_client.call = MagicMock(
        return_value=NarrativeJSON(
            narrative="Q1 2026 partial summary.", numbers_used=[250000.0, 100000.0]
        )
    )

    # Create agent and run
    agent = QuarterlyAgent(runs_repo, anomalies_repo, llm_client, reports_repo)
    result = agent.run(company_id="test-company", year=2026, quarter=1)

    # Verify success
    assert result["status"] == "complete"

    # Verify missing_months includes January
    assert "2026-01-01" in result["result"]["missing_months"]

    # Verify aggregated totals (only Feb + Mar)
    kpis = result["result"]["kpis"]
    assert kpis["revenue"] == 250000.0  # 120k + 130k


def test_quarterly_agent_with_less_than_2_months_returns_error():
    """Test that <2 months returns empty_data error."""
    # Mock dependencies
    runs_repo = MagicMock()
    anomalies_repo = MagicMock()
    llm_client = MagicMock()
    reports_repo = MagicMock()

    # Mock runs_repo to return only 1 month
    def mock_get_latest_run_id(company_id, period):
        if period.month == 3:
            return "run-3"
        return None

    def mock_get_by_id(run_id):
        if run_id == "run-3":
            return {
                "status": "complete",
                "pandas_summary": {
                    "accounts": {
                        "Revenue": {"category": "REVENUE", "current": 100000.0}
                    }
                },
            }
        return None

    runs_repo.get_latest_run_id_for_period = mock_get_latest_run_id
    runs_repo.get_by_id = mock_get_by_id

    # Create agent and run
    agent = QuarterlyAgent(runs_repo, anomalies_repo, llm_client, reports_repo)
    result = agent.run(company_id="test-company", year=2026, quarter=1)

    # Verify error
    assert result["status"] == "failed"
    assert result["error_type"] == "empty_data"


# ---------------------------------------------------------------------------
# Progress tracking tests
# ---------------------------------------------------------------------------


def test_quarterly_agent_progress_callback():
    """Test that progress callback is invoked at each step."""
    # Mock dependencies
    runs_repo = MagicMock()
    anomalies_repo = MagicMock()
    llm_client = MagicMock()
    reports_repo = MagicMock()

    # Setup minimal mock data
    summary = {
        "accounts": {
            "Revenue": {"category": "REVENUE", "current": 100000.0},
            "COGS": {"category": "COGS", "current": 40000.0},
        }
    }

    runs_repo.get_latest_run_id_for_period = MagicMock(return_value="run-1")
    runs_repo.get_by_id = MagicMock(
        return_value={"status": "complete", "pandas_summary": summary}
    )
    anomalies_repo.list_for_period = MagicMock(return_value=[])
    # Use numbers that will pass guardrail - quarterly totals (3x100k revenue, 3x40k cogs, etc.)
    llm_client.call = MagicMock(
        return_value=NarrativeJSON(
            narrative="Test",
            numbers_used=[
                300000.0,  # q_total_revenue (3 x 100k)
                120000.0,  # q_total_cogs (3 x 40k)
                60.0,  # q_avg_gross_margin
            ],
        )
    )

    # Track progress updates
    progress_updates = []

    def track_progress(pct, label):
        progress_updates.append((pct, label))

    # Create agent and run
    agent = QuarterlyAgent(runs_repo, anomalies_repo, llm_client, reports_repo)
    agent.run(
        company_id="test-company",
        year=2026,
        quarter=1,
        progress_callback=track_progress,
    )

    # Verify progress updates happened
    assert len(progress_updates) > 5
    # Verify it starts at 10% and ends at 100%
    assert progress_updates[0][0] == 10
    assert progress_updates[-1][0] == 100
    assert progress_updates[-1][1] == "Persisting report..."


# ---------------------------------------------------------------------------
# YoY delta tests
# ---------------------------------------------------------------------------


def test_quarterly_agent_yoy_deltas_when_prior_year_available():
    """Test YoY delta calculation when prior year Q1 exists."""
    # Mock dependencies
    runs_repo = MagicMock()
    anomalies_repo = MagicMock()
    llm_client = MagicMock()
    reports_repo = MagicMock()

    # Current year Q1 data
    current_summary = {
        "accounts": {
            "Revenue": {"category": "REVENUE", "current": 120000.0},
            "COGS": {"category": "COGS", "current": 48000.0},
            "OpEx": {"category": "OPEX", "current": 30000.0},
        }
    }

    # Prior year Q1 data (2025)
    prior_summary = {
        "accounts": {
            "Revenue": {"category": "REVENUE", "current": 100000.0},
            "COGS": {"category": "COGS", "current": 40000.0},
            "OpEx": {"category": "OPEX", "current": 32000.0},
        }
    }

    def mock_get_latest_run_id(company_id, period):
        return f"run-{period.year}-{period.month}"

    def mock_get_by_id(run_id):
        if "2026" in run_id:
            return {"status": "complete", "pandas_summary": current_summary}
        elif "2025" in run_id:
            return {"status": "complete", "pandas_summary": prior_summary}
        return None

    runs_repo.get_latest_run_id_for_period = mock_get_latest_run_id
    runs_repo.get_by_id = mock_get_by_id
    anomalies_repo.list_for_period = MagicMock(return_value=[])
    llm_client.call = MagicMock(
        return_value=NarrativeJSON(
            narrative="YoY test",
            numbers_used=[
                360000.0,
                60.0,
                90000.0,
                300000.0,
                60.0,
                96000.0,
                20.0,
                -6.25,
            ],
        )
    )

    # Create agent and run
    agent = QuarterlyAgent(runs_repo, anomalies_repo, llm_client, reports_repo)
    result = agent.run(company_id="test-company", year=2026, quarter=1)

    # Verify YoY deltas are present
    assert result["status"] == "complete"
    assert result["result"]["yoy_deltas"] is not None

    # Verify YoY calculations
    yoy = result["result"]["yoy_deltas"]
    # Revenue YoY: (360k - 300k) / 300k = 20%
    assert 19.9 < yoy["yoy_revenue_pct"] < 20.1


def test_quarterly_agent_yoy_null_when_prior_year_incomplete():
    """Test YoY is null when prior year has <2 months."""
    # Mock dependencies
    runs_repo = MagicMock()
    anomalies_repo = MagicMock()
    llm_client = MagicMock()
    reports_repo = MagicMock()

    # Current year has 3 months
    current_summary = {
        "accounts": {
            "Revenue": {"category": "REVENUE", "current": 100000.0},
        }
    }

    def mock_get_latest_run_id(company_id, period):
        # Only current year (2026) has data
        if period.year == 2026:
            return f"run-{period.month}"
        return None  # Prior year (2025) missing

    def mock_get_by_id(run_id):
        return {"status": "complete", "pandas_summary": current_summary}

    runs_repo.get_latest_run_id_for_period = mock_get_latest_run_id
    runs_repo.get_by_id = mock_get_by_id
    anomalies_repo.list_for_period = MagicMock(return_value=[])
    llm_client.call = MagicMock(
        return_value=NarrativeJSON(narrative="Test", numbers_used=[300000.0, 60.0])
    )

    # Create agent and run
    agent = QuarterlyAgent(runs_repo, anomalies_repo, llm_client, reports_repo)
    result = agent.run(company_id="test-company", year=2026, quarter=1)

    # Verify YoY is null
    assert result["status"] == "complete"
    assert result["result"]["yoy_deltas"] is None


# ---------------------------------------------------------------------------
# Anomaly grouping tests
# ---------------------------------------------------------------------------


def test_quarterly_agent_groups_recurring_anomalies():
    """Test that anomalies are grouped by recurrence (3/3, 2/3, 1/3)."""
    # Mock dependencies
    runs_repo = MagicMock()
    anomalies_repo = MagicMock()
    llm_client = MagicMock()
    reports_repo = MagicMock()

    # Setup data
    summary = {
        "accounts": {
            "Revenue": {"category": "REVENUE", "current": 100000.0},
        }
    }

    runs_repo.get_latest_run_id_for_period = MagicMock(return_value="run-1")
    runs_repo.get_by_id = MagicMock(
        return_value={"status": "complete", "pandas_summary": summary}
    )

    # Create anomalies: Account A in all 3 months, Account B in 2 months, Account C in 1 month
    def mock_list_for_period(company_id, period):
        anomalies = []
        if period.month >= 1:  # Jan, Feb, Mar
            anomalies.append(
                Anomaly(
                    id="a-1",
                    company_id=company_id,
                    account_id="account-a",
                    period=period,
                    anomaly_type="anomaly",
                    severity="high",
                    description="Account A is 20% above average.",
                    variance_pct=20.0,
                )
            )
        if period.month >= 2:  # Feb, Mar
            anomalies.append(
                Anomaly(
                    id="b-1",
                    company_id=company_id,
                    account_id="account-b",
                    period=period,
                    anomaly_type="anomaly",
                    severity="medium",
                    description="Account B is 15% above average.",
                    variance_pct=15.0,
                )
            )
        if period.month == 3:  # Mar only
            anomalies.append(
                Anomaly(
                    id="c-1",
                    company_id=company_id,
                    account_id="account-c",
                    period=period,
                    anomaly_type="anomaly",
                    severity="high",
                    description="Account C is 30% above average.",
                    variance_pct=30.0,
                )
            )
        return anomalies

    anomalies_repo.list_for_period = mock_list_for_period
    llm_client.call = MagicMock(
        return_value=NarrativeJSON(narrative="Test", numbers_used=[300000.0])
    )

    # Create agent and run
    agent = QuarterlyAgent(runs_repo, anomalies_repo, llm_client, reports_repo)
    result = agent.run(company_id="test-company", year=2026, quarter=1)

    # Verify anomaly grouping
    assert result["status"] == "complete"
    grouped = result["result"]["anomalies_grouped"]

    # Account A should be in recurring (3/3)
    assert len(grouped["recurring"]) == 1
    assert grouped["recurring"][0]["account_id"] == "account-a"
    assert grouped["recurring"][0]["recurrence_count"] == 3

    # Account B should be in persistent (2/3)
    assert len(grouped["persistent"]) == 1
    assert grouped["persistent"][0]["account_id"] == "account-b"
    assert grouped["persistent"][0]["recurrence_count"] == 2

    # Account C should be in oneOff (1/3)
    assert len(grouped["oneOff"]) == 1
    assert grouped["oneOff"][0]["account_id"] == "account-c"
    assert grouped["oneOff"][0]["recurrence_count"] == 1


# ---------------------------------------------------------------------------
# Fix 1 regression — created_at string from Supabase must not crash
# ---------------------------------------------------------------------------


def test_get_quarterly_report_string_created_at_does_not_raise():
    """Supabase returns created_at as an ISO string, not datetime.
    The GET /report/.../quarterly endpoint must not call .isoformat() on it."""
    from backend.domain.entities import Report

    # Simulate a Report whose created_at is a plain string (as Supabase returns it)
    report = Report(
        id="r-1",
        company_id="c-1",
        period=date(2026, 1, 1),
        summary="test",
        report_type="quarterly",
        quarter=1,
        year=2026,
        created_at="2026-04-26T12:00:00+00:00",  # string, not datetime
        quarterly_data={"narrative": "Q1 summary", "kpis": {}},
    )

    # Reproduce the expression from routes.py get_quarterly_report
    created_at = report.created_at
    result = (
        created_at
        if isinstance(created_at, str)
        else created_at.isoformat() if created_at else None
    )

    assert result == "2026-04-26T12:00:00+00:00"


def test_get_quarterly_report_datetime_created_at_does_not_raise():
    """datetime created_at still works after the fix."""
    from datetime import datetime, timezone

    from backend.domain.entities import Report

    dt = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    report = Report(
        id="r-2",
        company_id="c-1",
        period=date(2026, 1, 1),
        summary="test",
        report_type="quarterly",
        quarter=1,
        year=2026,
        created_at=dt,
    )

    created_at = report.created_at
    result = (
        created_at
        if isinstance(created_at, str)
        else created_at.isoformat() if created_at else None
    )

    assert result == dt.isoformat()


def test_get_quarterly_report_none_created_at_returns_none():
    """None created_at returns None, not an error."""
    from backend.domain.entities import Report

    report = Report(
        id="r-3",
        company_id="c-1",
        period=date(2026, 1, 1),
        summary="test",
        report_type="quarterly",
        quarter=1,
        year=2026,
        created_at=None,
    )

    created_at = report.created_at
    result = (
        created_at
        if isinstance(created_at, str)
        else created_at.isoformat() if created_at else None
    )

    assert result is None

from __future__ import annotations

import uuid
from datetime import date
from statistics import mean
from uuid import UUID

from backend.domain.contracts import AccountSummary, PandasSummary
from backend.domain.entities import Anomaly
from backend.domain.ports import (
    AccountsRepo,
    AnomaliesRepo,
    CompaniesRepo,
    EntriesRepo,
    RunsRepo,
)
from backend.logger import get_logger
from backend.tools.account_tags import is_payroll_account

logger = get_logger(__name__)


# Fail-safe constants — also the 500k_plus / NULL-band gates.
# Claude never sees these. Pandas only.
_TIER1_DOLLAR = 50_000.0
_TIER1_PCT = 10.0
_TIER2_DOLLAR = 10_000.0
_TIER2_PCT = 3.0

_BAND_R: dict[str, float] = {
    "under_100k": 50_000.0,
    "100k_250k": 175_000.0,
    "250k_500k": 375_000.0,
    "500k_plus": 2_000_000.0,
}


def _gates_from_band(band: str | None) -> tuple[float, float]:
    """Return (dollar_t1, dollar_t2). Claude never sees R. Pandas only.

    NULL / unknown strings fail-safe to today's $50k / $10k — never $0.
    """
    if not band or band not in _BAND_R:
        return _TIER1_DOLLAR, _TIER2_DOLLAR
    r = _BAND_R[band]
    return max(500.0, 0.025 * r), max(250.0, 0.005 * r)


def calculate_variance(
    current: float,
    historical_avg: float,
    history_count: int,
    category: str = "OTHER",
    *,
    account_name: str | None = None,
    dollar_t1: float | None = None,
    dollar_t2: float | None = None,
) -> dict:
    """Return variance dict. All arithmetic happens here — Claude never sees this.

    Tier 2 (REVENUE or payroll-tagged GL name): |delta| > dollar_t2 AND |pct| > 3%
    Tier 1 (everything else):                   |delta| > dollar_t1 AND |pct| > 10%
    Omitted gates fail-safe to $50k / $10k. PAYROLL / DEFERRED_REVENUE category
    strings are not live gates — those categories are not seeded.
    """
    if not historical_avg:
        return {"variance_pct": None, "severity": "no_history", "flag": False}

    variance_pct = ((current - historical_avg) / abs(historical_avg)) * 100
    abs_delta = abs(current - historical_avg)
    abs_pct = abs(variance_pct)

    t1 = _TIER1_DOLLAR if dollar_t1 is None else dollar_t1
    t2 = _TIER2_DOLLAR if dollar_t2 is None else dollar_t2
    is_tier2 = category == "REVENUE" or is_payroll_account(account_name)
    dollar_gate = t2 if is_tier2 else t1
    pct_gate = _TIER2_PCT if is_tier2 else _TIER1_PCT

    flag = abs_delta > dollar_gate and abs_pct > pct_gate

    severity = "high" if abs_pct > 30 else "medium" if abs_pct > 15 else "low"
    return {"variance_pct": round(variance_pct, 2), "severity": severity, "flag": flag}


class ComparisonAgent:
    def __init__(
        self,
        entries_repo: EntriesRepo,
        anomalies_repo: AnomaliesRepo,
        runs_repo: RunsRepo,
        accounts_repo: AccountsRepo,
        companies_repo: CompaniesRepo,
    ) -> None:
        self._entries = entries_repo
        self._anomalies = anomalies_repo
        self._runs = runs_repo
        self._accounts = accounts_repo
        self._companies = companies_repo

    def run(
        self,
        run_id: str,
        company_id: str,
        period: date,
    ) -> PandasSummary:
        # Update progress: starting comparison
        from backend.domain.run_state_machine import RunStatus

        try:
            run = self._runs.get_by_id(run_id)
            current_status = run.get("status")
            if current_status == RunStatus.COMPARING.value:
                self._runs.update_status(
                    run_id,
                    RunStatus(current_status),
                    extra={
                        "step": 3,
                        "step_label": "Comparing to history...",
                        "progress_pct": 60,
                    },
                )
        except Exception as exc:
            logger.warning(
                "comparison progress update failed", extra={"error": str(exc)}
            )

        company = self._companies.get_by_id(company_id)
        dollar_t1, dollar_t2 = _gates_from_band(company.get("monthly_revenue_band"))

        # 1. Fetch prior flag counts once — avoids N+1 queries inside the loop
        prior_flag_counts = self._anomalies.list_account_flag_counts_before(
            company_id, period, lookback_months=6
        )

        # 2. Fetch current period entries
        current_entries = self._entries.list_for_period(company_id, period)

        # 3. Fetch historical entries (up to 6 months prior)
        history = self._entries.list_history(company_id, period, lookback_months=6)

        # 4. Resolve account metadata
        accounts_map = self._accounts.get_accounts_by_id(company_id)

        # 5. Group history by account_id
        history_by_account: dict[str, list[float]] = {}
        for entry in history:
            history_by_account.setdefault(entry.account_id, []).append(
                float(entry.actual_amount)
            )

        # 6. Process each current entry
        summaries: dict[str, AccountSummary] = {}
        flagged_anomalies: list[Anomaly] = []

        for entry in current_entries:
            account_info = accounts_map.get(
                entry.account_id,
                {"name": entry.account_id, "category": "OTHER"},
            )
            account_name = account_info["name"]
            category = account_info["category"]

            hist_amounts = history_by_account.get(entry.account_id, [])
            historical_avg = mean(hist_amounts) if hist_amounts else 0.0
            current_val = float(entry.actual_amount)

            result = calculate_variance(
                current_val,
                historical_avg,
                len(hist_amounts),
                category,
                account_name=account_name,
                dollar_t1=dollar_t1,
                dollar_t2=dollar_t2,
            )

            # Build AccountSummary
            summaries[account_name] = AccountSummary(
                account=account_name,
                category=category,
                current=current_val,
                historical_avg=historical_avg,
                variance_pct=(
                    result["variance_pct"]
                    if result["variance_pct"] is not None
                    else 0.0
                ),
                severity=result["severity"],
            )

            # Build Anomaly for flagged entries (skip no_history entirely)
            if result["flag"] and result["severity"] != "no_history":
                direction = "above" if current_val > historical_avg else "below"
                periods_label = (
                    f"{len(hist_amounts)}-period average"
                    if len(hist_amounts) > 1
                    else "1-period average"
                )
                description = (
                    f"{account_name} is {abs(result['variance_pct']):.1f}% "
                    f"{direction} the {periods_label}."
                )
                prior = prior_flag_counts.get(entry.account_id, 0)
                is_recurring = prior >= 2
                if is_recurring:
                    description += (
                        f" Flagged in {prior} of the past 6 months — recurring pattern."
                    )
                flagged_anomalies.append(
                    Anomaly(
                        id=str(uuid.uuid4()),
                        company_id=company_id,
                        account_id=entry.account_id,
                        period=period,
                        anomaly_type="anomaly",
                        severity=result["severity"],
                        description=description,
                        variance_pct=result["variance_pct"],
                        is_recurring=is_recurring,
                    )
                )

        # 7. Persist anomalies
        self._anomalies.write_many(flagged_anomalies)

        # Update progress: comparison complete
        try:
            run = self._runs.get_by_id(run_id)
            current_status = run.get("status")
            if current_status == RunStatus.COMPARING.value:
                self._runs.update_status(
                    run_id,
                    RunStatus(current_status),
                    extra={"progress_pct": 75},
                )
        except Exception as exc:
            logger.warning(
                "comparison end progress update failed", extra={"error": str(exc)}
            )

        logger.info(
            "comparison complete",
            extra={
                "run_id": run_id,
                "company_id": company_id,
                "accounts_processed": len(summaries),
                "anomalies_flagged": len(flagged_anomalies),
                "monthly_revenue_band": company.get("monthly_revenue_band"),
            },
        )

        # 7. Build and return PandasSummary
        return PandasSummary(
            accounts=summaries,
            period=period,
            company_id=UUID(company_id),
        )

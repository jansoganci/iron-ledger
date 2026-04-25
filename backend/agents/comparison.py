from __future__ import annotations

import uuid
from datetime import date
from statistics import mean
from uuid import UUID

from backend.domain.contracts import AccountSummary, PandasSummary
from backend.domain.entities import Anomaly
from backend.domain.ports import AccountsRepo, AnomaliesRepo, EntriesRepo, RunsRepo
from backend.domain.run_state_machine import RunStatus
from backend.logger import get_logger

logger = get_logger(__name__)


# Tier 2 applies to high-stakes categories where small % gaps matter.
_TIER2_CATEGORIES = {"REVENUE", "PAYROLL", "DEFERRED_REVENUE"}

# Tier 1 (all other accounts): both gates must clear to flag.
_TIER1_DOLLAR = 50_000.0
_TIER1_PCT = 10.0

# Tier 2 (REVENUE / PAYROLL / DEFERRED_REVENUE): lower gates.
_TIER2_DOLLAR = 10_000.0
_TIER2_PCT = 3.0


def calculate_variance(
    current: float,
    historical_avg: float,
    history_count: int,
    category: str = "OTHER",
) -> dict:
    """Return variance dict. All arithmetic happens here — Claude never sees this.

    Tiered materiality (Track 4):
      Tier 2 (REVENUE, PAYROLL, DEFERRED_REVENUE): flag if |delta| > $10K AND |pct| > 3%
      Tier 1 (all others):                         flag if |delta| > $50K AND |pct| > 10%
    Both gates must be exceeded — dollar floor prevents noise on tiny accounts,
    percentage floor prevents noise on giant accounts with small swings.
    """
    if not historical_avg:
        return {"variance_pct": None, "severity": "no_history", "flag": False}

    variance_pct = ((current - historical_avg) / abs(historical_avg)) * 100
    abs_delta = abs(current - historical_avg)
    abs_pct = abs(variance_pct)

    is_tier2 = category in _TIER2_CATEGORIES
    dollar_gate = _TIER2_DOLLAR if is_tier2 else _TIER1_DOLLAR
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
    ) -> None:
        self._entries = entries_repo
        self._anomalies = anomalies_repo
        self._runs = runs_repo
        self._accounts = accounts_repo

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

        # 1. Fetch current period entries
        current_entries = self._entries.list_for_period(company_id, period)

        # 2. Fetch historical entries (up to 6 months prior)
        history = self._entries.list_history(company_id, period, lookback_months=6)

        # 3. Resolve account metadata
        accounts_map = self._accounts.get_accounts_by_id(company_id)

        # 4. Group history by account_id
        history_by_account: dict[str, list[float]] = {}
        for entry in history:
            history_by_account.setdefault(entry.account_id, []).append(
                float(entry.actual_amount)
            )

        # 5. Process each current entry
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
                current_val, historical_avg, len(hist_amounts), category
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
                    )
                )

        # 6. Persist anomalies
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
            },
        )

        # 7. Build and return PandasSummary
        return PandasSummary(
            accounts=summaries,
            period=period,
            company_id=UUID(company_id),
        )

from __future__ import annotations

from datetime import date

from backend.domain.contracts import NarrativeJSON
from backend.domain.entities import Report
from backend.domain.errors import GuardrailError
from backend.domain.ports import AnomaliesRepo, LLMClient, ReportsRepo, RunsRepo
from backend.logger import get_logger, get_trace_id
from backend.tools.guardrail import verify_guardrail

logger = get_logger(__name__)

QUARTERLY_MODEL = "claude-opus-4-7"  # no user toggle in MVP


def _month_offset(year: int, month: int, offset_months: int) -> tuple[int, int]:
    """Add or subtract offset_months from (year, month). Return (new_year, new_month)."""
    total_months = (year * 12 + month - 1) + offset_months
    new_year = total_months // 12
    new_month = (total_months % 12) + 1
    return new_year, new_month


def _quarter_to_months(year: int, quarter: int) -> list[date]:
    """Return list of 3 month start dates for the quarter (Q1=Jan/Feb/Mar, etc.)."""
    base_month = (quarter - 1) * 3 + 1
    return [date(year, base_month, 1), date(year, base_month + 1, 1), date(year, base_month + 2, 1)]


def _period_to_label(period: date) -> str:
    """Convert period date to 'Jan', 'Feb', etc."""
    return period.strftime("%b").lower()


class QuarterlyAgent:
    def __init__(
        self,
        runs_repo: RunsRepo,
        anomalies_repo: AnomaliesRepo,
        llm_client: LLMClient,
        reports_repo: ReportsRepo,
    ) -> None:
        self._runs = runs_repo
        self._anomalies = anomalies_repo
        self._llm = llm_client
        self._reports = reports_repo

    def run(
        self,
        company_id: str,
        year: int,
        quarter: int,
        progress_callback: callable | None = None,
    ) -> dict[str, any]:
        """Generate quarterly report. Returns dict with result or error.

        Progress callback signature: callback(progress_pct: int, step_label: str)

        Return shape on success:
        {
            "status": "complete",
            "result": {
                "narrative": str,
                "numbers_used": list[float],
                "kpis": dict,
                "missing_months": list[str],
                "yoy_deltas": dict | None,
                "anomalies_grouped": dict,
            }
        }

        Return shape on error:
        {
            "status": "failed",
            "error_type": "timeout" | "guardrail_failed" | "empty_data" | "internal",
            "message": str,
        }
        """

        def update_progress(pct: int, label: str):
            if progress_callback:
                progress_callback(pct, label)

        try:
            # Step 1: Fetch runs for 3 months, identify available + missing (10%)
            update_progress(10, "Fetching quarterly runs...")
            quarter_months = _quarter_to_months(year, quarter)
            runs_data = {}
            missing_months = []

            for period in quarter_months:
                latest_run_id = self._runs.get_latest_run_id_for_period(company_id, period)
                if latest_run_id:
                    run = self._runs.get_by_id(latest_run_id)
                    if run.get("status") == "complete" and run.get("pandas_summary"):
                        runs_data[period] = run["pandas_summary"]
                    else:
                        missing_months.append(str(period))
                else:
                    missing_months.append(str(period))

            if len(runs_data) < 2:
                return {
                    "status": "failed",
                    "error_type": "empty_data",
                    "message": (
                        "Not enough months uploaded. At least 2 complete months "
                        "required for quarterly report."
                    ),
                }

            # Steps 2-4: Aggregate each month (25%, 40%, 55%)
            month_labels = [
                "jan",
                "feb",
                "mar",
                "apr",
                "may",
                "jun",
                "jul",
                "aug",
                "sep",
                "oct",
                "nov",
                "dec",
            ]
            monthly_summaries = {}
            aggregated_summary = {}

            for idx, period in enumerate(sorted(runs_data.keys())):
                progress_pct = 25 + (idx * 15)
                month_label = month_labels[period.month - 1]
                update_progress(progress_pct, f"Aggregating {month_label.capitalize()}...")

                pandas_summary = runs_data[period]
                accounts = pandas_summary.get("accounts", {})

                monthly_summaries[month_label] = {
                    "period": str(period),
                    "accounts": accounts,
                }

                # Aggregate key metrics for this month
                total_revenue = 0.0
                total_cogs = 0.0
                total_opex = 0.0
                gross_profit = 0.0

                for account_name, account_data in accounts.items():
                    category = account_data.get("category", "OTHER")
                    current = account_data.get("current", 0.0)

                    if category == "REVENUE":
                        total_revenue += current
                    elif category == "COGS":
                        total_cogs += current
                    elif category in ("OPEX", "G&A", "R&D"):
                        total_opex += current

                gross_profit = total_revenue - total_cogs
                gross_margin = (gross_profit / total_revenue * 100) if total_revenue != 0 else 0.0

                # Store per-month values in aggregated_summary
                aggregated_summary[f"{month_label}_revenue"] = total_revenue
                aggregated_summary[f"{month_label}_cogs"] = total_cogs
                aggregated_summary[f"{month_label}_opex"] = total_opex
                aggregated_summary[f"{month_label}_gross_profit"] = gross_profit
                aggregated_summary[f"{month_label}_gross_margin"] = gross_margin

            # Step 5: Fetch prior-year quarter (65%)
            update_progress(65, "Fetching prior year data...")
            prior_year = year - 1
            prior_quarter_months = _quarter_to_months(prior_year, quarter)
            prior_runs_data = {}

            for period in prior_quarter_months:
                latest_run_id = self._runs.get_latest_run_id_for_period(company_id, period)
                if latest_run_id:
                    run = self._runs.get_by_id(latest_run_id)
                    if run.get("status") == "complete" and run.get("pandas_summary"):
                        prior_runs_data[period] = run["pandas_summary"]

            # Step 6: Compute aggregated_summary + yoy_deltas in Python (75%)
            update_progress(75, "Computing quarterly aggregates...")

            # Quarterly totals and averages
            available_month_labels = [month_labels[p.month - 1] for p in sorted(runs_data.keys())]

            q_total_revenue = sum(
                aggregated_summary.get(f"{m}_revenue", 0.0) for m in available_month_labels
            )
            q_total_cogs = sum(
                aggregated_summary.get(f"{m}_cogs", 0.0) for m in available_month_labels
            )
            q_total_opex = sum(
                aggregated_summary.get(f"{m}_opex", 0.0) for m in available_month_labels
            )
            q_gross_profit = q_total_revenue - q_total_cogs
            q_gross_margin = (
                (q_gross_profit / q_total_revenue * 100) if q_total_revenue != 0 else 0.0
            )

            aggregated_summary["q_total_revenue"] = q_total_revenue
            aggregated_summary["q_total_cogs"] = q_total_cogs
            aggregated_summary["q_total_opex"] = q_total_opex
            aggregated_summary["q_gross_profit"] = q_gross_profit
            aggregated_summary["q_avg_gross_margin"] = q_gross_margin

            # Month-over-month growth for adjacent available pairs
            sorted_periods = sorted(runs_data.keys())
            mom_revenue_growth = []
            for i in range(1, len(sorted_periods)):
                prev_period = sorted_periods[i - 1]
                curr_period = sorted_periods[i]
                prev_label = month_labels[prev_period.month - 1]
                curr_label = month_labels[curr_period.month - 1]

                prev_rev = aggregated_summary.get(f"{prev_label}_revenue", 0.0)
                curr_rev = aggregated_summary.get(f"{curr_label}_revenue", 0.0)

                if prev_rev != 0:
                    growth_pct = ((curr_rev - prev_rev) / abs(prev_rev)) * 100
                    mom_revenue_growth.append(round(growth_pct, 2))

            aggregated_summary["q_mom_revenue_growth"] = mom_revenue_growth

            # YoY deltas (only if prior-year quarter has ≥2 months)
            yoy_deltas = None
            if len(prior_runs_data) >= 2:
                # Calculate prior year quarterly totals
                py_total_revenue = 0.0
                py_total_cogs = 0.0
                py_total_opex = 0.0

                for period in sorted(prior_runs_data.keys()):
                    pandas_summary = prior_runs_data[period]
                    accounts = pandas_summary.get("accounts", {})

                    for account_name, account_data in accounts.items():
                        category = account_data.get("category", "OTHER")
                        current = account_data.get("current", 0.0)

                        if category == "REVENUE":
                            py_total_revenue += current
                        elif category == "COGS":
                            py_total_cogs += current
                        elif category in ("OPEX", "G&A", "R&D"):
                            py_total_opex += current

                py_gross_profit = py_total_revenue - py_total_cogs
                py_gross_margin = (
                    (py_gross_profit / py_total_revenue * 100) if py_total_revenue != 0 else 0.0
                )

                # Compute YoY deltas
                yoy_revenue_pct = (
                    ((q_total_revenue - py_total_revenue) / abs(py_total_revenue) * 100)
                    if py_total_revenue != 0
                    else None
                )
                yoy_gross_margin_delta = q_gross_margin - py_gross_margin
                yoy_opex_pct = (
                    ((q_total_opex - py_total_opex) / abs(py_total_opex) * 100)
                    if py_total_opex != 0
                    else None
                )

                yoy_deltas = {
                    "py_revenue": py_total_revenue,
                    "py_gross_margin": py_gross_margin,
                    "py_opex": py_total_opex,
                    "yoy_revenue_pct": yoy_revenue_pct,
                    "yoy_gross_margin_delta": yoy_gross_margin_delta,
                    "yoy_opex_pct": yoy_opex_pct,
                }

                # Add YoY values to aggregated_summary for guardrail
                if yoy_revenue_pct is not None:
                    aggregated_summary["yoy_revenue_pct"] = yoy_revenue_pct
                if yoy_gross_margin_delta is not None:
                    aggregated_summary["yoy_gross_margin_delta"] = yoy_gross_margin_delta
                if yoy_opex_pct is not None:
                    aggregated_summary["yoy_opex_pct"] = yoy_opex_pct
                aggregated_summary["py_revenue"] = py_total_revenue
                aggregated_summary["py_gross_margin"] = py_gross_margin
                aggregated_summary["py_opex"] = py_total_opex

            # Fetch and group anomalies by recurrence
            update_progress(70, "Analyzing anomalies...")
            anomalies_grouped = self._group_quarterly_anomalies(
                company_id, quarter_months, runs_data
            )

            # Step 7: Call Claude Opus 4.7 (85%)
            update_progress(85, "Calling Claude Opus...")

            context = {
                "year": year,
                "quarter": quarter,
                "monthly_summaries": monthly_summaries,
                "aggregated_summary": aggregated_summary,
                "missing_months": missing_months,
                "yoy_deltas": yoy_deltas,
                "anomalies_grouped": anomalies_grouped,
            }

            result = self._llm.call(
                prompt="quarterly_report_prompt.txt",
                model=QUARTERLY_MODEL,
                context=context,
                schema=NarrativeJSON,
            )

            # Step 8: verify_guardrail (95%)
            update_progress(95, "Verifying numbers...")

            success, message = verify_guardrail(
                claude_json=result.model_dump(),
                pandas_summary=aggregated_summary,
            )

            if not success:
                logger.warning(
                    "quarterly guardrail failed",
                    extra={
                        "year": year,
                        "quarter": quarter,
                        "reason": message,
                        "trace_id": get_trace_id(),
                    },
                )
                raise GuardrailError(f"Guardrail failed: {message}")

            # Step 9: Persist to DB and return result (100%)
            update_progress(100, "Persisting report...")

            # Build KPI summary for frontend
            kpis = {
                "revenue": q_total_revenue,
                "gross_margin": q_gross_margin,
                "opex": q_total_opex,
            }

            if yoy_deltas:
                kpis["yoy_revenue_pct"] = yoy_deltas.get("yoy_revenue_pct")
                kpis["yoy_gross_margin_delta"] = yoy_deltas.get("yoy_gross_margin_delta")
                kpis["yoy_opex_pct"] = yoy_deltas.get("yoy_opex_pct")

            # Persist quarterly report to DB
            import uuid
            from datetime import date as dt

            # Use first day of first quarter month as the period
            quarter_start_month = (quarter - 1) * 3 + 1
            period_for_report = dt(year, quarter_start_month, 1)

            # Build full quarterly data to persist
            quarterly_data_to_persist = {
                "narrative": result.narrative,
                "numbers_used": result.numbers_used,
                "kpis": kpis,
                "missing_months": missing_months,
                "yoy_deltas": yoy_deltas,
                "anomalies_grouped": anomalies_grouped,
            }

            report_entity = Report(
                id=str(uuid.uuid4()),
                company_id=company_id,
                period=period_for_report,
                summary=result.narrative,
                anomaly_count=sum(
                    len(anomalies_grouped.get(k, [])) for k in ["recurring", "persistent", "oneOff"]
                ),
                error_count=0,
                report_type="quarterly",
                quarter=quarter,
                year=year,
                is_stale=False,
                quarterly_data=quarterly_data_to_persist,
            )

            persisted_report = self._reports.write_quarterly(report_entity)

            logger.info(
                "quarterly report complete",
                extra={
                    "company_id": company_id,
                    "year": year,
                    "quarter": quarter,
                    "report_id": persisted_report.id,
                    "months_available": len(runs_data),
                    "yoy_available": yoy_deltas is not None,
                    "trace_id": get_trace_id(),
                },
            )

            return {
                "status": "complete",
                "result": {
                    "narrative": result.narrative,
                    "numbers_used": result.numbers_used,
                    "kpis": kpis,
                    "missing_months": missing_months,
                    "yoy_deltas": yoy_deltas,
                    "anomalies_grouped": anomalies_grouped,
                },
            }

        except GuardrailError as exc:
            logger.warning(
                "quarterly guardrail error",
                extra={
                    "year": year,
                    "quarter": quarter,
                    "error": str(exc),
                    "trace_id": get_trace_id(),
                },
            )
            return {
                "status": "failed",
                "error_type": "guardrail_failed",
                "message": (
                    "We couldn't verify the report's numbers. " "This usually resolves on a retry."
                ),
            }
        except Exception as exc:
            logger.error(
                "quarterly agent unexpected error",
                extra={
                    "year": year,
                    "quarter": quarter,
                    "error": str(exc),
                    "trace_id": get_trace_id(),
                },
                exc_info=True,
            )
            return {
                "status": "failed",
                "error_type": "internal",
                "message": "Something went wrong. Please try again or contact support.",
            }

    def _group_quarterly_anomalies(
        self,
        company_id: str,
        quarter_months: list[date],
        runs_data: dict[date, dict],
    ) -> dict[str, list]:
        """Group anomalies by recurrence count (3/3, 2/3, 1/3 months).

        Returns:
        {
            "recurring": [
                {
                    "account_id": ...,
                    "account_name": ...,
                    "recurrence_count": 3,
                    "monthly_details": [...]
                }
            ],
            "persistent": [...],  # 2/3 months
            "oneOff": [...],       # 1/3 months
        }
        """
        # Collect all anomalies across the quarter
        account_anomalies = {}  # {account_id: {period: anomaly_obj}}

        for period in quarter_months:
            if period not in runs_data:
                continue

            anomalies = self._anomalies.list_for_period(company_id, period)
            for anomaly in anomalies:
                # Only include medium and high severity
                if anomaly.severity not in ("medium", "high"):
                    continue

                account_id = anomaly.account_id
                if account_id not in account_anomalies:
                    account_anomalies[account_id] = {}

                account_anomalies[account_id][period] = {
                    "variance_pct": anomaly.variance_pct,
                    "severity": anomaly.severity,
                    "description": anomaly.description,
                }

        # Group by recurrence count
        recurring = []
        persistent = []
        one_off = []

        for account_id, periods_map in account_anomalies.items():
            recurrence_count = len(periods_map)

            # Determine account name from first anomaly description
            first_anomaly = list(periods_map.values())[0]
            # Extract account name from description (format: "Account Name is X% above...")
            description = first_anomaly["description"]
            account_name = description.split(" is ")[0] if " is " in description else account_id

            # Build monthly details
            monthly_details = []
            sorted_periods = sorted(periods_map.keys())
            for period in sorted_periods:
                anomaly_data = periods_map[period]
                month_label = _period_to_label(period)
                monthly_details.append(
                    {
                        "month": month_label,
                        "variance_pct": anomaly_data["variance_pct"],
                        "severity": anomaly_data["severity"],
                    }
                )

            # Determine trend
            variances = [
                d["variance_pct"] for d in monthly_details if d["variance_pct"] is not None
            ]
            if len(variances) >= 2:
                if all(variances[i] <= variances[i + 1] for i in range(len(variances) - 1)):
                    trend = "increasing"
                elif all(variances[i] >= variances[i + 1] for i in range(len(variances) - 1)):
                    trend = "decreasing"
                elif all(
                    abs(variances[i] - variances[i + 1]) <= 5 for i in range(len(variances) - 1)
                ):
                    trend = "stable"
                else:
                    trend = "mixed"
            else:
                trend = "n/a"

            item = {
                "account_id": account_id,
                "account_name": account_name,
                "recurrence_count": recurrence_count,
                "monthly_details": monthly_details,
                "trend": trend,
            }

            if recurrence_count == 3:
                recurring.append(item)
            elif recurrence_count == 2:
                persistent.append(item)
            else:
                one_off.append(item)

        return {
            "recurring": recurring,
            "persistent": persistent,
            "oneOff": one_off,
        }

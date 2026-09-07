"""Enriched account mapping — build per-account context, then call Haiku.

Extracted from `ParserAgent._map_accounts`. Kept in `agents/` rather than
`tools/` because it calls the LLM (CLAUDE.md: `tools/` is stateless, no DB,
no LLM). The three ports it needs (`AccountsRepo`, `LLMClient`, `RunsRepo`)
are passed in explicitly instead of living on `self`, so this is a plain
function `ParserAgent` calls rather than a bound method.
"""

from __future__ import annotations

import pandas as pd

from backend.domain.contracts import MappingOutput, MappingResponse
from backend.domain.errors import MappingAmbiguous, TransientIOError
from backend.domain.ports import AccountsRepo, LLMClient, RunsRepo

MAPPING_MODEL = "claude-haiku-4-5-20251001"

_HIGH_CONFIDENCE_THRESHOLD = 0.80


def map_accounts(
    run_id: str,
    company_id: str,
    df: pd.DataFrame,
    accounts_repo: AccountsRepo,
    llm_client: LLMClient,
    runs_repo: RunsRepo,
) -> tuple[dict[str, dict], list[MappingOutput]]:
    """Build per-account context with hierarchy fields, then call Haiku."""
    grouped = df.groupby("account", dropna=False)

    def _first_nonnull(series: pd.Series) -> str | None:
        s = series.dropna()
        return str(s.iloc[0]) if not s.empty else None

    account_info: dict[str, dict] = {}
    for account_name, group in grouped:
        name_str = str(account_name)
        account_info[name_str] = {
            "name": name_str,
            "total": float(group["amount"].sum()),
            "parent_category": _first_nonnull(
                group["parent_category"]
                if "parent_category" in group.columns
                else pd.Series([], dtype=object)
            ),
            "account_code": _first_nonnull(
                group["account_code"]
                if "account_code" in group.columns
                else pd.Series([], dtype=object)
            ),
            "department": _first_nonnull(
                group["department"]
                if "department" in group.columns
                else pd.Series([], dtype=object)
            ),
        }

    known: dict[str, str] = accounts_repo.list_for_company(company_id)

    # Accounts needing Haiku mapping — list-of-dicts per new prompt schema.
    unknown_accounts = [
        info for name, info in account_info.items() if name not in known
    ]

    high_conf: list[MappingOutput] = []
    low_conf: list[MappingOutput] = []

    if unknown_accounts:
        context = {
            "accounts": unknown_accounts,
            "known_mappings": known,
        }
        try:
            response: MappingResponse = llm_client.call(
                prompt="mapping_prompt.txt",
                model=MAPPING_MODEL,
                context=context,
                schema=MappingResponse,
            )
        except TransientIOError:
            raise MappingAmbiguous("LLM call failed during account mapping")

        for m in response.mappings:
            if m.confidence >= _HIGH_CONFIDENCE_THRESHOLD:
                high_conf.append(m)
            else:
                low_conf.append(m)

        # Single bulk call — 3 round-trips total regardless of batch size.
        # Previous per-row upsert loop saturated Supabase's HTTP/2
        # connection on 20+ accounts and caused RemoteProtocolError on
        # shared-stream tenants.
        if high_conf:
            accounts_repo.bulk_upsert_mappings(company_id, high_conf)

        if low_conf:
            runs_repo.set_low_confidence_columns(run_id, low_conf)

    mapped_columns: dict[str, dict] = {}

    for account_name, category in known.items():
        if account_name in account_info:
            mapped_columns[account_name] = {"category": category, "confidence": 1.0}

    for m in high_conf:
        mapped_columns[m.column] = {
            "category": m.category,
            "confidence": m.confidence,
        }

    for m in low_conf:
        mapped_columns[m.column] = {
            "category": "OTHER",
            "confidence": m.confidence,
        }

    for account_name in account_info:
        if account_name not in mapped_columns:
            mapped_columns[account_name] = {"category": "OTHER", "confidence": 0.0}

    return mapped_columns, low_conf

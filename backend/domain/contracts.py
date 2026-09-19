from __future__ import annotations

import logging
from datetime import date
from typing import Annotated, Literal, get_args
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

ReconciliationClassification = Literal[
    "timing_cutoff",
    "categorical_misclassification",
    "missing_je",
    "stale_reference",
    "accrual_mismatch",
    "structural_explained",
]
ALLOWED_RECONCILIATION_CLASSIFICATIONS: frozenset[str] = frozenset(
    get_args(ReconciliationClassification)
)
_logger = logging.getLogger(__name__)

SourceFileType = Literal[
    "general_ledger",
    "payroll",
    "supplier_invoices",
    "contracts",
    # Item 1 (bank/processor three-way). Declared in PR-A but deliberately NOT
    # wired into orchestrator._FILE_TYPE_PATTERNS / _detect_file_type — that is
    # PR-B. Until then no file can ever be detected as either of these, and a
    # bank/processor upload keeps defaulting to supplier_invoices exactly as
    # before. See kova2-implementation-plan.md item 1, sections C.2 and G.
    "bank_statement",
    "processor_settlement",
]

DEFAULT_GL_CATEGORIES: list[str] = [
    "REVENUE",
    "COGS",
    "OPEX",
    "G&A",
    "R&D",
    "OTHER_INCOME",
]

GoldenField = Literal[
    "account",
    "account_code",
    "amount",
    "date",
    "parent_category",
    "department",
    "description",
]

Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
RowIndex = Annotated[int, Field(ge=0)]


class AccountSummary(BaseModel):
    account: str
    category: str  # REVENUE | COGS | OPEX | G&A | R&D | OTHER_INCOME | OTHER
    current: float
    historical_avg: float  # 0.0 when severity == "no_history"
    variance_pct: float  # 0.0 when severity == "no_history"
    severity: str  # low | medium | high | no_history


class PandasSummary(BaseModel):
    accounts: dict[str, AccountSummary]
    period: date
    company_id: UUID


class NarrativeJSON(BaseModel):
    narrative: str
    numbers_used: list[float]
    reconciliation_classifications: dict[str, ReconciliationClassification] | None = (
        None
    )

    @field_validator("reconciliation_classifications", mode="before")
    @classmethod
    def drop_unknown_classification_tokens(cls, value: object) -> object:
        """Drop invented class tokens so the six-class Literal stays closed.

        Claude's class is advisory. Pandas residue and hints overwrite it on
        match, coverage, fee, deposit, annual, and roster-gap cards. An unknown
        string must not kill the run before that merge runs.
        """
        if value is None or not isinstance(value, dict):
            return value
        cleaned: dict[str, object] = {}
        dropped_accounts: list[str] = []
        dropped_tokens: list[str] = []
        for account, token in value.items():
            if token in ALLOWED_RECONCILIATION_CLASSIFICATIONS:
                cleaned[account] = token
            else:
                dropped_accounts.append(str(account))
                dropped_tokens.append(str(token))
        if dropped_tokens:
            _logger.warning(
                "invalid classification token dropped",
                extra={
                    "event": "invalid_classification_token",
                    "dropped_count": len(dropped_tokens),
                    "accounts": dropped_accounts,
                    "tokens": dropped_tokens,
                },
            )
        return cleaned


class MappingOutput(BaseModel):
    column: str
    category: str  # category name
    confidence: float  # 0.0–1.0; <0.80 flags for MappingConfirmModal


class MappingResponse(BaseModel):
    mappings: list[MappingOutput]


# ---------------------------------------------------------------------------
# AccountMapper contracts
# ---------------------------------------------------------------------------


class AccountMappingDecision(BaseModel):
    gl_account: str | None
    confident: bool


class AccountMappingResponse(BaseModel):
    """Haiku output: {raw_value: {gl_account, confident}}."""

    mappings: dict[str, AccountMappingDecision]


MappingOrigin = Literal["new", "remembered", "conflict"]
MappingMode = Literal["row", "file_total"]

ControlKey = Literal["payroll", "supplier_invoices", "contracts"]
ControlStatus = Literal[
    "tied_out",
    "has_exceptions",
    "mapping_required",
    "source_missing",
    "not_compared",
]


class MappingDraftItem(BaseModel):
    source_pattern: str  # raw value from file ("AlarmTech Industries")
    source_file: str  # filename it came from
    file_type: SourceFileType  # detected from filename
    suggested_gl_account: str | None
    confident: bool  # pre-check row in UI when True
    origin: MappingOrigin = "new"
    remembered_gl_account: str | None = None
    haiku_gl_account: str | None = None
    # File-total is a distinct mode. Absence of Account does not set this.
    mapping_mode: MappingMode = "row"
    amount_scope: str | None = None
    source_amount: float | None = None
    period: date | None = None


class MappingDraft(BaseModel):
    items: list[MappingDraftItem]
    gl_account_pool: list[str]  # valid GL account names for the dropdown


class ControlComparison(BaseModel):
    """One GL target inside a named close control. Python-only."""

    gl_account: str
    supporting_amount: float | None = None
    gl_amount: float | None = None
    difference: float | None = None
    classification: ReconciliationClassification | None = None
    complete: bool = True
    incomplete_reason: str | None = None


class ControlResult(BaseModel):
    key: ControlKey
    label: str
    status: ControlStatus
    source_file: str | None = None
    period: date | None = None
    amount_scope: str | None = None
    gl_targets: list[str] = Field(default_factory=list)
    mapping_mode: MappingMode | Literal["none"] = "none"
    comparisons: list[ControlComparison] = Field(default_factory=list)
    next_action: str = ""
    incomplete_reason: str | None = None


class ControlSummary(BaseModel):
    """Persisted close-control evidence. Counts are controls, not coverage cards."""

    schema_version: str = "close_controls_v1"
    controls: list[ControlResult]
    compared: int
    with_exceptions: int
    not_evaluated: int
    coverage_account_count: int
    scope_note: str
    legacy: bool = False


class ParserOutput(BaseModel):
    run_id: str
    rows_parsed: int
    mapped_columns: dict[str, dict]  # {account_name: {category, confidence}}
    metadata_rows_skipped: int
    pandera_errors: list[str]
    warnings: list[str]
    low_confidence_columns: list[
        dict
    ]  # mirrors runs.low_confidence_columns JSONB shape


class SendResult(BaseModel):
    status: str  # "sent" | "failed"
    message_id: str  # empty string when status == "failed"


class HierarchyHint(BaseModel):
    row_index: RowIndex
    parent_category: str


class DiscoveryPlan(BaseModel):
    header_row_index: RowIndex
    skip_row_indices: list[RowIndex]
    column_mapping: dict[str, GoldenField | None]
    hierarchy_hints: list[HierarchyHint]
    discovery_confidence: Confidence
    notes: str = ""


class GoldenSchemaRow(BaseModel):
    account: str
    account_code: str | None = None
    amount: float
    date: date
    parent_category: str | None = None
    department: str | None = None
    description: str | None = None


class DropReason(BaseModel):
    row_index: int
    account_snippet: str  # <=40 chars, PII-scrubbed via _scrub_value
    reason: Literal["amount_coerce_failed", "subtotal_safety_net"]


class NormalizerDropReport(BaseModel):
    entries: list[DropReason]
    total_dropped: int


# ---------------------------------------------------------------------------
# Item 1 — bank/processor three-way. PR-A ships these types INERT: nothing
# constructs them yet, no detection recognises the new file types, and no
# matcher exists. See kova2-implementation-plan.md item 1 C.1 / C.5.1.
# ---------------------------------------------------------------------------


class ProcessorSettlementRow(BaseModel):
    """One FSM / job card-batch row (`processor_settlement`).

    Sidecar only — these columns are copied off the raw frame BEFORE the
    normalizer drops non-golden columns, so `GoldenField` and the P&L pandera
    schema stay seven columns. Canonical names per C.5.1's frame table.
    """

    payout_id: str | None  # join id; None/blank is legal (ambiguous fallback)
    gross: float  # required on this frame
    net: float | None = None  # optional; absent in the C.5.3 fixture
    collected_date: date | None = None


class GLUFDetailRow(BaseModel):
    """One Undeposited-Funds detail row lifted from the GL file.

    Sidecar only the rows that carry a ref OR whose `gl_account` equals the
    company's UF account name — per C.5.1, "Do not sidecar Rent".
    """

    gl_ref: str | None
    gl_account: str | None
    amount: float
    gl_date: date | None = None


class BankStatementRow(BaseModel):
    """One bank / processor settlement row (`bank_statement`).

    Per C.5.1: `gross` / `fee` / `net` when the export has them; otherwise
    `amount` is net. `fee` is never trusted for the match decision — the
    matcher recomputes it as `gross - net` (N3).
    """

    bank_ref: str | None
    settlement_date: date | None = None
    gross: float | None = None
    fee: float | None = None  # informational only; never a match key
    net: float | None = None
    amount: float | None = None  # when present and `net` is absent, this is net


class BatchMatch(BaseModel):
    """One matched (or deliberately unmatched) cash batch.

    Frozen shape per C.1. Note there is NO `fee_pct` field, by decision E.1:
    it is an internal pandas gate computed inline in the matcher and must never
    reach a serialized payload or a prompt placeholder.
    """

    match_id: str
    processor_ref: str | None
    bank_ref: str | None
    gl_ref: str | None
    gl_account: str | None
    gl_amount: float | None  # UF (or wrong-account) line; None if no GL row
    gross: float
    fee: float
    net: float
    settlement_date: date | None
    match_kind: Literal["id", "amount_date", "none"]
    ambiguous: bool
    candidate_count: int
    unmatched: bool
    classification: ReconciliationClassification | None = None


class ReconciliationSource(BaseModel):
    source_file: str
    amount: float
    row_count: int


class ReconciliationHints(BaseModel):
    crosses_period_boundary: bool = False
    is_round_fraction: bool = False  # amount is exactly 50% of another source
    similar_amount_in_other_account: bool = False
    is_source_only: bool = False  # appears in dept file, not in GL
    is_gl_only: bool = False  # appears in GL, not in any dept file
    # Same-item |GL| vs |source| ≈ 12× (±10%). Not a P&L-wide hunt.
    looks_like_annual_prepayment: bool = False
    # pandas: max(|GL|, |source|) / 12 when looks_like_annual_prepayment.
    implied_monthly: float | None = None
    # Alias of looks_like_annual_prepayment — old JSONB still parses.
    delta_matches_known_vendor: bool = False
    # Customer 50% peşinat / unearned revenue — not a vendor prepaid.
    is_customer_deposit: bool = False
    # Two-sided gross-vs-net processor/platform gap — not a liability.
    is_processor_fee_gap: bool = False
    # Item 4 — RMR roster counts. Pandas-computed, optional so existing report
    # JSONB still parses. Rows are ACCOUNTS, not customers (R.3).
    n_active: int | None = None
    n_billed_in_period: int | None = None
    count_delta: int | None = None
    fee_sum_active: float | None = None
    fee_sum_billed: float | None = None
    # Pandas-computed dollar size of the gap, so the narrative can state it
    # without Claude subtracting the two sums itself.
    fee_gap: float | None = None


class ReconciliationItem(BaseModel):
    account: str
    category: str
    sources: list[ReconciliationSource]
    gl_amount: float | None  # None when GL has no entry for this account
    non_gl_total: float
    delta: float  # non_gl_total - gl_amount (None → non_gl_total)
    delta_pct: float | None  # None when gl_amount is 0 or None
    severity: Literal["low", "medium", "high"]
    classification: ReconciliationClassification | None = None
    narrative: str | None = None
    suggested_action: str | None = None
    hints: ReconciliationHints = ReconciliationHints()
    # "coverage" = GL line with no uploaded supporting file. Not a 7th class.
    card_kind: Literal["exception", "coverage"] = "exception"
    # Item 1: several cash batches nested under one UF account line. Optional
    # with a None default so existing JSONB on reports still parses unchanged.
    # Nothing populates this in PR-A. Per decision E.6, per-batch classes live
    # here — NarrativeJSON.reconciliation_classifications keeps its
    # dict[account -> class] shape and never carries a match_id.
    matches: list[BatchMatch] | None = None

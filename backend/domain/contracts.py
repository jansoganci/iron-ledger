from __future__ import annotations

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

ReconciliationClassification = Literal[
    "timing_cutoff",
    "categorical_misclassification",
    "missing_je",
    "stale_reference",
    "accrual_mismatch",
    "structural_explained",
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


class MappingOutput(BaseModel):
    column: str
    category: str  # category name
    confidence: float  # 0.0–1.0; <0.80 flags for MappingConfirmModal


class MappingResponse(BaseModel):
    mappings: list[MappingOutput]


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
    delta_matches_known_vendor: bool = False


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

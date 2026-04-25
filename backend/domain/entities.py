from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal


@dataclass
class Company:
    id: str
    owner_id: str
    name: str
    currency: str = "USD"
    sector: str | None = None
    created_at: datetime | None = None


@dataclass
class Account:
    id: str
    company_id: str
    category_id: int
    name: str
    code: str | None = None
    is_active: bool = True
    created_by: str = "agent"
    created_at: datetime | None = None


@dataclass
class MonthlyEntry:
    id: str
    company_id: str
    account_id: str
    period: date
    actual_amount: Decimal
    source_file: str | None = None
    source_column: str | None = None
    agent_notes: str | None = None
    source_breakdown: list[dict] | None = None
    created_at: datetime | None = None


@dataclass
class Anomaly:
    id: str
    company_id: str
    account_id: str
    period: date
    anomaly_type: str  # 'error' | 'warning' | 'anomaly'
    severity: str  # 'low' | 'medium' | 'high'
    description: str
    variance_pct: Decimal | None = None
    status: str = "open"
    created_at: datetime | None = None


@dataclass
class Report:
    id: str
    company_id: str
    period: date
    summary: str
    anomaly_count: int = 0
    error_count: int = 0
    mail_sent: bool = False
    mail_sent_at: datetime | None = None
    reconciliations: list[dict] | None = None
    created_at: datetime | None = None


@dataclass
class Run:
    id: str
    company_id: str
    period: date
    status: str = "pending"
    step: int = 0
    total_steps: int = 4
    step_label: str | None = None
    progress_pct: int = 0
    report_id: str | None = None
    raw_data_url: str | None = None
    error_message: str | None = None
    low_confidence_columns: list = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None

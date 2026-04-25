# IronLedger — Agent Flow
*Built with Opus 4.7 Hackathon — April 2026*
*v2 — Numeric guardrail and file-format edge cases added*

---

## Golden Rule

> **Numbers come from pandas. Prose comes from Claude. Numeric guardrail checks that prose matches pandas.**

Claude must never do math. Every calculation is done in Python. Claude only interprets Python output.

---

## Overall Flow

Agents depend on `domain.ports` (Protocol interfaces). Adapters implement those ports and wrap every third-party SDK. Agents never import `supabase`, `anthropic`, or `resend` directly — only ports.

```
User uploads file(s)
         ↓
   ┌─────────────────────────────────────────────────────────┐
   │ Parser Agent                                            │
   │   [format detection → read → normalize → pandera → map] │
   │                                                         │
   │   uses:  FileStorage port     → supabase_storage        │
   │         LLMClient port        → anthropic_llm (Haiku)   │
   │         EntriesRepo port      → supabase_repos          │
   │         RunsRepo port (status transitions via           │
   │                       RunStateMachine)                  │
   └─────────────────────────────────────────────────────────┘
         ↓  writes MonthlyEntry[] via EntriesRepo
   ┌─────────────────────────────────────────────────────────┐
   │ Comparison Agent (pure pandas — no LLM)                 │
   │   [variance → threshold → flag]                         │
   │                                                         │
   │   uses:  EntriesRepo port     ← read history            │
   │         AnomaliesRepo port    → write flagged items     │
   │         RunsRepo port         (status transition)       │
   │                                                         │
   │   emits: PandasSummary  (domain.contracts — the strict  │
   │                           Pydantic contract handed to   │
   │                           the Interpreter)              │
   └─────────────────────────────────────────────────────────┘
         ↓  writes Anomaly[] + returns PandasSummary
   ┌─────────────────────────────────────────────────────────┐
   │ Interpretation Agent                                    │
   │   receives: PandasSummary + Anomaly[]                   │
   │                                                         │
   │   uses:  LLMClient port       → anthropic_llm (Opus)    │
   │         ReportsRepo port      → write verified report   │
   │         RunsRepo port         (status transition)       │
   │                                                         │
   │   calls: tools/guardrail.py   (pure domain — unchanged) │
   │          on Claude's NarrativeJSON vs PandasSummary     │
   └─────────────────────────────────────────────────────────┘
         ↓  writes Report (only if guardrail passes)
   ┌─────────────────────────────────────────────────────────┐
   │ Dashboard + Email                                       │
   │   uses:  EmailSender port     → resend_email            │
   └─────────────────────────────────────────────────────────┘

Legend:
  Port (interface)  = domain.ports.{Name}
  Adapter           = adapters.{module}  — the only layer that imports SDKs
  RunStateMachine   = domain.run_state_machine — every runs.status write
                      goes through it; invalid transitions raise.
  PandasSummary     = domain.contracts.PandasSummary — Pydantic-validated
                      handoff between Comparison and Interpreter.
```

---

## Agent 1: Parser

### Input
- Uploaded file (Excel / CSV / XLS)
- `company_id`
- `period` (which period)

### Step 0: Format Detection
Format is determined before opening the file:

```python
def detect_format(filepath):
    ext = filepath.suffix.lower()
    if ext == ".csv":
        return "csv"
    if ext == ".xlsm":
        return "xlsm"  # macro-enabled, use openpyxl with data_only=True
    if ext in [".xlsx"]:
        return "xlsx"
    if ext == ".xls":
        # NetSuite .xls may actually be XML Spreadsheet 2003
        # Check first 2 bytes: PK = real xlsx, <?xml = NetSuite
        with open(filepath, "rb") as f:
            header = f.read(2)
        return "xml_spreadsheet" if header == b"<?" else "xls_binary"
```

**NetSuite edge case:** `.xls` extension but actually XML Spreadsheet 2003 format. openpyxl cannot open it. It must be parsed as XML.

### Step 1-7: Parse and Normalize

Pipeline order (strict — PII strip and pandera both run BEFORE any Claude call):

```
read → skip metadata → detect header → STRIP PII → pandera validate → column map → normalize → write
```

1. **Read** — opens file with the correct engine (openpyxl / xlrd / XML parser)
2. **Skip ERP metadata rows** — first 0-10 rows can be headers/banners
3. **Detect header row**
4. **STRIP PII** (`tools/pii_sanitizer.py`)
   - Header blacklist, **case-insensitive substring match**. Matched columns are **dropped entirely** — no hashing. The exact substring list (authoritative — `tools/pii_sanitizer.py` must implement this verbatim):

     | Category | Trigger condition | Substrings (case-insensitive substring match) |
     |---|---|---|
     | SSN / Tax ID | always | `ssn`, `social_security`, `social security`, `taxpayer_id`, `tax_id`, `tin` |
     | Date of Birth | always | `dob`, `date_of_birth`, `date of birth`, `birth_date`, `birthdate`, `birthday` |
     | Personal Name | **only when an `employee_id` column exists in the same sheet** | `first_name`, `last_name`, `full_name`, `employee_name`, `personal_name` |
     | Home Address | always | `home_address`, `residence`, `street_address`, `zip_code`, `postal_code`, `mailing_address` |
     | Bank Account / Routing | always | `bank_account`, `account_number`, `routing_number`, `iban`, `swift_code`, `aba_routing` |
     | Personal Contact | always | `phone_number`, `mobile_phone`, `cell_phone`, `personal_email`, `home_phone`, `home_email` |

     **Conservative bias rationale:** bare `name`, `address`, `phone`, `email`, `account` are intentionally **excluded** — they are extremely common in legitimate finance files (`account_name`, `vendor_name`, `billing_address`, `account_number_balance`, etc.). False-positive stripping of these would gut the file. False-negative risk is mitigated by the value-level SSN regex below.
   - **Value-level fallback, SSN only:** regex `^\d{3}-?\d{2}-?\d{4}$`. Column dropped if ≥20% of non-null values match.
   - Emits a structured log entry (`event="pii_sanitization"`) with `trace_id`, `run_id`, `columns_dropped` (header names), `rows_in_file`, `strategy` — **never cell values**.
   - If no valid columns survive: raises `FileHasNoValidColumns` → user sees `messages.FILE_HAS_NO_VALID_COLUMNS`.
5. **Pandera schema validation** — on the sanitized DataFrame only. Validates `amount: float`, `period: date`, `account: str`.
6. **Map column names to US GAAP categories** (claude-haiku-4-5-20251001)
   - Claude receives sanitized column headers + 2-3 sample rows drawn from the already-stripped DataFrame. Claude never sees PII.
   - Before sending anything to Claude, reduces pandas DataFrame to account-level totals:
     `df.groupby('account')['amount'].sum().to_dict()`
   - Context sent to Claude is this summary, not raw rows.
   - A 50,000-row Excel can become a 20-key dict at this step.
   - If mapping confidence is below 80%, only those columns are flagged and asked to the user.
   - Mapping confidence 80%+ columns are accepted silently.
   - Zero-friction does not mean no questions; it means asking the minimum questions only for ambiguous columns.
7. **Normalize** — cleans dirty data: symbols, empty rows, thousand separators
8. **Write to `monthly_entries`**

### Output
```json
{
  "status": "success",
  "file_format": "xlsx",
  "rows_parsed": 42,
  "metadata_rows_skipped": 5,
  "new_accounts_created": 3,
  "warnings": ["Row 14: empty value, skipped"],
  "pandera_errors": []
}
```

### Error State
Does not fail silently. Shows user:
> "We couldn't map these columns: [list]. Please review."

---

## Agent 2: Comparison

### Input
- `company_id`
- `period` (bu ay)
- Historical monthly data from Supabase

### What it does — ALL PYTHON

Claude is not used in this agent. All math is Python:

```python
def calculate_variance(current: float, historical_avg: float) -> dict:
    if historical_avg == 0:
        return {"variance_pct": None, "flag": "no_history"}
    variance_pct = ((current - historical_avg) / abs(historical_avg)) * 100
    severity = (
        "high"   if abs(variance_pct) > 30 else
        "medium" if abs(variance_pct) > 15 else
        "low"
    )
    return {
        "variance_pct": round(variance_pct, 2),
        "severity": severity,
        "flag": abs(variance_pct) > 15
    }
```

Thresholds:
- First 3 months: ±20% threshold (limited history)
- After 3+ months: dynamic based on company's own standard deviation

### Output
```json
{
  "comparisons_made": 38,
  "anomalies_found": 4,
  "high_severity": 1,
  "medium_severity": 2,
  "low_severity": 1,
  "pandas_summary": {
    "Travel": {"current": 45000, "avg": 28000, "variance_pct": 60.7},
    "Payroll": {"current": 120000, "avg": 115000, "variance_pct": 4.3}
  }
}
```

---

## Agent 3: Interpretation

### Input
- `anomalies` records for this month from table
- `pandas_summary` (from Comparison agent)
- Past reports (for context)

### What it does

Claude is used in this agent — only for language:

1. Ranks anomalies by importance
2. Builds context (seasonal or real issue)
3. Writes plain-language English report
4. Suggests actions
5. **Moves to Numeric Guardrail** — before writing the report

Note: Anomaly severity (low/medium/high) is determined by Python in comparison.py
using fixed thresholds (±15% = medium, ±30% = high). Claude does NOT classify severity.
Claude only writes the one-sentence business reason for each flagged item,
as part of the same narrative JSON output. No separate anomaly classification call.

### Output — Sample Report (US Demo)
```
March 2026 Financial Summary — DRONE

⚠️ 2 items require attention, 1 flagged for review.

1. TRAVEL & ENTERTAINMENT — High
   This month: $45,000 / 3-month avg: $28,000 / Variance: +61%
   Significantly above trend. Likely tied to Q1 trade show season.
   Recommend reviewing expense reports for March conferences.

2. G&A EXPENSES — Medium
   This month: $4.73M / Prior month avg: $5.71M / Variance: -17%
   Favorable variance — improved cost discipline vs February peak.
   Trend is positive; monitor to confirm sustained improvement.

✅ 36 other line items within normal range.
```

---

## Numeric Guardrail

Interpretation agent output does not go directly into report. Claude returns structured JSON:

```json
{
  "narrative": "Plain language report text...",
  "numbers_used": [45000, 28000, 61, 4730000, 5710000, -17, 36]
}
```

Then a simple Python function compares every number in `numbers_used` with `pandas_summary`:

```python
def flatten_summary(d: dict) -> list:
    """Recursively extract all numeric leaf values from nested dict."""
    values = []
    for v in d.values():
        if isinstance(v, dict):
            values.extend(flatten_summary(v))
        elif isinstance(v, (int, float)):
            values.append(float(v))
    return values

def verify_guardrail(claude_json: dict, pandas_summary: dict, tolerance=0.02) -> tuple:
    """Verify Claude's numbers match pandas output within tolerance."""
    flat_values = flatten_summary(pandas_summary)
    for num in claude_json["numbers_used"]:
        exists = any(
            abs(num - p_val) / abs(p_val) < tolerance
            for p_val in flat_values
            if p_val != 0
        )
        if not exists:
            return False, f"Mismatch: {num} not found in pandas output"
    return True, "Success"
```

```python
def run_with_guardrail(pandas_summary, max_retries=2):
    for attempt in range(max_retries):
        claude_json = call_claude_narrative(pandas_summary)
        success, message = verify_guardrail(claude_json, pandas_summary)
        if success:
            return claude_json
        # Retry with stronger instruction
        print(f"Attempt {attempt + 1} failed: {message}. Retrying...")
    # Both attempts failed
    raise GuardrailError("Report could not be verified after 2 attempts. Returning raw data.")
```

On retry, the prompt is updated to include: "Your previous response contained a number that did not match the source data. Use ONLY the exact values from the pandas_summary provided. Do not round or abbreviate numbers in the numbers_used array."

If guardrail fails, `GuardrailError` is raised and report is not written to Supabase. This is not a second validator agent; it is a single Python verification function.
Claude never receives raw DataFrame rows. Only the aggregated summary dict is passed as context.

---

## Tool List (Anthropic SDK)

```python
tools = [
    {
        "name": "detect_format",
        "description": "Detects file format (xlsx, csv, xls, xml_spreadsheet)"
    },
    {
        "name": "read_file",
        "description": "Reads file with correct engine, skips metadata rows"
    },
    {
        "name": "normalize_data",
        "description": "Cleans raw data and validates with pandera"
    },
    {
        "name": "map_to_accounts",
        "description": "Maps columns to US GAAP categories"
    },
    {
        "name": "get_history",
        "description": "Fetches historical monthly data from Supabase"
    },
    {
        "name": "calculate_variance",
        "description": "Calculates variance in Python — not Claude"
    },
    {
        "name": "write_anomaly",
        "description": "Writes anomaly record to Supabase"
    },
    {
        "name": "generate_narrative",
        "description": "Writes plain-language report with Claude Opus 4.7"
    },
    {
        "name": "numeric_guardrail",
        "description": "Verifies narrative numbers match pandas output"
    },
    {
        "name": "send_mail",
        "description": "Sends report by email via Resend API"
    }
]
```

---

## Error Handling

| Error | Agent Response |
|---|---|
| File format not recognized | Message user, process stops |
| NetSuite XML parse error | retry with xlrd, error is logged |
| Storage upload fails after 3 retries (0.5s→1.5s→4s backoff) | Adapter raises `TransientIOError`; run transitions to `upload_failed`; user re-uploads. No checkpoint resume. |
| File has no valid columns after PII strip | Parser raises `FileHasNoValidColumns` → user sees `messages.FILE_HAS_NO_VALID_COLUMNS` ("This file looks empty or contains only PII columns we removed. Please upload a file with financial data."). Run transitions to `parsing_failed`. |
| Column mismatch | asks user for confirmation |
| pandera schema error | detailed error list to user |
| No historical data | No comparison is made; stated in report |
| Numeric guardrail failed (attempt 1) | System automatically retries; prompt is updated and resent to Claude |
| Numeric guardrail failed (attempt 2) | Report is not written to Supabase. Run transitions to `guardrail_failed`. **File stays in Storage** (not cleaned up). `GuardrailWarning` screen shown with **Retry Analysis** button — clicking it starts a **fresh run with a new `run_id`**, reusing the stored file. Raw pandas summary is also made downloadable. |
| Email could not be sent | Shown on dashboard, retry |
| Storage cleanup (post-success) fails | Logged at WARNING with `trace_id` / `run_id` / `storage_key`, swallowed. Run stays `complete`. Leaked object handled by post-MVP sweep. |

---

## Data Flow Summary

```
File → Parser → monthly_entries (Supabase)
                      ↓
              Comparison (Python only)
                      ↓
              anomalies (Supabase)
                      ↓
              Interpretation (Claude)
                      ↓
              Numeric Guardrail (Python)
                      ↓
              reports (Supabase) → Dashboard + Mail
```

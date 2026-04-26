# Month Proof — API Contract
*Version 1.0 — Hackathon MVP*

Base URL (local): `http://localhost:8000`
Base URL (production): `https://your-app.railway.app`

All requests use `multipart/form-data` for file uploads, `application/json` for everything else.
All responses are JSON.
CORS is enabled for `http://localhost:5173` and the production Vercel URL.

---

## Authentication

Every endpoint except `GET /health` requires a Supabase Auth JWT:

```
Authorization: Bearer <supabase_access_token>
```

JWTs are issued by the frontend via `supabase.auth.signInWithPassword()`.
The backend validates the JWT, extracts `user_id`, and resolves `company_id` from
`companies.owner_id = user_id`. The client never sends `company_id` directly on
authenticated endpoints — it is derived server-side.

Unauthenticated or expired JWT → `401 unauthorized`.

---

## Endpoints

### 1. POST /upload
Upload one or more financial files for a given company and period.

**Request — multipart/form-data**
```
files:  File[]  — one or more .xlsx / .csv / .xls / .xlsm files
period: string  — ISO date, first day of month (e.g. "2026-03-01" for March 2026)
```

`company_id` is derived from the JWT — do not send it.

**Response 200**
```json
{
  "run_id": "uuid",
  "status": "processing",
  "files_received": 2,
  "message": "Files uploaded. Use /runs/{run_id}/status to poll progress."
}
```

**Response 422**
```json
{
  "error": "unsupported_format",
  "message": "File 'report.pdf' is not supported. Upload .xlsx, .csv, .xls, or .xlsm files only."
}
```

---

### 2. GET /runs/{run_id}/status
Poll the progress of an upload and analysis run.

**Response 200 — in progress**
```json
{
  "run_id": "uuid",
  "status": "parsing",
  "step": 1,
  "total_steps": 4,
  "step_label": "Reading files...",
  "progress_pct": 25
}
```

**Steps:**
| step | status | step_label |
|---|---|---|
| 1 | parsing | Reading files... |
| 2 | mapping | Mapping accounts... |
| 3 | comparing | Comparing to history... |
| 4 | generating | Generating report... |

**Response 200 — complete**
```json
{
  "run_id": "uuid",
  "status": "complete",
  "step": 4,
  "total_steps": 4,
  "progress_pct": 100,
  "report_id": "uuid"
}
```

**Response 200 — guardrail failed**
```json
{
  "run_id": "uuid",
  "status": "guardrail_failed",
  "message": "Report could not be verified after 2 attempts.",
  "raw_data_url": "/runs/{run_id}/raw"
}
```

---

### 3. GET /report/{company_id}/{period}
Retrieve the verified report for a company and period.

**Response 200**
```json
{
  "report_id": "uuid",
  "company_id": "uuid",
  "period": "2026-03-01",
  "generated_at": "2026-03-15T14:32:00Z",
  "summary": "March 2026 shows two items requiring attention...",
  "anomaly_count": 2,
  "error_count": 0,
  "anomalies": [
    {
      "account": "Travel & Entertainment",
      "severity": "high",
      "current": 45000,
      "historical_avg": 28000,
      "variance_pct": 60.7,
      "description": "Travel expense is 61% above the 3-period average."
    }
  ]
}
```

**Response 404**
```json
{
  "error": "not_found",
  "message": "No verified report found for this company and period."
}
```

---

### 4. GET /anomalies/{company_id}/{period}
Retrieve the raw anomaly list for a company and period.

**Response 200**
```json
{
  "company_id": "uuid",
  "period": "2026-03-01",
  "anomalies": [
    {
      "id": "uuid",
      "account": "Travel & Entertainment",
      "severity": "high",
      "variance_pct": 60.7,
      "status": "open"
    }
  ]
}
```

---

### 5. POST /mail/send
Send the report summary by email.

**Request — application/json**
```json
{
  "report_id": "uuid",
  "to_email": "cfo@company.com"
}
```

**Response 200**
```json
{
  "status": "sent",
  "message_id": "resend_message_id"
}
```

**Response 500**
```json
{
  "error": "mail_failed",
  "message": "Email could not be sent. Report is still available in the dashboard."
}
```

---

### 6. POST /runs/{run_id}/mapping/confirm
Persist user-confirmed column → category mappings from the MappingConfirmModal.
Called after a run completes with `low_confidence_columns` populated on the `runs` row.

**Path params**
- `run_id` — UUID of the run whose low-confidence columns are being confirmed.

**Authorization**
- JWT required. `company_id` is **derived server-side** from the run ownership check
  (`runs.company_id → companies.owner_id = auth.uid()`). The client **never** sends
  `company_id` — this matches the rule for every other authenticated endpoint.

**Request — application/json**
```json
{
  "mappings": [
    { "column": "Misc Acct Adj", "category": "OTHER_INCOME" },
    { "column": "T&E Reclass",   "category": "OPEX" }
  ]
}
```

- `column` — original header from the uploaded file (verbatim).
- `category` — one of: `REVENUE`, `COGS`, `OPEX`, `G&A`, `R&D`, `OTHER_INCOME`, `OTHER`, `SKIP`.
  - `SKIP` is a frontend-only sentinel meaning "do not import this column". When received
    it is NOT written to `accounts`; instead the column is removed from the persisted mapping.
  - All other values are validated against `account_categories` and written to `accounts`.

**Response 200**
```json
{
  "status": "confirmed",
  "persisted_count": 2,
  "skipped_count": 0
}
```

**Response 403**
```json
{
  "error": "forbidden",
  "message": "You do not have access to this run."
}
```

**Response 422**
```json
{
  "error": "invalid_category",
  "message": "Category 'FOO' is not a valid US GAAP category."
}
```

**Rate limit:** 30/min per user.

**Notes:**
- Confirmed mappings only affect **future** uploads. The current run's report is not regenerated
  — it was already verified by the guardrail; rewriting it would invalidate the Verified badge.
- Next upload for this company with the same column header auto-maps to the confirmed category
  without prompting.

---

### 7. POST /runs/{run_id}/retry
Re-trigger the pipeline against the storage key of a previously failed run. Used by the
`GuardrailWarning` screen's **Retry Analysis** button so the user does not need to re-upload.

**Path params**
- `run_id` — UUID of the failed run to retry.

**Preconditions**
- `runs.status` must be `guardrail_failed`. Any other status → 422 `invalid_retry_state`.
- `runs.storage_key` must be non-null (populated on `POST /upload`). If null → 422 `missing_storage_key`.
- JWT owner must match the run's company. Mismatch → 403 `forbidden`.

**Request — application/json**
```json
{}
```
Empty body. `period` and `storage_key` are read from the old run row server-side.

**Behavior**
- Creates a **new** `runs` row with a fresh `run_id`, `status=pending`, same `(company_id, period, storage_key)`.
- The old run is left untouched with `status=guardrail_failed` for audit.
- Schedules the Parser → Comparison → Interpreter background task against the existing storage file.
- Parser's DELETE-then-INSERT on `monthly_entries` keeps the re-run clean.

**Response 200**
```json
{
  "run_id": "uuid",
  "status": "processing",
  "message": "Retry started. Use /runs/{run_id}/status to poll progress."
}
```

**Response 422**
```json
{
  "error": "invalid_retry_state",
  "message": "This run cannot be retried. Only guardrail-failed runs support Retry Analysis."
}
```

**Rate limit:** 5/min per user (reuses the `/upload` cap — retry IS a new pipeline run).

---

### 8. GET /companies/me/has-history
Tell the frontend whether to render the `EmptyState` screen. A brand-new user who has never
uploaded anything sees the baseline-setup flow; a returning user lands on the upload UI.

**Request**
No body. JWT required (standard auth).

**Response 200**
```json
{
  "has_history": true,
  "periods_loaded": 3
}
```

- `has_history` — `false` iff the authenticated user's company has zero rows in `monthly_entries`.
- `periods_loaded` — count of distinct `period` values with entries. Used by the frontend to tailor copy
  ("1 month loaded — add 2 more for better comparisons.") when we go beyond a single-month baseline.

**Rate limit:** 60/min per user.

---

### 9. GET /companies/me
Return the authenticated user's company record. Frontend calls this once at mount to resolve
the `company_id` it needs for `/report/{company_id}/{period}` and `/anomalies/{company_id}/{period}` URLs.

**Request**
No body. JWT required (standard auth).

**Response 200**
```json
{
  "id": "uuid",
  "name": "DRONE Inc.",
  "currency": "USD",
  "sector": "Industrial"
}
```

MVP assumption: exactly one company per user (enforced by Supabase seed). Post-MVP multi-company
would change this shape to an array.

**Rate limit:** 60/min per user.

---

### 10. GET /reports
List verified reports for the authenticated user's company, ordered by period DESC.
Powers the Dashboard `HistoryList` and serves as the foundation for a future `/reports` page.

**Query params**
- `limit` — optional, default `12`. Clamped server-side to `[1, 50]`.

**Request**
No body. JWT required.

**Response 200**
```json
{
  "reports": [
    {
      "report_id": "uuid",
      "period": "2026-03-01",
      "generated_at": "2026-03-15T14:32:00Z",
      "anomaly_count": 2,
      "error_count": 0
    },
    {
      "report_id": "uuid",
      "period": "2026-02-01",
      "generated_at": "2026-02-14T09:10:00Z",
      "anomaly_count": 0,
      "error_count": 0
    }
  ]
}
```

**Notes**
- Only **verified** reports appear here (same rule as `GET /report/{company_id}/{period}`).
  Guardrail-failed runs never produce a `reports` row.
- `anomaly_count` is whatever was persisted on the `reports` row at generation time —
  not a live count. Sufficient for list rendering; the detailed counts come from
  `GET /anomalies/{company_id}/{period}`.
- Severity aggregation (high / medium / low counts per report) is intentionally NOT
  returned — it would require a JOIN to `anomalies` per row and the Dashboard doesn't
  need it for MVP. Revisit when HighSeverity-only filters ship.

**Rate limit:** 60/min per user.

---

## Error Codes Reference

| error | meaning | HTTP status |
|---|---|---|
| unauthorized | Missing or invalid JWT | 401 |
| forbidden | JWT valid but user does not own the requested company | 403 |
| unsupported_format | File type not accepted | 422 |
| parse_failed | File could not be read | 422 |
| mapping_failed | Columns could not be mapped | 422 |
| invalid_category | Mapping confirm received a category not in `account_categories` | 422 |
| invalid_retry_state | `/runs/{id}/retry` called on a run not in `guardrail_failed` | 422 |
| missing_storage_key | `/runs/{id}/retry` called on a run that has no stored file | 422 |
| guardrail_failed | Claude output failed numeric verification | 500 |
| not_found | Report or anomaly not found | 404 |
| mail_failed | Resend API error | 500 |
| rate_limited | Endpoint rate limit exceeded | 429 |

---

## CORS Configuration
Add to FastAPI startup:
```python
origins = [
    "http://localhost:5173",
    os.getenv("FRONTEND_URL", "")
]
```
Note: Forgetting CORS will cause silent failures on Day 4 frontend integration.

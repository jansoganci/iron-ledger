# Month Proof — Database Schema
*Built with Opus 4.7 Hackathon — April 2026*

> **Güncel durum (1 Ekim 2026).** Aşağıdaki tablo gövdeleri `0001` şemasıdır. Sonraki
> migrasyonlar (`0002`–`0012`) kolonları ve iki tabloyu ekledi; özetleri "Migrasyonlarla
> eklenenler" bölümünde. Şüphede `supabase/migrations/` ve kod doğrudur. `runs.status`
> değerlerinin tam listesi `backend/domain/run_state_machine.py` içindedir.

---

## Tables

### 1. companies
Company identity. Each company is owned by exactly one auth user. Isolation is enforced via RLS on `owner_id`.

```sql
CREATE TABLE companies (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name          TEXT NOT NULL,
  sector        TEXT,
  currency      TEXT DEFAULT 'USD',
  created_at    TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_companies_owner ON companies(owner_id);
```

---

### 2. account_categories
Fixed top-level categories. Immutable.

```sql
CREATE TABLE account_categories (
  id    SERIAL PRIMARY KEY,
  name  TEXT NOT NULL UNIQUE  -- REVENUE, COGS, OPEX, G&A, R&D, OTHER_INCOME, OTHER
);

-- Seed data (insertion order determines SERIAL id; OTHER is id=7)
-- OTHER is the explicit catch-all used by Parser when Haiku mapping
-- confidence is <0.80 (see docs/design.md MappingConfirmModal).
-- SKIP is NOT in this table — it is a frontend-only sentinel in the
-- MappingConfirmModal dropdown meaning "do not import this column";
-- skipped columns are never written to monthly_entries.
INSERT INTO account_categories (name) VALUES
  ('REVENUE'),       -- id=1
  ('COGS'),          -- id=2
  ('OPEX'),          -- id=3
  ('G&A'),           -- id=4
  ('R&D'),           -- id=5
  ('OTHER_INCOME'),  -- id=6
  ('OTHER')          -- id=7
ON CONFLICT (name) DO NOTHING;
```

---

### 3. accounts
Company-specific chart of accounts. Flexible, unlimited rows.

```sql
CREATE TABLE accounts (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id    UUID REFERENCES companies(id),
  category_id   INT REFERENCES account_categories(id),
  name          TEXT NOT NULL,   -- "Electricity Expense", "Payroll" etc.
  code          TEXT,            -- optional: "320", "600"
  is_active     BOOLEAN DEFAULT TRUE,
  created_by    TEXT DEFAULT 'agent',  -- 'agent' | 'user'
  created_at    TIMESTAMP DEFAULT NOW()
);
```

---

### 4. monthly_entries
Realized monthly data. Main data table.

```sql
CREATE TABLE monthly_entries (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id    UUID REFERENCES companies(id),
  account_id    UUID REFERENCES accounts(id),
  period        DATE NOT NULL,         -- first day of the month: 2026-02-01 = February 2026
                                         -- Demo: drone_feb_2026.xlsx → 2026-02-01
                                         --       drone_mar_2026.xlsx → 2026-03-01
  actual_amount DECIMAL(15,2),         -- actual
  source_file   TEXT,                  -- source filename / storage key
  source_column TEXT,                  -- original column header from uploaded file
                                         -- (added in 0003_add_source_column.sql)
                                         -- Used by /anomalies and /report to render provenance
                                         -- tooltips on AnomalyCard (Day 4 frontend).
                                         -- Written by Parser per row, after column mapping.
  agent_notes   TEXT,                  -- Claude notes
  created_at    TIMESTAMP DEFAULT NOW()
);

ALTER TABLE monthly_entries
  ADD CONSTRAINT unique_entry
  UNIQUE (company_id, account_id, period);
```

---

### 5. anomalies
Detected errors and anomalies.

```sql
CREATE TABLE anomalies (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id    UUID REFERENCES companies(id),
  account_id    UUID REFERENCES accounts(id),
  period        DATE NOT NULL,
  anomaly_type  TEXT NOT NULL,   -- 'error' | 'warning' | 'anomaly'
  severity      TEXT NOT NULL,   -- 'low' | 'medium' | 'high'
  description   TEXT NOT NULL,   -- plain-language description
  variance_pct  DECIMAL(8,2),    -- % variance (if any)
  status        TEXT DEFAULT 'open',  -- 'open' | 'resolved'
  created_at    TIMESTAMP DEFAULT NOW()
);
```

---

### 6. reports
Generated reports.

```sql
CREATE TABLE reports (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id    UUID REFERENCES companies(id),
  period        DATE NOT NULL,
  summary       TEXT NOT NULL,      -- plain-language summary
  anomaly_count INT DEFAULT 0,
  error_count   INT DEFAULT 0,
  mail_sent     BOOLEAN DEFAULT FALSE,
  mail_sent_at  TIMESTAMP,
  created_at    TIMESTAMP DEFAULT NOW()
);
```

---

### 7. runs
Tracks upload and analysis progress for the UI progress bar.

```sql
CREATE TABLE runs (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id      UUID REFERENCES companies(id),
  period          DATE NOT NULL,
  status          TEXT DEFAULT 'pending',
  -- Valid values (enforced by domain.run_state_machine.RunStateMachine):
  --   pending, parsing, mapping, comparing, generating, complete,
  --   upload_failed, parsing_failed, guardrail_failed
  -- Happy path:   pending → parsing → mapping → comparing → generating → complete
  -- Failure paths (all terminal):
  --   upload_failed   — Storage upload exhausted retries (TransientIOError)
  --   parsing_failed  — Parser crashed before mapping completed (pandera error,
  --                     FileHasNoValidColumns after PII strip, Haiku unreachable,
  --                     or any unhandled pre-Interpreter failure)
  --   guardrail_failed — Interpreter produced numbers not in PandasSummary
  --                      after 2 attempts (original + reinforced prompt)
  -- Invalid transitions raise domain.errors.InvalidRunTransition.
  step            INT DEFAULT 0,
  total_steps     INT DEFAULT 4,
  step_label      TEXT,
  progress_pct    INT DEFAULT 0,
  report_id       UUID REFERENCES reports(id),
  raw_data_url    TEXT,
  error_message   TEXT,
  storage_key     TEXT,                -- (added in 0004_add_storage_key.sql)
                                        -- Full Supabase Storage path of the uploaded file:
                                        --   financial-uploads/{auth.uid()}/{period}/{filename}
                                        -- Populated by POST /upload handler at run creation.
                                        -- Read by POST /runs/{run_id}/retry to re-run the
                                        -- pipeline without requiring the user to re-upload.
  created_at      TIMESTAMP DEFAULT NOW(),
  updated_at      TIMESTAMP DEFAULT NOW()
);
```

---

### 8. source_account_mappings
Persistent vendor / expense-item → GL memory (migration `0011`). Payroll
people and GL account names are excluded by CHECK constraint. v1 writes
`supplier_invoices` only. Unique on `(company_id, file_type, source_pattern)`.

```sql
CREATE TABLE source_account_mappings (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  file_type       TEXT NOT NULL,
  source_pattern  TEXT NOT NULL,
  gl_account      TEXT NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

### 9. period_closes
Dönem kilidi (migrasyon `0012`, Dil 3). Kullanıcı bitmiş bir aylık raporu "kapattım" der;
kim ve ne zaman burada saklanır. Bir `(company_id, period)` için aynı anda tek aktif kilit
vardır (`reopened_at IS NULL`, kısmi unique index). Yeniden açmak satırı silmez,
`reopened_*` alanlarını damgalar; DELETE politikası yoktur. `period` ayın ilk günüdür.

```sql
CREATE TABLE period_closes (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id        UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  period            DATE NOT NULL,          -- ayın ilk günü (CHECK)
  closed_by         UUID NOT NULL REFERENCES auth.users(id),
  closed_by_email   TEXT,                   -- kapanış anındaki anlık görüntü
  closed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  reopened_by       UUID REFERENCES auth.users(id),
  reopened_by_email TEXT,
  reopened_at       TIMESTAMPTZ             -- NULL = kilit aktif
);
-- UNIQUE INDEX uq_period_closes_active ON (company_id, period) WHERE reopened_at IS NULL
```

---

### 10. period_close_log
Yalnız ekleme günlüğü: her kapatma ve yeniden açma bir satır (`event` = `closed` | `reopened`,
`actor_id`, `actor_email`, `created_at`). RLS yalnız SELECT ve INSERT'e izin verir. Log yazımı
başarısız olursa kapanış bozulmaz; asıl kayıt `period_closes` satırıdır.

---

## Migrasyonlarla eklenenler (`0002`–`0012`)

| Migrasyon | Ne ekledi |
|---|---|
| `0002` | `runs.pandas_summary` (JSONB) |
| `0003` | `monthly_entries.source_column` |
| `0004` | `runs.storage_key` |
| `0005` | `runs.parse_preview` (JSONB; önizleme, eşleme taslağı, `_regenerate` bayrağı) |
| `0006` | `runs.discovery_plan`, `runs.discovery_approval_mode` |
| `0007` | `monthly_entries.source_breakdown`, `reports.reconciliations` (JSONB), `runs.file_count` |
| `0008` | `runs.opus_status`, `reports.opus_upgraded` |
| `0009` | `reports.report_type` (`monthly` / `quarterly`), `quarter`, `year`, `is_stale`, `quarterly_data`; aylık ve çeyrek için kısmi unique index; `anomalies.is_recurring` |
| `0010` | `companies.monthly_revenue_band` |
| `0011` | `source_account_mappings` tablosu (bölüm 8) |
| `0012` | `period_closes` ve `period_close_log` tabloları (bölüm 9 ve 10) |

`runs.status` artık `discovering`, `awaiting_discovery_confirmation`,
`awaiting_mapping_confirmation`, `applying_mapping`, `awaiting_confirmation` ve
`report_failed` değerlerini de taşır. `closed` bir run durumu **değildir**; dönem kilidi
`period_closes` tablosundadır.

---

## Indexes

```sql
CREATE INDEX idx_monthly_entries_company_period ON monthly_entries(company_id, period);
CREATE INDEX idx_anomalies_company_period ON anomalies(company_id, period);
CREATE INDEX idx_runs_company_period ON runs(company_id, period);
```

---

## Relationship Diagram

```
10 tables + Supabase Storage bucket

companies
    │
    ├── accounts (company_id)
    │       └── account_categories (category_id)
    │
    ├── monthly_entries (company_id, account_id)
    │
    ├── anomalies (company_id, account_id)
    │
    ├── reports (company_id)
    │
    ├── runs (company_id, report_id)
    │
    ├── source_account_mappings (company_id)
    │
    └── period_closes (company_id)
            └── period_close_log (close_id)

supabase-storage/
└── financial-uploads/{company_id}/{period}/{filename}
```

---

## Row Level Security (Auth)

Supabase Auth (email + password) owns identity. Every table carrying company data enables RLS and checks ownership via `companies.owner_id = auth.uid()`.

```sql
-- companies: user owns the company
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
CREATE POLICY company_owner ON companies
  FOR ALL
  USING  (owner_id = auth.uid())
  WITH CHECK (owner_id = auth.uid());

-- accounts / monthly_entries / anomalies / reports / runs:
-- access via the owned company
ALTER TABLE accounts          ENABLE ROW LEVEL SECURITY;
ALTER TABLE monthly_entries   ENABLE ROW LEVEL SECURITY;
ALTER TABLE anomalies         ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports           ENABLE ROW LEVEL SECURITY;
ALTER TABLE runs              ENABLE ROW LEVEL SECURITY;

CREATE POLICY accounts_via_company ON accounts
  FOR ALL USING (EXISTS (
    SELECT 1 FROM companies c
    WHERE c.id = accounts.company_id AND c.owner_id = auth.uid()
  ));

-- Repeat the same policy pattern for monthly_entries, anomalies, reports,
-- runs, and source_account_mappings.

-- account_categories is a public lookup table — no RLS.
```

Backend-side rule: after validating the JWT, always resolve `company_id` from `companies.owner_id = user_id` before reading or writing. Never accept `company_id` directly from the client.

---

## Important Notes

- Each company's data is isolated by `company_id`, enforced at the DB level via RLS
- `accounts` table is auto-populated by the agent and can be edited by user
- `period` is always stored as first day of month (2026-03-01)
- `actual_amount` can be negative (refund, adjustment)
- `anomalies.description` is always plain-language English
- `runs` table tracks progress for the 4-step UI progress bar
- Unique constraint on `monthly_entries(company_id, account_id, period)` prevents duplicate uploads
- Files are stored in Supabase Storage, not locally — Railway containers are ephemeral
- `company_id` is always UUID — never use string slugs like "drone" or "e-inc"

---

## File Storage

Uploaded files are stored in **Supabase Storage**, not on the application server.
Railway containers are ephemeral — local file storage does not persist across restarts.

### Bucket structure
```
supabase-storage/
└── financial-uploads/
    └── {company_id}/
        └── {period}/
            └── {filename}
```

### RLS Policy
Each company can only access its own files.
Row Level Security must be enabled on the `financial-uploads` bucket.

```sql
-- Enable RLS on storage bucket.
-- Uploads are scoped to the authenticated user's own folder.
CREATE POLICY "user_owns_upload"
ON storage.objects
FOR ALL
USING (
  bucket_id = 'financial-uploads'
  AND (storage.foldername(name))[1] = auth.uid()::text
);
```

Folder layout is therefore `financial-uploads/{auth.uid()}/{period}/{filename}`, not `{company_id}/...`. Backend resolves company from the user before writing.

Files are deleted from storage after the run completes successfully.
On guardrail failure, raw pandas output is returned directly — the file stays in storage for retry.

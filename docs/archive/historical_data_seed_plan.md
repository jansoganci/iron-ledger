# Historical Data Seed Plan

> **Created:** 2026-04-26  
> **Purpose:** Seed Sentinel Secure with 16 months of historical financial data to enable variance analysis, anomaly detection, and Opus deep analysis with context for demo months 17 and 18.

---

## Executive Summary

**Goal:** Make Sentinel Secure appear as if it's been using IronLedger for 1.5 years, with realistic month-over-month variance patterns that showcase the platform's analytical capabilities.

**Approach:** Python script generates SQL INSERT statements for 16 months (Jan 2025 - Apr 2026) of financial data, bypassing the upload pipeline entirely. Months 17 and 18 will be uploaded manually through the app to demonstrate the live pipeline.

**Timeline:** Jan 2025 → Apr 2026 (seed data) + May 2026 & Jun 2026 (manual demo uploads)

---

## 1. What Data Needs to Be Seeded?

### Required Tables

**`monthly_entries` (primary)**
- Core financial data — one row per account per period
- The comparison agent's `list_history()` reads from here (lookback: 6 months)
- **Volume:** 21 accounts × 16 months = 336 rows

**`accounts` (prerequisite)**
- Chart of accounts mapping names to categories (REVENUE, COGS, OPEX, G&A, etc.)
- Must be created ONCE with stable UUIDs referenced across all monthly_entries
- **Volume:** 21 rows (created before monthly_entries)

**`reports`**
- Historical narrative summaries for each month
- Adds realism to dashboard history view
- Can use simple templated narratives or Haiku-generated summaries
- **Volume:** 16 rows

**`runs`**
- Upload status records — all historical runs should have `status='complete'`
- **Volume:** 16 rows

### Optional (Recommended)

**`anomalies`**
- Flagged variance items from prior months
- Not read by comparison agent but adds realism for historical browsing
- **Volume:** ~50-80 rows (3-5 anomalies per month)

### Not Needed

- `companies` — Already exists (Sentinel Secure company record)
- `account_categories` — Static lookup table, already populated in migration

### Critical Constraint

**Account ID Stability:** All 16 months MUST reference the exact same `account_id` UUIDs. Do NOT create new account rows per month — create the `accounts` table entries ONCE, then reuse those IUIDs across all periods.

---

## 2. Which Company Should We Use?

**Selected: Sentinel Secure (Security Systems Installation)**

### Why Sentinel Secure?

**1. Natural Seasonality**
- Q4 (Oct-Dec): High season (holiday security upgrades, year-end business spending)
- Q1 (Jan-Mar): Moderate (new year budgets kick in)
- Q2-Q3: Slower (summer construction delays)

**2. Clear Growth Narrative**
- 8-person SMB in expansion mode
- Believable 18-month arc: bootstrapped start → team expansion → enterprise contract → steady growth

**3. Interesting Anomaly Patterns**
- Equipment COGS: Spikes when inventory pre-purchased (creates variance)
- Installation Revenue: Lumpy, project-based (high variance month-to-month)
- Service Revenue: Recurring monitoring contracts (smooth, predictable)
- Vehicle Expenses: Seasonal (winter maintenance spikes)
- Payroll: Step function (hiring events create clear anomalies)

**4. Best Documentation**
- 21 accounts already defined in `sentinel_gl_mar_2026.xlsx`
- 5 reconciliation files already exist in `docs/demo_data/sentinel/`
- Account categories well-distributed across GAAP types

### Alternatives Considered (and rejected)

| Company | Why Rejected |
|---------|-------------|
| **Helix IT (consulting)** | Too linear/predictable. Billable hours create boring variance patterns with no seasonality. |
| **Harvest Table (restaurant)** | Great seasonality, but COGS margins are TOO consistent (food cost % is robotic). |
| **CoreBuilt (construction)** | Extremely lumpy month-to-month (project-based). Hard to explain variance without confusing narrative. |
| **ClearView Medical (healthcare)** | Insurance timing complexities create noise, not insight. Harder to demo cleanly. |

---

## 3. What Should the 16-Month Trajectory Look Like?

### Narrative Arc: Sentinel Secure (Jan 2025 - Apr 2026)

#### Phase 1: Bootstrap (Months 1-4, Jan-Apr 2025)

**Baseline Metrics:**
- Revenue: $12-18K/month
- Team: 5 employees (3 techs, 1 office manager, 1 sales)
- Payroll: ~$18K/month
- Installation Revenue: Inconsistent (some months zero — no large projects yet)
- Service Revenue: Linear growth $3K → $6K (adding monitoring contracts)

**Character:** Small, scrappy startup. High month-to-month variance due to project lumpiness.

---

#### Phase 2: First Growth (Months 5-8, May-Aug 2025)

**Key Events:**
- **Month 5 (May 2025):** Hired 2 new technicians
  - Payroll spikes: $18K → $28K (+56%) — **HIGH severity anomaly**
  - Installation capacity doubles
  
- **Months 6-8:** Revenue ramps as new techs deliver
  - Revenue: $25-35K/month
  - Installation backlog clears
  
- **Month 7 (Jul 2025):** Bulk equipment purchase
  - Equipment COGS spikes: $8K → $18K (+120%) — **HIGH severity anomaly**
  - Pre-buying inventory for upcoming Q3-Q4 projects
  
- **Month 6:** Marketing spend appears for first time ($2K/month)

**Character:** Growing pains. Clear investment phase (people + inventory).

---

#### Phase 3: Enterprise Contract (Months 9-12, Sep-Dec 2025)

**Key Events:**
- **Month 9 (Sep 2025):** Landed 120-unit commercial property contract
  - Installation Revenue: $28K → $55K (+85%) — **HIGH severity anomaly**
  - Multi-month deployment begins
  
- **Q4 Seasonal Boost:** 20-30% higher than Q2-Q3 baseline
  - Residential upgrades (holiday security concerns)
  - Year-end business budget spending
  
- **Month 11 (Nov 2025):** Winter maintenance event
  - Vehicle Expenses: $1.2K → $1.7K (+40%) — **MEDIUM severity anomaly**
  - Winter tires, battery replacements, heater repairs
  
- **Service Revenue:** Reaches 82 customers by Dec 2025 (existing baseline from Mar 2026 GL)

**Character:** Breakthrough moment. Enterprise contract validates business model.

---

#### Phase 4: Steady State (Months 13-16, Jan-Apr 2026)

**Baseline Metrics:**
- Revenue: $40-50K/month (new normal)
- Team: 7 employees (stable)
- Payroll: $28-29K/month (small raises)
- Service Revenue: 80-90 customers (steady growth)

**Key Events:**
- **Month 14 (Feb 2026):** Post-holiday lull
  - Total Revenue: -18% vs Jan — **MEDIUM severity anomaly**
  - Normal seasonal dip after Q4 peak
  
- **Month 15 (Mar 2026):** Current demo file baseline
  - This month already exists in `sentinel_gl_mar_2026.xlsx`
  - Use as anchor point for seeding prior months
  
- **Month 16 (Apr 2026):** Setup for live demo
  - Slightly above Mar 2026 (continuing growth trend)
  - Months 17-18 will be uploaded manually to show live pipeline

**Character:** Maturity. Predictable patterns with minor seasonal variance.

---

### Key Variance Events Summary

| Month | Event | Account | Variance | Severity |
|-------|-------|---------|----------|----------|
| 5 (May 2025) | New hires | Payroll | +56% | HIGH |
| 7 (Jul 2025) | Bulk inventory | Equipment COGS | +120% | HIGH |
| 9 (Sep 2025) | Enterprise contract | Installation Revenue | +85% | HIGH |
| 11 (Nov 2025) | Winter maintenance | Vehicle Expenses | +40% | MEDIUM |
| 14 (Feb 2026) | Seasonal dip | Total Revenue | -18% | MEDIUM |

These events ensure that:
- Historical data has interesting anomalies for Opus to analyze
- Variance thresholds are exercised (Tier 1 and Tier 2 gates)
- Month 17-18 comparisons have rich context ("Revenue is up 12% vs 6-month average...")

---

## 4. How Do We Generate 16 Months of Realistic P&L Data?

### Recommended Approach: Python Script → SQL INSERTs

**Process:**

1. **Extract March 2026 Baseline**
   - Read `docs/demo_data/sentinel/sentinel_gl_mar_2026.xlsx`
   - Extract 21 account names, categories, and March amounts
   - Use as anchor point for reverse-engineering prior months

2. **Define Growth Curves Per Account Type**

   **Revenue Accounts:**
   - Sigmoid growth curve: slow start (months 1-4) → acceleration (months 5-9) → plateau (months 10-16)
   - Seasonal multiplier: Q4 × 1.25, Q1 × 1.0, Q2-Q3 × 0.9
   - Installation Revenue: Add randomness (±20%) for project lumpiness
   - Service Revenue: Linear growth (new contracts added monthly)

   **COGS (Equipment, Subcontractors):**
   - Track revenue at 60-65% margin (slight monthly variation)
   - Month 7: Spike to 80% margin (bulk purchase event)
   - After month 9: Stabilize at 62-63% (economies of scale)

   **Payroll:**
   - Step function:
     - Months 1-4: $18K (5 employees)
     - Months 5-16: $28K (7 employees)
     - Add ±$500 randomness (overtime, bonuses)
     - 2% annual raises in Month 13 (Jan 2026)

   **Operating Expenses:**
   - Vehicle: Baseline $1.2K ± 15% (spike in Month 11)
   - Marketing: $0 for months 1-5, then $2K/month ± 20%
   - Insurance, Utilities, Rent: Very stable (±5% max)
   - Office Supplies, Software: Minor randomness (±10%)

3. **Generate Month-by-Month DataFrames**

   For each month (Jan 2025 → Apr 2026):
   ```python
   monthly_entries_row = {
       'id': uuid.uuid4(),
       'company_id': SENTINEL_COMPANY_ID,  # from companies table
       'account_id': ACCOUNT_UUID_MAP[account_name],  # stable UUIDs
       'period': '2025-01-01',  # first day of month
       'actual_amount': calculated_amount,  # per growth curves above
       'source_file': 'historical_seed',
       'agent_notes': None,
       'created_at': NOW()
   }
   ```

4. **Generate Simple Reports**

   Template per month:
   ```
   Sentinel Secure financial summary for [Month YYYY].
   Total revenue: $X,XXX. Total expenses: $Y,YYY. Net income: $Z,ZZZ.
   
   [1-2 sentence narrative about variance or key event]
   ```

   Examples:
   - Month 5: "Payroll increased significantly due to hiring two additional technicians to support growing installation demand."
   - Month 9: "Installation revenue surged with the start of a 120-unit commercial property deployment."
   - Month 14: "Revenue declined seasonally following the holiday peak, consistent with Q1 patterns."

5. **Output SQL INSERT Statements**

   ```sql
   -- 1. Insert accounts (run ONCE)
   INSERT INTO accounts (id, company_id, category_id, name, code, created_by) VALUES
   ('uuid-1', 'sentinel-company-id', 1, 'Service Revenue', '4010', 'historical_seed'),
   ('uuid-2', 'sentinel-company-id', 1, 'Installation Revenue', '4020', 'historical_seed'),
   ...;

   -- 2. Insert monthly_entries (16 months × 21 accounts = 336 rows)
   INSERT INTO monthly_entries (id, company_id, account_id, period, actual_amount, source_file) VALUES
   ('...', 'sentinel-company-id', 'uuid-1', '2025-01-01', 3200.00, 'historical_seed'),
   ...;

   -- 3. Insert reports (16 months)
   INSERT INTO reports (id, company_id, period, summary, anomaly_count, error_count) VALUES
   ('...', 'sentinel-company-id', '2025-01-01', 'Sentinel Secure financial...', 0, 0),
   ...;

   -- 4. Insert runs (16 months)
   INSERT INTO runs (id, company_id, period, status, progress_pct) VALUES
   ('...', 'sentinel-company-id', '2025-01-01', 'complete', 100),
   ...;
   ```

6. **Execute via Supabase SQL Editor or psql**

### Why This Approach?

**Pros:**
- Bypasses upload pipeline entirely (no file parsing, no Claude mapping calls, no storage uploads)
- Guarantees data consistency (same script = same account_id references across all months)
- Easily tweakable (adjust growth rates, add/remove variance events, re-run)
- Fast (all 16 months generated in <10 seconds)
- Deterministic (re-running produces identical data for testing)

**Alternatives Rejected:**

❌ **Manual Excel files (16 months)**
- Would require hand-crafting 16 separate `.xlsx` files
- Would need to upload each through the app (16 × Claude Haiku calls)
- Error-prone (typos in account names → new accounts created → comparison breaks)
- Time-consuming (~4-6 hours of manual work)

❌ **Direct DataFrame → JSONB storage**
- Complex serialization/deserialization
- No version control (binary data)
- Harder to inspect/debug

---

## 5. Data Consistency Rules

### CRITICAL (Non-Negotiable)

**1. Account Name Stability**
- All 21 account names from March 2026 GL MUST appear in EVERY month
- Identical spelling (case-sensitive)
- Even if an account has $0 in a month, include the row (comparison logic groups by account_id)

**2. Category Stability**
- Each account's category MUST remain constant across all 16 months
- "Equipment COGS" is always `COGS`, never `OTHER` or `OPEX`
- Category determines variance thresholds (Tier 1 vs Tier 2)

**3. Account ID Stability**
- Generate `accounts` table ONCE with fixed UUIDs
- Reference the SAME UUIDs across all monthly_entries rows
- DO NOT create new account rows per month
- Store UUID mapping in script: `ACCOUNT_UUID_MAP = {'Service Revenue': 'uuid-1', ...}`

**4. Period Format**
- First day of month: `2025-01-01`, `2025-02-01`, etc.
- NOT last day of month (`2025-01-31`) — breaks comparison logic
- NOT mid-month — must be consistent

**5. Company ID**
- All rows MUST reference Sentinel Secure's `company_id`
- RLS policies enforce `company_id` isolation — wrong ID = invisible data

### IMPORTANT (Quality Standards)

**6. Variance Realism**
- Don't just multiply March values by random factors
- Revenue should trend upward over 16 months (not flat or declining)
- COGS should track revenue at realistic margins (60-65% for installation business)
- Payroll should be step function, not wavy (hiring events, not monthly adjustments)
- OpEx can have randomness but avoid wild swings (±15% max for most accounts)

**7. Month-to-Month Variation**
- No two consecutive months should have IDENTICAL values for the same account
- Exception: Payroll during stable periods can be very similar (but add ±$200-500 jitter for overtime/bonuses)
- Add ±2-5% randomness to most accounts to simulate real-world variation

**8. Decimal Precision**
- Schema uses `DECIMAL(15,2)` — round all amounts to 2 decimal places
- No trailing precision: `1234.56` not `1234.5678`

**9. Negative Values**
- Revenue accounts: ALWAYS positive
- Expense accounts: ALWAYS positive (no credits in seed data for simplicity)
- Only exception: Refunds/adjustments in OTHER_INCOME (if seeding those)

**10. Account Distribution**
- Avoid accounts with $0 for many consecutive months (looks unrealistic)
- If an account is truly seasonal (e.g., "Snow Removal"), explain in narrative

---

## 6. Volume and Risk Assessment

### Data Volume

| Table | Rows | Notes |
|-------|------|-------|
| `accounts` | 21 | Created once, referenced across all periods |
| `monthly_entries` | 336 | 21 accounts × 16 months |
| `reports` | 16 | 1 per month |
| `runs` | 16 | 1 per month |
| `anomalies` | 50-80 | Optional: 3-5 flagged variances per month |
| **TOTAL** | **~450 rows** | Across 5 tables |

### Storage Impact

**Supabase Free Tier:**
- 500 MB database limit
- Unlimited API requests
- Current usage: <5 MB (schema + DRONE demo data)
- **450 rows ≈ 50-100 KB** (trivial)

**PostgreSQL Performance:**
- Handles millions of rows easily
- Existing index on `monthly_entries(company_id, period)` ensures fast queries
- Comparison agent already fetches "up to 600 rows" per analysis (line 142 in `supabase_repos.py`)

**Verdict: ZERO risk from volume.**

### Real Risks (and Mitigations)

**Risk 1: Account Name Mismatch**
- **Problem:** "Equipment COGS" in March 2026 vs "Equipment - COGS" in historical months → comparison breaks (no matching account_id)
- **Mitigation:** Extract account names programmatically from March 2026 GL. Use exact strings. Validate before execution.

**Risk 2: Account ID References**
- **Problem:** Wrong `account_id` UUID → JOINs return nothing → comparison agent sees zero history
- **Mitigation:** Generate accounts table first, capture returned UUIDs, use in monthly_entries. Add validation query: `SELECT COUNT(*) FROM monthly_entries WHERE account_id NOT IN (SELECT id FROM accounts)` — should return 0.

**Risk 3: Company ID Mismatch**
- **Problem:** Wrong `company_id` → RLS policies block all reads → app sees no data
- **Mitigation:** Query companies table for Sentinel Secure's actual UUID. Hardcode in script. Test with a single month insert before running full 16 months.

**Risk 4: Period Format**
- **Problem:** `2025-01-31` instead of `2025-01-01` → comparison logic breaks (periods don't match)
- **Mitigation:** Use Python `date(year, month, 1)` for all periods. Validate with regex: `^\d{4}-\d{2}-01$`

**Risk 5: Duplicate Periods**
- **Problem:** Accidentally seeding a period that already exists (e.g., March 2026) → unique constraint violation
- **Mitigation:** Check existing periods before seeding: `SELECT DISTINCT period FROM monthly_entries WHERE company_id = 'sentinel-id' ORDER BY period;`

---

## 7. Does Comparison Logic Actually Use Historical Data?

### Confirmed: YES

**Source:** `backend/agents/comparison.py`, lines 101-114

```python
# 1. Fetch current period entries
current_entries = self._entries.list_for_period(company_id, period)

# 2. Fetch historical entries (up to 6 months prior)
history = self._entries.list_history(company_id, period, lookback_months=6)

# 3. Group history by account_id
history_by_account: dict[str, list[float]] = {}
for entry in history:
    history_by_account.setdefault(entry.account_id, []).append(
        float(entry.actual_amount)
    )

# 4. Calculate average for each account
historical_avg = mean(hist_amounts) if hist_amounts else 0.0

# 5. Calculate variance
variance_pct = ((current - historical_avg) / abs(historical_avg)) * 100
```

### How `list_history()` Works

**Implementation:** `backend/adapters/supabase_repos.py`, lines 112-148

**Query Logic:**
1. **Fast existence check** (lines 121-128): Check if ANY prior data exists
   - Saves heavy SELECT on first upload (no history yet)
   - Returns empty list immediately if no prior periods found

2. **Fetch prior periods** (lines 136-144):
   ```python
   .lt("period", str(period))           # Only periods BEFORE current month
   .order("period", desc=True)          # Most recent first
   .limit(lookback_months * 100)        # Up to 600 rows (6 months × ~100 accounts)
   ```

3. **Convert to MonthlyEntry dataclasses** (line 148)

### What This Means for Demo

**When you upload Month 17 (May 2026) manually:**
- Comparison agent looks back at months **Nov 2025 - Apr 2026** (6 months)
- Calculates 6-month average for each account
- Flags variances using tiered thresholds

**When you upload Month 18 (Jun 2026):**
- Comparison agent looks back at months **Dec 2025 - May 2026** (6 months)
- Now includes Month 17's data in the historical average
- Variance calculations become more sophisticated (larger sample size)

**Critical Insight:**
Your 16 months of seed data (Jan 2025 - Apr 2026) provide the **full historical context** needed for realistic variance analysis in the live demo uploads.

**Without seed data:**
- Month 17 upload: "No history available" → all variance = 0%, no anomalies flagged
- Opus narrative: Bland, no comparative insights

**With seed data:**
- Month 17 upload: "Installation Revenue is 22% above the 6-month average, driven by new commercial contracts. This is the highest level since September 2025 when the enterprise deployment began."
- Opus narrative: Rich, contextual, demonstrates the platform's value

### Validation Test

**After seeding, before live demo:**

Run this query to confirm history is accessible:

```sql
SELECT 
  period,
  COUNT(*) as account_count,
  SUM(actual_amount) as total
FROM monthly_entries
WHERE company_id = 'sentinel-company-id'
  AND period < '2026-05-01'  -- Before Month 17
GROUP BY period
ORDER BY period DESC
LIMIT 6;
```

**Expected output:** 6 rows (Nov 2025 - Apr 2026) with ~21 accounts each.

If this works, the comparison agent WILL see the history.

---

## Next Steps

### Phase 1: Script Development

1. **Create `scripts/seed_historical_data.py`**
   - Read `docs/demo_data/sentinel/sentinel_gl_mar_2026.xlsx`
   - Extract 21 accounts (names, categories, March amounts)
   - Define growth trajectory functions (revenue curves, COGS margins, payroll steps)
   - Generate 16 months of data (Jan 2025 - Apr 2026)
   - Output SQL INSERT statements to `scripts/seed_data.sql`

2. **Define Configuration**
   - Sentinel company_id (query from Supabase)
   - Account UUID generation strategy (deterministic or random)
   - Growth parameters (revenue CAGR, seasonal multipliers, variance event dates)
   - Randomness seeds (for reproducibility)

### Phase 2: Validation

3. **Generate and Review SQL**
   - Run script locally
   - Inspect `scripts/seed_data.sql`
   - Validate:
     - 336 monthly_entries rows (21 accounts × 16 months)
     - 21 accounts rows (no duplicates)
     - 16 reports rows
     - 16 runs rows
     - All amounts are positive (except intentional credits)
     - All periods are first-of-month

4. **Test with Subset**
   - Seed ONLY 3 months first (Jan-Mar 2025)
   - Upload a fake "Apr 2025" file through the app
   - Confirm comparison agent sees 3-month history
   - Verify variance calculations match expectations

### Phase 3: Full Seeding

5. **Execute Full Seed**
   - Run `scripts/seed_data.sql` against Supabase
   - Verify row counts: `SELECT COUNT(*) FROM monthly_entries WHERE source_file = 'historical_seed';` → should return 336

6. **Sanity Check Queries**
   ```sql
   -- Check period coverage
   SELECT MIN(period), MAX(period), COUNT(DISTINCT period) FROM monthly_entries WHERE company_id = '...';
   -- Expected: 2025-01-01, 2026-04-01, 16

   -- Check account consistency
   SELECT period, COUNT(DISTINCT account_id) FROM monthly_entries WHERE company_id = '...' GROUP BY period;
   -- Expected: 21 accounts in every period

   -- Check for orphaned account_id references
   SELECT COUNT(*) FROM monthly_entries m WHERE NOT EXISTS (SELECT 1 FROM accounts a WHERE a.id = m.account_id);
   -- Expected: 0
   ```

### Phase 4: Live Demo Preparation

7. **Create Month 17 & 18 Excel Files**
   - Manually craft `sentinel_gl_may_2026.xlsx` and `sentinel_gl_jun_2026.xlsx`
   - Use March 2026 structure, adjust amounts to show growth
   - Include 1-2 intentional anomalies (e.g., equipment COGS spike, new marketing campaign)

8. **Rehearse Live Upload**
   - Upload Month 17 through app
   - Verify comparison sees 6-month history (Nov 2025 - Apr 2026)
   - Check Opus narrative mentions historical context
   - Upload Month 18
   - Verify comparison now includes May 2026 in history

9. **Document Demo Script**
   - Talking points for each variance flagged
   - Historical context explanations (e.g., "This is the highest revenue since the enterprise contract in September 2025")

---

## Technical Specifications

### Database Schema (Relevant Columns)

**`accounts`**
```sql
CREATE TABLE accounts (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id  UUID REFERENCES companies(id) ON DELETE CASCADE,
  category_id INT  REFERENCES account_categories(id),
  name        TEXT NOT NULL,
  code        TEXT,
  is_active   BOOLEAN DEFAULT TRUE,
  created_by  TEXT DEFAULT 'agent',
  created_at  TIMESTAMP DEFAULT NOW()
);
```

**`monthly_entries`**
```sql
CREATE TABLE monthly_entries (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id    UUID REFERENCES companies(id) ON DELETE CASCADE,
  account_id    UUID REFERENCES accounts(id),
  period        DATE NOT NULL,  -- first day of month: 2026-02-01
  actual_amount DECIMAL(15,2),
  source_file   TEXT,
  agent_notes   TEXT,
  created_at    TIMESTAMP DEFAULT NOW(),
  CONSTRAINT unique_entry UNIQUE (company_id, account_id, period)
);
```

**`reports`**
```sql
CREATE TABLE reports (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id    UUID REFERENCES companies(id) ON DELETE CASCADE,
  period        DATE NOT NULL,
  summary       TEXT NOT NULL,
  anomaly_count INT DEFAULT 0,
  error_count   INT DEFAULT 0,
  mail_sent     BOOLEAN DEFAULT FALSE,
  mail_sent_at  TIMESTAMP,
  created_at    TIMESTAMP DEFAULT NOW()
);
```

**`runs`**
```sql
CREATE TABLE runs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id    UUID REFERENCES companies(id) ON DELETE CASCADE,
  period        DATE NOT NULL,
  status        TEXT DEFAULT 'pending',
  step          INT DEFAULT 0,
  total_steps   INT DEFAULT 4,
  step_label    TEXT,
  progress_pct  INT DEFAULT 0,
  report_id     UUID REFERENCES reports(id),
  error_message TEXT,
  created_at    TIMESTAMP DEFAULT NOW(),
  updated_at    TIMESTAMP DEFAULT NOW()
);
```

### Variance Calculation Thresholds

**From `backend/agents/comparison.py`:**

**Tier 2 (High-Stakes Categories):**
- Accounts: REVENUE, PAYROLL, DEFERRED_REVENUE
- Dollar gate: $10,000
- Percentage gate: 3%
- Both must be exceeded to flag

**Tier 1 (All Other Accounts):**
- Dollar gate: $50,000
- Percentage gate: 10%
- Both must be exceeded to flag

**Severity Levels:**
- HIGH: |variance_pct| > 30%
- MEDIUM: |variance_pct| > 15%
- LOW: |variance_pct| ≤ 15%

**Example:**
- Service Revenue (Tier 2): $82K current vs $78K avg = +5.1% variance, $4K delta
  - Dollar gate: $4K < $10K → NOT flagged (gate not cleared)
  
- Installation Revenue (Tier 2): $55K current vs $30K avg = +83% variance, $25K delta
  - Dollar gate: $25K > $10K ✓
  - Percentage gate: 83% > 3% ✓
  - Severity: HIGH (83% > 30%)
  - **FLAGGED**

---

## Success Criteria

**Seed data is complete when:**

✅ 336 rows in `monthly_entries` (21 accounts × 16 months)  
✅ 21 rows in `accounts` with stable UUIDs  
✅ 16 rows in `reports` with realistic narratives  
✅ 16 rows in `runs` with `status='complete'`  
✅ All periods are first-of-month (YYYY-MM-01 format)  
✅ All account_id references are valid (no orphaned UUIDs)  
✅ Revenue shows upward trend over 16 months  
✅ COGS tracks revenue at 60-65% margin  
✅ Payroll has step function at Month 5 (hiring event)  
✅ 5-8 clear variance events across the timeline  
✅ Month 17 manual upload sees 6 months of history  
✅ Comparison agent flags anomalies based on historical averages  
✅ Opus narrative includes historical context (e.g., "highest since Q4 2025")

**Demo is ready when:**

✅ Months 17-18 Excel files created  
✅ Live upload of Month 17 completes successfully  
✅ Variance report shows comparisons to Nov 2025 - Apr 2026  
✅ Anomalies are flagged with realistic descriptions  
✅ Opus narrative is rich and contextual (not generic)  
✅ Dashboard history view shows 18 months of data  
✅ No errors in console or logs  

---

## File Outputs

**From seed script:**
- `scripts/seed_historical_data.py` — Python data generator
- `scripts/seed_data.sql` — Generated SQL INSERT statements
- `scripts/seed_config.yaml` — Growth parameters, variance events (optional)

**For live demo:**
- `docs/demo_data/sentinel/sentinel_gl_may_2026.xlsx` — Month 17 upload file
- `docs/demo_data/sentinel/sentinel_gl_jun_2026.xlsx` — Month 18 upload file

**Documentation:**
- This file (`docs/02-planning/historical_data_seed_plan.md`)

---

## References

**Code:**
- `backend/agents/comparison.py` — Variance calculation logic
- `backend/adapters/supabase_repos.py` — `list_history()` implementation
- `supabase/migrations/0001_initial_schema.sql` — Table definitions

**Data:**
- `docs/demo_data/sentinel/sentinel_gl_mar_2026.xlsx` — March 2026 baseline (21 accounts)
- `docs/archive/three_sector_demo_plan.md` — Multi-sector demo context
- `docs/06-reports/hackathon_findings_report.md` — Sentinel Secure scenario details

**Architecture:**
- `CLAUDE.md` — System overview, agent pipeline, guardrail rules
- `docs/01-architecture/db-schema.md` — Database schema documentation

---

**END OF PLAN**

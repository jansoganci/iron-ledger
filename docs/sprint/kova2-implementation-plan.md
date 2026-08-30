# Kova 2 — implementation plan

*Planning artifact only. No product code from this document until explicit go-ahead **per item**.*  
*Date: 26 August 2026.*  
*Parent: [kova2-comprehensive-analysis.md](kova2-comprehensive-analysis.md) (approved). Sequence here is the single checkpoint at the end of that document — do not re-rank, merge items, or add a seventh classification.*  
*Code read on `cursor/kova2-comprehensive-analysis-d72a` (Kova 1 recon stack + analysis). PAYROLL tag still lives on PR #5 (`cursor/payroll-pattern-match-d72a`), off this stack and off `origin/main`.*

This is the engineering spec that later PRs execute literally. Ambiguity left here is a failure of this document, not something to resolve while coding.

---

## Constraints (locked)

- Golden rule: Claude never computes. Pandas always computes. Guardrail still checks `numbers_used` only.
- Six `ReconciliationClassification` values only, throughout: `timing_cutoff`, `categorical_misclassification`, `missing_je`, `stale_reference`, `accrual_mismatch`, `structural_explained`. No seventh. Coverage stays `card_kind`, not a class.
- No SQL migration for anything that can live in JSONB.
- Do not touch Kova 1 recon code (deposit/fee, annual 12×, coverage, cutoff allowlist, consolidator `_is_material`) unless item 5’s threshold change requires updating a test’s **expected values**. The cross-cutting matrix at the end shows that those tests do **not** call `calculate_variance` and do **not** need expected-value edits.
- Do not implement parked items 2, 3, 6 beyond the one-paragraph notes at the end.
- Do not start item 1 or item 4 implementation until the previous item has shipped **and** there is an explicit go-ahead.

## Build sequence

| Order | Item | This document | Later PRs |
|-------|------|---------------|-----------|
| 1 | Item 5 — Revenue-scaled materiality (onboarding) | Full A–H. **BUILD FIRST.** | One product PR after go-ahead. |
| 2 | Item 1 — Bank/processor three-way MVP | Full A–H. **SPEC ONLY** until item 5 ships, then a separate go-ahead to build. Sections C/D/E are design for future PRs, not to implement yet. | PR-A / PR-B / PR-C as specified in G. |
| 3 | Item 4 — RMR account-count vs GL | Full A–H. Build after item 1 ships. | PR-A / PR-B as specified in G. |
| — | Items 2, 3, 6 | Parked. One paragraph each. No implementation detail. | None. |

Clarifications locked 26 August 2026 (before this file was written):

1. There is **no Recurrence agent**. Recurrence is a suffix inside `ComparisonAgent.run`. See item 5 F and the cross-cutting matrix.
2. `supabase/seed.sql` and existing tests never hit `CreateCompanyRequest`. Making the band required on POST does not 422 seed or integration fixtures. See item 5 B and D.
3. **Do not change POST `/companies` idempotency.** The first insert writes the band. `PATCH /companies/me` is the only update path. See item 5 D.

---

# Item 5 — Revenue-scaled materiality (onboarding)

Flux only (`comparison.py::calculate_variance`). Not recon `_is_material`. Not a hint. Not a classification change.

## A. Pre-conditions

What must already be true before this item’s product PR starts:

- Kova 1 recon stack is the product baseline (AND-gate, coverage, deposit/fee, cutoff allowlist, annual 12×). Item 5 does **not** import any of those modules.
- **PAYROLL tag (PR #5, branch `cursor/payroll-pattern-match-d72a`) is not merged to this stack or to `origin/main`.** `backend/tools/account_tags.py` does not exist on this branch. `calculate_variance` has no `account_name` argument. Item 5’s product PR **must include** `is_payroll_account` (needles: `payroll`, `wages`, `salary`, `salaries`, `compensation`) rather than waiting on a separate merge. If PR #5 lands first, do not duplicate the helper — import it.
- `companies` schema is unchanged since `supabase/migrations/0001_initial_schema.sql` (`id, owner_id, name, sector, currency, created_at`). Migrations `0002`–`0009` do not touch `companies`. Highest file on disk is `0009_add_report_type_and_quarterly.sql`. Next write is **`0010`**.
- Not blocked on item 1 (bank matcher), item 4 (RMR counts), or `0011`.
- Not blocked on anything else that is not yet in `main`, other than folding PR #5 as above.

## B. Database / migration

**Filename:** `supabase/migrations/0010_add_company_monthly_scale.sql`

**Full DDL:**

```sql
-- Item 5: revenue-scaled flux materiality.
-- Band lives on companies (server-side comparison reads by company_id).
-- NULL is intentional: existing rows and skip-the-question keep today's $50k/$10k fail-safe.
-- Do not put this on auth.users raw_user_meta_data.

ALTER TABLE companies
  ADD COLUMN IF NOT EXISTS monthly_revenue_band TEXT;

ALTER TABLE companies
  ADD CONSTRAINT companies_monthly_revenue_band_chk
  CHECK (
    monthly_revenue_band IS NULL
    OR monthly_revenue_band IN (
      'under_100k',
      '100k_250k',
      '250k_500k',
      '500k_plus'
    )
  );
```

**Backfill:** none. Existing rows stay `NULL`. Pandas fail-safe is today’s constants (`_TIER1_DOLLAR = 50_000`, `_TIER2_DOLLAR = 10_000`). Never treat NULL as `$0`.

**Seed impact (checked, not assumed):** `supabase/seed.sql` lines 7–14 insert DRONE as:

```sql
INSERT INTO companies (owner_id, name, currency)
SELECT id, 'DRONE Inc.', 'USD'
FROM auth.users
WHERE email = 'demo@dronedemo.com'
ON CONFLICT DO NOTHING;
```

That INSERT does not list `monthly_revenue_band`. After `0010` the new column is nullable, so the seed still runs. The DRONE row is `NULL` → fail-safe `$50k` / `$10k`, which is the same as today’s hardcoded gates and is the correct DRONE-scale behaviour (`500k_plus` / `R=$2,000,000` is the same pair). Seed never goes through `CreateCompanyRequest`.

**What is NOT migrated:**

- No new table.
- No `NUMERIC monthly_revenue` (users type annual or a goal; the UI is four radios).
- No Auth `user_metadata` key next to `onboarding_done`. Comparison runs by `company_id`, not JWT metadata.
- No recon `$100` / `$500` retune (`consolidator.py::_is_material`).
- No `0011_add_bank_attestation.sql` in this item. Do not reuse `0010` for bank.
- No unique constraint change on `companies.owner_id` (idempotency of POST remains application-level `get_by_owner`).

**RLS:** existing policy `company_owner` on `companies` (`0001_initial_schema.sql` ~147–151) is `FOR ALL USING (owner_id = auth.uid()) WITH CHECK (owner_id = auth.uid())`. The new column is on that table. **No new policy.** Backend still never accepts `company_id` from the client.

## C. Backend — file by file

### C.1 `backend/tools/account_tags.py` (new; copy from PR #5 if still unmerged)

**Responsibility:** pure helper, no I/O, no LLM.

```python
def is_payroll_account(name: str) -> bool
```

- **Input:** canonical GL account name (already mapped), e.g. `"Salaries & Wages"`, `"Engineering Salaries"`.
- **Return:** `True` if any needle is a case-insensitive substring of `name`: `payroll`, `wages`, `salary`, `salaries`, `compensation`.
- **Called from:** `calculate_variance` / `ComparisonAgent.run` only in this item. Do **not** call from consolidator, AccountMapper, or parser.
- **Does not:** persist a category, invent a `PAYROLL` `account_categories` row, log the name next to cell values, or change recon materiality.

If PR #5 has merged, import that module; do not fork the needle list.

### C.2 `backend/agents/comparison.py` (modified)

**Keep as fail-safe constants (do not delete):**

```python
_TIER1_DOLLAR = 50_000.0
_TIER1_PCT = 10.0
_TIER2_DOLLAR = 10_000.0
_TIER2_PCT = 3.0
```

**Delete as the live Tier 2 set:**

```python
_TIER2_CATEGORIES = {"REVENUE", "PAYROLL", "DEFERRED_REVENUE"}
```

`PAYROLL` and `DEFERRED_REVENUE` are not seeded in `0001` (`REVENUE, COGS, OPEX, G&A, R&D, OTHER_INCOME, OTHER`). Parser/Haiku never emit them. Wages land in OPEX/G&A and currently miss Tier 2. After this item, Tier 2 is `category == "REVENUE"` **or** `is_payroll_account(account_name)`. Do **not** keep `category == "PAYROLL"` or `category == "DEFERRED_REVENUE"` in the live gate.

**Add:**

```python
_BAND_R: dict[str, float] = {
    "under_100k": 50_000.0,
    "100k_250k": 175_000.0,
    "250k_500k": 375_000.0,
    "500k_plus": 2_000_000.0,
}

def _gates_from_band(band: str | None) -> tuple[float, float]:
    """Return (dollar_t1, dollar_t2). Claude never sees R. Pandas only."""
```

Formula (pandas only):

```
dollar_t1 = max(500,  0.025 * R)   # 2.5% of monthly revenue
dollar_t2 = max(250,  0.005 * R)   # 0.5% of monthly revenue
pct_t1    = 10                     # unchanged
pct_t2    = 3                      # unchanged
```

Worked values (must match tests):

| `monthly_revenue_band` | R | dollar_t1 | dollar_t2 |
|------------------------|---|-----------|-----------|
| `under_100k` | 50_000 | 1_250 | 250 |
| `100k_250k` | 175_000 | 4_375 | 875 |
| `250k_500k` | 375_000 | 9_375 | 1_875 |
| `500k_plus` | 2_000_000 | 50_000 | 10_000 |
| `None` or unknown string | — | **50_000** | **10_000** (never 0) |

`500k_plus` equals the fail-safe constants by construction. Unknown strings (`"annual"`, `""`, garbage) must take the fail-safe branch, not a KeyError and not `$0`.

**`calculate_variance` today:**

```python
def calculate_variance(
    current: float,
    historical_avg: float,
    history_count: int,
    category: str = "OTHER",
) -> dict:
```

Behaviour today: `is_tier2 = category in _TIER2_CATEGORIES`; dollar/pct gates from module constants; `flag = abs_delta > dollar_gate and abs_pct > pct_gate`. `history_count` accepted and unused (leave unused).

**`calculate_variance` after:**

```python
def calculate_variance(
    current: float,
    historical_avg: float,
    history_count: int,
    category: str = "OTHER",
    *,
    account_name: str | None = None,
    dollar_t1: float | None = None,
    dollar_t2: float | None = None,
) -> dict:
```

- If `dollar_t1 is None`, use `_TIER1_DOLLAR`. If `dollar_t2 is None`, use `_TIER2_DOLLAR`. Callers that omit gates (unit tests of the AND-gate) keep today’s `$50k` / `$10k` fail-safe.
- `is_tier2 = (category == "REVENUE") or is_payroll_account(account_name or "")`.
- Percent gates stay `_TIER1_PCT` / `_TIER2_PCT`.
- Severity still %-only (`>30` high, `>15` medium, else low). Unchanged.
- `historical_avg == 0` still returns `{variance_pct: None, severity: "no_history", flag: False}`.

**`ComparisonAgent.__init__` today:**

```python
def __init__(self, entries_repo, anomalies_repo, runs_repo, accounts_repo) -> None
```

No `companies_repo`. `run(run_id, company_id, period)` loads: prior flag counts, current entries, history, `accounts_map = self._accounts.get_accounts_by_id(company_id)`. It does **not** load the company row. `calculate_variance` is called at ~137 as:

```python
result = calculate_variance(
    current_val, historical_avg, len(hist_amounts), category
)
```

`account_name` is already resolved at ~130 (`account_info["name"]`) and unused for gating.

**`ComparisonAgent.__init__` after:** add `companies_repo: CompaniesRepo`. Store as `self._companies`.

**`run` after — company read happens once, before the per-entry loop,** immediately after the existing progress update (after ~98, before prior-flag fetch at ~101):

```python
company = self._companies.get_by_id(company_id)
dollar_t1, dollar_t2 = _gates_from_band(company.get("monthly_revenue_band"))
```

If `get_by_id` raises, do not swallow into `$0` floors. Let it propagate (orchestrator already has a top-level failure path). A missing band **key** on a found row is `None` → fail-safe.

Per-entry call becomes:

```python
result = calculate_variance(
    current_val,
    historical_avg,
    len(hist_amounts),
    category,
    account_name=account_name,
    dollar_t1=dollar_t1,
    dollar_t2=dollar_t2,
)
```

**Recurrence (not a separate agent):** still the same block at ~167–183. If `result["flag"]` and `prior >= 2`, append `"Flagged in {prior} of the past 6 months — recurring pattern."` and set `is_recurring`. Item 5 does not change that copy. Fixture `$360k` vs `$300k` (`$60k` / 20%) still flags under fail-safe Tier 2 and under every scaled band, so recurrence assertions keep their expected strings. The only new requirement is mocking `companies_repo.get_by_id`.

Do **not** log `monthly_revenue_band` next to DataFrame values. Logging the band enum on the existing `"comparison complete"` extra is allowed (it is not a cell value). Do not log `R`, `dollar_t1`, or `dollar_t2` as if they were user-typed dollars.

### C.3 `backend/agents/orchestrator.py` (modified)

**Today** `run_comparison_and_report` (~337–342) constructs:

```python
comparison = ComparisonAgent(
    entries_repo=get_entries_repo(),
    anomalies_repo=get_anomalies_repo(),
    runs_repo=get_runs_repo(),
    accounts_repo=get_accounts_repo(),
)
```

`company_id` is already passed to `comparison.run(...)`. Orchestrator does **not** need to load the company itself.

**After:** pass `companies_repo=get_companies_repo()`. No other signature change. Do not compute gates in the orchestrator.

### C.4 `backend/domain/ports.py` — `CompaniesRepo` (modified)

**Today:**

```python
def get_by_owner(self, user_id: str) -> dict: ...
def create(self, owner_id: str, name: str, sector: str | None, currency: str) -> dict: ...
```

**After — add / extend:**

```python
def get_by_id(self, company_id: str) -> dict: ...
# Full row including monthly_revenue_band. Raises RLSForbiddenError if no row.

def update(
    self,
    company_id: str,
    *,
    monthly_revenue_band: str,
) -> dict: ...
# PATCH path only. Returns the updated row.

def create(
    self,
    owner_id: str,
    name: str,
    sector: str | None,
    currency: str,
    monthly_revenue_band: str | None = None,
) -> dict: ...
```

Do **not** introduce a `Company` dataclass. Repos keep returning `dict` (CLAUDE.md hybrid return-type policy).

### C.5 `backend/adapters/supabase_repos.py` — `SupabaseCompaniesRepo` (modified)

- `get_by_owner` already `select("*")` (~641). No change other than the new column appearing on the dict.
- **Add `get_by_id`:** `select("*").eq("id", company_id).limit(1)`. Empty → `RLSForbiddenError`. Same retry wrap as `get_by_owner`.
- **Add `update`:** `.update({"monthly_revenue_band": monthly_revenue_band}).eq("id", company_id)`. Return the row. Constraint violations (bad enum) are not retried.
- **`create`:** add `"monthly_revenue_band": monthly_revenue_band` to the insert dict (~664–669).

### C.6 `backend/api/auth.py` (modified)

`_COMPANY_TTL = 300.0` with comment “company row is immutable within a session” (~24). After PATCH that comment is false.

**Add:**

```python
def invalidate_company_cache(user_id: str) -> None:
    _company_cache.pop(user_id, None)
```

Call from `PATCH /companies/me` after a successful update. Without this, `GET /companies/me` can return stale `NULL` for up to 5 minutes.

`get_cached_company` / `get_company_id` stay as they are otherwise. Comparison does **not** use this cache; it reads via `get_by_id`.

### C.7 Files that must NOT change in item 5

- `backend/tools/guardrail.py` — still `numbers_used` vs pandas_summary. No new flux floors in the check list.
- `backend/agents/interpreter.py::_run_with_guardrail` (~340–347) — recon_values stay `gl_amount`, `non_gl_total`, `delta`, `sources[].amount`. Do **not** append `dollar_t1` / `dollar_t2` / `R`. Claude must not mention the floor.
- `backend/prompts/narrative_prompt.txt` — **no change.** Do not put `$4,375`, `$875`, `2.5%`, or `0.5%` in the prompt. Flagged anomalies already carry pandas `variance_pct` in `description`.
- `backend/prompts/narrative_prompt_reinforced.txt` — no change.
- `backend/tools/hint_computer.py` — no change.
- `backend/agents/consolidator.py::_is_material` — no change (`$500` OR (`$100` AND `>5%`)).
- `backend/tools/excel_export.py` — no change.

**Guardrail impact for item 5:** none. No new numeric values on the verification list. Flux floors are internal to pandas and must never appear in `numbers_used`.

**Prompt impact for item 5:** none. Claude copies `variance_pct` from the anomaly list. Never divide, never apply a threshold.

## D. API / routes

Auth / `company_id` resolution: unchanged. Still JWT → `user_id` → `companies.owner_id`. Never accept `company_id` from the client.

### D.1 `CreateCompanyRequest` (`backend/api/routes.py` ~111)

**Before:**

```python
class CreateCompanyRequest(BaseModel):
    name: str
    sector: str | None = None
```

**After:**

```python
class CreateCompanyRequest(BaseModel):
    name: str
    sector: str | None = None
    monthly_revenue_band: Literal[
        "under_100k", "100k_250k", "250k_500k", "500k_plus"
    ]
```

Required. Omit or invalid → FastAPI **422**. This is an HTTP-body rule only.

**Will this break seed or tests? No.** Checked:

- `supabase/seed.sql` is raw SQL, not this model.
- No pytest posts `/companies` or instantiates `CreateCompanyRequest` (`tests/` has zero hits).
- `CompaniesRepo.create` is only called from `create_company` in `routes.py`.
- Integration `tests/integration/conftest.py` synthesizes Excel/CSV bytes; it does not insert companies.

### D.2 `POST /companies` (`create_company`, ~1246)

**Before request:** `{ name, sector? }`. **After:** `{ name, sector?, monthly_revenue_band }` (band required).

**Before response (201 and idempotent 200):** `{ id, name, sector, currency }`. **After:** same plus `monthly_revenue_band` (nullable on the 200 path if the stored row is pre-0010).

**Idempotent path (~1264–1278) stays a pure read.** Today: if `get_by_owner` finds a row, return 200 with that row unchanged. **Keep that.** Do **not** UPDATE the band on retry.

Rationale (locked): once the field is required, the first successful insert already stored the band. The documented retry (`CompanySetupForm.tsx` ~41–44: company row exists, `onboarding_done` metadata write failed) only needs the existing row back. Pre-0010 NULL-band companies are already past onboarding; they use **PATCH**, not a second POST. Mutating on POST would also let a DRONE seed retry silently retune demo flux.

**Create path (~1283–1288):** pass `monthly_revenue_band=body.monthly_revenue_band` into `companies_repo.create`.

Rate limit stays `@limiter.limit("5/hour")`.

### D.3 `GET /companies/me` (~1213)

**Before response:** `{ id, name, sector, currency }`.  
**After:** add `"monthly_revenue_band": company.get("monthly_revenue_band")` (JSON `null` when unset).

Old clients ignore the extra field. Existing companies created before the column existed: `null` → flux fail-safe → Profile banner.

### D.4 `PATCH /companies/me` (new)

This is the **only** writer for an existing row’s band.

- Auth: `Depends(get_current_user)` + `Depends(get_cached_company)` (or `get_company_id`). No `company_id` in body or path.
- Request: `UpdateCompanyRequest` with required `monthly_revenue_band` (same Literal). Invalid → 422.
- Behaviour: `companies_repo.update(company["id"], monthly_revenue_band=body.monthly_revenue_band)`, then `invalidate_company_cache(user_id)`, return the same shape as GET.
- Rate limit: `@limiter.limit("5/hour")` (same family as POST create).
- 429: existing `Retry-After` + `messages.RATE_LIMITED`.
- Do not accept `name` / `sector` / `currency` on this PATCH in v1 (not requested).

### D.5 Backward compatibility

| Client | Behaviour |
|--------|-----------|
| New onboarding POST without band | 422. Form will not submit without a radio. |
| New onboarding POST with band | 201, row stored. |
| Retry POST after company exists | 200, existing row, **no mutation**. |
| GET `/companies/me` old client | Extra field ignored. |
| Company row from seed / pre-0010 | `monthly_revenue_band` NULL. Flux = `$50k`/`$10k`. Profile must offer PATCH. |
| Comparison run, NULL band | Fail-safe constants. Never `$0`. |

## E. Frontend

Do not show raw dollar floors (`$4,375`, `$875`, `$50,000`, `$10,000`). Do not show `2.5%` / `0.5%`. Do not let the user type a threshold. Do not parse `sector` free-text to pick gates.

Radio labels (ask **typical monthly revenue**, not annual, not “materiality”, not “Tier 2”):

| UI label | Stored value |
|----------|----------------|
| Under $100k / month | `under_100k` |
| $100k–$250k / month | `100k_250k` |
| $250k–$500k / month | `250k_500k` |
| $500k+ / month | `500k_plus` |

Helper copy: “Not annual. Not a target. What usually lands in a month.”

### E.1 `frontend/src/hooks/useCompany.ts`

**Today `Company`:** `id, name, sector, currency`.  
**After:** add `monthly_revenue_band: string | null`.

`queryKey` stays `["company-me"]`. PATCH must `invalidateQueries` / `setQueryData` so Profile and any other consumer update.

### E.2 `frontend/src/components/CompanySetupForm.tsx`

**Today `handleSubmit` POST:** `{ name: companyName.trim(), sector }` (~33–36). Submit disabled when name/company/email/sector empty (~24–25).

**After:**

- New required control: four radios (or a select with the four labels). Same card, not a second onboarding screen.
- `disabled` also requires a chosen band.
- POST JSON: `{ name: companyName.trim(), sector, monthly_revenue_band }`.
- Cache `setQueryData` already stores the POST response; the response now includes the band.

Follow `docs/01-architecture/design.md` language: plain English, teal accent, no jargon.

### E.3 `frontend/src/pages/ProfilePage.tsx`

**Today:** read-only Name / Sector / Currency. File comment (~14–17) says “no backend changes required” — **delete that comment**.

**After — new state this page did not render:**

- If `company.monthly_revenue_band == null` (and not loading): banner + the same four radios + Save → `PATCH /companies/me`. Copy: ask them to set typical monthly revenue so close flags match shop size. Do not mention thresholds.
- If set: show the **human label**, not the enum. Allow change via the same radios + PATCH (existing shops must not be stuck on `$50k` forever, and a wrong first pick must be correctable).
- On success: update `["company-me"]` cache.

### E.4 What must NOT appear in the UI

- Raw floors, percents used in the formula, `R`, “Tier 1”, “Tier 2”, “materiality”.
- A dollar text input.
- A control that edits recon `_is_material` (`$100`/`$500`).

## F. Tests

### F.1 `tests/agents/test_comparison.py` (existing; expected values that hardcode `$50k`/`$10k` become fail-safe / `500k_plus`)

Existing tests call `calculate_variance` **without** `dollar_t1`/`dollar_t2`. After the signature change they remain valid **fail-safe** tests if omitted gates map to `_TIER1_DOLLAR` / `_TIER2_DOLLAR`. Keep the assertions; rename comments from “Tier 1 $50K” to “fail-safe / omitted gates = $50k”.

| Test | Today | After |
|------|-------|-------|
| `test_no_category_defaults_to_tier1_thresholds` | $60k/20% flags Tier 1 | Same; omitted gates = fail-safe Tier 1. Still flags. |
| `test_no_category_below_tier1_dollar_gate_not_flagged` | $40k/40% no flag | Same fail-safe. |
| `test_tier1_both_gates_must_clear` | OPEX $60k/20% flags | Same. OPEX is not REVENUE and has no payroll name. |
| `test_tier1_only_dollar_gate_not_flagged` | $60k/2% no flag | Same. Pct gate unchanged. |
| `test_tier1_only_pct_gate_not_flagged` | G&A $20k/25% no flag | Same at fail-safe $50k. |
| `test_tier2_revenue_fires_at_lower_gates` | REVENUE $15k/5% flags at $10k | Same at fail-safe t2. |
| `test_tier2_payroll_fires_at_lower_gates` | `category="PAYROLL"`, $12k/4% flags | **Change:** pass `account_name="Salaries & Wages"` (or `"Payroll"`) and `category="G&A"`. Category `PAYROLL` is no longer a live gate. |
| `test_tier2_deferred_revenue_fires_at_lower_gates` | `category="DEFERRED_REVENUE"` flags t2 | **Convert to negative:** `category="DEFERRED_REVENUE"`, no payroll name, $11k/3.5% → **Tier 1, not flagged** (fails $50k). Rename e.g. `test_deferred_revenue_category_is_not_tier2`. |
| `test_tier2_below_dollar_gate_not_flagged` | REVENUE $8k/10% no flag | Same at fail-safe t2 $10k. |
| `test_tier2_below_pct_gate_not_flagged` | `category="PAYROLL"` $12k/1% | Pass `account_name` payroll needle; still no flag (pct). |
| `test_severity_*` / `test_no_history_*` / `test_unknown_category_treated_as_tier1` | Unrelated to dollars that change | Keep. Unknown category still Tier 1. |

**`_make_agent` (~196) / recurrence tests:** not a Recurrence agent. These construct `ComparisonAgent` and call `run`. After `__init__` grows `companies_repo`, `_make_agent` must pass a MagicMock whose `get_by_id` returns `{ "monthly_revenue_band": None }`. Account name is already `"Engineering Salaries"` (~213) → `is_payroll_account` True. Amounts `$360k` vs `$300k` still flag. Assertions on the suffix strings **do not change**.

Tests that stay as-is besides the mock:

- `test_recurrence_suffix_appended_when_prior_count_is_2`
- `test_recurrence_suffix_appended_when_prior_count_exceeds_2`
- `test_recurrence_suffix_not_appended_when_prior_count_is_1`
- `test_recurrence_suffix_not_appended_when_no_prior_flags`
- `test_list_account_flag_counts_called_once_not_per_entry`

### F.2 New tests in `tests/agents/test_comparison.py`

| Function | Proves |
|----------|--------|
| `test_gates_from_band_null_equals_legacy_constants` | `_gates_from_band(None) == (50_000, 10_000)` |
| `test_gates_from_band_500k_plus_equals_legacy_constants` | `_gates_from_band("500k_plus") == (50_000, 10_000)` |
| `test_gates_from_band_under_100k` | `(1250, 250)` |
| `test_gates_from_band_100k_250k` | `(4375, 875)` |
| `test_gates_from_band_250k_500k` | `(9375, 1875)` |
| `test_unknown_band_string_fail_safe` | `"annual"` / `""` / `"not_a_band"` → `(50_000, 10_000)`, no exception |
| `test_null_band_never_zero_floors` | Fail-safe is not `(0, 0)` |
| `test_icp_100k_250k_salaries_flags` | current=43500, avg=38000, category=`G&A`, `account_name="Salaries & Wages"`, gates from `100k_250k` → `flag is True` ($5500 > $875 and 14.47% > 3%) |
| `test_icp_installation_revenue_flags` | current=15000, avg=10000, category=`REVENUE`, gates `100k_250k` → True ($5000 > $875 and 50% > 3%) |
| `test_icp_rent_noise_not_flagged` | current=3200, avg=3000, category=`OPEX`, no payroll name, gates `100k_250k` → False ($200 ≰ $4375) |
| `test_payroll_name_uses_tier2_of_band` | category=`G&A`, `account_name="Salaries & Wages"`, same $5500 / 14.5% with `under_100k` t2=$250 → True |
| `test_payroll_name_without_scale_still_misses_icp_noise` | same $5500 / 14.5%, omitted gates (fail-safe t2=$10k) → False. Documents why PR #5 alone is not enough. |
| `test_revenue_without_payroll_name_is_tier2` | category=`REVENUE`, `account_name="Installation Revenue"` uses t2 |
| `test_opex_non_payroll_uses_tier1_of_band` | category=`OPEX`, `account_name="Rent"`, $5500 / 14.5% at `100k_250k` t1=$4375 and pct 10% → True on both; add a case $3000 / 8% → False (pct) |

### F.3 `tests/tools/test_account_tags.py` (new)

| Function | Proves |
|----------|--------|
| `test_salary_wages_compensation_needles` | Each needle matches |
| `test_case_insensitive` | `"SALARIES & WAGES"` True |
| `test_non_payroll_name_false` | `"Rent"`, `"Installation Revenue"`, `"Bank Charges"` False |
| `test_empty_and_none_safe` | `""` False; do not crash |

### F.4 API tests (new file `tests/api/test_companies_band.py` if the suite can construct the app; otherwise mark as route-level unit tests with mocked repo)

| Function | Proves |
|----------|--------|
| `test_post_companies_omitting_band_is_422` | Required field |
| `test_post_companies_invalid_band_is_422` | CHECK-aligned Literal |
| `test_post_companies_idempotent_does_not_update_band` | Existing row returned unchanged even if body has a different band |
| `test_patch_companies_me_sets_band` | Update path |
| `test_patch_invalidates_company_cache` | Subsequent GET sees the new value (or cache pop called) |

### F.5 Kova 1 tests — do **not** change expected values

See the cross-cutting matrix. No file in `tests/tools/test_deposit_vs_fee.py`, `tests/tools/test_annual_prepayment.py`, `tests/tools/test_hint_computer.py`, `tests/agents/test_consolidator.py`, `tests/agents/test_interpreter_classify.py` calls `calculate_variance`. `test_consolidator.py` `(50000.0, "high")` is recon **severity**, not flux. Leave it.

`tests/agents/test_quarterly.py` groups already-written anomalies; it does not call `calculate_variance`. No expected-value change.

## G. Sequencing within the item

**One product PR.** Do not split SQL vs API vs UI.

| If split hypothetically | Safe to merge alone? |
|-------------------------|----------------------|
| Migration only | Yes: NULL = old flux. But onboarding cannot write the band. Do not ship this way. |
| Backend without UI | New companies 422 on POST (band required) with no radio to send it. **Not safe.** |
| PAYROLL helper without scale | Wages enter a still-DRONE `$10k` gate. Harmless if unused, but this spec includes both so ICP wages use **scaled** t2. |

If PR #5 is already merged when this PR opens: do not copy `account_tags.py`; only wire `account_name` + gates.

No PR-B for item 5.

## H. Rollback

- Revert the single product commit (or the PR).
- Optional DOWN (only if the column must leave a database that keeps the new app code off):

```sql
ALTER TABLE companies DROP CONSTRAINT IF EXISTS companies_monthly_revenue_band_chk;
ALTER TABLE companies DROP COLUMN IF EXISTS monthly_revenue_band;
```

- No data backfill to undo. NULL rows were never filled.
- If the column is dropped while new code still runs, `company.get("monthly_revenue_band")` is `None` → fail-safe. Prefer reverting code and migration together.
- Auth cache: reverting PATCH removes the need for `invalidate_company_cache`; leftover function is unused, not harmful if a revert is code-only.

---

# Item 1 — Bank / processor three-way MVP

**SPEC ONLY until item 5 has shipped and there is an explicit go-ahead to build.**  
This section is the freeze so a later build has zero open product questions. Do not write matcher code, do not add `SourceFileType` values, do not open an item-1 PR from this document.

Kova 1 already has **account-total** `is_processor_fee_gap` (3–8%, two-sided, not a deposit) → interpreter forces `structural_explained`. That is **not** this item. This item is identity matching **before** `groupby("account")`.

**MVP boundary (locked):** one processor, one Undeposited Funds (or merchant clearing) GL account, one bank, one period. Match **batch/reference id first**; exact net amount + date window only as fallback. Pandas computes gross, fee, net, unmatched counts. Claude copies; never subtracts. Emit existing classes only. No A2X, no auto-JE, no multi-currency, no many-to-many splits, no connectors.

| Matcher state | Class (existing six only) |
|---------------|---------------------------|
| Gross vs net, fee explained | `structural_explained` |
| Payout dated after period_end | `timing_cutoff` |
| Processor batch not in GL | `missing_je` |
| Bank deposit not in GL / UF | `missing_je` |
| Posted to the wrong clearing account | `categorical_misclassification` |

Account-total fee-band stays the **fallback** when the user did not upload a settlement file.

## A. Pre-conditions

- **Roadmap block:** item 5 product PR merged (so cash cards sit next to shop-scale flux). Not a Python import of `_gates_from_band`.
- Kova 1 `is_processor_fee_gap` on this stack (PR #9) so the fallback exists.
- `SourceFileType` today (`backend/domain/contracts.py` ~18–23): `general_ledger \| payroll \| supplier_invoices \| contracts`. Unknown files **default to `supplier_invoices`** (`orchestrator.py::_detect_file_type` ~526–532). A `bank_statement.csv` or `stripe_payouts.xlsx` is a vendor file today.
- Golden fields today: `account, account_code, amount, date, parent_category, department, description`. `normalizer.apply_plan` drops every other column (~108–134). `validator.py` pandera `strict=True` on those seven.
- `monthly_entries` unique `(company_id, account_id, period)` cannot store batches. Do not try.
- Demo: Sentinel has **no** bank/processor file. Vandelay Shopify/Amazon payouts are **two-sided processor vs GL, not three-way** (no bank). Isolated three-file fixture is required.
- Not blocked on item 4. Do not steal `0010` (that is item 5). Attestation, if ever persisted, is `0011`.

## B. Database / migration

**No SQL in v1.**

| Change | Migration? |
|--------|------------|
| `SourceFileType` literals | No (Pydantic) |
| Matcher results on `reports.reconciliations` JSONB | No (`0007` already JSONB) |
| Extra columns on the **file** (`batch_id`, `gross`, `fee`, `net`) | No SQL. Sidecar / contracts-like optional fields in code, **not** widening all-file `GoldenField` |
| Persist line-level matches for audit | **Not in v1.** Ephemeral matcher from the three uploads; persist classified cards in existing JSONB only |
| Bank attestation checkbox | If persisted later: `0011_add_bank_attestation.sql`. **Not this item. Not `0010`.** |

**What is NOT migrated:** no `bank_batches` table, no payout identity table, no change to `monthly_entries` unique key, no new RLS policy (cards stay on `reports`, already company-gated).

**RLS:** none new.

## C. Backend — file by file

***Design for future PR, not to be implemented yet.***

### C.1 `backend/domain/contracts.py`

**Modify `SourceFileType`:** add `"bank_statement"` and `"processor_settlement"`. Still four-or-six literals total for files; do not add a seventh **classification**.

**Do not** add `batch_id` / `gross` / `fee` / `net` to `GoldenField` for every file (pandera `strict=True` on P&L would then require those columns). Prefer a **sidecar** typed model, e.g. `ProcessorSettlementRow` / `BankStatementRow`, used only when `file_type` is the new literals.

**Modify `ReconciliationItem` (JSONB, no migration):** optional nested `matches: list[BatchMatch] | None = None` (or equivalent) so several batches on one UF line can be classified without a seventh class. `NarrativeJSON.reconciliation_classifications` is `dict[account → class]` today — **insufficient** for per-batch speech. Future interpreter must classify by match id **or** nest class on each match and keep the account-level class as the primary residue. Do not invent a seventh enum. Exact shape to freeze at build time:

```python
class BatchMatch(BaseModel):
    match_id: str
    processor_ref: str | None
    bank_ref: str | None
    gl_ref: str | None
    gross: float
    fee: float
    net: float
    unmatched: bool
    classification: ReconciliationClassification | None = None
```

Numbers are pandas. Claude copies `gross` / `fee` / `net`.

**Modify `ReconciliationHints` only if a post-match bool is needed** (e.g. `is_three_way_fee_explained`). Prefer putting the speech act on `BatchMatch.classification` + interpreter force, not a new hint that re-runs after `groupby` (groupby already destroyed ids).

### C.2 `backend/agents/orchestrator.py`

**Today `_FILE_TYPE_PATTERNS` (~511–523)** has no bank/processor keys. `_detect_file_type` defaults to `supplier_invoices`.

**After (PR-B, not PR-A):** add patterns, e.g.:

- `bank_statement`: `bank`, `statement`, `checking`, `deposit_account` (be conservative; do not steal `deposit` from customer-deposit files).
- `processor_settlement`: `stripe`, `shopify_payout`, `paypal`, `square`, `processor`, `settlement`, `payout`.

**PR-A must not wire this dict.** If PR-A is merged alone with patterns live, Vandelay `vandelay_shopify_payouts_mar_2026.xlsx` would stop being `supplier_invoices` and consolidator would tell a fee story without a matcher. PR-A is types + fixture only.

Pass `file_type` into `parse_file_silently` so the sidecar is only built for bank/processor files.

### C.3 `backend/tools/normalizer.py` / `backend/tools/validator.py`

**Today:** `apply_plan` drops unmapped and non-golden columns (~108–134). Validator `_SCHEMA` is seven columns, `strict=True`.

**After:** do **not** put `batch_id` on the P&L schema. For `file_type in {bank_statement, processor_settlement}`, **before** the extra-column drop, copy identity/amount-component columns into a sidecar frame keyed by `_orig_row_index`. Then run the existing golden path so `monthly_entries` stay account totals.

Sidecar columns (pandas): `batch_id` / `payout_id` / bank reference, `gross`, `fee`, `net`, settlement date if distinct from txn date. Discovery `column_mapping` for these files may map those headers to sidecar names without claiming `GoldenField`.

### C.4 `backend/agents/parser.py::parse_file_silently`

**Today (~493–560):** discover → sanitize → `apply_plan` → validate → optional `account_name_map` → `groupby("account")["amount"].sum()` → `df_detailed` is the **post-golden** frame (ids already gone).

**After:** accept `file_type`. If bank/processor, build sidecar from `df_raw` **before** `apply_plan` drops columns. Return sidecar alongside `(preview_rows, source_column, df_detailed)`. Preview rows remain account totals for consolidator. Sidecar is **not** written to `monthly_entries`.

### C.5 `backend/tools/batch_matcher.py` (new)

**Responsibility:** deterministic pandas matcher. No Claude. No DB.

**Input:** three frames (processor sidecar, GL UF lines or GL sidecar, bank sidecar) + `period`.  
**Output:** `list[BatchMatch]` plus unmatched counts.  
**Called from:** orchestrator, **after** parse, **before or beside** consolidator — consolidator must **not** become the matcher.  
**Does not:** post JEs, call A2X, fuzzy-match GL account names (that is consolidator’s WRatio job), write `monthly_entries`, invent a seventh class.

Match order (locked):

1. Exact `batch_id` / `payout_id` / bank reference across processor ↔ GL ↔ bank.
2. Fallback: exact `net` amount and settlement date within the period window (same calendar date first; ±1 business day only if id match is empty — freeze the window at build time as **same date only** unless a fixture proves otherwise; do not silently widen).
3. Unmatched processor batch → `missing_je`. Unmatched bank deposit → `missing_je`. Matched gross/fee/net with residue in the fee band → `structural_explained`. Date after `period_end` → `timing_cutoff`. Amount on the wrong GL clearing name → `categorical_misclassification`.

Pandas computes `gross`, `fee`, `net` (`gross - net` is pandas, not Claude). Unmatched counts are `int`.

### C.6 `backend/agents/consolidator.py`

**Not the matcher.** `_build_item` continues to emit account-total cards. `ReconciliationSource.row_count = 1` (~275) stays for this item (item 4 owns that lie). Matcher cards are a **separate** list merged into `parse_preview.reconciliations` JSONB, or nested under the UF account item. Do not un-hardcode `row_count` here and call it batch count.

`_is_material` unchanged (item 5 already forbade retuning it).

### C.7 `backend/tools/hint_computer.py`

Account-total `is_processor_fee_gap` remains the fallback when no settlement sidecar exists. Matcher results **must not** also fire the 3–8% account-total hint on the same card if three-way already explained the fee (double speech). Priority at interpreter: three-way match class wins over `is_processor_fee_gap` when `matches` is non-empty.

Do not scan P&L for `batch_id`.

### C.8 `backend/agents/interpreter.py`

**Modify `_apply_reconciliation_classifications` (~115) and `_classify_from_hints` (~71):** if an item has `matches`, force each match’s pandas class; do not let Claude pick `structural_explained` without a match or fee hint (existing guard already blocks unprompted `structural_explained` at ~140–141).

**Modify `_run_with_guardrail` (~340–347):** for each recon item, also append pandas `gross`, `fee`, `net`, and unmatched counts (and `abs` of each, same pattern as `delta`). Exact fields: `item["matches"][i]["gross"]`, `["fee"]`, `["net"]`, plus a top-level `unmatched_count` if present. If `matches` is absent, behaviour is today’s list.

**Prompt impact:** `backend/prompts/narrative_prompt.txt` `structural_explained` template stays for account-total fee fallback. **Add** a three-way template that copies `[gross]`, `[fee]`, `[net]`, `[unmatched_count]` with an explicit line: **Claude must copy these numbers, never subtract gross − net, never compute a fee %.** Same reminder in `narrative_prompt_reinforced.txt`.

### C.9 `backend/prompts/account_mapping_prompt.txt`

**Today** `file_type` one of `payroll, supplier_invoices, contracts`. **After:** document `bank_statement` / `processor_settlement`: map payout/batch identifiers to the UF / merchant clearing / bank GL names, not to COGS. Do not perform arithmetic.

### C.10 Dead / hardcoded logic to watch

- Default-to-`supplier_invoices` (~532): after PR-B, bank files must not fall through. Test: filename `stripe_payouts.xlsx` → `processor_settlement`, not vendor.
- `consolidator.py::_is_gl_label`: independent of `SourceFileType`. A bank file must not be treated as GL.
- `row_count=1`: leave it; matcher has its own identity. Confirm `excel_export.py` (~231, ~287) still prints source `row_count` as rolled lines, **not** as matched batches.

## D. API / routes

***Design for future PR, not to be implemented yet.***

No new endpoint in v1. Reconciliations already flow through existing run parse-preview JSONB and report payload.

| Endpoint | Change |
|----------|--------|
| `POST /upload` (and multi-file run start) | None required. Filename detection is server-side. |
| Mapping confirm | `file_type` already on mapping draft items (`MappingReview.tsx`). New types must round-trip. |
| Report GET | Response may include nested `matches` on recon items. Old clients that ignore unknown keys keep working. |

Auth / `company_id`: unchanged.

**Backward compatibility:** runs without bank/processor files behave exactly as today (fee-band fallback). Nested `matches: null` / omitted.

## E. Frontend

***Design for future PR, not to be implemented yet.***

- `frontend/src/components/FileUpload.tsx`: optional helper copy that a bank CSV and a processor payout file can be uploaded **together** with the GL. No new file-type picker required if detection stays filename-based. Do not ask the user to type match keys.
- `frontend/src/components/MappingReview.tsx`: payroll has a “Set All to Salaries & Wages” special case (~232). Do **not** add a similar “set all to COGS” for bank files. Optionally a UF quick-apply if the GL pool contains an Undeposited Funds name — only if a fixture has that name; otherwise skip.
- Recon cards: may stay account-grouped if `matches` nest inside the UF card. Do **not** expose raw matcher debug (unmatched id lists) in v1 beyond the pandas counts Claude is allowed to copy.
- **Never** show a user-typed match threshold.

## F. Tests

| File | Functions / what they prove |
|------|------------------------------|
| `tests/tools/test_batch_matcher.py` (new) | `test_id_match_three_way_fee_explained` — id hits, pandas fee = gross−net, class `structural_explained`. `test_unmatched_processor_batch_missing_je`. `test_unmatched_bank_deposit_missing_je`. `test_payout_after_period_end_timing_cutoff`. `test_wrong_clearing_account_categorical`. `test_fallback_amount_date_only_when_id_absent`. `test_does_not_match_on_gross_against_net` (negative). |
| Isolated three-file fixture | Hand-crafted processor / UF / bank frames. Pin dollar values. |
| `tests/tools/test_detect_file_type.py` or orchestrator tests | PR-B: `stripe_payouts` → `processor_settlement`; `bank_statement` → `bank_statement`; unknown still `supplier_invoices`. **PR-A: these must still be supplier/unknown** (detection not wired). |
| Vandelay negative | Shopify/Amazon payouts **without** a bank file: matcher does **not** claim three-way. Account-total fee fallback may still fire. |
| Sentinel negative | No bank file. Bank Charges $95 is not this item. |
| `tests/agents/test_interpreter_classify.py` | Force class from `matches`; Claude cannot override to a different class; no seventh class in the Literal. |
| Guardrail | `numbers_used` containing pandas `gross`/`fee`/`net` passes; a Claude-invented `gross - net` that is not on the item fails. |
| Kova 1 fee tests | `is_processor_fee_gap` still true on two-sided 3–8% **without** matches. Do not retune `_FEE_BAND_*`. |

## G. Sequencing within the item

Analysis size: large, three PRs. **Do not ship A as user-facing without B.**

| PR | Ships | Default behaviour if merged alone | Why that is / is not safe |
|----|-------|-----------------------------------|---------------------------|
| **PR-A** | `SourceFileType` literals unused by `_detect_file_type`; sidecar **type** names; isolated fixture checked in; maybe empty `batch_matcher.py` with no call site | Unknown files still `supplier_invoices`. Consolidator unchanged. | **Safe.** Inert types. Do not wire filename patterns in A. |
| **PR-B** | Wire `_FILE_TYPE_PATTERNS` + `parse_file_silently(file_type=...)` + sidecar extract + `batch_matcher.py` + interpreter force + guardrail recon_values | Bank/processor filenames change type; matcher runs; classes appear on cards. Prompt may still be the old fee template. | **Behaviour change.** Merge only after A. Guardrail still passes if Claude does not mention gross/fee/net. |
| **PR-C** | `narrative_prompt.txt` / reinforced three-way template; FileUpload helper copy; optional MappingReview | Speech quality. Without C, cards exist with pandas numbers but Claude may use the generic fee sentence. | Safe after B. Ship immediately after B so the prompt copies pandas gross/fee/net. |

Do not merge PR-A to `main` as a “user-facing bank” story. Stack A←B←C.

## H. Rollback

- Revert PR-C first (prompt/UI). Cards still classify via pandas force.
- Revert PR-B: detection and matcher gone; files again default to `supplier_invoices`; Kova 1 fee fallback remains. No migration DOWN.
- Revert PR-A: unused literals. JSONB with unknown extra keys still parses if Pydantic models ignore extras; if `matches` was added with a default `None`, old rows without the key are fine.
- No SQL to roll back. No batch table to truncate.

---

# Item 4 — RMR account-count vs GL

Build **after item 1 ships** and after an explicit go-ahead. Not a deferred-revenue waterfall. Not annual 12× (already Kova 1). Class stays **`stale_reference`**.

There is **no** RMR/subscriber concept in the backend today (`backend/` grep: zero `RMR`, `subscriber`, `active_count`). `contracts` as `SourceFileType` already exists. Filename patterns already include `roster`, `subscription`, `recurring`, `customer`. The type exists; the count does not.

## A. Pre-conditions

- Item 1 shipped (roadmap). Not a Python import of `batch_matcher`.
- Cutoff allowlist (PR #11) **must stay**: `hint_computer.py::_crosses_period_boundary` skips contracts filenames (`_is_contracts_roster_file`) and ignores Last Billed / renewal headers. Item 4 **reads** Last Billed as a **count input**. Do **not** re-widen the cutoff allowlist.
- Independent of item 5 / `0010`. Do not steal that filename.
- Sentinel contracts xlsx is **designed** (85 rows, $285, 3 stale) but **missing** on this branch. Isolated fixture is required even if the xlsx is restored.
- Vandelay / DRONE: no subscriber roster. They are negatives, not demos of this item.
- `parse_file_silently` does **not** currently receive `file_type` (orchestrator detects it separately). Item 4 must pass `file_type` in so the sidecar is contracts-only.

## B. Database / migration

**No SQL.** Highest migration stays whatever item 5 wrote (`0010`). Do not write `0011` for counts.

| Change | Migration? |
|--------|------------|
| `n_active`, `n_billed_in_period`, `count_delta`, `fee_sum_active` on hints / item JSONB | **No** (`reports.reconciliations`) |
| 85 subscriber rows in `monthly_entries` | **Do not.** Unique `(company_id, account_id, period)` cannot hold them |
| New `SourceFileType` | **No** — `contracts` exists |
| Extra golden fields on **all** files (`status`, `customer_id`) | **No.** Contracts-only sidecar. P&L/payroll stay 7-column pandera |
| Customer dimension table | **No** in v1. Ephemeral counts per run |

**RLS:** none new.

**What is NOT migrated:** everything in the table above.

## C. Backend — file by file

### C.1 Exact drop path today (this is the grain kill)

```
parser.parse_file_silently                          backend/agents/parser.py ~493
  sample = read + pii_sanitizer.sanitize_sample
  plan = discovery.discover(...)
  df_raw = read_full + pii_sanitizer.sanitize       Status / Last Billed still present
        │
        ▼
  df_normalized, _ = normalizer.apply_plan(df_raw, plan, period)
        backend/tools/normalizer.py::apply_plan
        ~108–134  ← DROP POINT
          column_mapping: target is None → drop
          extra columns not in _GOLDEN_FIELDS → drop
          Status, Customer ID, Last Billed gone
          Monthly Fee survives only if Discovery mapped it → amount
          Customer Name survives only if mapped → account
        │
        ▼
  df_validated = validator.validate(df_normalized)  pandera strict 7-col
        │
        ▼
  if account_name_map:
      df_validated["account"] = map to GL names
      "Oak Street Dental" → "Service Revenue"       AccountMapper
        │
        ▼
  groupby("account")["amount"].sum()                parser.py ~542–552
      85 customer rows → ONE preview row
      account=Service Revenue, amount=3825
        │
        ▼
  df_detailed = df_validated.copy()                 parser.py ~555–558
      already 7-col, already mapped, Status gone
        │
        ▼
orchestrator → consolidator.consolidate
  _build_item → ReconciliationSource.row_count = 1  consolidator.py ~275
        (hardcoded; ignores _roll_up's len(tagged) at ~199)
        │
        ▼
hint_computer.compute_hints(item, source_raw_dfs=df_detailed)
      sees gl_amount=3540, non_gl_total=3825, delta=285
      No 85. No 82. No 3.
```

`df_detailed` is documented as “per-row … for hint_computer dates” (`parser.py` ~506–507). That is **too late** for Status: the normalizer already dropped it. Un-hardcoding `row_count=1` is **still the wrong grain**: 85 Excel lines ≠ 82 billed this month. The GL has **no** customer count.

### C.2 Intercept (exact)

**Where:** `ParserAgent.parse_file_silently`, **after** PII sanitize of `df_raw` and **before** `normalizer.apply_plan` extra-column drop — or inside `apply_plan` gated on `file_type == "contracts"` so P&L files never keep Status.

**Preferred:** keep `apply_plan` golden for all files. In `parse_file_silently`:

1. Orchestrator passes `file_type` (new argument; default `None` = today’s behaviour).
2. If `file_type == "contracts"` (or `_is_contracts_roster_file(storage_key)` as a belt), copy a sidecar from `df_raw` **using the Discovery header row** so columns are named. Sidecar keeps: Status, Last Billed, Monthly Fee (or the header Discovery mapped to `amount`), Customer ID / customer name. Align on `_orig_row_index`.
3. Then call `apply_plan` as today (sidecar is already copied; drop is fine).
4. After `account_name_map` (so we know the GL name) and **before** `groupby`, call `roster_counts.compute(sidecar, period)`.
5. Return counts with the existing tuple, e.g. `(preview_rows, source_column, df_detailed, roster_counts | None)`.

Do not put Status on `df_detailed` and then run pandera `strict=True` — that fails validation. Sidecar bypasses pandera.

### C.3 `backend/tools/roster_counts.py` (new)

**Responsibility:** pandas counts on a contracts sidecar. No Claude. No DB. No classification.

**Input:** `sidecar: pd.DataFrame`, `period: date`.

**Output** (typed dict or dataclass in `domain/contracts.py` is fine; not a SQL table):

```python
n_active: int              # count(Status == Active)                     # 85
n_billed_in_period: int    # count(Last Billed in period month)          # 82
count_delta: int           # n_active - n_billed_in_period               # 3
fee_sum_active: float      # sum(Monthly Fee | Active)                   # 3825
fee_sum_billed: float      # sum(Monthly Fee | billed in period)         # 3540 if complete
```

Status match: case-insensitive `active`. Last Billed: `pd.to_datetime`, compare year-month to `period`. Never log cell values (customer names, fees). Log `event="roster_counts"` with `n_active`, `n_billed_in_period`, `count_delta`, `rows_in_sidecar` only.

**Called from:** `parse_file_silently` (and tests).

**Does not:** fuzzy-match GL names, write `monthly_entries`, force a class, treat `_roll_up.row_count` as subscribers, re-open cutoff dates, split mid-month rate changes (v1 sums fees).

### C.4 `backend/domain/contracts.py` — `ReconciliationHints`

Add optional fields (defaults keep old JSONB parseable), same pattern as `implied_monthly`:

```python
n_active: int | None = None
n_billed_in_period: int | None = None
count_delta: int | None = None
fee_sum_active: float | None = None
```

No new hint **bool** is required if interpreter keys off `count_delta is not None and count_delta > 0`. If a bool is easier for force-class priority, `has_roster_count_gap: bool = False` is allowed — still JSONB, still not a seventh class.

### C.5 `backend/agents/orchestrator.py`

Plumb `file_type` into `parse_file_silently`. After consolidate, attach `roster_counts` onto the recon item whose canonical name is the mapped GL revenue account (the one all customers collapsed to). If consolidate dropped the item as immaterial, **do not** resurrect it as a count card when `count_delta == 0`; if `count_delta > 0` and the dollar delta was under `_is_material`, still attach counts only when the dollar item exists — v1 does **not** retune `_is_material` to keep a $285 card (Sentinel $285 already clears `$100` AND `>5%` if pct is large enough; pin this in the fixture). Do not create a seventh-class “count only” card.

### C.6 `backend/agents/consolidator.py::_build_item`

**Leave `row_count=1` hardcoded (~275).** Do not un-hardcode and call that RMR. `_roll_up`’s `len(tagged[...])` (~199–206) is “Excel lines after account map,” still not “billed this month.”

`excel_export.py` (~231, ~287) prints `src.row_count`. After this item it remains “rolled source lines,” **not** `n_active`. Do not change the export header to “accounts” in this item. If a comment exists, add that `row_count` is not a subscriber count.

Attach roster fields on `item.hints`, not on `ReconciliationSource.row_count`.

### C.7 `backend/tools/hint_computer.py`

Do **not** scan P&L `df_detailed` for Status (it is gone). Read `item.hints` counts if the parser already set them, **or** accept an optional `roster_counts_by_account` map from the orchestrator. Do not set `crosses_period_boundary` from Last Billed. Add a regression test that a contracts sidecar with April Last Billed does **not** flip cutoff.

Do not hang this off `looks_like_annual_prepayment` or `similar_amount_in_other_account`.

### C.8 `backend/agents/interpreter.py`

**Force class:** if `count_delta` is not None and `count_delta > 0`, force `stale_reference`, unless an earlier pandas speech act already won (fee, deposit, annual). Insert in `_apply_reconciliation_classifications` **after** annual, **before** Claude’s map — roster counts are not 12× and not a deposit.

Coverage / `is_gl_only`: no roster counts (no sidecar). Do not classify coverage.

**Guardrail — `_run_with_guardrail` ~340–347:** for each recon item, also append `hints.n_active`, `hints.n_billed_in_period`, `hints.count_delta` when not None (as `float`, same as other numbers). Claude writing “3 cancelled customers” without `3.0` on the item is a golden-rule failure; this list is how it passes.

### C.9 `backend/prompts/narrative_prompt.txt`

**Today** `stale_reference` prose says “customer count or rate differences” but the template only has `[amount]`, `[GL amount]`, `[delta]`.

**After:** when `count_delta` / `n_active` / `n_billed_in_period` are present, use a template that copies those **ints from hints**. Explicit reminder: **Claude must copy `n_active`, `n_billed_in_period`, and `count_delta`. Never write “about 3”. Never subtract 85−82. Never invent a count from the dollar delta.** Same line in `narrative_prompt_reinforced.txt`.

When those hints are absent, keep the current dollar-only stale_reference template (negative: $285 with `count_delta=0` or missing).

### C.10 Files that must NOT change (except tests’ expected values if a new field appears with default)

- Cutoff allowlist needles in `hint_computer.py`.
- `looks_like_annual_prepayment` logic.
- `GoldenField` / P&L pandera schema (sidecar, not a 8th golden column).
- Item 5 flux gates.

## D. API / routes

No new endpoint. Counts ride on existing `parse_preview.reconciliations` / report JSON.

Old clients: extra hint keys ignored. Auth unchanged.

**Backward compatibility:** non-contracts uploads unchanged. Contracts uploads without Status/Last Billed: `roster_counts` is None; dollar stale_reference as today.

## E. Frontend

Not required for v1. Cards already show recon narrative. If a count appears in the narrative, it came from pandas via the prompt.

**Do not** add a subscriber dashboard, attrition chart, or a user-typed count threshold. **Do not** relabel `row_count` in the Excel export as “RMR accounts.”

## F. Tests

| File | Functions / what they prove |
|------|------------------------------|
| `tests/tools/test_roster_counts.py` (new) | `test_sentinel_shape_85_82_3` — n_active=85, n_billed=82, count_delta=3, fee_sum_active=3825. `test_status_case_insensitive`. `test_last_billed_other_month_not_counted`. `test_empty_sidecar_zeros`. |
| Isolated fixture (new) | 85/82/3 plus GL $3540 vs roster $3825. Pin `count_delta=3`. |
| `tests/tools/test_hint_computer.py` | Existing Last Billed cutoff tests **must stay False** for contracts filenames (PR #11 regression). Add `test_roster_counts_do_not_set_crosses_period_boundary`. |
| `tests/tools/test_annual_prepayment.py` | Negative: Software $13,200 / $1,100 stays annual 12×, **not** a count card. `count_delta` absent. |
| Dollar-only stale_reference | `count_delta=0` (or None) with $285 → class `stale_reference`, narrative must not say “0 accounts.” |
| `tests/agents/test_interpreter_classify.py` | Force `stale_reference` when `count_delta > 0`; fee/deposit/annual still win if those hints are set; no seventh class. |
| `tests/agents/test_consolidator.py` | `row_count` on sources remains 1 (or whatever `_build_item` still hardcodes). Do not assert 85. |
| Parser plumbing | `test_parse_file_silently_contracts_returns_counts_before_groupby` — after map+groupby preview is one row, counts still 85/82/3. `test_pnl_file_has_no_sidecar` — Status column on a GL file is dropped, no counts. |

## G. Sequencing within the item

Two PRs. Bigger than annual 12×; smaller than bank matcher.

| PR | Ships | Default behaviour if merged alone | Safe? |
|----|-------|-----------------------------------|-------|
| **PR-A** | `file_type` argument on `parse_file_silently`; contracts sidecar; `roster_counts.py`; attach hint fields on the item; **no** force-class; **no** prompt change; `row_count=1` left alone | Extra JSONB keys, classifications unchanged. Claude may ignore counts. Guardrail: if Claude does not mention 85/82/3, still passes (numbers only checked when used). | **Yes.** Additive hints. |
| **PR-B** | Interpreter force `stale_reference`; prompt template; guardrail appends the three ints; isolated 85/82/3 fixture; negatives (12×, cutoff, dollar-only) | Speech + force. Without B, counts sit unused. | Merge after A. Behaviour change is classification force + copy. |

PR-A does not change default class of any existing fixture. That is why it is safe.

## H. Rollback

- Revert PR-B first: force-class and prompt gone; leftover hint keys are ignored.
- Revert PR-A: sidecar and helper gone. No SQL DOWN. No customer rows to delete (`monthly_entries` never stored them).
- JSONB on old reports may still contain `n_active`; Pydantic defaults make them optional on read.

---

# Parked items (no implementation plan)

## Item 2 — Truck stock / van inventory

Parked because ICP 5–40 person shops typically expense van parts on purchase; a true cycle-count is a balance-sheet rollforward (`opening + receipts − consumption − adjustments = GL inventory`) that `monthly_entries`’ unique `(company_id, account_id, period)` cannot hold. Vandelay `vandelay_inventory_purchases_mar_2026.xlsx` is already `supplier_invoices` (filename contains `purchase`) — that is AP vs COGS, not on-hand qty. JSONB hints cannot represent a quantity rollforward; building it would commit the product to an inventory engine. **Revisit when** a dealer inboxes a real count-vs-GL workbook (SKU, qty, location, opening), not a purchases register.

## Item 3 — Central-station wholesale accrual

Parked because it is alarm-only, HVAC in the same wave does not have this vendor, and the honest pandas story is `active_count × rate` which **requires item 4’s counts**. Until then, today’s supplier vs GL COGS path (`missing_je` / `accrual_mismatch`) is enough when the invoice lands. A fake “if COGS is big, accrue” hint would invent wholesale. **Revisit when** a dealer inboxes a one-page central-station March bill vs roster **and** item 4 has shipped, as a named `accrual_mismatch` with pandas `count × rate` — still not a seventh class, still not a vendor-rate SQL table.

## Item 6 — WIP / professional services

Parked because professional services is the documented **second vertical**, not the ICP, and Helix `helix_project_hours_mar_2026.xlsx` is hours-as-dollars against a GL name (current consolidator), not percent-complete. A real WIP file needs job grain (`job_id`, contract value, cost-to-date, billed-to-date, `% complete`) which Discovery would drop and `groupby("account")` would destroy. Unbilled vs write-off is human collectability; a hint cannot pick it. **Revisit when** there is an explicit product decision to sell professional services, after field-service cash (item 1) and shop-scale flux (item 5) exist — then a new vertical spec, not a Kova 2 PR. Helix remaining in `docs/demo_data/` is not that trigger.

---

# Cross-cutting — item 5 vs Kova 1 expected values

Item 5 changes **flux** gates inside `calculate_variance`. It does not change recon hints, force-class, or `_is_material`.

| Kova 1 feature | Module | Calls `calculate_variance`? | Item 5 impact on expected values |
|----------------|--------|------------------------------|----------------------------------|
| Deposit / fee hints | `hint_computer.py`, `tests/tools/test_deposit_vs_fee.py`, `tests/tools/deposit_vs_fee_fixture.py` | **No** | **Unchanged.** Do not retouch. |
| Annual 12× | `hint_computer.py` `looks_like_annual_prepayment`, `tests/tools/test_annual_prepayment.py` | **No** | **Unchanged.** |
| Coverage cards | `consolidator.py` `card_kind=coverage`, interpreter skips class | **No** | **Unchanged.** |
| Cutoff allowlist | `hint_computer.py::_crosses_period_boundary`, PR #11 tests | **No** | **Unchanged.** |
| Consolidator AND-gate | `consolidator.py::_is_material` (`$500` OR (`$100` AND `>5%`)) | **No** | **Do not retune.** `tests/agents/test_consolidator.py` `(50000.0, "high")` is recon **severity**, not flux — **leave the expected 50000.** |
| Interpreter force-class | `interpreter.py::_apply_reconciliation_classifications` | **No** | **Unchanged.** |
| PAYROLL name tag | `account_tags.py` (included in item 5 if PR #5 unmerged) | **Yes**, once wired into `calculate_variance` | Comparison tests updated as in item 5 F. Uses **scaled** t2, not leftover `$10k`. New negative: ICP $5.5k miss at fail-safe `$10k`, hit at `$875`. |
| Recurrence suffix | **Not an agent.** `ComparisonAgent.run` ~167–183 and `test_recurrence_suffix_*` | **Yes** (via `run` → `calculate_variance`) | Suffix **strings unchanged**. `$360k` vs `$300k` still flags under fail-safe and every band. `_make_agent` must mock `companies_repo.get_by_id`. |
| Quarterly grouping | `quarterly.py::_group_quarterly_anomalies` | **No** (reads stored anomalies) | **Unchanged.** |

**Prompt / guardrail:** item 5 adds **zero** entries to `numbers_used` and **zero** lines to `narrative_prompt.txt`. Items 1 and 4 specify their own append lists (gross/fee/net; n_active/count_delta) for **later** PRs.

---

# What this document does not approve

- Writing `0010` or any product code until explicit go-ahead on **item 5**.
- Building item 1 or item 4 from this file until item 5 has shipped **and** a later go-ahead.
- Changing POST `/companies` idempotency (locked: PATCH only).
- A Recurrence agent module (does not exist; do not create one).
- Seventh classification, A2X, inventory engine, WIP %complete, central-station vendor-rate table.
- Un-hardcoding `row_count=1` and calling that RMR or batch count.
- Treating Vandelay Shopify payouts as three-way cash.
- Treating Vandelay purchases as a cycle count.
- Treating Helix hours as WIP.
- Retuning recon `_is_material` in the item 5 PR.
- Putting `$4,375` or any flux floor in a Claude prompt.

---

# Go-ahead gate

Implementation PRs start only when this sentence is explicit, per item:

1. **Item 5** — first and only product PR until it ships.
2. **Item 1** — spec is this document’s item 1 section; build PR-A only after item 5 + go-ahead.
3. **Item 4** — after item 1 + go-ahead.

No code from this file until then.

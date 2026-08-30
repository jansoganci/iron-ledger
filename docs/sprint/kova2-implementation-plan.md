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

**MVP boundary (locked):** one processor, one Undeposited Funds (or merchant clearing) GL account, one bank, one period. Match **batch/reference id first**; fallback is **exact cents + same calendar date (0-day window)** — not a multi-day lag. Pandas computes gross, fee, net, unmatched counts. Claude copies; never subtracts. Emit existing classes only. No A2X, no auto-JE, no multi-currency, no many-to-many splits, no connectors.

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

**Do not** add `batch_id` / `gross` / `fee` / `net` to `GoldenField` for every file (pandera `strict=True` on P&L would then require those columns). Prefer a **sidecar** typed model, used only when `file_type` is the new literals.

**There are three sidecar models, one per frame in C.5.1's table** — `ProcessorSettlementRow` (FSM / card-batch: `payout_id`, `gross`, optional `net`, `collected_date`), `GLUFDetailRow` (Undeposited-Funds detail lifted from the GL file: `gl_ref`, `gl_account`, `amount`, `gl_date`), and `BankStatementRow` (bank / processor settlement: `bank_ref`, `settlement_date`, `gross`, `fee`, `net`, `amount`). The GL sidecar was previously left unnamed here while C.5.1 already required three frames; it is named now so the document and the shipped code agree. `GLUFDetailRow` is **not** a new `SourceFileType` — the GL file stays `general_ledger`, and only rows carrying a ref **or** sitting on the UF account are sidecarred ("Do not sidecar Rent").

**Modify `ReconciliationItem` (JSONB, no migration):** optional nested `matches: list[BatchMatch] | None = None` so several batches on one UF line can be classified without a seventh class. Do not invent a seventh enum.

**DECIDED (gap E.6 — resolved 30 August 2026).** The earlier "classify by match id **or** nest class on each match" fork is closed in favour of **nesting**. The rule:

1. `NarrativeJSON.reconciliation_classifications` **stays exactly `dict[account → ReconciliationClassification]`. No JSON shape change, no new key, no match ids in Claude's output.**
2. Per-batch classes live on `BatchMatch.classification`, set by **pandas** in `_classify` and forced by the interpreter. Claude never writes them.
3. The account-level `ReconciliationItem.classification` is the **residue**: pandas picks the most action-requiring class among that account's matches, using this fixed order (first present wins):

   `missing_je` → `categorical_misclassification` → `stale_reference` → `timing_cutoff` → `structural_explained`

   Rationale: action-required beats no-action. A card must never read "No action required" (`structural_explained` / `timing_cutoff`) while a batch nested under it needs a JE or a reclass.

**Why nesting, not match-id keying.** Keying `reconciliation_classifications` by `match_id` would require Claude to emit pandas-constructed opaque identifiers it cannot verify; one typo becomes an unmatched key and a silently dropped classification. Nesting leaves Claude's output shape untouched, keeps every per-batch class pandas-forced (golden rule), and is backward compatible — old clients that ignore unknown keys keep working, and reports without `matches` behave exactly as today.

Exact shape to freeze at build time:

```python
class BatchMatch(BaseModel):
    match_id: str
    processor_ref: str | None
    bank_ref: str | None
    gl_ref: str | None
    gl_account: str | None
    gl_amount: float | None   # UF (or wrong-account) line; None if no GL row
    gross: float
    fee: float
    net: float
    settlement_date: date | None
    match_kind: Literal["id", "amount_date", "none"]
    ambiguous: bool
    candidate_count: int
    unmatched: bool
    classification: ReconciliationClassification | None = None
```

Numbers are pandas. Claude copies `gross` / `fee` / `net` / `gl_amount` / `candidate_count`. Never subtracts. Never counts candidates in prose. `fee_pct` is an internal pandas gate only — **not** a prompt placeholder (no “4.5%” in the sentence).

**DECIDED (gap E.1 — resolved 30 August 2026): `fee_pct` is NOT a field on `BatchMatch`.**

The model above is final as written — no `fee_pct` field, private or otherwise. `_classify` computes it inline from `gross` and `fee`, both of which are already on the model:

```python
def _fee_pct(gross: float, fee: float) -> float | None:
    """Internal pandas gate for the 3–8% band. Never stored, never serialized,
    never a prompt placeholder. Returns None when gross is 0."""
    if gross == 0:
        return None
    return abs(fee) / abs(gross)
```

`_classify` calls it once: `fee_pct = _fee_pct(m.gross, m.fee)`.

**Why inline rather than `PrivateAttr` / `exclude=True`.** A derived gate is not state. Computing it inline means there is **no serialization path at all**, so the Claude-facing exclusion is enforced structurally rather than by Pydantic configuration that a later `model_dump(mode=...)` change could quietly defeat. It also leaves the frozen model byte-identical, so PR-A ships the shape above unchanged. `PrivateAttr` would work but adds a field that must be set at construction and re-audited on every serializer change; the exclusion rule is too important to hang on config.

**DECIDED (gap E.4 — resolved 30 August 2026): `match_id` construction.**

`match_id` is required and must be **deterministic** — the same three input files must always produce the same ids, since C.8 may key per-batch speech off them. Construction by `match_kind`:

| `match_kind` | `match_id` |
|---|---|
| `"id"` (Pass 1, unique **or** ambiguous) | `norm(id_val)` — the normalized join id, i.e. `str(id).strip().casefold()`. Example: `PZ-100` → `pz-100`. |
| `"amount_date"` (Pass 2, unique **or** ambiguous) | `f"ad:{amount:.2f}:{day.isoformat()}"` from the **group key**, not from any member row. Example: the blank-ref `$100` pair → `ad:100.00:2026-03-25`. |
| `"none"` (Pass 3 leftover) | `f"none:{side}:{norm(ref)}"` when the leftover row has a non-null ref (`side` ∈ `fsm` \| `bank`). Example: DEP-99 → `none:bank:dep-99`. When the ref is null: `f"none:{side}:{amount:.2f}:{day.isoformat()}:{seq}"`, where `seq` is the row's 0-based ordinal among leftovers on the **same side** sharing that amount and date, assigned in ascending `_orig_row_index` order. |

**Uniqueness.** Pass 1 emits exactly one match per `id_val`; Pass 2 emits exactly one match per `(amount, date)` group (unique **or** ambiguous branch, never both); Pass 3 emits one per leftover row. The `ad:` and `none:` prefixes make cross-kind collision impossible, and a Pass-1 id can never reappear as a Pass-3 ref because an id living on ≥2 sides is consumed in Pass 1 while an id on exactly one side is never emitted there.

**Stability across re-runs.** Every input to the construction is derived from file content — the normalized id, the rounded amount, the calendar date — except `seq`, which is derived from `_orig_row_index` (row order within the uploaded file). For identical input files all four are identical, so `match_id` is stable. Do **not** use a UUID, a hash of object identity, an insertion counter, or anything derived from dict/set iteration order.

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

**Responsibility:** deterministic pandas matcher. No Claude. No DB. No WRatio. No amount “close enough.”

**Input:** three sidecar frames + `period: date` + `uf_account_name: str` (the company’s single Undeposited Funds / merchant-clearing GL name for this MVP).
**Output:** `list[BatchMatch]`, plus `unmatched_processor_count: int`, `unmatched_bank_count: int`.
**Called from:** orchestrator, **after** parse, **beside** consolidator — consolidator must **not** become the matcher.
**Does not:** post JEs, call A2X, fuzzy-match GL account names, write `monthly_entries`, invent a seventh class, call the LLM.

The earlier one-line “±1 business day” fallback is **withdrawn**. It was not backed by the research docs. v1 fallback is **same calendar date and exact cents only**. See C.5.1 assumptions.

#### C.5.1 Exact matching algorithm (pandas pseudocode)

**Canonical sidecar columns after Discovery mapping** (not `GoldenField`; not SQL). Header names on disk vary; Discovery maps onto these:

| Frame | Join id | Amount components | Date |
|-------|---------|-------------------|------|
| FSM / card-batch (`processor_settlement`) | `payout_id` | `gross` required; `net` optional | `collected_date` |
| GL UF-detail sidecar (from the GL file, not the whole P&L) | `gl_ref` | `amount` | `gl_date` |
| Bank / processor settlement (`bank_statement`) | `bank_ref` | `gross`, `fee`, `net` when the export has them; otherwise `amount` is **net** | `settlement_date` |

MVP file roles (locked, three files only):

1. FSM/job card-batch export → `payout_id`, `gross`, `collected_date`.
2. GL with Undeposited Funds **line detail** → `gl_ref`, `gl_account`, `amount`, `gl_date`. Sidecar only rows that have a ref **or** whose `gl_account` equals `uf_account_name`. Do not sidecar Rent.
3. Bank **or** processor payout CSV → `bank_ref`, `settlement_date`, `net` (and `gross`/`fee` when present). One processor, one bank.

**Join-key hierarchy**

```
norm(id) := None if id is null/blank else str(id).strip().casefold()
```

| Side | Field that feeds `norm` |
|------|-------------------------|
| FSM / processor | `payout_id` |
| GL | `gl_ref` (memo / Check No. / payout id booked on the UF line) |
| Bank | `bank_ref` (payout id or bank reference). On a Stripe-style payout export this **is** the payout id. |

A three-way **ID match** is `norm(payout_id) == norm(gl_ref) == norm(bank_ref)` and that value is not `None`.

**When one side has an id and another does not:**

- Do **not** invent an id. Do **not** match that pair on ID.
- That pair may still match in the amount+date fallback **only if both rows are still unmatched after the ID pass**.
- Example: FSM `payout_id=PZ-100`, GL `gl_ref` blank, bank `bank_ref=PZ-100` → ID-match FSM↔bank on `pz-100`; GL is not in that ID triple. GL may join the same bank row later only via amount+date, and only if that join is unique.

**Assumptions (not in the research docs — do not present as derived):**

| Knob | v1 lock | What the docs actually say |
|------|---------|----------------------------|
| Date window | **0 days** — `settlement_date.date() == collected_date.date() == gl_date.date()` | Field-service research: practitioners reconcile cash **daily**; month-end is residue (unbooked fees, **straddling** batches, undeposited ≠ 0). **No day-count** (no T+1, T+2, “2 business days”). E-commerce Amazon “14-day settlement” in `close-process-by-sector.md` is a **different vertical** — do not import it. |
| Dollar tolerance | **$0.00** after `round(..., 2)` | No cent-slack in the research. Card nets are exact. |
| Fee band for “fee explained” | reuse Kova 1 `_FEE_BAND_MIN/_MAX` = **3%–8% of gross** (`hint_computer.py`) | Already shipped. Do not invent Jobber 2.9% (triage forbade unverified vendor rates in prompts). |
| ±1 business day | **out of v1** | Was a leftover sentence in this spec. Withdrawn because no research number backs it. Revisit only if a real dealer file shows same-id or same-net pairs that miss same-calendar-date; that is a new go-ahead, not a silent widen. |

**Pandas amounts (always, never Claude).**

**DECIDED (gap E.2 — resolved 30 August 2026).** The earlier two-branch snippet was undefined for a match with no bank/settlement row, which Pass 2 can reach (FSM↔GL on the same amount and date). Three readings were possible — `net := gross`, `net := None`, `net := 0.0` — producing a dropped card, a `TypeError`, and a spurious 100%-fee card respectively. The rules below are exhaustive and ordered. Apply **N1 → N2 → N3**, in that order, for every match regardless of pass.

**N1 — `net`** (cash that actually landed):

1. Settlement/bank row in the match **and** it has `net` → that value.
2. Settlement/bank row in the match, no `net`, has `amount` → that amount. Per the frame table above, a bank `amount` **is** net.
3. **No settlement/bank row in the match → `net := gross`** (from N2).

**N2 — `gross`** (amount collected before deductions):

1. Settlement/bank row in the match **and** it has `gross` → that value.
2. Else FSM row in the match → FSM `gross`.
3. Else → `gross := net`.

**N3 — `fee`**: `fee = round(gross - net, 2)`. Always. Never from a vendor `fee` column.

All three round to 2dp with `round(float(x), 2)` before use.

**Terminal case (N1.3 and N2.3 both firing).** Only reachable for an **ambiguous group with no FSM and no settlement row** — e.g. two GL rows sharing an amount and date, which Pass 2 marks ambiguous. Set `gross = net = fee = 0.00`. `_classify` returns at the `ambiguous` rule before any amount is read, so these values are never surfaced. A GL-only *leftover* never reaches here at all — Pass 3 leaves unused GL UF lines to coverage/consolidator.

**Ambiguous matches do not borrow amounts from a member row.** When `ambiguous=True`, picking one row's amount would be the silent pick rule (c) forbids. For a Pass-2 ambiguous group, `gross = net = the group's amount key` and `fee = 0.00` — this is what lets the fixture's blank-ref sentence copy `100.00`. For a Pass-1 ambiguous group (same id on more than one row on a side), `gross = net = fee = 0.00`; the narrative may copy only `candidate_count` and the id.

**Why `net := gross` and not `0.0` when there is no bank row.** With no settlement row in the match there is no evidence of any deduction. `net := gross` states "no fee observed"; `net := 0.0` would assert that the entire collection was consumed by fees, producing `fee_pct = 1.0`, falling past the 3–8% band to the residue rule, and emitting a spurious `stale_reference` card for what is actually a clean FSM↔GL pair. Verified against the true-negative path: a clean FSM↔GL match booked to the UF account gets `fee = 0.00` and `gl_amount == net`, so `_classify` rule 6 drops it — **no card** — exactly as PZ-900 does with a bank row present.

If the settlement file also has a `fee` column, **ignore it for the match decision**. Guardrail-safe number is pandas `gross - net`. (A disagreeing fee column is a file-quality issue, not a second match key.)

**DECIDED (gap E.3 — resolved 30 August 2026): `settlement_date` precedence.**

**S1.** `BatchMatch.settlement_date` is populated **only** from the bank/processor settlement row's `settlement_date`. FSM `collected_date` and GL `gl_date` are **never** used, at any precedence, even when the settlement row is absent.

**S2.** No settlement/bank row in the match → `settlement_date = None`.

**S3.** There is never a within-side conflict to resolve on a **non-ambiguous** match: it holds at most one row per side (Pass 1 routes `len(rows) > 1` to the ambiguous branch before emit; Pass 2's unique branch requires `nf ≤ 1 and ng ≤ 1 and nb ≤ 1`). So "precedence" is a single-source rule, not a tie-break.

**S4 — ambiguous matches.** An ambiguous group may hold several settlement rows, and picking one would be the silent pick rule (c) forbids. Therefore:

- **Pass 2 ambiguous** (grouped by `(amount, date)`): `settlement_date = the group's date key`. Every member shares that date by construction, so no row is being preferred. This is what populates `2026-03-25` on the fixture's blank-ref card.
- **Pass 1 ambiguous** (same id on more than one row on a side): `settlement_date = None`. Members may carry different dates and there is no key to fall back on.

Either way rule 1 classifies the match `stale_reference` before the cutoff rule is reached, so `settlement_date` on an ambiguous match is display context only — never a classification input.

**Why only the settlement row.** `timing_cutoff` asserts that *the payout settled after the period closed*. Only the settlement row records a settlement event. PZ-200 is the case that forces this: FSM `2026-03-31` and GL `2026-03-31` are both inside the period, and only the bank row's `2026-04-02` is outside it. Sourcing the date from FSM or GL would classify PZ-200 as a fee, and the state table would be wrong.

**Consequence — a no-bank match can never be `timing_cutoff`.** Because the cutoff rule is guarded by `settlement_date is not None`, an FSM↔GL match is ineligible for `timing_cutoff` no matter how late its FSM or GL dates are. **This is intentional.** With no settlement row there is no evidence the money ever moved, so the honest classes are "not in the GL" (`missing_je`), "booked to the wrong account" (`categorical_misclassification`), or residue (`stale_reference`). A late FSM collection with no payout is a missing-payout story, not a cut-off; calling it `timing_cutoff` would assert a settlement event the uploaded files do not show, and would tell the user "expect this to clear next month" about money that may never have settled.

**Classification priority** (`_classify`, pandas, then interpreter force). First matching rule wins.

**CORRECTED (nit E.7 — resolved 30 August 2026).** Earlier prose in and around this document summarised the order as "cutoff → missing GL → wrong UF → fee → `$0` drop → stale". That omitted the **ambiguous** check, which runs **first, above cutoff**. The complete and authoritative order is:

| # | Rule | Result |
|---|---|---|
| 1 | `m.ambiguous` | `stale_reference`, `unmatched=True` |
| 2 | `settlement_date is not None and settlement_date > period_end` | `timing_cutoff` |
| 3 | `not has_gl` | `missing_je`, `unmatched=True` |
| 4 | `gl_account != uf_account_name` | `categorical_misclassification` |
| 5 | `fee_pct` in `[0.03, 0.08]` | `structural_explained` |
| 6 | `fee == 0 and gl_amount is not None and round(gl_amount,2) == round(net,2)` | **drop — no card** |
| 7 | otherwise | `stale_reference` (matched residue outside the fee band) |

**Ambiguous outranks cutoff deliberately.** You cannot assert that a *specific* batch settled after `period_end` when you have refused to identify which row that batch is. Rule 1 is a statement about our confidence, not about the money; every later rule presumes a single identified counterpart. Do not "restore" cutoff to the top.

**Do not apply the 3–8% fee band unless a GL row is in the match** — otherwise PZ-300 (`fee_pct = 0.04`, no GL) would be labelled `structural_explained` and the state table would be a lie. This is why rule 3 sits above rule 5.

```
def _classify(m, period_end, uf_account_name) -> BatchMatch | None:
    has_gl = m.gl_account is not None or m.gl_ref is not None or m.gl_amount is not None
    fee_pct = _fee_pct(m.gross, m.fee)   # E.1: computed here, never a model field

    if m.ambiguous:
        m.classification = stale_reference          # (c)
        m.unmatched = True
        return m

    # Cutoff beats fee AND beats missing-GL. A payout that settled after
    # period_end is month-end residue even if the GL line is absent.
    if m.settlement_date is not None and m.settlement_date > period_end:
        m.classification = timing_cutoff            # state 2
        return m

    if not has_gl:
        m.classification = missing_je               # states 3 and 4
        m.unmatched = True
        return m

    if m.gl_account != uf_account_name:
        m.classification = categorical_misclassification  # state 5
        return m

    if fee_pct is not None and 0.03 <= fee_pct <= 0.08:
        m.classification = structural_explained     # state 1
        return m

    if m.fee == 0 and m.gl_amount is not None and round(m.gl_amount, 2) == round(m.net, 2):
        return None                                 # true negative: drop, no card

    m.classification = stale_reference              # matched residue outside the fee band
    return m
```

Unmatched after both passes (Pass 3 leftovers call `_classify` with `match_kind="none"`, `has_gl=False` → `missing_je`):

- Processor/FSM row with no GL and no unique bank ID/fallback → `missing_je` (`unmatched_processor`).
- Bank row with no GL and no unique FSM ID/fallback → `missing_je` (`unmatched_bank`).
- Ambiguous (rule c below) → `stale_reference`, `ambiguous=True`, `unmatched=True`. **Not** `missing_je` (the money is on more than one row; we refused to pick).

**Fallback never explains fees — and the reason is the `$0.00` tolerance, not the choice of column.**

**CORRECTED (nit E.5 — resolved 30 August 2026).** Earlier prose here claimed Pass 2 "compares **net to net**, never FSM `gross` to bank `net`." That is not what the pseudocode does. FSM `net` is *optional* (see the frame table above) and the C.5.3 fixture's FSM file has **no `net` column at all**, so in the canonical case the grouping key takes `fsm.net if present else fsm.gross` — an FSM **gross** — and compares it against a bank **net**. Gross and net share one key space.

The guarantee still holds, for a different reason. Grouping requires **exact equality after `round(..., 2)`** — the `$0.00` dollar tolerance locked in the assumptions table. A gross and a net can only land in the same group when `fee == 0`, which is a genuine match, not a fee in disguise. Any batch carrying a real fee has `gross ≠ net`, so the two values fall into different groups and never meet.

Worked through: a PZ-100-shaped batch with ids stripped (`1000.00` FSM/GL vs `955.00` bank, same date) does **not** become `structural_explained`. It ID-fails, then fsm↔gl groups uniquely on `1000.00` (no bank row → N1.3 gives `net := gross`, `fee = 0.00`, dropped by rule 6 if booked to UF), and the leftover bank `955.00` goes to Pass 3 → `missing_je` by rule 3, since `has_gl` is false there. The bank row's own `fee_pct` of `0.045` is never reached.

**The tolerance lock and this guarantee are the same lock.** Widening the dollar tolerance into fee territory would let a gross and a net group together *while a fee exists*, which is precisely how a real exception becomes a false "no action required." Do not treat them as two independent decisions, and do not "fix" a missed match by relaxing the tolerance.

Fee speech requires either (1) an **ID** triple/pair that includes the settlement row’s gross and net, or (2) the Kova 1 **account-total** 3–8% hint when no settlement sidecar exists.

**Pseudocode (literal build order for `batch_matcher.match`):**

```
def match(fsm_df, gl_df, bank_df, period, uf_account_name) -> list[BatchMatch]:
    period_end = last_day_of(period)   # pandas; March 2026 → 2026-03-31

    fsm  = _norm_ids(fsm_df,  id_col="payout_id")
    gl   = _norm_ids(gl_df,   id_col="gl_ref")
    bank = _norm_ids(bank_df, id_col="bank_ref")

    used_fsm, used_gl, used_bank = empty sets of row indices
    matches = []

    # ---- Pass 1: exact ID, 1:1 only ---------------------------------
    for id_val in unique_non_null(concat(fsm.id, gl.id, bank.id)):
        f_rows = fsm[fsm.id == id_val]
        g_rows = gl[gl.id == id_val]
        b_rows = bank[bank.id == id_val]
        # (c) ambiguous ID: more than one row on any side
        if len(f_rows) > 1 or len(g_rows) > 1 or len(b_rows) > 1:
            matches.append(_ambiguous_group(id_val, f_rows, g_rows, b_rows))
            mark all those indices used
            continue
        if len(f_rows) + len(g_rows) + len(b_rows) < 2:
            continue   # id lives on only one side; leave for fallback / unmatched
        # (a) exact unique ID match across the sides that have it
        matches.append(_emit(f_rows, g_rows, b_rows, match_kind="id"))
        mark those indices used

    # ---- Pass 2: fallback exact net + same calendar date ------------
    # Only unused rows. Dollar: round to 2dp equality. Date: equality, 0-day window.
    # NET never GROSS: fsm.net if present else fsm.gross; gl.amount;
    #                  bank.net if present else bank.amount.
    leftover_f = fsm[~used_fsm]
    leftover_g = gl[~used_gl]
    leftover_b = bank[~used_bank]

    # Group leftover rows by (round(net, 2), calendar_date). Looping
    # per bank row would split two $100 blanks into one stale_reference
    # plus a leftover missing_je — the fixture requires ONE card.
    for (amt, day), grp in leftover grouped by (net, date):
        nf, ng, nb = counts of fsm/gl/bank in grp
        if nf + ng + nb < 2:
            continue
        unique = (nf <= 1 and ng <= 1 and nb <= 1)
        if unique:
            # (b) at most one row per side
            matches.append(_emit(grp, match_kind="amount_date"))
            mark grp used
        else:
            # (c) do NOT pick first / largest / closest
            matches.append(_ambiguous_amount_date(
                grp,
                candidate_count=max(nf, ng, nb),   # fixture blanks: 2
                match_kind="amount_date",
            ))
            mark ALL rows in grp used

    # No second fsm↔gl pass: no-bank pairs are already in the same groups (nb=0).

    # ---- Pass 3: leftovers ------------------------------------------
    for row in fsm still unused:   # (d)
        matches.append(_unmatched_processor(row))   # missing_je via _classify
    for row in bank still unused:  # (d)
        matches.append(_unmatched_bank(row))        # missing_je via _classify
    # unused GL-only UF lines are coverage/consolidator territory, not this matcher.

    out = []
    for m in matches:
        classified = _classify(m, period_end, uf_account_name)
        if classified is not None:          # PZ-900 dropped here
            out.append(classified)
    return out
```

**(a) Exact match found:** `match_kind="id"`, `ambiguous=False`, `candidate_count=1`, `unmatched=False`. Then apply classification priority.

**(b) Fallback match found:** `match_kind="amount_date"`, same uniqueness. Then the same classification priority. No LLM. No WRatio. No “closest amount.”

**(c) Multiple candidates (ambiguous):** `ambiguous=True`, `candidate_count=max(nf, ng, nb)` (pandas `int`; fixture blanks = 2, not 4), `match_kind` is `"id"` or `"amount_date"`, `unmatched=True`, class `stale_reference`. **Never silently pick** the first / largest / closest row. A wrong silent pick would label a real miss as a fee.

**(d) No match:** `match_kind="none"`, `unmatched=True`, class `missing_je` for leftover FSM or leftover bank.

Every branch above is pandas/Python. Claude is not called inside `batch_matcher.py`.

#### C.5.2 Worked examples — five states + true negative

Period `2026-03-01`. `period_end = 2026-03-31`. `uf_account_name = "Undeposited Funds"`. All dollars below are fixture literals; `fee` and `fee_pct` are pandas.

**State 1 — Gross vs net, fee explained → `structural_explained`**

| Side | Id | Gross | Fee | Net | Date | GL account |
|------|----|------:|----:|----:|------|------------|
| FSM | PZ-100 | 1000.00 | — | — | 2026-03-15 | — |
| GL | PZ-100 | — | — | 1000.00 | 2026-03-15 | Undeposited Funds |
| Bank | PZ-100 | 1000.00 | — | 955.00 | 2026-03-15 | — |

- Pass 1: ID `pz-100` unique on all three → (a).
- Pandas: `fee = 1000.00 - 955.00 = 45.00`; `fee_pct = 0.045` ∈ [0.03, 0.08].
- Date 2026-03-15 ≤ period_end. GL account is UF. `_classify`: not cutoff, `has_gl`, account is UF, then fee band.
- Class: `structural_explained`.
- Guardrail-safe sentence (copy only; never subtract):
  `"Undeposited Funds shows a 45.00 difference between sources. Gross is 1000.00 and the net payout is 955.00. This is structurally explained by processor or platform fees deducted before the net payout landed. This is not a missing journal entry, not a customer deposit, and not unearned revenue. No action required."`

**State 2 — Payout dated after period_end → `timing_cutoff`**

| Side | Id | Gross | Net | Date | GL account |
|------|----|------:|----:|------|------------|
| FSM | PZ-200 | 2000.00 | — | 2026-03-31 | — |
| GL | PZ-200 | — | 2000.00 | 2026-03-31 | Undeposited Funds |
| Bank | PZ-200 | 2000.00 | 1920.00 | **2026-04-02** | — |

- Pass 1: ID `pz-200` unique → (a).
- Pandas: `fee = 80.00`; `fee_pct = 0.04` (would be a fee **if** cutoff did not win).
- `_classify`: `2026-04-02 > 2026-03-31` → **cutoff wins** (before `has_gl` and before the fee band).
- Class: `timing_cutoff`.
- Guardrail-safe sentence:
  `"Undeposited Funds shows a 80.00 difference between sources. Gross is 2000.00 and the net payout is 1920.00. The payout date is 2026-04-02, after the period closed on 2026-03-31. This appears to be a timing cut-off. No action required — expect this to clear next month."`

**State 3 — Processor batch not in GL → `missing_je`**

| Side | Id | Gross | Net | Date | GL account |
|------|----|------:|----:|------|------------|
| FSM | PZ-300 | 500.00 | — | 2026-03-20 | — |
| GL | — | — | — | — | **no row** |
| Bank | PZ-300 | 500.00 | 480.00 | 2026-03-20 | — |

- Pass 1: ID `pz-300` on FSM+bank only (two sides, unique) → (a) two-way, GL missing.
- Pandas: `fee = 20.00`; `fee_pct = 0.04` ∈ [0.03, 0.08] — **ignored**. `_classify` hits `not has_gl` before the fee band. Two-way with no GL is **not** a fee story.
- Class: `missing_je`. `unmatched` relative to GL = true. Pandas still stores gross 500.00, net 480.00, fee 20.00 so Claude may copy them; the speech is missing JE, not fee.
- Guardrail-safe sentence:
  `"Undeposited Funds shows 500.00 in the card-batch file with no matching entry in the GL. A journal entry may be missing. Recommended action: verify whether this transaction has been posted and enter the missing JE if not."`

**State 4 — Bank deposit not in GL / UF → `missing_je`**

| Side | Id | Amount | Date |
|------|----|-------:|------|
| FSM | — | — | **no row** |
| GL | — | — | **no row** |
| Bank | DEP-99 | 750.00 | 2026-03-22 |

- Pass 1: id `dep-99` lives on one side only → skip.
- Pass 2: no FSM/GL leftover with net 750.00 on 2026-03-22 → (d).
- Class: `missing_je`. `unmatched_bank_count` includes this row.
- Guardrail-safe sentence:
  `"The bank file shows 750.00 with no matching entry in the GL. A journal entry may be missing. Recommended action: verify whether this deposit has been posted and enter the missing JE if not."`

**State 5 — Posted to the wrong clearing account → `categorical_misclassification`**

| Side | Id | Gross | Net | Date | GL account |
|------|----|------:|----:|------|------------|
| FSM | PZ-500 | 600.00 | — | 2026-03-18 | — |
| GL | PZ-500 | — | 600.00 | 2026-03-18 | **Accounts Receivable** |
| Bank | PZ-500 | 600.00 | 600.00 | 2026-03-18 | — |

- Pass 1: ID `pz-500` unique → (a).
- Pandas: `fee = 0.00`. Date in period. `_classify`: `has_gl`, then `Accounts Receivable != Undeposited Funds`.
- Class: `categorical_misclassification`.
- Guardrail-safe sentence:
  `"Undeposited Funds shows a 0.00 fee and a 600.00 payout. The GL booked 600.00 under Accounts Receivable. The GL appears to have booked this amount under a different category. Recommended action: review the GL coding and reclassify to align with Undeposited Funds."`

**True negative — clean three-way, no card**

| Side | Id | Gross | Net | Date | GL account |
|------|----|------:|----:|------|------------|
| FSM | PZ-900 | 300.00 | — | 2026-03-10 | — |
| GL | PZ-900 | — | 300.00 | 2026-03-10 | Undeposited Funds |
| Bank | PZ-900 | 300.00 | 300.00 | 2026-03-10 | — |

- Pass 1: ID match. Pandas `fee = 0.00`. GL amount == net. Rule 4 → **drop**. Not in `matches` that become exception cards. Consolidator `_is_material` would also drop a $0 UF delta. Acceptance: zero cards for `PZ-900`.

**Ambiguous fallback (not a sixth class — extra fixture rows):** two bank deposits of `100.00` on `2026-03-25` with **blank** `bank_ref`, two FSM rows of `100.00` the same day with blank `payout_id`. Pass 2 sees `len(cand_f) > 1` → (c) `stale_reference`, `candidate_count=2`, do not pick. Sentence copies `100.00` and `2` (the pandas count), never “about two.”

#### C.5.3 Isolated three-file fixture (acceptance spec for PR-B)

**Self-contained.** No Sentinel files, no Vandelay Shopify/Amazon payouts, no DRONE P&L. Filenames must **not** be wired in PR-A (`_detect_file_type` stays supplier-default until PR-B). Suggested names for PR-B:

- `tests/tools/fixtures/kova_cash_fsm_mar_2026.csv`
- `tests/tools/fixtures/kova_cash_gl_mar_2026.csv`
- `tests/tools/fixtures/kova_cash_bank_mar_2026.csv`

`period = 2026-03-01`. Company UF name in the test harness: `"Undeposited Funds"`.

**File 1 — FSM / job card-batch** (`processor_settlement` once PR-B wires types)

| payout_id | collected_date | gross | customer |
|-----------|----------------|------:|----------|
| PZ-100 | 2026-03-15 | 1000.00 | Oak Street Dental |
| PZ-200 | 2026-03-31 | 2000.00 | Harbor HVAC |
| PZ-300 | 2026-03-20 | 500.00 | Mill Road Alarm |
| PZ-500 | 2026-03-18 | 600.00 | Pine Ridge |
| PZ-900 | 2026-03-10 | 300.00 | True Negative LLC |
| | 2026-03-25 | 100.00 | Ambiguous A |
| | 2026-03-25 | 100.00 | Ambiguous B |

`customer` is dropped by the normalizer (not a GoldenField). Sidecar keeps `payout_id`, `collected_date`, `gross` **before** that drop.

**File 2 — GL with UF detail** (`general_ledger`)

| date | account | amount | memo |
|------|---------|-------:|------|
| 2026-03-15 | Undeposited Funds | 1000.00 | PZ-100 |
| 2026-03-31 | Undeposited Funds | 2000.00 | PZ-200 |
| 2026-03-18 | Accounts Receivable | 600.00 | PZ-500 |
| 2026-03-10 | Undeposited Funds | 300.00 | PZ-900 |
| 2026-03-01 | Service Revenue | 3540.00 | |
| 2026-03-01 | Rent | 3200.00 | |

`memo` → sidecar `gl_ref`. Rent / Service Revenue have no ref and are not UF → **not** matcher inputs. There is **no** GL row for PZ-300 and **no** GL row for DEP-99.

**File 3 — Bank / processor settlement** (`bank_statement` once PR-B wires types)

| bank_ref | settlement_date | gross | net |
|----------|-----------------|------:|----:|
| PZ-100 | 2026-03-15 | 1000.00 | 955.00 |
| PZ-200 | 2026-04-02 | 2000.00 | 1920.00 |
| PZ-300 | 2026-03-20 | 500.00 | 480.00 |
| DEP-99 | 2026-03-22 | 750.00 | 750.00 |
| PZ-500 | 2026-03-18 | 600.00 | 600.00 |
| PZ-900 | 2026-03-10 | 300.00 | 300.00 |
| | 2026-03-25 | 100.00 | 100.00 |
| | 2026-03-25 | 100.00 | 100.00 |

No `fee` column on purpose: pandas `fee = gross - net`.

**Expected matcher output (PR-B acceptance — pin these):**

| match_id / refs | match_kind | fee (pandas) | settlement_date | gl_account | class | card? |
|-----------------|------------|-------------:|-----------------|------------|-------|-------|
| PZ-100 | id | 45.00 | 2026-03-15 | Undeposited Funds | `structural_explained` | yes |
| PZ-200 | id | 80.00 | 2026-04-02 | Undeposited Funds | `timing_cutoff` | yes |
| PZ-300 | id (FSM+bank, no GL) | 20.00 | 2026-03-20 | None | `missing_je` | yes |
| DEP-99 | none | 0.00 | 2026-03-22 | None | `missing_je` | yes |
| PZ-500 | id | 0.00 | 2026-03-18 | Accounts Receivable | `categorical_misclassification` | yes |
| PZ-900 | id | 0.00 | 2026-03-10 | Undeposited Funds | — | **no** |
| two blank $100 on 2026-03-25 | amount_date | 0.00 | 2026-03-25 | — | `stale_reference` (`ambiguous=True`, `candidate_count=2`) | yes |

`unmatched_processor_count = 0` after ID/fallback (ambiguous FSM rows are consumed as ambiguous, not as unmatched-processor). `unmatched_bank_count = 1` (DEP-99) plus the ambiguous bank pair counted as ambiguous, not unmatched.

**Re-verification after gaps E.1–E.7 were closed (30 August 2026).** Every expected outcome above was re-traced against the new N/S rules and the corrected priority table. **All seven are unchanged** — these were fixes to unstated rules, not changes to intended behaviour. The added column is the `match_id` now produced by the E.4 rule.

| Fixture id | Path | `gross` / `net` / `fee` (N rules) | `settlement_date` (S rules) | Deciding rule | Class | Card? | `match_id` |
|---|---|---|---|---|---|---|---|
| PZ-100 | Pass 1 id, 3 sides | N1.1/N2.1 → 1000.00 / 955.00 / 45.00 | S1 → 2026-03-15 | 5 (`fee_pct` 0.045 in band) | `structural_explained` | yes | `pz-100` |
| PZ-200 | Pass 1 id, 3 sides | N1.1/N2.1 → 2000.00 / 1920.00 / 80.00 | S1 → **2026-04-02** (bank only) | 2 (cutoff, above fee) | `timing_cutoff` | yes | `pz-200` |
| PZ-300 | Pass 1 id, FSM+bank | N1.1/N2.1 → 500.00 / 480.00 / 20.00 | S1 → 2026-03-20 | 3 (`not has_gl`, above fee) | `missing_je` | yes | `pz-300` |
| DEP-99 | Pass 3 leftover bank | N1.1/N2.1 → 750.00 / 750.00 / 0.00 | S1 → 2026-03-22 | 3 (`not has_gl`) | `missing_je` | yes | `none:bank:dep-99` |
| PZ-500 | Pass 1 id, 3 sides | N1.1/N2.1 → 600.00 / 600.00 / 0.00 | S1 → 2026-03-18 | 4 (wrong account, **above** rule 6's drop) | `categorical_misclassification` | yes | `pz-500` |
| PZ-900 | Pass 1 id, 3 sides | N1.1/N2.1 → 300.00 / 300.00 / 0.00 | S1 → 2026-03-10 | 6 (`fee == 0`, `gl_amount == net`) | — | **no** | `pz-900` |
| blank ×2 | Pass 2 ambiguous | ambiguous → 100.00 / 100.00 / 0.00 (group key) | S4 → 2026-03-25 (group key) | 1 (ambiguous, above cutoff) | `stale_reference` | yes | `ad:100.00:2026-03-25` |

Two rule interactions worth pinning in the PR-B tests, both load-bearing and neither obvious:

- **PZ-500 survives only because rule 4 outranks rule 6.** It has `fee == 0.00` and `gl_amount == net`, which is rule 6's drop condition verbatim. Rule 4 fires first because the GL booked it to `Accounts Receivable`, not the UF account. If the order were ever reversed, a wrong-account batch would silently vanish instead of raising `categorical_misclassification`.
- **The blank-ref pair yields `candidate_count = 2`, not 4.** `max(nf, ng, nb) = max(2, 0, 2)`. Counting group members instead of per-side maxima gives 4 and the narrative would overstate the ambiguity.

Also re-verified: `test_does_not_match_on_gross_against_net` (PR-B, section F). With ids stripped, FSM/GL group uniquely on `1000.00` with **no bank row** → N1.3 sets `net := gross`, `fee = 0.00`, and rule 6 drops the card; the bank `955.00` falls to Pass 3 and hits rule 3 (`not has_gl`) → `missing_je`. The bank row's own `fee_pct` of 0.045 is never reached, so no `structural_explained` appears. Unchanged from the original intent.

**Negatives (not in this fixture, still required in PR-B tests):** Vandelay Shopify payouts without a bank file → matcher does not claim three-way. Sentinel Bank Charges $95 is not this item.

**Prompt placeholders Claude may copy from a `BatchMatch`:** `gross`, `fee`, `net`, `gl_amount`, `settlement_date`, `period_end` (already known), `candidate_count`. **Forbidden in the prompt:** “subtract,” “4.5%,” “about 2,” any Jobber/Stripe rate. `fee_pct` is pandas-internal for `_classify` only — do not serialize it onto the item that Claude sees.

### C.6 `backend/agents/consolidator.py`

**Not the matcher.** `_build_item` continues to emit account-total cards. `ReconciliationSource.row_count = 1` (~275) stays for this item (item 4 owns that lie). Matcher cards are a **separate** list merged into `parse_preview.reconciliations` JSONB, or nested under the UF account item. Do not un-hardcode `row_count` here and call it batch count.

`_is_material` unchanged (item 5 already forbade retuning it).

### C.7 `backend/tools/hint_computer.py`

Account-total `is_processor_fee_gap` remains the fallback when no settlement sidecar exists. Matcher results **must not** also fire the 3–8% account-total hint on the same card if three-way already explained the fee (double speech). Priority at interpreter: three-way match class wins over `is_processor_fee_gap` when `matches` is non-empty.

Do not scan P&L for `batch_id`.

### C.8 `backend/agents/interpreter.py`

**Modify `_apply_reconciliation_classifications` (~115) and `_classify_from_hints` (~71):** if an item has `matches`, force each match’s pandas class; do not let Claude pick `structural_explained` without a match or fee hint (existing guard already blocks unprompted `structural_explained` at ~140–141).

**Account-level residue (per the E.6 decision in C.1).** When an item has `matches`, the item's own `classification` is set by **pandas**, not by Claude, to the most action-requiring class present among its matches, in this order (first present wins):

`missing_je` → `categorical_misclassification` → `stale_reference` → `timing_cutoff` → `structural_explained`

Claude's `reconciliation_classifications` entry for that account is **overridden**, exactly as the existing force path does for hints. `NarrativeJSON.reconciliation_classifications` keeps its `dict[account → class]` shape — Claude never sees or emits a `match_id`. Matches dropped by `_classify` (rule 6, the true negative) contribute nothing; if every match on an account is dropped, the item has no matcher story and falls back to today's account-total behaviour.

**Modify `_run_with_guardrail` (~340–347):** for each recon item, also append pandas `gross`, `fee`, `net`, and unmatched counts (and `abs` of each, same pattern as `delta`). Exact fields: `item["matches"][i]["gross"]`, `["fee"]`, `["net"]`, plus a top-level `unmatched_count` if present. If `matches` is absent, behaviour is today’s list.

**Prompt impact:** `backend/prompts/narrative_prompt.txt` `structural_explained` template stays for account-total fee fallback. **Add** a three-way template that copies `[gross]`, `[fee]`, `[net]`, `[unmatched_count]` with an explicit line: **Claude must copy these numbers, never subtract gross − net, never compute a fee %.** Same reminder in `narrative_prompt_reinforced.txt`.

### C.9 `backend/prompts/account_mapping_prompt.txt`

**Today** `file_type` one of `payroll, supplier_invoices, contracts`. **After:** document `bank_statement` / `processor_settlement`: map payout/batch identifiers to the UF / merchant clearing / bank GL names, not to COGS. Do not perform arithmetic.

### C.10 Dead / hardcoded logic to watch

- Default-to-`supplier_invoices` (~532): after PR-B, bank files must not fall through. Test: filename `stripe_payouts.xlsx` → `processor_settlement`, not vendor.
- `consolidator.py::_is_gl_label`: independent of `SourceFileType`. A bank file must not be treated as GL.
- `row_count=1`: leave it; matcher has its own identity. Confirm `excel_export.py` (~231, ~287) still prints source `row_count` as rolled lines, **not** as matched batches.

## D. API / routes

***Design for future PR, not to be implemented yet.*** Matcher freeze is C.5.1; column contracts and expected cards are C.5.3. This section is ingest only.

No new endpoint in v1. Reconciliations already flow through existing run parse-preview JSONB and report payload.

**Do not** add `SourceFileType` literals (`bank_statement`, `processor_settlement`) in a docs-only PR. Describe them here; ship the enum in PR-A with no `_detect_file_type` wiring (see G). Parser maps uploaded headers onto the C.5.3 sidecar names (rename only — no arithmetic).

| Endpoint | Change |
|----------|--------|
| `POST /upload` (and multi-file run start) | None required. Filename detection is server-side (PR-B). MVP: **one** `processor_settlement` and **one** `bank_statement` per `(company_id, period)`. A second file of the same kind is rejected in plain English (“This close already has a processor file. Remove it first or upload a replacement.”). |
| Mapping confirm | `file_type` already on mapping draft items (`MappingReview.tsx`). New types must round-trip. |
| Report GET | Response may include nested `matches` on recon items. Old clients that ignore unknown keys keep working. |

**Period vs bank dates:** the run period is still the close month (`2026-03-01` in the fixture). Bank rows with `settlement_date > period_end` are **kept at ingest** (PZ-200 is `2026-04-02`). Dropping them would make `timing_cutoff` impossible. They are not a second period’s close.

Auth / `company_id`: unchanged.

**Backward compatibility:** runs without bank/processor files behave exactly as today (fee-band fallback). Nested `matches: null` / omitted.

## E. Frontend

***Design for future PR, not to be implemented yet.*** Cards use the six existing classes only. Frozen mapping from C.5.3:

| Three-way state | Fixture id | Classification | Card? |
|---|---|---|---|
| Gross vs net / fee-explained | PZ-100 | `structural_explained` | yes |
| Payout dated after `period_end` | PZ-200 | `timing_cutoff` | yes |
| Processor batch not in GL | PZ-300 | `missing_je` | yes |
| Bank deposit not in GL / UF | DEP-99 | `missing_je` | yes |
| Posted to wrong clearing account | PZ-500 | `categorical_misclassification` | yes |
| Clean three-way, fee `$0` | PZ-900 | none | **no** |
| Ambiguous leftover (blank id, same amount+date) | (blank)×2 | `stale_reference` | yes |

No 7th class. No `unmatched_cash`. The existing coverage-card renderer + `AnomalyCard` already handle these six. `is_material` still applies (Kova 1 AND-gate unchanged). PZ-900 never reaches the renderer.

Narrative sentences are C.5.2: pandas supplies every dollar and date; the prompt forbids computing the fee, a %, or the class. Claude never sees a candidate list and is never asked to pick among ambiguous matches.

- `frontend/src/components/FileUpload.tsx`: optional helper copy that a bank CSV and a processor payout file can be uploaded **together** with the GL. No new file-type picker required if detection stays filename-based. Do not ask the user to type match keys.
- `frontend/src/components/MappingReview.tsx`: payroll has a “Set All to Salaries & Wages” special case (~232). Do **not** add a similar “set all to COGS” for bank files. Optionally a UF quick-apply if the GL pool contains an Undeposited Funds name — only if a fixture has that name; otherwise skip.
- Recon cards: may stay account-grouped if `matches` nest inside the UF card. Do **not** expose raw matcher debug (unmatched id lists) in v1 beyond the pandas counts Claude is allowed to copy.
- **Never** show a user-typed match threshold.

## F. Tests

Acceptance dollars, ids, and classes are C.5.3 — this table is the function list, not a second spec.

| File | Functions / what they prove |
|------|------------------------------|
| `tests/tools/test_batch_matcher.py` (new) | Load C.5.3 CSVs. Pin: PZ-100 `structural_explained` / `match_kind="id"` / `fee==45.00`; PZ-200 `timing_cutoff` (not fee, even though `fee==80.00`); PZ-300 `missing_je` (not `structural_explained` despite `fee_pct==0.04`); DEP-99 `missing_je` / `match_kind="none"`; PZ-500 `categorical_misclassification`; PZ-900 **absent** from cards; two blank `$100` on `2026-03-25` → one `stale_reference` with `ambiguous is True` and `candidate_count == 2`. |
| Same file | `test_does_not_match_on_gross_against_net` — copy of PZ-100 with ids stripped must **not** emit `structural_explained`. `test_fallback_amount_date_only_when_id_absent`. Fee comes from `gross - net`, never from a settlement `fee` column (fixture has none). |
| Isolated three-file fixture | `tests/tools/fixtures/kova_cash_{fsm,gl,bank}_mar_2026.csv` as specified in C.5.3. **Do not** reuse Sentinel or Vandelay CSVs. Check in at PR-A; matcher assertions at PR-B. |
| `tests/tools/test_detect_file_type.py` or orchestrator tests | PR-B: `stripe_payouts` → `processor_settlement`; `bank_statement` → `bank_statement`; unknown still `supplier_invoices`. **PR-A: these must still be supplier/unknown** (detection not wired). |
| Vandelay negative | Shopify/Amazon payouts **without** a bank file: matcher does **not** claim three-way. Account-total fee fallback may still fire. |
| Sentinel negative | No bank file. Bank Charges $95 is not this item. |
| `tests/agents/test_interpreter_classify.py` | Force class from `matches`; Claude cannot override to a different class; no seventh class in the Literal. |
| Guardrail | `numbers_used` containing pandas `1000.00` / `955.00` / `45.00` for PZ-100 passes. A Claude-invented `45` that is not on the item fails. Do **not** put `4.5` in `numbers_used` — `fee_pct` is not a prompt field. |
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

*Revised 30 August 2026, after Item 1 shipped. This replaces the first-pass
Item 4 section rather than sitting alongside it — there is one Item 4 section,
not two. The A–H skeleton and every locked decision from the first pass are
preserved; what is new is the R-series resolutions in C.3, written to the
standard Item 1 only reached after E.1–E.7 were forced out by implementation.*

Not a deferred-revenue waterfall. Not annual 12× (already Kova 1). Class stays
**`stale_reference`**. No seventh class.

**The grain problem, stated once.** Alarm RMR close asks *how many* accounts are
billable and at what rate, not just what the dollars total. Today 85 roster rows
collapse to one consolidated line (`Service Revenue $3,825`) at
`parser.py::parse_file_silently`'s `groupby("account")`, and the normalizer has
already dropped Status / Last Billed / Customer ID before that. By the time
`hint_computer` runs it can see `gl_amount=3540`, `non_gl_total=3825`,
`delta=285` — and no 85, no 82, no 3. This is Item 1's grain mismatch again:
identity destroyed before aggregation. The fix is the same shape — preserve the
columns in a sidecar before the drop, count in pandas, attach the result.

**v1 boundary (locked), stated in the Item 1 style:** one roster file, one
mapped GL revenue account, one period, row-grain counts only. No customer
dimension, no attrition trend, no churn rate, no `count × rate` wholesale
accrual (that is item 3, and it depends on this).

## A. Pre-conditions

- **Item 1 is shipped.** `backend/tools/batch_matcher.py::match` exists with a
  live call site (`orchestrator::_attach_batch_matches`), and PR-C landed the
  sidecar machinery. Its roadmap pre-condition is satisfied.
- **The sidecar interception already exists — this is the single biggest change
  since the first pass.** `parser.py` now has `file_type` on
  `parse_file_silently`, a `_build_sidecar` method, and a `_SIDECAR_COLUMNS`
  registry keyed by file type (`processor_settlement`, `bank_statement`,
  `general_ledger`). Item 4 adds a **fourth key** — `contracts` — and reuses the
  existing "copy off `df_raw` before `apply_plan` drops non-golden columns"
  path. The first-pass spec budgeted a new interception point; that work is
  done. Size drops accordingly (see G).
- **`contracts` already detects.** `orchestrator._FILE_TYPE_PATTERNS["contracts"]`
  is `["contract", "subscription", "recurring", "roster", "customer"]`. **No new
  `SourceFileType`**, no detection change of any kind.
- **PR #11's cutoff allowlist must stay intact.** `hint_computer` blocks roster
  cycle columns from `crosses_period_boundary` via `_CUTOFF_DATE_BLOCK`, which
  contains `"last billed"`, `"renewal"`, `"start date"`, `"end date"`,
  `"next bill"`, `"contract end"`, `"payout period"`, plus the
  `_is_contracts_roster_file(filename)` guard. Item 4 **reads Last Billed as a
  count input** and must not re-widen that hint. A regression test is required
  (F), not merely an intention.
- **Sentinel's contracts file is still absent from the tracked demo tree.**
  Verified: `docs/demo_data/sentinel/` holds `sentinel_gl_mar_2026.xlsx` and
  `february/` only. The 85-row roster is designed but not checked in, so an
  isolated fixture is **required**, not optional.
- Not blocked on item 3 (which wants these counts later) or on anything else
  unbuilt.

## B. Database / migration

**No SQL. Highest migration stays `0010`.**

| Change | Migration? |
|---|---|
| `n_active`, `n_billed_in_period`, `count_delta`, `fee_sum_active`, `fee_sum_billed` on `ReconciliationHints` | **No** — `reports.reconciliations` JSONB, already there since `0007` |
| 85 subscriber rows in `monthly_entries` | **Never.** See below |
| New `SourceFileType` | **No** — `contracts` exists |
| `status` / `customer_id` as golden fields on every file | **No.** Contracts-only sidecar; P&L and payroll stay seven-column pandera `strict=True` |
| Customer dimension table | **No** in v1. Counts are ephemeral per run |

**Why `monthly_entries` cannot hold the roster.** `0001_initial_schema.sql:72`
declares `CONSTRAINT unique_entry UNIQUE (company_id, account_id, period)`. All
85 roster rows map through `AccountMapper` to **one** GL account (`Service
Revenue`) in **one** period for **one** company — so all 85 would collide on a
single key. The table's grain is one amount per account per month by design;
storing subscribers there would require either a synthetic per-customer
`account_id` (inventing 85 chart-of-accounts entries that do not exist) or
dropping the constraint that protects against duplicate-upload double counting.
Both are worse than keeping counts in JSONB. **RLS:** none new.

## C. Backend — file by file

### C.1 Interception point (exact)

`ParserAgent.parse_file_silently`, in the slot Item 1 already created:

```
df_raw = self._read_full(storage_key)
df_raw = pii_sanitizer.sanitize(df_raw, run_id=run_id)
        │
        ▼
sidecar = self._build_sidecar(df_raw, file_type)      <- ADD "contracts" HERE
        │                                                (before the drop)
        ▼
df_normalized, _ = normalizer.apply_plan(df_raw, plan, period)
        ~108-134  <- Status / Last Billed / Customer ID dropped here
        ▼
df_validated = validator.validate(df_normalized)       pandera strict, 7 cols
        ▼
account_name_map applied      "Oak Street Dental" -> "Service Revenue"
        ▼
groupby("account")["amount"].sum()                     85 rows -> 1 preview row
```

Add to `_SIDECAR_COLUMNS`:

```python
"contracts": {
    "customer_id": ("customer_id", "customer", "account_id", "site_id"),
    "status": ("status", "account_status", "contract_status"),
    "monthly_fee": ("monthly_fee", "monthly_amount", "rate", "mrr", "rmr"),
    "last_billed": ("last_billed", "last_billed_date", "last_invoice_date"),
},
```

**Do not** put Status on `df_detailed` — pandera `strict=True` would reject the
eighth column. The sidecar bypasses pandera by construction, exactly as the
bank/processor sidecars do.

### C.2 `backend/tools/roster_counts.py` (new)

**Responsibility:** pandas counts on a contracts sidecar. No Claude, no DB, no
classification, no I/O.

**Input:** `sidecar: pd.DataFrame`, `period: date`.
**Output:** a small typed result (dataclass or `TypedDict`; not SQL):

```python
n_active: int              # rows whose status normalizes to "active"
n_billed_in_period: int    # of those, billed inside the period month
count_delta: int           # n_active - n_billed_in_period
fee_sum_active: float      # sum(monthly_fee) over active rows
fee_sum_billed: float      # sum(monthly_fee) over active-and-billed rows
```

**Does not:** fuzzy-match GL names, write `monthly_entries`, force a class,
dedupe customers, read `_roll_up.row_count` as a subscriber count, re-open
cutoff dates, or split mid-period rate changes.

**Logging:** `event="roster_counts"` with the five integers/floats and
`rows_in_sidecar` only. **Never log a customer name, a customer id, or a fee**
— CLAUDE.md forbids logging cell values, and a roster is the most
PII-adjacent file the product ingests.

### C.3 Resolutions — the rules that must not be left as narrative

*Item 1's first pass left seven rules implicit and paid for it in E.1–E.7.
These are the equivalents for Item 4, decided here rather than during coding.*

**R.1 — "billed in period" is defined over Active rows only.**
`n_billed_in_period = count(row is active AND last_billed falls in the period month)`.
Parse with `pd.to_datetime(..., errors="coerce")` and compare **(year, month)**
to the period; no day-level or timezone logic. A **null, blank or unparseable**
`last_billed` is **not billed** — absence of billing evidence is not evidence of
billing, and a never-billed active account is precisely the miss this item
exists to surface. Restricting the count to Active rows makes `count_delta`
mean exactly "Active but not billed this month" and guarantees the invariant
`0 <= n_billed_in_period <= n_active`, so **`count_delta` can never be
negative**. If a future change breaks that invariant, emit nothing rather than a
negative count.

**R.2 — "Active" is an exact match on the normalized status token.**
Normalize with `str(value).strip().casefold()`; a row is active iff the result
is exactly `"active"`. Everything else — `cancelled`, `suspended`, `pending`,
`on hold`, `inactive`, `terminated`, and any value not anticipated — is **not
active**. Rationale: the claim being made is "this many accounts are billable
this month"; a suspended or pending account is not billable, and stretching the
definition would invent revenue. Consequence to accept: a roster using
`"Active - pending cancel"` will under-count. Mitigation: log the **distinct
non-active status values and their counts** (values only, never rows) so a
mis-shaped roster is visible in ops rather than silently wrong.
**If the sidecar has no status column at all, emit no counts** — do not assume
every row is active.

**R.3 — Mid-period rate changes are out of scope for v1, and rows are
"accounts", never "customers".**
`fee_sum_active` sums `monthly_fee` across active rows as the roster presents
them. One row = one account. If a rate increase is represented as two rows for
the same site, v1 counts two accounts and sums two fees. This is **deferred, not
solved**. Two required guards: (a) the prompt and every template must say
**"accounts"**, never "customers" or "subscribers", so the number we publish is
the number we actually computed; (b) when `customer_id` is present and contains
duplicates, log a warning with the duplicate **count** so the limitation is
observable. Counts are still emitted — a multi-site customer legitimately has
several accounts, and suppressing that would be its own error.

**R.4 — One roster file per run.**
If **two or more** uploaded files detect as `contracts`, emit **no counts** and
log. Merging rosters needs a cross-file identity rule that does not exist, and
guessing one would double-count or silently drop accounts. Mirrors Item 1's
"one processor, one UF account, one bank, one period" lock.

**R.5 — Counts attach to exactly one GL account, or not at all.**
The roster's rows map through `AccountMapper` to a GL revenue name. After
`account_name_map` is applied and **before** `groupby`, collect the distinct
mapped account names for sidecar rows. If there is exactly **one**, that is the
target reconciliation item. If there are **zero or more than one**, emit no
counts and log — attaching "85 accounts" to a line that only represents some of
them would be false. This rule was implicit in the first pass ("the recon item
whose canonical name is the mapped GL revenue account") and is the Item 4
analogue of Item 1's missing-UF-item case.

**R.6 — `count_delta == 0` produces counts but no forced class.**
`count_delta > 0` → force `stale_reference`. `count_delta == 0` → the count
fields are still attached (they are true, and the guardrail may need them) but
**no class is forced** and the prompt must not produce a "0 accounts" sentence.
A `$285` dollar gap with `count_delta == 0` stays a dollar-only
`stale_reference`, told the way it is told today.

**R.7 — Materiality is not retuned, and a dropped item is not resurrected.**
If `consolidator._is_material` already dropped the account, do **not** bring it
back as a count-only card, even when `count_delta > 0`; discard the counts and
log. Do **not** adjust `$100` / `$500` to keep a card alive. Item 5 forbade
retuning those and that still holds.

**R.8 — Guardrail units: counts are point values, not percentages.**
`n_active`, `n_billed_in_period` and `count_delta` are **counts**; at the
guardrail's cent tolerance each is a point value in the **money pool**, exactly
like Item 1's `candidate_count`. `fee_sum_active` / `fee_sum_billed` are money.
**No ratio, rate, or percentage may be added to the reference pool** — no churn
%, no "3 of 85 = 3.5%". That is the mixed-unit bug the guardrail fix removed.

### C.4 `backend/domain/contracts.py`

Add to `ReconciliationHints`, all optional with defaults so existing report
JSONB still parses:

```python
n_active: int | None = None
n_billed_in_period: int | None = None
count_delta: int | None = None
fee_sum_active: float | None = None
fee_sum_billed: float | None = None
```

No new bool is required — the interpreter keys off
`count_delta is not None and count_delta > 0`. Do **not** hang this off
`looks_like_annual_prepayment` or `similar_amount_in_other_account`.

### C.5 `backend/agents/orchestrator.py`

Add `_attach_roster_counts(recon_items, per_file_data, period, run_id)`,
modelled directly on the shipped `_attach_batch_matches`: run after
`consolidate()` and `compute_hints()`, **beside** the consolidator, never inside
it. It applies R.4 (one roster file), R.5 (one mapped account), and writes the
five fields onto that item's `hints`. Same skip-and-log discipline: if any gate
fails, attach nothing and leave today's behaviour untouched.

### C.6 `backend/agents/consolidator.py::_build_item`

**Leave `row_count=1` hardcoded.** Do not un-hardcode it and call it RMR —
`_roll_up`'s `len(tagged[...])` is "Excel lines after account mapping", not
"accounts billed this month". `excel_export.py` keeps printing `row_count` as
rolled source lines; do **not** relabel that column "accounts" in this item.

### C.7 `backend/tools/hint_computer.py`

**No change required.** Counts arrive from the parser via the orchestrator, the
same route Item 1's matches take. Do **not** scan `df_detailed` for Status (it
is gone by then), and do **not** set `crosses_period_boundary` from Last Billed.

### C.8 `backend/agents/interpreter.py`

**Force-class order** (the shipped chain, with roster counts inserted):

```
coverage -> matches (three-way) -> is_processor_fee_gap -> deposit
        -> annual 12x -> roster count -> Claude's map -> hint fallback
```

Roster counts sit **after** annual and **before** Claude, per the first pass.
Rationale: fee / deposit / annual are statements about the money itself and are
more specific; a stale roster is a statement about the reference list. `matches`
outranks everything, unchanged.

**Guardrail** — extend the existing loop that already appends `gl_amount`,
`non_gl_total`, `delta`, `hints.implied_monthly` and Item 1's match fields:
append `hints.n_active`, `hints.n_billed_in_period`, `hints.count_delta`,
`hints.fee_sum_active`, `hints.fee_sum_billed` when not None, as floats. Without
this a correct "3 accounts" sentence fails verification.

### C.9 `backend/prompts/narrative_prompt.txt`

Today the `stale_reference` prose mentions "customer count or rate differences"
but the template only has `[amount]`, `[GL amount]`, `[delta]`. Add a count
template used **only** when `count_delta > 0`:

> "The [account] roster lists [n_active] active accounts but only
> [n_billed_in_period] were billed in this period, a gap of [count_delta]
> accounts. The roster shows [fee_sum_active] against [GL amount] in the GL.
> The reference data may be out of date. Recommended action: reconcile the
> active list against the GL and update cancelled or re-priced accounts."

Forbidden, in the Item 1 style:
- Never subtract. Do not compute `n_active - n_billed_in_period`; copy `[count_delta]`.
- Never approximate a count: no "about 3", no "a few", no "several".
- Never write a percentage or churn rate.
- Never say "customers" or "subscribers" — say **accounts** (R.3).
- Never state a count when `count_delta` is absent, and never write "0 accounts".

Same reminder block in `narrative_prompt_reinforced.txt` so a retry cannot drop
or reword the count finding.

### C.10 Files that must NOT change

Cutoff allowlist needles in `hint_computer.py`; `looks_like_annual_prepayment`;
`GoldenField` / the P&L pandera schema; Item 5's flux gates; Item 1's matcher,
`_SIDECAR_COLUMNS` entries for bank/processor/GL, and `_attach_batch_matches`.

## D. API / routes

**Zero API changes.** Counts ride on `parse_preview.reconciliations` and the
report payload, which already carry `hints`. No new endpoint, no auth change, no
response-shape change. Old clients ignore unknown hint keys. A contracts upload
without Status or Last Billed simply yields no counts and behaves as today.

## E. Frontend

**No new UI required for v1.** A count-bearing card is still a
`stale_reference` `ReconciliationCard`; the counts reach the user through the
narrative that Claude copies from pandas, not through a new component. Existing
rendering needs no change to display it.

Explicitly **not** in v1: a subscriber dashboard, an attrition chart, a
per-customer list, or any user-typed count threshold. Do **not** relabel the
Excel export's `row_count` column as "accounts".

## F. Tests

| File | What it proves |
|---|---|
| `tests/tools/test_roster_counts.py` (new) | `test_sentinel_shape_85_82_3` → `n_active=85`, `n_billed_in_period=82`, `count_delta=3`, `fee_sum_active=3825.00`. `test_status_case_and_whitespace_insensitive`. `test_suspended_pending_onhold_are_not_active` (R.2). `test_null_or_unparseable_last_billed_is_not_billed` (R.1). `test_missing_status_column_emits_nothing`. `test_count_delta_never_negative`. `test_empty_sidecar_zeros`. |
| Isolated fixture (new) | `tests/tools/fixtures/kova_rmr_roster_mar_2026.csv` — 85 rows, 82 with `Last Billed` in March 2026, 3 Active-but-unbilled, fees summing to `3825.00`; plus a small GL fixture at `3540.00`. **Self-contained** — Sentinel's roster is not in the tracked tree (verified), so nothing may depend on it. Include at least one `Suspended` and one blank-status row as shape noise. |
| `tests/tools/test_hint_computer.py` | **PR #11 regression:** a contracts sidecar whose `Last Billed` falls in April must still leave `crosses_period_boundary` False. Add `test_roster_counts_do_not_set_crosses_period_boundary`. |
| `tests/tools/test_annual_prepayment.py` | **Negative:** Software `13,200` / `1,100` stays `accrual_mismatch`; `count_delta` absent; no count card. |
| Dollar-only negative | `count_delta == 0` (and `None`) with a `285.00` gap → class `stale_reference`, and the narrative contains no "0 accounts" (R.6). |
| `tests/agents/test_interpreter_classify.py` | Force `stale_reference` when `count_delta > 0`; matches / fee / deposit / annual still outrank it; Claude's contrary class is overridden; no seventh class. |
| `tests/agents/test_consolidator.py` | `ReconciliationSource.row_count` stays `1`. Do **not** assert 85. |
| Parser plumbing | `test_contracts_sidecar_survives_groupby` — preview collapses to one row while counts remain 85/82/3. `test_pnl_file_gets_no_roster_sidecar`. |
| Gate tests | R.4: two contracts files → no counts. R.5: roster mapping to two GL accounts → no counts. R.7: immaterial account → counts discarded, no resurrected card. |

## G. Sequencing within the item

**Two PRs, but PR-A is materially smaller than the first pass assumed**, because
Item 1 already built the interception, and `contracts` already detects.

| PR | Ships | If merged alone | Safe? |
|---|---|---|---|
| **PR-A** | `contracts` entry in `_SIDECAR_COLUMNS`; `roster_counts.py`; optional hint fields; `_attach_roster_counts` writing them; **no** force-class, **no** prompt change | Extra JSONB keys only. No classification changes anywhere. Claude never sees the counts because the prompt does not mention them. | **Yes** — purely additive |
| **PR-B** | Interpreter force-class; guardrail append; prompt + reinforced templates; isolated fixture assertions; all negatives | Speech + force. Without B the counts sit unused. | Merge after A |

A single PR is tempting given the smaller PR-A, but the split is still right:
PR-A changes no card's class, so it can land and be observed on real uploads
before any narrative depends on it — the same reason Item 1's PR-A was inert.

## H. Rollback

- Revert PR-B: force-class and prompt gone; leftover hint keys are ignored by
  every reader.
- Revert PR-A: the `_SIDECAR_COLUMNS` entry, `roster_counts.py` and the attach
  helper disappear. Item 1's sidecar machinery is untouched.
- **No SQL to roll back, no backfill.** Nothing was written to `monthly_entries`,
  no table was created. Old reports whose JSONB already carries `n_active` still
  parse, because every field is optional with a default.

## Open questions — flag, do not decide while coding

1. **Should non-active statuses be counted separately?** R.2 folds
   `Suspended` / `Pending` / `On Hold` into "not active". A future
   `n_suspended` would let the narrative say "3 cancelled, 2 suspended", which
   is more useful and more honest. Deferred from v1; needs a product call.
2. **Should Sentinel's 85-row roster be restored to `docs/demo_data/`?** The
   isolated fixture is required regardless (F), but the demo cannot show this
   feature without the file. Restoring it is a separate decision from shipping
   the item.
3. **Mid-period rate changes (R.3) are deferred.** If real rosters commonly
   represent a rate increase as two rows, the account count will overstate.
   Revisit when a real dealer roster is available — not before.

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

# Pre-analysis: Coverage UI (GL-only “Not compared”)

Status: analysis only. No code in this change.
Date: 2026-08-24.
Checkout verified: `main` at `a876a73` (no `card_kind` on this branch).

---

## 0. Why PR #4’s summary did not match the running app

**What was scanned is `main`. PR #4 is not on `main`.**

- PR: https://github.com/jansoganci/iron-ledger/pull/4 — **OPEN**, not merged.
- Head: `cursor/orphan-coverage-cards-d72a`
- Base: `cursor/is-material-and-gate-d72a` (another unmerged branch, **not** `main`)
- `git grep card_kind main` → no hits.

The PR body described the **PR branch** as if it were production. It is not. Anyone testing `main` (local or deployed from `main`) will still see GL-only lines as red/amber `missing_je` cards.

### Backend: `main` vs PR #4 branch

- `hints.is_gl_only` set by consolidator: **yes on both**.
- That hint stored in `reports.reconciliations` JSONB and returned by `GET /report/{company_id}/{period}`: **yes on both** (nested under `hints`).
- `card_kind` on `ReconciliationItem`: **no on `main`**. Yes on PR branch (`"exception"` | `"coverage"`).
- Interpreter override (`classification=null` for GL-only): **no on `main`**. Yes on PR branch.
- Excel `INFO` / `Not compared`: **no on `main`**. Yes on PR branch.
- Grey “Not compared” section + `CoverageBadge`: **no on `main`**. Yes on PR branch.
- `StatsStrip` mounted in the page: **no on `main`**. **Still no on the PR branch.**

### StatsStrip claim was false even on the PR branch

PR #4 added coverage filtering **inside** `StatsStrip`, then left the comment `unused — kept for reference` and never rendered `<StatsStrip />`.

On both `main` and the PR branch, [frontend/src/components/ReportSummary.tsx](../../frontend/src/components/ReportSummary.tsx) only mounts `FinancialsStrip`. High/Medium exclusion lives in a dead function. Reporting that as shipped UI was incorrect.

### Interpreter on `main` (why cards are red)

```184:191:backend/agents/interpreter.py
            for item in reconciliations:
                account = item.get("account", "")
                if account in cls_map:
                    item["classification"] = cls_map[account]
                elif not item.get("classification"):
                    item["classification"] = _classify_from_hints(item.get("hints", {}))
```

`_classify_from_hints` on `main` returns `missing_je` when `is_gl_only` is true (GL-only and source-only share that branch). Claude can also stamp `missing_je` in `reconciliation_classifications`. There is **no** coverage override on `main`.

On the PR branch the hint fallback returns `None` for `is_gl_only`, and `_apply_reconciliation_classifications` forces `card_kind="coverage"` and `classification=None` even if Claude stamps `missing_je`.

### Rule for later PR summaries

Describe `main` after merge, or write “on branch X, not merged.” Do not treat a stacked Cursor PR body as the running app.

---

## 1. Affected files (real names)

User-listed names mapped to this repo:

| Mentioned | Actual path | State on `main` |
|---|---|---|
| ReconciliationPanel.tsx | [frontend/src/components/ReconciliationPanel.tsx](../../frontend/src/components/ReconciliationPanel.tsx) | Groups **all** items by `\|delta\|` into high/medium/low. No coverage split. |
| ReconciliationCard.tsx | [frontend/src/components/ReconciliationCard.tsx](../../frontend/src/components/ReconciliationCard.tsx) | Type has no `card_kind`, no `hints`. Always a severity card. |
| ReportSummary.tsx | [frontend/src/components/ReportSummary.tsx](../../frontend/src/components/ReportSummary.tsx) | `StatsStrip` defined, never called. Counts every recon by `\|delta\|`. |
| ClassificationBadge.tsx | [frontend/src/components/ClassificationBadge.tsx](../../frontend/src/components/ClassificationBadge.tsx) | Six exception classes only. |
| excel_export.py | [backend/tools/excel_export.py](../../backend/tools/excel_export.py) | `severity.upper()` + classification title-case. No `INFO` / `Not compared`. |

Also required if this later becomes an implementation (do not edit in this change):

- [backend/domain/contracts.py](../../backend/domain/contracts.py) — add `card_kind: Literal["exception", "coverage"] = "exception"`
- [backend/agents/consolidator.py](../../backend/agents/consolidator.py) — set `card_kind="coverage"` when `hints.is_gl_only`
- [backend/agents/interpreter.py](../../backend/agents/interpreter.py) — force `classification=None` for coverage; do not let Claude’s `missing_je` stick
- [backend/prompts/narrative_prompt.txt](../../backend/prompts/narrative_prompt.txt) — omit GL-only accounts from `reconciliation_classifications`; `missing_je` is source-only only
- Tests: PR branch already has `tests/agents/test_interpreter_classify.py` (not on `main`)

### ClassificationBadge vs separate component

Keep a **separate** `CoverageBadge` in the same file (PR #4 already did this).

Coverage is not a seventh reconciliation class. Putting `"coverage"` into the `Classification` union would undo the orphan-policy decision: visible coverage card, six-class `Literal` unchanged.

- `CoverageBadge`: Info icon, label “Not compared”, `bg-canvas text-text-secondary border-border`
- Exception badges: keep red / amber / explained-green as they are today

### Excel on `main`

GL-only rows look like High/Medium exceptions (`HIGH` + `Missing Je`).

PR branch maps coverage → severity cell `INFO`, classification cell `Not compared`, grey fill (`_COVERAGE_FILL`).

Field-name check (no bug): model field is `non_gl_total`. `main` excel reads `item.get("non_gl_total")`. PR branch excel reads the same key. No rename needed when copying that hunk.

---

## 2. `card_kind` chain — where it breaks

```
consolidator._build_item
  → ReconciliationItem (Pydantic)
  → model_dump JSON
  → reports.reconciliations JSONB
  → GET /report/{company_id}/{period}  (pass-through, no field strip)
  → frontend ReconciliationItem type
  → ReconciliationPanel
```

**On `main` the break is at the Pydantic model.** [backend/domain/contracts.py](../../backend/domain/contracts.py) `ReconciliationItem` ends at `hints`. There is no `card_kind`, so `model_dump` cannot emit it.

Orchestrator already does `item.model_dump(mode="json")`. API already returns `report.reconciliations or []` with no allowlist ([backend/api/routes.py](../../backend/api/routes.py) around the report GET handler). JSONB round-trip in [backend/adapters/supabase_repos.py](../../backend/adapters/supabase_repos.py) stores the dict as-is.

**What does reach the client today:** `hints.is_gl_only` (boolean on the nested hints object). Frontend `ReconciliationItem` omits `hints`, and the panel never reads it. Runtime JSON still has the hint if you inspect the network tab.

**On the PR branch the chain is complete** for `card_kind`:

1. Consolidator sets `card_kind="coverage"` when `hints.is_gl_only`.
2. Interpreter re-asserts `card_kind="coverage"` and nulls `classification`.
3. JSONB stores both fields.
4. GET returns them.
5. TS type has `card_kind?: CardKind` and `hints?: { is_gl_only?: boolean }`.
6. `isCoverageItem()` is true when `card_kind === "coverage"` **or** `hints.is_gl_only` (fallback for old rows).

Adding `card_kind` to the model is enough for it to appear in the API. No new column, no new endpoint.

---

## 3. Visual design (neutral only)

From [docs/01-architecture/design.md](../01-architecture/design.md):

- Normal / info: `#F3F4F6` background, `#6B7280` text — **not green**
- Green: favorable variance only
- Red / amber: exception severity only

Coverage card tokens (existing CSS, no new palette):

- Background: `bg-canvas` (`--canvas` → `--neutral-50`, warm stone)
- Border: `border-border`
- Type and amount: `text-text-secondary`
- Badge: `CoverageBadge` — Info icon, “Not compared”
- Do not use `text-severity-high-fg`, `text-severity-medium-fg`, or favorable green

Placement:

1. High / medium / low **exception** grids first (errors first).
2. Below them, heading `Not compared · N`.
3. One-line explanation: these GL accounts were not in any supporting file; this is not a missing journal entry.
4. Coverage cards in the same grid as exceptions (`grid-cols-1 xl:grid-cols-2`).

---

## 4. StatsStrip — activate and filter

Mount `<StatsStrip />` in [frontend/src/components/ReportSummary.tsx](../../frontend/src/components/ReportSummary.tsx) (document header, above narrative or above the panel). PR #4 already has the filter inside the dead function; it was never used.

Logic:

```
exceptions = items.filter(i => !isCoverageItem(i))
high   = exceptions where |delta| >= 5000
medium = exceptions where 500 <= |delta| < 5000
low    = exceptions where 0 < |delta| < 500
Not compared = items.length - exceptions.length
```

“Findings” / “To review” must equal `exceptions.length`, not `items.length`.

### Before / after (Vandelay, Advertising — Meta $8,200)

**Before (`main` today):** Meta is a High exception (`|delta| >= 5000` and class `missing_je`). High includes it. There is no Not compared count (and StatsStrip is not on screen).

**After:** Meta is coverage. High/Medium ignore it. “Not compared” increments by 1. Card sits in the grey section, not the red High grid.

---

## 5. Test plan (Vandelay)

Files in [docs/demo_data/vandelay/](../demo_data/vandelay/):

1. `vandelay_gl_mar_2026.xlsx`
2. `vandelay_shopify_payouts_mar_2026.xlsx`
3. `vandelay_amazon_settlement_mar_2026.xlsx`
4. `vandelay_inventory_purchases_mar_2026.xlsx`

Period: **March 2026**. Upload all four → Analyze → open Report.

Supporting files use an `Account` column that matches GL names. Coverage = GL account with no row in Shopify, Amazon, or inventory after consolidator matching.

### Must appear under Not compared (GL-only)

These GL lines have no counterpart in the three supporting files (amounts from the GL workbook):

- Advertising — Meta — $8,200 (High if it were an exception — this is the counter check)
- Advertising — Google — $4,150
- Salaries & Wages — $21,000
- Payroll Taxes — $1,890
- Insurance — $850
- Legal & Professional Fees — $1,200
- Office Supplies — $215 (only if it clears the dollar floor; Bank Charges $95 likely dropped)

### Must stay exception cards (not coverage)

- Warehouse Rent — also in inventory purchases ($6,500)
- Software Subscriptions — also in Amazon settlement
- Product Sales / fees / COGS with counterparts in Shopify / Amazon / inventory

### StatsStrip checks

- High/Medium must **not** include Advertising — Meta.
- Not compared >= 1 (expect several GL-only opex lines).
- “Findings” / “To review” equals exception count, not exception + coverage.

### Excel

Download the close package. Advertising — Meta row: Severity `INFO`, Classification `Not compared`, grey fill. Not `HIGH` / `Missing Je`.

### Negative check

Upload **only** the GL file. Consolidator skips orphans when `total_sources < 2`. Not compared section must be absent. Coverage UI is not a default screen.

---

## 6. Risk and rollback

- **Do not merge PR #4 as-is.** It is stacked on `cursor/is-material-and-gate-d72a`, not `main`. StatsStrip is still unmounted on that branch. Cherry-pick or re-apply the coverage commits onto current `main` after a dedicated implementation PR.
- Old reports in JSONB have no `card_kind`. UI must keep `hints.is_gl_only` fallback. Those rows still have `classification=missing_je` until the period is re-run through the new interpreter.
- Materiality: GL-only under the dollar floor never becomes a card (Bank Charges $95 is the example).
- Rollback: stop writing `card_kind` (Pydantic default `"exception"`); panel treats unknown / missing as exception; Excel falls back to `severity.upper()`. No migration — JSONB, no new column.

---

## Out of scope for this document

- Implementing the UI or backend override
- Merging or rebasing PR #4
- Changing the six-class `Literal`
- PAYROLL helper, fee-hint `structural_explained`, grouping-by-canonical

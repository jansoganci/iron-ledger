# Persistent source mappings (v1)

Locked 16 September 2026. Implement this slice; do not reopen the product
questions below without an explicit new decision.

---

## Problem

Source-value → GL mapping (Haiku `AccountMapper`) is computed every upload and
then thrown away with `runs.parse_preview`. The same vendor is remapped from
scratch each month. Payroll people are also pushed through that review, which
is the wrong loop for a payroll file.

This is **not** the column → GAAP mapping on `accounts`. Do not reuse
`AccountsRepo.upsert_mapping` for vendor names.

---

## Locked decisions

| Decision | Choice |
|---|---|
| What to remember | Vendor names and general expense items (electricity, phones, vehicle rentals, other AP-style lines) |
| What not to remember | Payroll people. Payroll is not a mapping dictionary. |
| How payroll enters the close | Straight into the process as the file's lines: a grand total, or sub-lines such as meals / office rent / salary / bonus, kept as those names |
| Haiku vs saved mapping | Haiku still runs on remembered vendor rows. If it disagrees with the saved GL account, ask the user. |
| Sidebar | No Mapping nav item |
| Where to review this run | Upload flow, `MappingReview` |
| Where to revise later | Data page → **Saved names** tab |

Out of this slice: close checklist, 4-layer mapping, financial canvas, GL+dept
double-count fix, attestation columns.

---

## Data model

Table `source_account_mappings` (migration `0011`):

- Unique key: `(company_id, file_type, source_pattern)`
- `company_id` from the authenticated company only — never from the client
- RLS via owned company, same pattern as `accounts` / `runs`
- `file_type` may not be `payroll` or `general_ledger` (CHECK constraint)
- v1 writes **only** `supplier_invoices` (filename fallback is also this type,
  so `vehicle_expenses.xlsx` and similar expense workbooks are remembered)

No version history table. An upsert overwrites `gl_account` and `updated_at`.

---

## Pipeline behaviour

### Payroll files

1. Do not call Haiku.
2. Do not show rows in `MappingReview`.
3. Do not persist mappings.
4. Auto-map each non-empty line **to itself** (identity). If the name already
   exists in the GL pool, that is the GL account. If it does not (meals, rent,
   bonus), the line is still accepted as that account so the breakdown survives.
5. If payroll is the only non-GL file, skip `awaiting_mapping_confirmation`
   and apply (`parsing` → `applying_mapping` → consolidation).

### Vendor / expense files (`supplier_invoices`)

1. Load saved rows for this company.
2. Call Haiku on the unique source values (including remembered ones).
3. Annotate each draft row:
   - `new` — no saved row
   - `remembered` — saved GL equals Haiku, or Haiku returned nothing
   - `conflict` — saved GL and Haiku both present and differ
4. Pause for review when any row is `new` or `conflict`.
5. If every persistable row is `remembered`, auto-apply (same skip as payroll).
6. On confirm, upsert persistable decisions (user's choice wins).

### Other non-GL types (contracts, bank, processor)

Still go through Haiku + review. v1 does **not** persist them.

---

## UI

**Upload / MappingReview**

- No sidebar Mapping link.
- Copy talks about vendor and expense names, not "AI Account Mapping" as a
  product area.
- Surface conflicts first, then new names, then already-saved rows.
- Conflict rows are empty until the user picks. Show both the saved account
  and the Haiku suggestion.
- Payroll quick-apply is gone; payroll never appears here.

**Data / Saved names**

- Tab on the existing Data page (Entries | Saved names).
- List, change GL account, delete.
- Empty state: nothing saved yet; confirming vendors on upload will fill this.

---

## API

All routes resolve `company_id` from the JWT.

| Method | Path | Purpose |
|---|---|---|
| GET | `/source-mappings` | List saved names + current GL pool for the dropdown |
| PATCH | `/source-mappings/{id}` | Change `gl_account` |
| DELETE | `/source-mappings/{id}` | Forget a name |
| POST | `/runs/{id}/confirm-mappings` | Existing; now also upserts persistable decisions |

No client `company_id`. Do not log source patterns or cell values.

---

## Tests that must exist

- Payroll does not call Haiku and does not pause for mapping review.
- Payroll identity map keeps sub-line names.
- Saved vendor + matching Haiku → auto-apply, no review.
- Saved vendor + different Haiku → conflict, user must choose.
- Confirm upserts `supplier_invoices` only, never payroll.
- `PARSING` → `APPLYING_MAPPING` is a legal transition.
- GET/PATCH/DELETE are company-scoped; PATCH/DELETE on another company's id
  is 404/403, never a cross-tenant write.

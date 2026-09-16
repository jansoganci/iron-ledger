# Pre-analysis — Close checklist (raporu kapanış listesine çevir)

Status: Slice 1 implemented. Slice 2 not started.
Date: 2026-09-16.
Parent: `docs/02-planning/close-flow-contract.md`;
`docs/06-reports/close-process-by-sector.md` §5;
`docs/06-reports/pending-decisions-audit.md` §1.1;
`docs/sprint/field-service-close-triage.md` Bucket 1 item 6–7.
Checkout: `main`.

Process: (1) this pre-analysis → approval, (2) implementation as **two
slices**, (3) verification vs this file. Do not start coding until §10 is
locked.

---

## One-sentence diagnosis

The engine already compares department files to the GL. The report still
*reads* like a story plus a pile of cards, so the office manager cannot
answer “how many controls are left, what do I do next.” First action is
**regroup the existing payload**. It is not a new agent, not `closed`,
and not bank matching.

---

## Scope lock

| In this family | Out |
|---|---|
| Reorder the report: tie-out summary → exceptions by file type → flux/narrative → bank attestation line | `closed` / sign-off / period lock (contract slice 3) |
| Group recon by supporting-file type, not by dollar-severity pile | Day 0 expected-file manifest |
| One bank sentence + optional session checkbox (display-only) | Bank CSV / line matching |
| Soften “Verified” so it does not mean “close is done” | Open-item aging from last month |
| Excel: one attestation sentence on the existing recon sheet **or** a thin checklist sheet of the same groups | New agent, new table, 7th class, ERP |

Two slices. Not one PR that also invents five named controls, install/fuel
file types, and a file-total→GL map.

---

## 1. What this item actually is

A US field-service close is a **control list**, not a narrative:

1. Cash (bank = GL cash) — Month Proof does **not** do this.
2. Five subledger vs GL tie-outs — the engine already computes these.
3. Accruals / open items that must reverse.
4. Flux (variance story) — already written, currently shown **first**.
5. Package + lock the period.

Today the product does step 4 early and dumps step 2 as “Reconciliation
findings” sorted by `|delta|`. Coverage cards (GL line, no supporting
file) already sit in a grey “Not compared” block. That is progress. It is
still a **finding pile**, not “3 of 4 controls clean.”

Contract one-liner, still correct:

> Raporu close checklist’e çevir; motoru değiştirme.

---

## 2. What the code does today (evidence)

| Surface | Today |
|---|---|
| Report order | KPI strip → **narrative** → recon → Account Variance below (`ReportPage.tsx`, `ReportSummary.tsx`) |
| Recon grouping | Exception cards by `$5k / $500` severity; coverage separately (`ReconciliationPanel.tsx`) |
| Run machine | Terminal = `complete` / `*_failed`. **No `closed`.** |
| Excel | Three sheets: P&L, Reconciliations, Source Breakdown. No checklist sheet. |
| File types | `payroll`, `contracts`, `supplier_invoices`, `general_ledger`, plus Item 1 `bank_statement` / `processor_settlement`. **No install. No fuel.** |
| Item shape | `sources[].source_file` exists; frontend grouping does not use it |
| Materiality | `$100` AND `5%`, or `$500` hard — **already in** `consolidator.py`. Do not reopen. |
| Orphans | `card_kind=coverage` for GL-only — **already in**. Do not reopen. |
| Badge | “Verified · Guardrail Passed” on a `complete` report |

Sentinel five-file pack is **gone**. On disk:

- `docs/demo_data/sentinel/` — GL March + GL February only
- Living analog: **Redhawk** (GL + payroll + vendor + contracts)
- Riverbend is cash three-way, not the five P&L tie-outs

The August paper walk cannot be re-run as written until those four
department files exist again. That restore is **not** required to ship
slice 1 if Redhawk is the acceptance fixture.

---

## 3. Why this is two debts, not one button

### Debt A — the page lies about what is done

The user sees a story, then a severity grid, then a green Verified chip.
Nothing says “payroll tied out, contracts did not, bank was outside the
tool.” Grouping by `$5,000` answers the wrong question.

This debt is **frontend + copy**. Payload already has `sources`,
`card_kind`, `classification`.

### Debt B — “5/N” is not a real number yet

The contract’s five named controls are:

1. Payroll vs GL wages
2. Supplier vs GL COGS
3. Contracts × fee vs GL monitoring revenue
4. Install jobs vs GL install revenue
5. Fuel card vs GL vehicle

The engine emits **account cards**, not named controls. Install and fuel
are not `SourceFileType` values, so a filename like
`sentinel_installation_payments_*.xlsx` today falls through the detector
(likely `supplier_invoices` via “invoice”/nothing useful). Fuel has no
needle at all.

Real contract workbooks often have customer + fee, **not** a GL account
column. AccountMapper maps **row values** → GL account. It does not map
**this file’s total** → GL account X. The contract called that map
mandatory before first code. Putting it in the same PR as the UI regroup
hides a mapping outage inside a layout change.

### Same family, different blast radius

| | Debt A (page skeleton) | Debt B (named 5 + file-total map) |
|---|---|---|
| Touches | `ReportSummary`, `ReconciliationPanel`, maybe Excel sentence | `SourceFileType` / detector, mapping mode, possibly consolidator join |
| Failure mode | Ugly / wrong order | Wrong GL target → fake pass or fake fail |
| Demo | Redhawk 4 files | Needs install/fuel types + a file without `Account` |
| Migration | None if bank box is session-only | Maybe none; still a product contract, not a flag flip |

---

## 4. What is *not* the problem

- The six-class taxonomy. Do not add a 7th.
- Guardrail / Claude arithmetic. Numbers stay pandas.
- `_is_material` ($100 and 5%). Already shipped.
- Coverage vs `missing_je`. Already shipped.
- Duplicate-period re-run (`REPORT_FAILED` / silent replace). Separate
  family; more urgent for stuck runs, but not this screen.
- Email stub. Out.

---

## 5. Recommended slices (after approval)

### Slice 1 — regroup the report (no new engine)

1. Page order: (1) tie-out summary “N compared / M with a gap / K not
   compared”, (2) exceptions **grouped by supporting file type** derived
   from `sources[].source_file` + existing `_detect_file_type` labels,
   (3) coverage block unchanged in meaning, (4) narrative/flux, (5) one
   bank line: cash rec is outside Month Proof. Optional checkbox stored
   **only in the browser session** (no `0011`, no `closed`).
2. “Verified” copy: numbers passed the guardrail. Not “period closed.”
3. Groups we can name from types we already detect: Payroll, Vendors,
   Contracts, plus a leftover “Other supporting files” (Item 1 cash,
   unknown names). Do **not** invent Install / Fuel labels until slice 2.
4. Clean two-sided match (delta under the existing gate) already does
   not emit a card — that *is* a passed control. Count it in the summary
   from files present vs files that still have exception cards.
5. Tests: Redhawk-shaped fixture — payroll group exists; coverage stays
   out of “to review”; bank sentence renders; narrative is not above the
   summary. Intentional: a vendor gap still appears under Vendors.

Exit: an office manager can say in one glance which **file-typed**
control still has work. They do not count 16 grey cards as 16 failures.

### Slice 2 — make “5 of 5” true (pandas + types, then UI labels)

Do **not** start slice 2 by painting Install/Fuel on the page.

1. Decide the five names against **Redhawk + what we still lack**
   (install, fuel). Add detector needles only for files we will actually
   demo. Do not add truck-stock.
2. File-total → GL account map for supporting files that have no Account
   column. This is a mapping **mode**, not a new consolidator engine.
   Persistent source mappings (other branch, unmerged) are adjacent, not
   a substitute: they remember row values, not “this whole file is
   Service Revenue.”
3. Then rename the UI groups to the five controls. A passed control with
   no card still counts as passed.

Exit: “3 of 5 clean” is a pandas fact, not a CSS heading.

### Sequencing

Slice 1 then 2. Combining them hides a mapping miss inside a layout PR.
Slice 2 without 1 leaves the right math on a page that still leads with
prose.

`closed` / sign-off / lock stays **slice 3**, later, with a migration and
run-state work. Do not sneak it into 1.

---

## 6. Options considered and rejected

| Option | Why not |
|---|---|
| One PR: new `closed` status + checklist UI + five types | Contract forbade this. Period lock is a different machine. |
| Restore Sentinel four department xlsx as the first code | Useful fixture later; Redhawk already has four living files. Do not block UI on binary restore. |
| Drop coverage cards so the count looks like 4 | Already rejected in orphan policy: forgetting Rent looks like a clean close. |
| Persist bank checkbox in `0011` in slice 1 | Display-only is enough to stop lying. Persist when slice 3 locks the period. |
| Ask Claude to write “3 of 5” | Golden rule. Count in Python from cards + file types. |

---

## 7. Tests each slice must add

### Slice 1

1. Report order: summary heading before narrative in the tree.
2. Two exception cards from `*payroll*` and `*vendor*` filenames land in
   two groups, not one severity list.
3. Coverage item is not in “to review.”
4. Bank attestation sentence is in the page (and Excel if we touch the
   recon sheet).
5. Guardrail / classification tests unchanged.

### Slice 2

1. File with no Account column, mapped as a whole to one GL account,
   produces one two-sided item (not 16 coverage cards).
2. Install/fuel (or whatever names we lock) only appear if detector +
   fixture exist.
3. Invented 5th control with no file does not count as “passed.”

No live LLM. No `supabase db push`.

---

## 8. Files (implementation, not now)

### Slice 1

| File | Change |
|---|---|
| `frontend/src/components/ReportSummary.tsx` | Order; bank line; Verified copy |
| `frontend/src/components/ReconciliationPanel.tsx` | Group by file type |
| `frontend/src/pages/ReportPage.tsx` | Variance block stays **after** checklist+narrative |
| `backend/tools/excel_export.py` | Attestation sentence only if we touch the sheet |
| Tests colocated with those components / export |

### Slice 2

| File | Change |
|---|---|
| `backend/domain/contracts.py` `SourceFileType` | Only if we add install/fuel |
| `backend/agents/orchestrator.py` detector | Needles |
| Account mapping path | File-total mode |
| Same UI files | Rename groups to the five controls |

No `guardrail.py` tolerance change. No new classification.

---

## 9. Infra

Slice 1: no migration. Slice 2: no migration unless we persist a
file-total map table — prefer run-scoped mapping draft first.
Slice 3 (`closed`) is the first one that needs SQL + `RunStateMachine`.
Not this family.

---

## 10. Approval checklist

Reply with yes/no per row. Implementation of a slice starts only when that
slice is locked.

- [x] This is **two slices**, not “add closed + checklist in one job.”
- [x] Slice 1: regroup existing cards + bank sentence + Verified copy.
      No new file types. No `closed`. No SQL.
- [ ] Slice 2: named five controls + file-total→GL map, **after** 1.
- [x] Demo fixture for slice 1 is **Redhawk**, not restoring Sentinel binaries.
- [x] Do not reopen materiality, coverage/`missing_je`, or a 7th class.
- [x] Do not ask Claude to calculate N of M.
- [x] No live SQL / deploy in these slices.

If slice 1 is “no,” say whether we skip this family and take duplicate-period
re-run instead (stuck runs vs. wrong screen).
If slice 2 is “no,” slice 1 still ships a honest page for the types we have.

---

## SONUÇ — Slice 1

Counts live in `backend/tools/tie_out_summary.py` (uploaded filenames vs
exception cards). GET `/report` adds `tie_out_summary` and `tie_out_group`.
The report page leads with that summary, then exceptions by Payroll /
Vendors / Contracts / Other, then coverage, then narrative, then a
session-only bank checkbox. “Numbers verified” is not “period closed.”
Excel recon sheet carries the same bank sentence. No `closed` state, no
SQL, no install/fuel types.

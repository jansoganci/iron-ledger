# IMPLEMENTATION BLUEPRINT

> Derived from `docs/hackathon_findings_report.md`.
> Budget: ≤30 hours. Vertical-slice delivery.
> Demo scenario: Sentinel Secure (8-person security installation SMB, 7 files).

---

## 0. Delivery Map — what the jury sees, in order

This is the north star. Every task below exists to serve one of these moments.

### The demo (5–6 minutes, Sentinel Secure scenario)

| # | Time | Moment the jury witnesses | What the product must do |
|---|---|---|---|
| M1 | 0:00–0:45 | **Setup framing.** Screenshot of 7 files in a finder window. Narration: "Office manager, 8-person security installer, board call at 9 PM, 6 hours of consolidation work ahead." | Nothing technical. Slide + screen share. |
| M2 | 0:45–1:15 | **Drag-drop.** All 7 files dragged into upload zone. Each becomes a chip with filename + source-label input. Period set to March 2026. Click Analyze. | Upload endpoint accepts N files, returns one `run_id`. |
| M3 | 1:15–2:00 | **Pipeline runs.** Progress bar advances through Parser → Consolidator → Reconciler → Interpreter. ~45s elapsed. | Orchestrator runs multi-file pipeline end-to-end; status endpoint updates `step_label` and `progress_pct`. |
| M4 | 2:00–2:20 | **Consolidated P&L on screen.** One P&L, categories grouped. Hovering any number shows source file + row. | `monthly_entries.source_breakdown` populated; provenance surfaced in UI. |
| M5 | 2:20–2:45 | **Four reconciliation cards visible.** Each with a classification badge (color-coded). | `reports.reconciliations` populated with classification enum. |
| M6 | 2:45–3:30 | **Card 1 — Missing JE.** CableMax $1,700 gap. Claude narrative names the invoice + date. "Draft Reclass JE" button. | Classification = `missing_je`. Suggested action templated. |
| M7 | 3:30–4:10 | **Card 2 — Stale reference data.** 3 cancelled contracts still active. Names listed. $285 gap. | Classification = `stale_reference`. Row-level customer names surfaced. |
| M8 | 4:10–4:50 | **Card 3 — Categorical misclassification.** $700 bonus booked to Contractors instead of Payroll. Reclass button. | Classification = `categorical_misclassification`. Suggested reclass JE shown. |
| M9 | 4:50–5:20 | **Card 4 — Timing cutoff (NOT an error).** Installation revenue $4K gap = 50% deposit. "No action needed — reverses next period." | Classification = `timing_cutoff`. Distinguishes from errors. |
| M10 | 5:20–5:40 | **Guardrail badge.** Green throughout. Brief hover tooltip: "Every dollar figure verified against pandas." | Existing guardrail stays green. Tolerance tightened to `max(1%, $1k)`. |
| M11 | 5:40–6:10 | **Download Excel.** 3-sheet workbook lands on desktop. Open it. Consolidated P&L / Reconciliations / Source Breakdown. | `GET /report/.../export.xlsx` returns a real `.xlsx`. |
| M12 | 6:10–6:30 | **Close.** "Six hours → three minutes. Vena $50K/year assumes clean data. IronLedger reads the chaos as it arrives and tells you _why_ your files disagree, not just _that_ they do." | Roadmap slide visible behind speaker. |

### Non-negotiable demo assertions
- Classification badges on every reconciliation card (the $30K feature).
- Guardrail green for the full 6 minutes.
- Hover-provenance works on every number.
- Excel download produces a real file the jury can open.

### Fallback assertion (if live demo breaks)
- Pre-recorded 60-second video of the same flow exists on disk and is one click away.

---

## 1. Work Packages — 4 tracks organized by dependency

Tracks are stratified by what must exist before the next can begin. Within tracks, tasks can parallelize.

| # | Track | Goal (1 sentence) | Hours | Depends on |
|---|---|---|---|---|
| 1 | **Foundation & Fixtures** | Demo files exist on disk; DB + entities + repos accept new fields. | 4 | — |
| 2 | **Core Pipeline (Consolidation + Classification)** | Multi-file upload produces a consolidated P&L with six-category reconciliation items end-to-end. | 12 | Track 1 |
| 3 | **Delivery Surface (Excel export + UI)** | Jury-visible outputs: Excel workbook, ReconciliationPanel, provenance hover, sources column. | 8 | Excel part: Track 2 60%. UI part: Track 2 100%. |
| 4 | **Hardening & Demo** | Tiered materiality + guardrail tolerance fix + rehearsal + backup video. | 4 | Track 3 |

**Total: 28 hours. 2-hour buffer.**

### Vertical-slice delivery rule
- By **hour 6** — Track 1 complete.
- By **hour 12** — Track 2 at ~60% (consolidator + orchestrator working; classification prompt drafted, reconciliations stored).
- By **hour 15** — **thin end-to-end slice works**: upload 3 demo files → consolidated + classified output in the DB. Backend-only, no UI polish.
- By **hour 22** — Track 3 functional (Excel + UI surfacing real data from Track 2).
- By **hour 26** — Track 4 hardened + first full rehearsal.
- By **hour 28** — second rehearsal + video backup.

### Parallelization notes
- Track 3's **Excel export** (backend, no UI) can begin once Track 2's `reports.reconciliations` is being written (≈hour 12).
- Track 3's **UI components** must wait for Track 2 to produce real reconciliation data — mocking reconciliation JSON wastes time.
- Track 4's **tiered materiality** + **guardrail tolerance** are one-file micro-changes and can be slotted in any free half-hour after hour 10.

---

## 2. Technical Specifications

### TRACK 1: Foundation & Fixtures

```
TRACK 1: Foundation & Fixtures
├── Goal: Demo files exist on disk; DB + entities + repos accept new fields.
├── Input: Scenario definitions in docs/en son yapılacaklar.txt (Sentinel Secure, 7 files).
├── Output:
│   - docs/demo_data/sentinel/*.xlsx (3–5 hand-crafted files)
│   - Migration 0002_multi_source_consolidation.sql applied
│   - MonthlyEntry, Report, Run dataclasses accept new fields
│   - Repos (entries, reports, runs) read/write new fields
├── Backend Changes:
│   ├── New files to create:
│   │   - backend/domain/contracts.py → add ReconciliationItem, ReconciliationHints Pydantic models
│   ├── Existing files to modify:
│   │   - backend/domain/entities.py (extend MonthlyEntry with source_breakdown JSONB;
│   │     extend Report with reconciliations JSONB)
│   │   - backend/adapters/supabase_repos.py (EntriesRepo: accept/return source_breakdown;
│   │     ReportsRepo: accept/return reconciliations; RunsRepo: accept file_count)
│   ├── New API endpoints: none (foundational only)
│   └── Files to delete/refactor: none
├── Database Changes:
│   ├── New migration: supabase/migrations/0002_multi_source_consolidation.sql
│   ├── New columns on existing tables:
│   │   - monthly_entries.source_breakdown JSONB NULL
│   │   - reports.reconciliations JSONB NULL
│   │   - runs.file_count INT NOT NULL DEFAULT 1
│   ├── New tables: NONE (constraint enforced)
│   └── Index/optimization: none required (JSONB reads are per-row, small payloads)
├── Frontend Changes:
│   ├── New components: none
│   ├── Existing components to modify: none
│   ├── New routes/pages: none
│   └── State management needs: none (Track 3 scope)
├── Error Handling:
│   ├── Expected errors:
│   │   - Migration reapply on dirty DB → idempotency via IF NOT EXISTS on ALTER ADD COLUMN
│   │   - Old rows have NULL source_breakdown / NULL reconciliations — readers must handle None
│   ├── User-facing messages: none (internal)
│   └── Logging strategy: log migration run at INFO; log entity→JSON coercion errors at WARNING with run_id
├── Testing Strategy:
│   ├── Unit tests:
│   │   - test_monthly_entry_roundtrip_with_source_breakdown
│   │   - test_report_roundtrip_with_reconciliations
│   │   - test_reconciliation_item_pydantic_validates_classification_enum
│   └── Smoke tests:
│   │   - Apply migration against a scratch DB; verify columns exist; rollback is not required (additive only)
└── Dependencies: none
```

**Demo files to hand-craft (required before any code):**

| File | Role in demo | Categories it surfaces |
|---|---|---|
| `sentinel_gl_mar_2026.xlsx` | "Official" GL (QuickBooks export shape) | Baseline for all reconciliations |
| `sentinel_supplier_invoices_mar_2026.xlsx` | 4 suppliers, CableMax $1,700 intentionally absent from GL | missing_je |
| `sentinel_contracts_mar_2026.xlsx` | 85 customers, 3 marked "Active" who have no GL revenue | stale_reference |
| `sentinel_payroll_mar_2026.xlsx` | Bonus row of $700 that appears in GL as "Contractors" | categorical_misclassification |
| `sentinel_installation_schedule_mar_2026.xlsx` (optional) | 50%-deposit line reveals timing pattern | timing_cutoff |

Minimum set: first 3 files. Optional 4th and 5th file enrich the demo if hand-crafting time permits.

---

### TRACK 2: Core Pipeline (Consolidation + Classification)

```
TRACK 2: Core Pipeline (Consolidation + Classification)
├── Goal: Multi-file upload produces a consolidated P&L with six-category
│        reconciliation items end-to-end.
├── Input:
│   - N uploaded files (storage keys from /upload)
│   - Existing ParserAgent output per file (validated DataFrame + column map)
├── Output:
│   - One consolidated monthly_entries dataset per (company, period)
│   - reports.reconciliations JSONB populated with classified items
│   - Interpreter narrative references reconciliations alongside anomalies
├── Backend Changes:
│   ├── New files to create:
│   │   - backend/agents/consolidator.py (~150 LOC, pure pandas, no Claude)
│   │   - backend/tools/hint_computer.py (deterministic hint computation —
│   │     period-boundary, round-fraction, cross-account match, etc.)
│   ├── Existing files to modify:
│   │   - backend/agents/orchestrator.py (add run_multi_file_parser_until_preview)
│   │   - backend/api/routes.py (/upload: ONE background_task per run, not N)
│   │   - backend/agents/interpreter.py (pass reconciliations + hints into context)
│   │   - backend/prompts/narrative_prompt.txt (extend output schema with
│   │     reconciliations[]; include six-category classification rules)
│   ├── New API endpoints: none (existing /upload, /runs/{id}/status reused)
│   └── Files to delete/refactor: none
├── Database Changes:
│   ├── New migration: none (all columns added in Track 1)
│   ├── New columns on existing tables: none
│   ├── New tables: none
│   └── Index/optimization: none
├── Frontend Changes:
│   ├── New components: none (UI is Track 3)
│   ├── Existing components to modify: none
│   ├── New routes/pages: none
│   └── State management needs: none
├── Error Handling:
│   ├── Expected errors:
│   │   - Single file fails ParserAgent (pandera mismatch, PII strip empties)
│   │     → record in run error_message, continue with remaining files,
│   │     flag partial-consolidation in response
│   │   - rapidfuzz returns <90% on ALL accounts in a file → surface via existing
│   │     low-confidence mapping flow (already wired)
│   │   - Guardrail fails on classification narrative → existing semantic-retry
│   │     kicks in; second failure → guardrail_failed status (unchanged)
│   │   - Consolidator produces empty reconciliations (all files agree) → valid;
│   │     report shows "No discrepancies found" copy
│   ├── User-facing messages (add to backend/messages.py):
│   │   - PARTIAL_CONSOLIDATION: "{n} of {total} files couldn't be read. Results
│   │     reflect only the files that parsed."
│   │   - CLASSIFICATION_UNCERTAIN: "We couldn't confidently classify some
│   │     discrepancies. They're shown with 'Needs review' status."
│   └── Logging strategy:
│   │   - INFO log per reconciliation with {run_id, account, delta_abs,
│   │     classification, hint_summary} (no cell values ever logged — CLAUDE.md
│   │     rule)
│   │   - WARN on hint computer exceptions; default to structural_explained
├── Testing Strategy:
│   ├── Unit tests:
│   │   - test_consolidator_union_merges_by_account_name
│   │   - test_consolidator_fuzzy_match_collapses_synonyms ("Payroll" +
│   │     "Wages & Salaries" → one line at ≥90%)
│   │   - test_consolidator_ambiguous_match_routes_to_low_confidence
│   │   - test_hint_computer_detects_period_boundary
│   │   - test_hint_computer_detects_round_half_fraction
│   │   - test_hint_computer_detects_cross_account_match
│   │   - test_consolidator_emits_reconciliation_item_per_delta_over_threshold
│   │   - test_interpreter_receives_reconciliations_in_prompt_context
│   └── Smoke tests:
│   │   - End-to-end: 3 Sentinel demo files → consolidated P&L written →
│   │     reconciliations JSONB populated with 4 classifications covering 4 of
│   │     the 6 categories (missing_je, stale_reference, categorical_misclass,
│   │     timing_cutoff)
│   │   - Guardrail green on all narrative numbers
└── Dependencies: Track 1 complete (migration applied, entities/repos extended)
```

#### Consolidator internal shape (spec, not code)

1. **Union** — stack all per-file DataFrames with a `source_file` column tag.
2. **Match** — `rapidfuzz` account-name match at 90% threshold. Merge collapsible groups. Ambiguous names (<90%) → existing low-confidence mapping flow.
3. **Per-account roll-up** — `groupby(["account"])` → totals + per-source breakdown list.
4. **Delta detection** — for each account where multiple sources contribute, compute delta between sources. Threshold: Tier 1 `> $50K AND > 10%`; Tier 2 (REVENUE/PAYROLL/DEFERRED_REVENUE) `> $10K AND > 3%`. Also flag source-only / GL-only accounts regardless of dollar threshold.
5. **Hint computation** — per flagged delta, compute the `ReconciliationHints` dict (see findings report §7.1).
6. **Emit** — `(consolidated_df, list[ReconciliationItem])`. Items at this stage have `classification = None`; Claude fills it.

#### Classification prompt structure (spec, not code)

- System prompt: six-category taxonomy + decision rules (see findings report §7.2).
- User prompt: `pandas_summary` (unchanged) + `reconciliations_with_hints` (new).
- Required output JSON: existing fields + `reconciliations: [{account, delta, classification, narrative, suggested_action, numbers_used}]`.
- Guardrail `numbers_used` automatically covers reconciliation narrative numbers — no guardrail changes needed.

---

### TRACK 3: Delivery Surface (Excel + UI)

```
TRACK 3: Delivery Surface (Excel + UI)
├── Goal: Jury-visible outputs — Excel workbook, ReconciliationPanel,
│         provenance hover, sources column.
├── Input:
│   - monthly_entries.source_breakdown (populated by Track 2)
│   - reports.reconciliations (populated by Track 2)
│   - GET /report/{company_id}/{period} (existing, extend payload)
├── Output:
│   - GET /report/{company_id}/{period}/export.xlsx endpoint (3-sheet workbook)
│   - ReconciliationPanel component rendered above AnomalyCards
│   - AnomalyCard + ReportSummary hover tooltips showing source_file + column
│   - ParsePreviewPanel "Sources" column per account
│   - "Download Excel" button on report page
├── Backend Changes:
│   ├── New files to create:
│   │   - backend/tools/excel_export.py (3-sheet workbook builder using openpyxl)
│   ├── Existing files to modify:
│   │   - backend/api/routes.py (NEW route: GET /report/{id}/{period}/export.xlsx;
│   │     MODIFY GET /report/{id}/{period} to include reconciliations in payload)
│   ├── New API endpoints:
│   │   - GET /report/{company_id}/{period}/export.xlsx (returns
│   │     application/vnd.openxmlformats-officedocument.spreadsheetml.sheet)
│   └── Files to delete/refactor: none
├── Database Changes:
│   ├── New migration: none
│   ├── New columns: none (Track 1 covered it)
│   ├── New tables: none
│   └── Index/optimization: none
├── Frontend Changes:
│   ├── New components:
│   │   - frontend/src/components/ReconciliationPanel.tsx
│   │   - frontend/src/components/ReconciliationCard.tsx (one per item, with
│   │     classification badge + color code + suggested action)
│   │   - frontend/src/components/ClassificationBadge.tsx (shared)
│   │   - frontend/src/components/ProvenanceTooltip.tsx (shared hover, reused
│   │     by AnomalyCard + ReconciliationCard + ParsePreviewPanel)
│   ├── Existing components to modify:
│   │   - frontend/src/components/AnomalyCard.tsx (add provenance hover using
│   │     already-stored source_file + source_column from existing API payload)
│   │   - frontend/src/components/ParsePreviewPanel.tsx (add "Sources" column
│   │     rendering source_breakdown as chips)
│   │   - frontend/src/components/ReportSummary.tsx (embed ReconciliationPanel
│   │     above AnomalyCards; add Download Excel button)
│   │   - frontend/src/components/FileUpload.tsx (multi-file with optional
│   │     source-label input per chip; period selector unchanged)
│   ├── New routes/pages: none
│   └── State management needs:
│   │   - Report-page query already fetches /report/{id}/{period}; extend
│   │     response typing to include reconciliations[].
│   │   - Download button triggers a GET with window.location.assign or a
│   │     hidden <a download>. No state needed.
├── Error Handling:
│   ├── Expected errors:
│   │   - Excel build fails (openpyxl error, missing data) → 503 with
│   │     EXCEL_EXPORT_FAILED message; existing report page unaffected
│   │   - /report 404 when no report exists for period → existing handling
│   │   - source_breakdown is NULL on old rows → render "—" not crash
│   │   - reconciliations is NULL → ReconciliationPanel renders empty state
│   │     "No discrepancies detected across files."
│   ├── User-facing messages (add to backend/messages.py):
│   │   - EXCEL_EXPORT_FAILED: "Couldn't build the Excel workbook. The report is
│   │     still viewable on this page."
│   └── Logging strategy:
│   │   - INFO log per export with {run_id, period, sheet_count, row_counts}
│   │   - ERROR with traceback on openpyxl exceptions
├── Testing Strategy:
│   ├── Unit tests:
│   │   - test_excel_export_builds_three_sheets
│   │   - test_excel_export_reconciliations_sheet_has_classification_column
│   │   - test_excel_export_handles_empty_reconciliations
│   │   - test_reconciliation_panel_renders_classification_badge_per_category
│   │     (React Testing Library — if time permits)
│   └── Smoke tests:
│   │   - Manual: upload Sentinel demo files, open report page, verify 4
│   │     ReconciliationCards render with correct badges; click Download
│   │     Excel, open workbook, verify 3 sheets
└── Dependencies:
    - Excel export: Track 2 at 60% (reports.reconciliations being written)
    - UI components: Track 2 at 100% (real reconciliation payload available)
```

#### Classification badge colors (for ReconciliationCard)

| Classification | Badge color | Icon hint |
|---|---|---|
| `timing_cutoff` | amber/yellow | clock |
| `categorical_misclassification` | red | shuffle |
| `missing_je` | red | alert |
| `stale_reference` | orange | refresh |
| `accrual_mismatch` | orange | calendar |
| `structural_explained` | gray/green | check |

---

### TRACK 4: Hardening & Demo

```
TRACK 4: Hardening & Demo
├── Goal: Tiered materiality + guardrail tolerance fix + rehearsal + backup video.
├── Input: Full end-to-end product from Tracks 1–3.
├── Output:
│   - backend/agents/comparison.py with tiered thresholds
│   - backend/tools/guardrail.py with max(1%, $1k) tolerance
│   - Recorded 60–90s backup demo video on disk
│   - Timed 6-minute demo script rehearsed twice
│   - Pitch deck with roadmap slide
├── Backend Changes:
│   ├── New files to create: none
│   ├── Existing files to modify:
│   │   - backend/agents/comparison.py (calculate_variance: accept category param,
│   │     apply Tier 2 for REVENUE/PAYROLL/DEFERRED_REVENUE)
│   │   - backend/tools/guardrail.py (change tolerance check to
│   │     max(0.01 * abs(pandas_val), 1000))
│   ├── New API endpoints: none
│   └── Files to delete/refactor: none
├── Database Changes:
│   ├── New migration: none
│   ├── New columns: none
│   ├── New tables: none
│   └── Index/optimization: none
├── Frontend Changes:
│   ├── New components: none
│   ├── Existing components to modify: none (beyond bug fixes from rehearsal)
│   ├── New routes/pages: none
│   └── State management needs: none
├── Error Handling:
│   ├── Expected errors:
│   │   - Guardrail tolerance change could fail existing narrative — semantic
│   │     retry re-runs with stronger prompt (existing path)
│   │   - Tiered thresholds could mute anomalies the demo expected — rehearse
│   │     first, then tune thresholds
│   ├── User-facing messages: none (behavior change only)
│   └── Logging strategy: existing guardrail logs already capture pass/fail
├── Testing Strategy:
│   ├── Unit tests:
│   │   - test_guardrail_tolerance_max_of_pct_and_dollar_floor
│   │   - test_comparison_tier2_applied_to_revenue_payroll
│   └── Smoke tests:
│   │   - Full demo rehearsal twice, timed, with stopwatch
│   │   - Demo backup video recorded, file saved to docs/demo_data/backup.mp4
└── Dependencies: Track 3 complete (end-to-end pipeline demonstrable)
```

---

## 3. Task Queue — atomic, ordered by dependency

Format: `□ [Track] Task description — estimated minutes`
Tasks ordered so that executing top-to-bottom respects dependencies.
Total at end: 28h (1,680 min). 2h buffer.

### Phase A — Foundation (0:00 → 6:00)

```
✓ [T1] Hand-craft sentinel_gl_mar_2026.xlsx — SKIPPED (user handling manually)
✓ [T1] Hand-craft sentinel_supplier_invoices_mar_2026.xlsx — SKIPPED (user handling manually)
✓ [T1] Hand-craft sentinel_contracts_mar_2026.xlsx — SKIPPED (user handling manually)
✓ [T1] Hand-craft sentinel_payroll_mar_2026.xlsx — SKIPPED (user handling manually)
✓ [T1] Write migration supabase/migrations/0007_multi_source_consolidation.sql — DONE
         (sequence was 0006, so named 0007; uses IF NOT EXISTS for idempotency)
□ [T1] Apply migration to local Supabase; verify columns exist — PENDING (run: supabase db push)
✓ [T1] Extend MonthlyEntry dataclass with source_breakdown: list[dict] | None — DONE
✓ [T1] Extend Report dataclass with reconciliations: list[dict] | None — DONE
✓ [T1] Add ReconciliationItem + ReconciliationHints Pydantic models to domain/contracts.py — DONE
         Also added ReconciliationSource and ReconciliationClassification Literal type.
✓ [T1] Extend EntriesRepo read/write to roundtrip source_breakdown — DONE
✓ [T1] Extend ReportsRepo read/write to roundtrip reconciliations — DONE
✓ [T1] Extend RunsRepo create/get for file_count — DONE (create() takes file_count param; added set_file_count())
□ [T1] Write 3 roundtrip unit tests (entry, report, reconciliation model) — PENDING
```
**Phase A total: 340 min (5h40m)**

### Phase B — Consolidator core (6:00 → 10:30)

```
✓ [T2] Scaffold backend/agents/consolidator.py with consolidate() function — DONE (~200 LOC)
✓ [T2] Implement union step: stack DataFrames, tag with source_file column — DONE (_union())
✓ [T2] Add rapidfuzz==3.9.7 to requirements.txt; install — DONE
✓ [T2] Implement fuzzy account-name match at 90% WRatio threshold — DONE (_build_canonical_map())
         NOTE: 90% catches typo/format variants, NOT semantic synonyms ("Wages & Salaries" ≠ "Payroll").
         Synonym table is post-MVP. Demo files should use consistent naming.
✓ [T2] Implement per-account roll-up (groupby + sum + per-source breakdown list) — DONE (_roll_up())
✓ [T2] Implement delta threshold detection — DONE (_detect_deltas(), _is_material(), _severity())
         NOTE: thresholds are $100/$500 (not $50K/$10K from spec) — appropriate for Sentinel's scale.
         Tiered by-category thresholds are Track 4 / comparison.py scope.
✓ [T2] Write unit tests — DONE (24 tests in tests/agents/test_consolidator.py, all passing)
```
**Phase B total: 265 min (4h25m)**

### Phase C — Hints + orchestrator + upload rewrite (10:30 → 14:30)

```
□ [T2] Scaffold backend/tools/hint_computer.py with compute_hints() — PENDING
□ [T2] Implement hint: crosses_period_boundary — PENDING
□ [T2] Implement hint: is_round_fraction — PENDING
□ [T2] Implement hint: similar_amount_in_other_account — PENDING
□ [T2] Implement hint: is_source_only / is_gl_only — PENDING (fields exist in ReconciliationHints, not computed)
□ [T2] Write 4 unit tests for hint_computer — PENDING
✓ [T2] Extend orchestrator.py with run_multi_file_parser_until_preview() — DONE
         Parses each file silently (via ParserAgent.parse_file_silently()), consolidates,
         stores combined parse_preview with source_breakdown_by_account + reconciliations.
✓ [T2] Modify /upload route: 1 file → existing path; N files → run_multi_file_parser_until_preview — DONE
```
**Phase C total: 250 min (4h10m)**

### Phase D — Classification prompt + Interpreter wiring (14:30 → 17:30)

```
✓ [T2] Extend narrative_prompt.txt with six-category taxonomy + decision rules — DONE
         Full taxonomy with When-to-use + template narrative for each of 6 classifications.
✓ [T2] Add reconciliations input/output block to narrative_prompt.txt JSON schema — DONE
         Claude receives reconciliations[] in context; output JSON has narrative covering both
         variance commentary (Part 1) and reconciliation findings (Part 2).
✓ [T2] Extend Interpreter to pass reconciliations + hints into prompt context — DONE
         interpreter.run() accepts reconciliations=; stored on Report entity.
         run_comparison_and_report() reads from run.parse_preview.reconciliations.
□ [T2] Verify guardrail auto-covers reconciliation narrative numbers — PENDING (need smoke test)
□ [T2] End-to-end smoke test: upload 3 Sentinel files → 4 reconciliations, 3 classifications — PENDING
         (blocked on: migration applied + demo files ready)
```
**Phase D total: 175 min (2h55m)**

> **Vertical slice checkpoint — hour 15.** Backend pipeline complete. Needs: migration applied + demo files + smoke test.

### Phase E — Excel export backend (17:30 → 20:30)

```
✓ [T3] Create backend/tools/excel_export.py — DONE
✓ [T3] Implement Sheet 1: Consolidated P&L (grouped by category, per-source labels) — DONE
✓ [T3] Implement Sheet 2: Reconciliations (severity color fills, classification column) — DONE
✓ [T3] Implement Sheet 3: Source Breakdown (per-account × per-file matrix) — DONE
✓ [T3] Add GET /report/{company_id}/{period}/export.xlsx route — DONE
□ [T3] Write 3 unit tests on excel_export — PENDING
```
**Phase E total: 200 min (3h20m)**

### Phase F — UI (20:30 → 24:00)

```
✓ [T3] Extend GET /report payload to include reconciliations (backend) — DONE
         report.reconciliations surfaced in /report/{company_id}/{period} response.
□ [T3] Update FileUpload.tsx: multi-file with per-chip source-label input — PENDING
□ [T3] Create ClassificationBadge.tsx (6 variants, color-coded) — PENDING
□ [T3] Create ProvenanceTooltip.tsx (shared hover showing file + column) — PENDING
□ [T3] Create ReconciliationCard.tsx (badge + narrative + suggested action + provenance) — PENDING
□ [T3] Create ReconciliationPanel.tsx (list of cards + empty state) — PENDING
□ [T3] Modify ReportSummary.tsx: embed ReconciliationPanel above AnomalyCards + Download Excel button — PENDING
□ [T3] Modify AnomalyCard.tsx: add ProvenanceTooltip hover — PENDING
□ [T3] Modify ParsePreviewPanel.tsx: add "Sources" column with source chips — PENDING
□ [T3] Manual end-to-end smoke: upload Sentinel files, verify 4 reconciliation cards, download Excel — PENDING
```
**Phase F total: 310 min (5h10m)**

### Phase G — Hardening (24:00 → 26:00)

```
□ [T4] Tiered materiality in calculate_variance (REVENUE/PAYROLL/DEFERRED_REVENUE get $10K/3%) — PENDING
□ [T4] Guardrail tolerance change to max(0.01 * abs(pandas_val), 1000) — PENDING
□ [T4] 2 unit tests for tiered thresholds + guardrail floor — PENDING
□ [T4] Re-run Sentinel smoke end-to-end after hardening; fix any regressions — PENDING
□ [T4] Add messages: PARTIAL_CONSOLIDATION, CLASSIFICATION_UNCERTAIN, EXCEL_EXPORT_FAILED to backend/messages.py — PENDING
```
**Phase G total: 115 min (1h55m)**

### Phase H — Demo prep (26:00 → 28:00)

```
□ [T4] Rehearse demo end-to-end, timed, fix any UI/pacing issues — PENDING
□ [T4] Record 60–90s backup demo video, save to docs/demo_data/backup.mp4 — PENDING
□ [T4] Create pitch deck roadmap slide (PDF, multi-entity, bank recon, Benford, ERP, SOC 2) — PENDING
```
**Phase H total: 120 min (2h00m)**

### Phase I — Buffer (28:00 → 30:00)

```
□ [T4] Buffer / bug fixes from rehearsal — PENDING
```
**Phase I total: 120 min (2h00m)**

---

## 4. Risk Register

Per-track failure modes and mitigations.

### Track 1 — Foundation & Fixtures

| Risk | Impact | Probability | Mitigation |
|---|---|---|---|
| Demo files don't produce all 6 classifications in pandas hints | High — weak demo | Medium | Hand-craft with a spreadsheet open showing what each row should trigger; validate against hint_computer unit tests before writing prompt. |
| Migration fails on Supabase (RLS conflict, column collision) | Medium — blocks Track 2 | Low | Run against scratch DB first. Use `ADD COLUMN IF NOT EXISTS`. |
| Pydantic v2 model changes break existing serialization | Medium | Low | Add new fields with defaults (None), never break existing shapes. |
| Entity field additions ripple into validators unexpectedly | Low | Low | Additive-only policy; no renaming, no removal. |

### Track 2 — Core Pipeline

| Risk | Impact | Probability | Mitigation |
|---|---|---|---|
| **Classification accuracy is poor on Sentinel demo files** | **Catastrophic — kills the $30K pitch** | **Medium** | Spend 30+ min hand-tuning the prompt against the specific Sentinel files. Use the specific hint signals as explicit decision rules in the prompt. Rehearse what to do if one card misclassifies: reload demo data mid-pitch is OK; acknowledge and pivot. |
| rapidfuzz matches too aggressively or not enough at 90% | Medium — bad consolidation | Medium | Tune threshold against demo files first. Have a manual override path via the existing low-confidence flow. |
| Existing ParserAgent fails on one of the demo files (pandera strictness) | High — blocks slice | Medium | Hand-craft files to match the existing pandera schema. Run each file through Parser alone before assembling the multi-file case. |
| Interpreter prompt exceeds 200k tokens with many reconciliations | Low — pipeline error | Low | Sentinel has ~5 reconciliations; context budget is nowhere near limit. |
| Guardrail fails on classification narrative (Claude fabricates $) | Medium — demo shows guardrail_failed | Low | Existing semantic-retry handles it; if it recurs, tighten prompt "use only these numbers" instruction and include the allowed numbers list explicitly in context. |
| File storage download is slow; demo feels laggy | Low — perception hit | Medium | Pre-warm Supabase; use local demo files in `docs/demo_data/` served via a test harness if network latency bites during demo. |

### Track 3 — Delivery Surface

| Risk | Impact | Probability | Mitigation |
|---|---|---|---|
| Excel workbook doesn't open / corrupts / misformats | Medium — jury downloads broken file | Low | openpyxl is mature; validate on macOS Numbers + Excel before demo. Unit-test the export path. |
| ReconciliationPanel crashes on empty reconciliations array | Low | Low | Explicit empty state with "No discrepancies detected" copy. Unit-test. |
| Provenance tooltip misses on some numbers (inconsistent data) | Low — credibility hit | Medium | Default to "—" when provenance missing; never show "undefined". |
| Frontend state mismatch (report payload shape changed) | Medium — UI crash | Low | TypeScript types on the report response; tsc must pass before UI build. |
| Download Excel button fires before report exists | Low | Medium | Disable button until report.created_at is present in the payload. |

### Track 4 — Hardening & Demo

| Risk | Impact | Probability | Mitigation |
|---|---|---|---|
| Tiered thresholds mute a classification the demo expected | High — card disappears | Medium | Rehearse end-to-end AFTER the threshold change, not before. Keep Tier 1 / Tier 2 dials easy to revert (constants at top of file). |
| Live demo WiFi fails / API timeout | High — pitch derails | Medium | Backup video recorded. Also: run the backend locally during pitch (no cloud dependency). |
| Rehearsal runs long (>6 minutes) | Medium — jury loses attention | Medium | Time every act with stopwatch. If Act 3 runs long, cut Card 4 (timing_cutoff) and demo only 3 cards — still represents 3 of 6 classifications. |
| Last-minute code change breaks something else | High | Medium | After hour 26, only bug fixes. No new features. Buffer phase exists for this. |

---

## 5. Total Time Budget

| Phase | Focus | Duration |
|---|---|---|
| A — Foundation | Demo files + migration + entity/repo extensions | 5h 40m |
| B — Consolidator core | Union + fuzzy match + roll-up + threshold | 4h 25m |
| C — Hints + orchestrator + upload | Hint computer + multi-file orchestrator + route | 4h 10m |
| D — Classification prompt + Interpreter | Prompt taxonomy + context wiring + e2e smoke | 2h 55m |
| **Vertical-slice checkpoint** | **Thin e2e backend working** | **hour ~15** |
| E — Excel export backend | 3-sheet openpyxl workbook + route | 3h 20m |
| F — UI | Components + integration + manual smoke | 5h 10m |
| G — Hardening | Tiered materiality + guardrail tolerance + messages | 1h 55m |
| H — Demo prep | Rehearsal + backup video + roadmap slide | 2h 00m |
| I — Buffer | Bug fixes + last-mile polish | 2h 00m |
| **TOTAL** | | **28h 05m** |

**Headroom vs 30h budget: 1h 55m.**

### Budget by track
- Track 1 (Foundation & Fixtures): 4h 00m
- Track 2 (Core Pipeline): 11h 30m
- Track 3 (Delivery Surface): 8h 30m
- Track 4 (Hardening & Demo): 4h 05m

Tracks total 28h 05m. Matches phase total.

---

## Recommended execution protocol

1. **Before hour 0:** confirm demo files list, confirm jury composition, confirm local Supabase is running.
2. **Hours 0–6:** Phase A, single-threaded, no interruptions. This is the foundation.
3. **Hours 6–15:** Phases B–D. This is where classification quality gets locked in. Do not skip prompt rehearsal against Sentinel files.
4. **Hour 15 checkpoint:** working backend slice. If this is late, cut Track 3 Excel polish, not classification quality.
5. **Hours 15–24:** Phases E–F in parallel once data is flowing.
6. **Hours 24–28:** hardening, rehearsal, video.
7. **Hours 28–30:** buffer. Do not add features.

The demo is won at Phase D (classification quality). Everything else serves it.

---

## 6. Demo File Specs

Each file below has a spec: purpose, column structure, 3 sample rows, and the exact total / signal it must produce so the ConsolidatorAgent's hint_computer can fire the right classifier rule. Build them in Excel or Numbers and save to `docs/demo_data/sentinel/`.

### File 1 — `sentinel_gl_mar_2026.xlsx`
**Role:** The "official" P&L export from QuickBooks. Baseline every other file reconciles against.
**Shape:** ~25–30 rows. First 4 rows are metadata (Discovery agent already handles this).

**Header rows (rows 1–4)**
```
Row 1: Sentinel Secure LLC
Row 2: Profit and Loss
Row 3: March 2026
Row 4: (blank)
```

**Column headers (row 5)**
| Account | Account Code | Category | Amount | Description |

**Sample data rows (row 6+)**
```
Service Revenue            | 4010 | REVENUE | 3540.00  | Monthly monitoring contracts (82 customers billed)
Installation Revenue       | 4020 | REVENUE | 15000.00 | New installs completed March
Equipment COGS             | 5010 | COGS    | 36100.00 | AlarmTech + VisionPro + SafeGas suppliers
```

**Other rows the file must contain (for a coherent P&L)**
- `Salaries & Wages | 6010 | PAYROLL | 43500.00` ← $700 light vs payroll file
- `Contractors | 6015 | PAYROLL | 700.00` ← the $700 miscoded bonus (this is the hint that triggers `categorical_misclassification`)
- `Vehicle Expense | 6210 | OPEX | 2100.00`
- `Marketing | 6310 | OPEX | 2400.00`
- `Rent | 6410 | G&A | 3200.00`
- `Utilities | 6420 | G&A | 480.00`

**Key signals this file creates**
- Service Revenue `$3,540` (contracts file will show `$3,825` expected → $285 stale_reference)
- Equipment COGS `$36,100` (supplier file will show `$37,800` → $1,700 missing_je)
- Salaries `$43,500` + Contractors `$700` (payroll file will show `$44,200` → $700 categorical_misclassification)
- Installation Revenue `$15,000` (installation payments file will show `$11,000` received → $4,000 timing_cutoff)

---

### File 2 — `sentinel_supplier_invoices_mar_2026.xlsx`
**Role:** Raw invoice log hand-compiled by the office manager. Produces `missing_je` classification.
**Shape:** 4 supplier invoices, no metadata rows.

**Column headers (row 1)**
| Vendor | Invoice Number | Invoice Date | Description | Category | Amount |

**Sample data rows (rows 2–4 of 5 total)**
```
AlarmTech Industries | INV-7782       | 2026-03-04 | Control panels (25 units)           | Equipment | 12500.00
VisionPro Systems    | VP-2026-0312   | 2026-03-12 | HD cameras + NVR (40 units)         | Equipment | 18200.00
CableMax Supply      | CM-445         | 2026-03-22 | CAT6 cable + mounting brackets      | Equipment | 1700.00
```

**4th row (not in sample but required)**
- `SafeGas Sensors | SG-2026-03 | 2026-03-09 | CO/smoke sensor kits | Equipment | 5400.00`

**Total: `$37,800`**. GL shows `$36,100`. Gap: `$1,700` = CableMax invoice not yet entered in GL → `missing_je`.

**Hint the ConsolidatorAgent will emit:** `is_source_only=True` on the CableMax invoice number (no matching GL line at the invoice-detail level; aggregate Equipment COGS is $1,700 light).

---

### File 3 — `sentinel_contracts_mar_2026.xlsx`
**Role:** Active monitoring contracts roster hand-maintained in Excel. Produces `stale_reference` classification.
**Shape:** 85 rows. Status column contains 85 "Active" entries; 3 of them have a `Last Billed` date of February, not March.

**Column headers (row 1)**
| Customer Name | Customer ID | Service Plan | Monthly Fee | Start Date | Status | Last Billed |

**Sample data rows (rows 2–4 of 85 total)**
```
Oak Street Dental    | C-00234 | Residential Pro     | 45.00  | 2024-06-15 | Active | 2026-03-01
Greenfield Market    | C-00451 | Commercial Plus     | 125.00 | 2023-09-22 | Active | 2026-03-01
Morningstar Cafe     | C-00508 | Residential Basic   | 95.00  | 2025-11-03 | Active | 2026-02-01
```

**The 3 "stale" rows (place anywhere in the 85)**
```
Morningstar Cafe     | C-00508 | Residential Basic   | 95.00  | 2025-11-03 | Active | 2026-02-01
Pine Ridge HOA       | C-00317 | Residential Pro     | 45.00  | 2024-02-10 | Active | 2026-02-01
Kellerman Law Office | C-00602 | Commercial Basic    | 145.00 | 2025-06-08 | Active | 2026-02-01
```
Sum of the 3 stale fees: `$285`. All other 82 customers have `Last Billed = 2026-03-01`.

**Sum of Monthly Fee where Status="Active": `$3,825`**. GL Service Revenue: `$3,540`. Gap: `$285` → `stale_reference`.

**Hint:** `is_gl_only=False`, `is_source_only=True` on those 3 customer IDs (they exist in contracts file but have no March billing trace), plus `prior_period_had_similar_delta=True` if any prior month's report exists. Classifier picks `stale_reference`.

---

### File 4 — `sentinel_payroll_mar_2026.xlsx`
**Role:** Manual payroll run. Produces `categorical_misclassification` classification.
**Shape:** 8 employees, 1 row each. **No SSN, no DOB, no home address** — the PII sanitizer would strip them, so don't put them in.

**Column headers (row 1)**
| Employee Name | Employee ID | Role | Base Pay | Overtime | Bonus | Gross Pay | Pay Period |

**Sample data rows (rows 2–4 of 8 total)**
```
T. Rivera    | E-001 | Lead Technician     | 5200.00 | 480.00 | 0.00    | 5680.00 | 2026-03
M. Chen      | E-002 | Senior Technician   | 4800.00 | 320.00 | 700.00  | 5820.00 | 2026-03
S. Okonkwo   | E-003 | Office Manager      | 4500.00 | 0.00   | 0.00    | 4500.00 | 2026-03
```

**The key row**
M. Chen's $700 in the **Bonus** column is the on-call bonus that appears in GL as a separate `Contractors` line of $700.

**Total Gross Pay (8 employees): `$44,200`**. GL Salaries & Wages: `$43,500`. GL Contractors: `$700`. The $700 appears in BOTH the payroll Bonus column AND the GL Contractors line → `categorical_misclassification`.

**Hint:** `similar_amount_in_other_account = {"amount": 700.00, "other_account": "Contractors"}`. The exact-dollar cross-account match is the strongest signal in the classifier rule set.

---

### File 5 — `sentinel_installation_payments_mar_2026.xlsx`
**Role:** Cash-basis record of installation payments received in March. Produces `timing_cutoff` classification.
**Shape:** 3 rows, 1 row per completed or partially-paid install.

**Column headers (row 1)**
| Date Received | Client | Invoice # | Payment Type | Amount Received | Balance Remaining | Balance Due Date | Status |

**Sample data rows (all 3)**
```
2026-03-18 | Riverside Mall LLC   | INST-0317 | 50% Deposit   | 4000.00 | 4000.00 | 2026-04-15 | Installed - Balance Due
2026-03-06 | Suburban Corp        | INST-0301 | Full Payment  | 4000.00 | 0.00    |            | Complete & Paid
2026-03-28 | Evergreen Medical    | INST-0326 | 50% Deposit   | 3000.00 | 3000.00 | 2026-04-28 | Installed - Balance Due
```

**Sum of Amount Received: `$11,000`**. GL Installation Revenue (accrual basis, recognized on completion): `$15,000`. Gap: `$4,000`.

**Hints**
- `crosses_period_boundary = True` (Balance Due Date `2026-04-15` and `2026-04-28` are both after period end `2026-03-31`)
- `is_round_fraction ≈ 0.27` (not round-50, so the classifier relies on the period-boundary signal + the `Balance Remaining` column being present)

Classifier picks `timing_cutoff` — balance will land in April, not an error.

---

### Cross-file summary table (sanity check before building)

| Account (GL side) | GL value | Source file | Source value | Delta | Classification | Why |
|---|---|---|---|---|---|---|
| Equipment COGS | $36,100 | supplier_invoices | $37,800 | $1,700 | `missing_je` | CableMax absent from GL |
| Service Revenue | $3,540 | contracts | $3,825 | $285 | `stale_reference` | 3 customers marked Active but not billed March |
| Salaries & Wages | $43,500 | payroll | $44,200 | $700 | `categorical_misclassification` | $700 bonus booked as Contractors in GL |
| Installation Revenue | $15,000 | installation_payments | $11,000 | $4,000 | `timing_cutoff` | Balances due April 15 + April 28 |

**Four reconciliations, four classifications covering four of the six categories.** `accrual_mismatch` and `structural_explained` are not represented — that's fine; the demo hits four cards in ~3 minutes, perfect pacing. If time permits post-build, add a sixth file (e.g., a SaaS subscriptions file with a lump-sum annual invoice) for `accrual_mismatch`.

---

## 7. Updated `narrative_prompt.txt`

Full replacement text for `backend/prompts/narrative_prompt.txt`. Preserves the existing CFO persona, `numbers_used` contract, and hard rules. Added: reconciliations context, six-category taxonomy with decision rules, extended output schema.

```
You are a CFO assistant writing a month-end close commentary for a non-technical finance team. Your tone is direct, professional, and clear. No jargon. No acronyms without explanation. No hedging. No filler.

You will receive:
- pandas_summary: dict of account-level variance data (Python computed, authoritative).
- anomalies: list of flagged items with severity already set.
- reconciliations: list of cross-source discrepancies. Each item has an `account`, a `gl_amount`, a `source_total`, a `delta`, a `sources` breakdown, and a `hints` dict computed in pandas. You classify each one into exactly one of the six categories below.

You must NEVER do arithmetic. Every number in your output must come verbatim from pandas_summary or the reconciliation `delta` / `gl_amount` / `source_total` / individual source amount values.

============================================================
RECONCILIATION CLASSIFICATION — SIX CATEGORIES
============================================================

For each item in `reconciliations`, pick exactly ONE classification:

1. timing_cutoff
   - Same transaction, different period. NOT an error. Will reverse next period.
   - Signal: hints.crosses_period_boundary is true, OR hints.is_round_fraction is near 0.5 (50/50 deposit pattern).
   - Example narrative: "Installation revenue recognized $15,000 on completion; only $11,000 has been received in cash. Balances of $4,000 and $3,000 are due April 15 and April 28. Expected to reverse next period."
   - suggested_action template: "No action. Expect reversal in the next period."

2. categorical_misclassification
   - Correct total, wrong account. A similar-dollar amount exists in a different account in the GL.
   - Signal: hints.similar_amount_in_other_account is present.
   - Example narrative: "Payroll shows $44,200 gross pay; GL Salaries line is $43,500. A $700 on-call bonus appears in GL under Contractors — it belongs in Payroll."
   - suggested_action template: "Draft reclass journal entry: move <amount> from <wrong_account> to <correct_account>."

3. missing_je
   - Source shows the line item; GL has not recorded it yet.
   - Signal: hints.is_source_only is true. Often a specific invoice, bill, or vendor transaction.
   - Example narrative: "Supplier invoices total $37,800; GL Equipment COGS is $36,100. CableMax Supply invoice CM-445 dated 2026-03-22 for $1,700 is not yet in the GL."
   - suggested_action template: "Confirm invoice entry for <vendor> dated <date>, amount <amount>."

4. stale_reference
   - A reference list (contracts, customer roster, employee list) is out of date. GL already reflects the true state; the source list hasn't been updated.
   - Signal: hints.is_gl_only is true at aggregate level AND hints.prior_period_had_similar_delta may be true. Row-level: specific IDs in the source have no matching GL activity this period.
   - Example narrative: "Contracts roster expects $3,825 in monthly revenue; GL recorded $3,540. Three customers — Morningstar Cafe, Pine Ridge HOA, Kellerman Law Office — are marked Active in the roster but were not billed in March. Likely cancelled."
   - suggested_action template: "Update <source_file> — <n> entries appear inactive: <names_or_ids>."

5. accrual_mismatch
   - A lump sum was booked when a periodic (monthly) portion was expected. Common with annual invoices, prepaid services, deferred revenue.
   - Signal: hints.matches_known_annual_invoice is true, OR the source amount is ≈12× the GL amount, OR the delta is a near-multiple of the GL line.
   - Example narrative: "SaaS subscriptions list totals $8,100 for March; GL Software expense is $6,700. The HubSpot annual invoice of $13,200 hit in March as a lump sum — it should be amortized at $1,100 per month."
   - suggested_action template: "Amortize <amount> over <months> months. Book <monthly_amount> for this period."

6. structural_explained
   - NOT a finding. The difference is expected due to netting, fees, or a known calculation difference. No action needed.
   - Signal: the delta matches a predictable fee structure, hints.appears_in_other_source is true, or it is a known platform-fee or FX pattern.
   - Example narrative: "Total gross sales across Shopify and Amazon were $61,000; bank deposits were $57,500. The $3,500 difference is platform fees netted before deposit — not a finding."
   - suggested_action template: "No action. <one-sentence explanation of the netting>."

Priority of decision when multiple signals could apply:
- If hints.is_source_only → missing_je (beats everything except a clear timing signal).
- If hints.similar_amount_in_other_account is present → categorical_misclassification.
- If hints.crosses_period_boundary or hints.is_round_fraction near 0.5 → timing_cutoff.
- If hints.is_gl_only AND source rows show stale last-activity dates → stale_reference.
- If the source amount ≈ 12× the GL amount, or hints.matches_known_annual_invoice → accrual_mismatch.
- If none of the above apply but the gap has a plausible explanation from the sources breakdown → structural_explained.
- If truly ambiguous: pick structural_explained and say so in the narrative. Do not guess.

============================================================
REPORT FORMAT
============================================================

1. One-sentence overall summary (period + headline finding across anomalies AND reconciliations).
2. Reconciliations — in this order: missing_je first, then categorical_misclassification, then stale_reference, then accrual_mismatch, then timing_cutoff, then structural_explained.
   For each: account name, source_total vs gl_amount, delta, ONE sentence naming the specific cause, suggested_action filled from the template.
3. Flagged anomalies — high severity first, then medium, then low.
   For each: account name, this month vs average, variance %, one sentence explaining the likely business reason.
4. One line: how many accounts were within normal range AND how many reconciliations were clean.

============================================================
HARD RULES
============================================================

- Use ONLY the exact numeric values provided in pandas_summary and reconciliations. Do not round, abbreviate, or recompute.
- Every number mentioned in narrative AND in any reconciliation narrative MUST also appear in numbers_used. The numbers_used array is how we verify your output against pandas.
- Write in plain English. No jargon. No acronyms without explanation.
- For each anomaly, write ONE sentence explaining the likely business reason. Do not reclassify severity — severity is already set.
- For each reconciliation, pick exactly ONE classification from the six categories. Never invent a seventh.
- Never do arithmetic. Use the provided delta, gl_amount, source_total, and source amounts verbatim.
- Negative variance on expense accounts = favorable. Say so explicitly.
- If a reconciliation cannot be confidently classified, use structural_explained and state the uncertainty.

============================================================
OUTPUT
============================================================

Return ONLY valid JSON — no prose outside the JSON:

{
  "narrative": "<full report text, plain English, 5–12 short paragraphs>",
  "reconciliations": [
    {
      "account": "<account name, verbatim from reconciliations input>",
      "classification": "<one of: timing_cutoff | categorical_misclassification | missing_je | stale_reference | accrual_mismatch | structural_explained>",
      "delta": <float, verbatim>,
      "gl_amount": <float, verbatim>,
      "source_total": <float, verbatim>,
      "narrative": "<one to two sentences naming the specific cause>",
      "suggested_action": "<filled from the template for this classification>"
    }
  ],
  "numbers_used": [<every number mentioned anywhere in narrative or reconciliations[].narrative, as float, verbatim from inputs>]
}
```

### Integration notes

- The new `reconciliations` output block is **additive** — the existing `narrative` and `numbers_used` fields still fire the existing guardrail unchanged. No guardrail code needs to change.
- Every `reconciliations[].narrative` contributes numbers to the top-level `numbers_used` array. That means the guardrail verifies reconciliation narrative numbers for free.
- Classification rules live in the prompt, not in Python. If a category misfires during rehearsal, tune the prompt's "priority of decision" block first before touching the `hint_computer.py` signals.
- The prompt is intentionally verbose on the taxonomy block. Claude Opus handles this well at 1M context; the cost of explicit rules is negligible vs. the cost of a misclassification on stage.

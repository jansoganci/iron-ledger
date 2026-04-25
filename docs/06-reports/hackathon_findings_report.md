# IronLedger Hackathon Findings Report

> Synthesis of three source documents:
> - `docs/en son yapılacaklar.txt` (master brief + three SMB scenarios)
> - `docs/30hr_execution_plan.md` (product audit + execution plan)
> - `docs/compass_artifact_wf-d3f746cb-6d79-4994-bd31-47ef15c3045e_text_markdown.md` (one-week market/architecture research)
>
> Purpose: a build blueprint for the final ~30 hours of the hackathon, prioritized by direct impact on the $30K jury decision.
> Drafted 2026-04-24.

---

## 0. Executive summary

The three documents converge on the same architectural spine. No core decisions need to be reopened. The single strategic sharpening this report recommends: **promote "classification of discrepancies" from a footnote to the demo's centerpiece.** That one shift separates IronLedger from every enterprise close tool on the market and is the most defensible claim the product can make to the jury.

Priority-ordered build:

1. **Consolidation plumbing** — multi-file → one consolidated P&L (30hr plan as written)
2. **Classification layer** — every reconciliation item labeled with one of six pattern categories
3. **Finance-trust surface** — Excel export, provenance UI, tiered materiality, tighter guardrail
4. **Roadmap slide** — PDF, bank-recon, multi-entity, Benford, ERP integrations (pitch only, not build)

Everything else: cut.

---

## 1. Document convergence — decisions that are locked in

| Decision | Brief | 30hr plan | Compass research |
|---|---|---|---|
| Multi-file consolidation = headline | ✅ | ✅ | ✅ (#3 of 13 automation targets) |
| Cross-source reconciliation = #2 | ✅ | ✅ | ✅ (#2 ROI) |
| Variance narrative = table stakes | ✅ already built | ✅ | ✅ (highest raw ROI but low differentiation) |
| pandas computes / Claude narrates / guardrail verifies | ✅ | ✅ | ✅ "the single most important architectural rule" |
| Excel export is mandatory | ✅ | ✅ | ✅ "finance people trust Excel" |
| Provenance / audit trail | ✅ | ✅ | ✅ addresses #1 adoption barrier (SOX concern) |
| Cut: PDF, multi-entity, pgvector, bank recon, scheduled runs | ✅ | ✅ | ✅ |
| Start with Anthropic SDK direct (no LangChain) | ✅ | ✅ | ✅ "Anthropic's own guidance" |
| pandera over Great Expectations | ✅ existing | ✅ | ✅ "GE's config sprawl costs half a day" |

**Implication for the build:** zero architectural re-litigation. The brief already contains the 30-hour plan verbatim. Spend build time on execution, not on reconsidering the plan.

---

## 2. The six-category classification pattern — the prize-winning insight

### 2.1 Why this is the wedge

Every enterprise close tool (Vena, FloQast, BlackLine, Numeric, Nominal) can compute a dollar delta between two data sources. What none of them ship in 2026 is a **classification layer that tells a CFO _why_ the delta exists**. That is the jury-visible differentiator.

The compass research confirms this at §2: "route remaining exceptions through Claude to classify (timing/error/missing JE) and draft AP-clerk request emails." The 60–70% reconciliation-workload reductions cited by the AICPA Continuous Finance Survey all come from automating this classification step, not just the detection step.

### 2.2 The six categories derived from the brief's scenarios

Every one of the 13 discrepancies in the brief maps to exactly one of six categories:

| # | Category | Definition | Scenario examples |
|---|---|---|---|
| 1 | **Timing cutoff** | Same transaction, different period. Not an error. Will reverse next month. | BlueLine Shopify $3K ($28 Mar payout landed Apr 1); Sentinel installation $4K (50% deposit, balance due Apr) |
| 2 | **Categorical misclassification** | Real error. Correct total, wrong account. | Sentinel payroll $700 (bonus → Contractors); Vantage severance $3.5K (payroll → OpEx) |
| 3 | **Missing journal entry** | Real error. Source shows it; GL doesn't yet. | Sentinel CableMax $1.7K; Vantage contractor $3.5K; Vantage travel $2.8K |
| 4 | **Stale reference data** | Real error. Upstream list not updated. | Sentinel 3 cancelled contracts; Vantage paused retainer + old-rate client |
| 5 | **Accrual / amortization mismatch** | Real error. Lump sum booked instead of period portion. | Vantage HubSpot $13.2K annual → $1.1K/mo; accrued revenue $12.5K |
| 6 | **Structural / explained** | Not a finding. Known netting or calculation difference. | BlueLine bank $57.5K vs sales $61K (platform fees netted before deposit) |

### 2.3 Detection hints pandas can compute before Claude sees the item

The guardrail principle (pandas computes, Claude narrates) still applies. Pandas emits hints; Claude classifies using hints + context. Do NOT let Claude compute thresholds.

For each reconciliation item, pre-compute in pandas:

```python
hints = {
    "delta_abs": abs(delta),
    "delta_pct": abs(delta) / max(abs(gl_amount), 1),
    "is_round_fraction": abs(delta / gl_amount - 0.5) < 0.01,  # 50/50 deposit pattern
    "crosses_period_boundary": last_source_txn_date > period_end,  # timing flag
    "source_only_accounts": [...],   # appears in source, not GL → missing JE
    "gl_only_accounts": [...],        # appears in GL, not source → stale/miscat
    "prior_period_pattern": "...",    # did this account have a similar delta last month?
    "amount_matches_known_invoice": bool,  # lump-sum → amortization
    "appears_in_other_source": bool,  # netted across sources → structural
}
```

### 2.4 The Interpreter prompt extension (conceptual shape)

Extend `backend/prompts/narrative_prompt.txt` to require one of six `classification` enum values per reconciliation item. Prompt structure:

```
For each reconciliation item, emit:
{
  "account": str,
  "delta": float (from pandas; never recompute),
  "classification": "timing_cutoff" | "categorical_misclassification" |
                    "missing_je" | "stale_reference" | "accrual_mismatch" |
                    "structural_explained",
  "narrative": str (<= 2 sentences),
  "suggested_action": str ("Draft reclass JE" | "Confirm invoice entry" | ...),
  "numbers_used": [all $ values mentioned in narrative]
}
```

The existing numeric guardrail already verifies `numbers_used` against the pandas summary — classification inherits the safety net for free.

### 2.5 Why classification is demo-central, not a side feature

Before classification: "We found a $3,000 gap between your supplier file and your GL." → judge response: *"OK, Excel can do that."*

After classification: "This $1,700 gap is a missing journal entry for CableMax's March 22 invoice. It's not in QuickBooks yet. Here's the draft JE." → judge response: *"This is a real tool."*

Classification is the single feature on the build list that no enterprise incumbent ships in 2026. If time pressure forces a cut, cut anything before cutting this.

---

## 3. Compass research additions — three surgical improvements

These are each <1 hour of work and each directly strengthens the pitch.

### 3.1 Tiered materiality thresholds

**Current state:** `backend/agents/comparison.py:17-32` uses flat 15%/20% percentage thresholds with no dollar gate. A $200 variance on a $500 account triggers a "medium" severity flag — which any controller would dismiss.

**Recommendation (compass §2):**

```python
def flag(row):
    mat_dollar, mat_pct = 50_000, 0.10          # Tier 1 default
    tight = {'REVENUE', 'PAYROLL', 'DEFERRED_REVENUE'}
    if row.category in tight:
        mat_dollar, mat_pct = 10_000, 0.03       # Tier 2 sensitive
    return abs(row.delta) >= mat_dollar and abs(row.pct) >= mat_pct
```

**Demo framing:** "We don't flag every swing. We flag swings against the thresholds a real controller uses — tighter on revenue and payroll because errors there compound quarterly."

**Effort:** ~30 minutes in `calculate_variance()`.

### 3.2 Tighter guardrail tolerance

**Current state:** `backend/tools/guardrail.py` uses flat 2% tolerance. On small numbers (e.g., $40), a 2% band is ±$0.80 — effectively no check.

**Recommendation (compass §4):** `tolerance = max(1%, $1k)` — tiny numbers get a dollar floor; large numbers get a percentage band.

**Effort:** ~10 minutes, one line.

**Demo framing:** the guardrail badge stays green for the whole demo. No further mention needed — finance judges will assume sound tolerance policy.

### 3.3 Dual-LLM pattern for payroll PII — claim it, don't rebuild it

Your codebase already implements this pattern:
- `backend/tools/pii_sanitizer.py` strips PII headers + redacts SSN patterns before any Claude call
- Haiku sees sanitized column headers + sample rows; Opus sees only aggregated pandas summary
- Opus never touches raw file rows

Compass §4 calls this the "dual-LLM defense pattern" and recommends it as best practice for payroll files. **You already have it.** The build action is zero — the pitch action is to name it.

**Pitch line:** "Your payroll SSNs never reach the reasoning model. Raw files pass through a quarantined Haiku boundary; Opus only sees aggregated totals. This is the dual-LLM pattern the security literature recommends — and we ship it by default."

### 3.4 Variance-threshold flagging
Compass recommends both dollar AND percentage gates simultaneously. Implement as part of 3.1.

---

## 4. Essential vs. Extra — ranked by jury impact

### ESSENTIAL (these win or lose the prize)

| Feature | Why essential | Build cost |
|---|---|---|
| Multi-file consolidation | Proposition delivery. | ~6h (ConsolidatorAgent + orchestrator) |
| Six-category classification | THE demo moment. No incumbent has this. | ~4h (prompt + pandas hints) |
| One end-to-end demo scenario with all six categories represented | Demo narrative backbone. | ~1h crafting demo files |
| Excel export (3-sheet audit workbook) | What the judge downloads and trusts. | ~3h |
| Provenance UI (hover → file + row) | Addresses #1 adoption barrier (SOX). | ~2h (data already stored) |
| Guardrail green throughout demo | One bad number = dead product. | ~10min tolerance fix |
| Tiered materiality | Credibility with finance judges. | ~30min |

### EXTRA (skip if time-constrained)

| Feature | Why extra |
|---|---|
| Benford's Law anomaly detection | ~4h calibration; won't trigger on clean demo files; low visible payoff |
| Row-level reconciliation (generic) | Build for ONE category only — service contracts in Sentinel |
| Bank reconciliation (full) | Different data shape, breaks schema. Do lightweight bank-balance check instead (30min) |
| Multi-entity consolidation | Requires auth rework. Roadmap slide only. |
| PDF ingestion | 2 days minimum. Roadmap slide only. |
| Scheduled / continuous monitoring | No demo surface. Roadmap slide only. |
| New LLM model experiments / cache tuning | Zero jury visibility. |
| UI redesign beyond the listed components | Low ROI vs. finishing classification |

---

## 5. The $30K demo narrative — full script

Target length: **5–6 minutes**, not 2. Classification needs airtime to land. Jury attention span for finance pitches is generous if the story is concrete.

### Scenario: Sentinel Secure (from the brief)

Chosen because (a) it's a relatable 8-person SMB, (b) all six discrepancy categories appear naturally, (c) it isn't so complex it loses non-finance jurors.

### Act 1 — The pain (60s)
> "Meet the office manager at Sentinel Secure, an 8-person security installation business. It's April 3rd. Her inbox has 7 files — QuickBooks export, payroll spreadsheet, supplier invoices, service contract list, vehicle expenses, ad spend CSV, bank statement. Every month she spends 6 hours consolidating and 2 hours hunting discrepancies. Tonight there's a board call at 9 PM."

**Visual:** screenshot of the 7 filenames in a finder window.

### Act 2 — The drop (90s)
> "She drags all 7 files into IronLedger, labels the period March 2026, clicks Analyze."

**Visual:** live drag-drop into the upload UI. Files appear as chips. Progress bar runs through Parser → Consolidator → Reconciler → Interpreter. 45s later: consolidated P&L on screen. Hover any number → tooltip shows source file + row.

### Act 3 — The classification moment (180s, the wow)

Four highlighted reconciliations. Click each. (Timing: ~45s per card.)

**Card 1 — Missing journal entry**
> "Supplier invoices total $37,800. QuickBooks COGS: $36,100. Gap: $1,700."
> IronLedger's narrative: *"This is a missing journal entry. CableMax's invoice dated March 22 appears in your supplier file but not in QuickBooks. Likely not yet entered."*
> [Button: Draft Reclass JE]

**Card 2 — Stale reference data**
> "Service contracts expected $3,825. GL shows $3,540. Gap: $285."
> IronLedger: *"This is stale reference data. Three customers are marked 'Active' in your contract file but have no matching revenue this period: [names]. They likely cancelled without the list being updated."*

**Card 3 — Categorical misclassification**
> "Payroll file: $44,200. GL wages: $44,900. Gap: $700."
> IronLedger: *"This is a categorical misclassification. A $700 on-call bonus appears in your GL under 'Contractors' but matches a line in your payroll file. Should be reclassed to Payroll."*
> [Button: Draft Reclass JE]

**Card 4 — Timing cutoff (not an error)**
> "Installation revenue in GL: $8,000. Bank deposits: $4,000. Gap: $4,000."
> IronLedger: *"This is a timing cutoff, not an error. Your GL recognizes full installation revenue on completion; the bank shows only the 50% deposit. Balance is due April 15. Expect reversal next period — no action needed."*

**Guardrail badge: green throughout. Every dollar figure hoverable to source.**

### Act 4 — The deliverable (60s)
> "Download Excel."

**Visual:** a 3-sheet `.xlsx` lands on desktop. Open it.
- Sheet 1: Consolidated P&L with source-file notes
- Sheet 2: Reconciliations — every delta, category, and source trace
- Sheet 3: Per-source breakdown

> "This is what she sends to her auditor. Every number traced to a file and row."

### Act 5 — The close (30s)
> "Six hours of work, three minutes. Vena costs $50K/year and assumes clean data. FloQast assumes your GL is the source of truth. IronLedger is the only product that reads **the chaos as it arrives** — and tells you **why** your files disagree, not just that they do."

---

## 6. Strategic roadmap — four tracks

Priority order. Within each track, cut scope before cutting the track.

### Track 1 (MUST SHIP) — Consolidation plumbing

**Files changed/created:**
- **New** `backend/agents/consolidator.py` — pure pandas, ~150 LOC. Input: `list[tuple[str, pd.DataFrame]]`. Output: `(consolidated_df, list[ReconciliationItem])`. Three operations: union → fuzzy account-name match (`rapidfuzz` 90% threshold) → per-account totals + deltas.
- `backend/agents/orchestrator.py` — add `run_multi_file_parser_until_preview(run_id, storage_keys, ...)`. One task per run, not N.
- `backend/api/routes.py:/upload` — stop looping `background_tasks.add_task` per file. One task, pass full key list.
- **New migration** `supabase/migrations/0002_multi_source_consolidation.sql` — adds `monthly_entries.source_breakdown JSONB`, `reports.reconciliations JSONB`, `runs.file_count INT`.
- `backend/domain/entities.py` — extend `MonthlyEntry` and `Report` dataclasses for new fields.
- `backend/adapters/supabase_repos.py` — thread new fields through repo methods.

**Dependency added:** `rapidfuzz`.

### Track 2 (MUST SHIP) — Classification layer

**Files changed/created:**
- `backend/agents/consolidator.py` — in addition to the delta computation, emit a `ReconciliationHints` dict per item (see §2.3).
- `backend/prompts/narrative_prompt.txt` — extend required output JSON with `reconciliations: [{account, delta, classification, narrative, suggested_action, numbers_used}]`.
- `backend/domain/contracts.py` — new Pydantic model `ReconciliationItem` with `classification: Literal["timing_cutoff", "categorical_misclassification", "missing_je", "stale_reference", "accrual_mismatch", "structural_explained"]`.
- `backend/agents/interpreter.py` — pass `reconciliations` + `hints` into prompt context alongside anomalies.
- **No guardrail changes needed** — existing `numbers_used` verification covers reconciliation narrative numbers automatically.

**This is the prize-winning track. Spend real hours here.**

### Track 3 (MUST SHIP) — Finance-trust surface

**Excel export:**
- **New route** `GET /report/{company_id}/{period}/export.xlsx` in `backend/api/routes.py`.
- Build with `openpyxl` (already a dependency). Three sheets:
  - `Consolidated P&L`: account, category, current period, source count, total
  - `Reconciliations`: account, sources breakdown columns, delta, classification, narrative
  - `Source Breakdown`: source_file × account matrix with amounts
- Add "Download Excel" button to report page.

**Provenance UI:**
- `frontend/src/components/AnomalyCard.tsx` — surface `source_file` and `source_column` already stored on `MonthlyEntry`. Hover shows "from payroll_mar.xlsx, column Gross Pay".
- **New** `frontend/src/components/ReconciliationPanel.tsx` — lists each reconciliation item with classification badge, per-source breakdown, suggested action, provenance hover.
- `frontend/src/components/ParsePreviewPanel.tsx` — add "Sources" column showing which files contributed to each account.

**Tiered materiality:**
- `backend/agents/comparison.py:calculate_variance()` — extend signature with `category` parameter; apply Tier 2 thresholds for REVENUE / PAYROLL / DEFERRED_REVENUE.

**Guardrail tolerance fix:**
- `backend/tools/guardrail.py` — change tolerance check to `max(0.01 * abs(pandas_val), 1000)`.

### Track 4 (CUT FROM BUILD → ADD TO PITCH) — Roadmap slide

One slide titled **"What ships next quarter."** Single line per item:

- PDF ingestion for scanned vendor invoices
- Multi-entity consolidation with FX + eliminations
- Bank statement transaction-level reconciliation
- Benford's Law + outlier + duplicate anomaly detection
- Scheduled / continuous close monitoring
- Direct ERP integrations (QuickBooks, NetSuite, Xero)
- SOC 2 evidence pack export

Shows full product surface without forcing the build.

---

## 7. Classification layer — detailed design

This is the single most important part of the build. Treating it as spec, not suggestion.

### 7.1 Pandas-side hints (ConsolidatorAgent emits)

For each reconciliation item where sources disagree:

```python
@dataclass
class ReconciliationHints:
    delta_abs: float
    delta_pct: float
    sources: list[dict]              # [{source_file, amount, row_count}, ...]
    is_source_only: bool             # appears in sources but not GL → missing_je candidate
    is_gl_only: bool                 # appears in GL but not sources → stale/miscat candidate
    is_round_fraction: bool          # e.g. delta ≈ 0.5 × GL → 50/50 deposit pattern (timing)
    crosses_period_boundary: bool    # any source txn dated after period_end → timing candidate
    similar_amount_in_other_account: dict | None  # e.g. $700 in Contractors matches $700 in Payroll bonus → misclassification
    prior_period_had_similar_delta: bool  # recurring gap → structural
    matches_known_annual_invoice: bool    # lump sum → accrual_mismatch
```

### 7.2 Claude-side classification prompt (skeleton)

```
You are classifying reconciliation deltas between a consolidated GL and
supporting source files. Each item includes pandas-computed hints. You must
output one of exactly six classifications. Do not compute numbers; use only
the amounts given.

Classifications:
1. timing_cutoff — Same transaction, different period. Not an error.
2. categorical_misclassification — Correct total, wrong account.
3. missing_je — Source shows it; GL doesn't yet.
4. stale_reference — Upstream reference list not updated.
5. accrual_mismatch — Lump sum booked instead of period portion.
6. structural_explained — Known netting or calc difference; not a finding.

Rules:
- If hints.crosses_period_boundary AND hints.is_round_fraction → strong
  signal for timing_cutoff.
- If hints.similar_amount_in_other_account is present → strong signal for
  categorical_misclassification.
- If hints.is_source_only → missing_je.
- If hints.is_gl_only AND prior_period_had_similar_delta → stale_reference.
- If hints.matches_known_annual_invoice → accrual_mismatch.
- Otherwise → structural_explained, and explain the netting.

For each item return {account, delta, classification, narrative (<=2
sentences, plain English, no finance jargon), suggested_action,
numbers_used}. Narrative numbers must come from the pandas inputs verbatim.
```

### 7.3 Guardrail inheritance

No guardrail changes needed. The existing `verify_guardrail()` iterates `claude_json["numbers_used"]` against `pandas_summary.values()`. Reconciliation narrative numbers will be in `numbers_used` automatically. If Claude fabricates a figure in classification narrative, the existing guardrail catches it and the existing semantic-retry kicks in.

### 7.4 Suggested-action templates

Per classification, a deterministic action string (no Claude computation):

| Classification | Suggested action template |
|---|---|
| timing_cutoff | "No action. Expect reversal in {next_period}." |
| categorical_misclassification | "Draft reclass JE: {amount} from {from_account} to {to_account}." |
| missing_je | "Confirm invoice entry for {vendor} dated {date}, amount {amount}." |
| stale_reference | "Update {source_file} — {n} entries inactive: {names}." |
| accrual_mismatch | "Amortize {amount} over {months} months; book {monthly_amount} for this period." |
| structural_explained | "No action. {explanation}." |

---

## 8. Excel export — sheet-level schema

### Sheet 1: Consolidated P&L

| Account | Category | Period Total | Source Count | Sources |
|---|---|---|---|---|
| Salaries & Wages | PAYROLL | $44,900.00 | 2 | payroll_mar.xlsx; gl_export.xlsx |
| ... | ... | ... | ... | ... |

Header row styled bold, period total column currency-formatted, subtotal rows by category with bold + top border.

### Sheet 2: Reconciliations

| Account | Classification | GL Amount | Source Total | Delta | Narrative | Suggested Action |
|---|---|---|---|---|---|---|
| Supplier COGS | missing_je | $36,100.00 | $37,800.00 | $1,700.00 | CableMax invoice dated 2026-03-22 appears in source file but not in GL. | Confirm invoice entry for CableMax dated 2026-03-22, amount $1,700. |
| ... | ... | ... | ... | ... | ... | ... |

Classification column has conditional-formatting color codes (red for error categories, yellow for timing, green for structural_explained).

### Sheet 3: Source Breakdown

Matrix: rows = accounts, columns = source files, cells = amount contributed. Row totals and column totals.

| Account | gl_export.xlsx | payroll.xlsx | supplier_invoices.xlsx | ... | Total |
|---|---|---|---|---|---|
| Salaries & Wages | $44,200 | $44,900 | — | ... | reconciled |
| Supplier COGS | $36,100 | — | $37,800 | ... | $1,700 delta |
| ... | ... | ... | ... | ... | ... |

This is the sheet auditors will spend the most time in.

---

## 9. The one thing that, if missing, kills the prize

**Classification.** If the demo shows reconciliations with dollar deltas but no classification, IronLedger looks like a prettier diff tool. Every enterprise incumbent already computes dollar deltas. The moat is that Claude Opus, given pandas-computed residuals + per-source breakdowns + detection hints, labels each delta with one of six pattern-categories. That is the only feature in the build that an off-the-shelf BI tool cannot produce in 2026.

If time pressure forces a cut, **cut anything before cutting classification.** Cut UI polish. Cut the third Excel sheet. Cut provenance hover. Do not cut classification.

---

## 10. Open questions to resolve before code

Not blockers. Pitch-strengtheners.

### 10.1 Demo scenario files
The brief describes 7 files for Sentinel Secure in detail but `docs/demo_data/` currently has only DRONE Inc. single-file data. **Hand-craft the Sentinel file set before writing any code.** ~1 hour. The classification prompt has to be tuned against real data, and the demo narrative has to rehearse against real files.

Minimum demo-file set (3 files, all 6 categories represented):
1. `sentinel_gl_mar_2026.xlsx` — the "official" GL
2. `sentinel_supplier_invoices_mar_2026.xlsx` — for the missing-JE + categorical-misclass cards
3. `sentinel_contracts_mar_2026.xlsx` — for the stale-reference + timing-cutoff cards

Optional: payroll + ad spend if time permits (richer demo).

### 10.2 Jury composition
Same product, two different pitches:
- **Finance operators in the panel** → classification story + provenance + Excel deliverable. Overlook UI rough edges.
- **Pure technologists in the panel** → "Claude reasons across files + numeric guardrail proves no hallucination" + architecture diagram.

Both pitches share the same demo; the 30-second close differs. Worth deciding in advance which version is default.

### 10.3 Fallback demo recording
Record a 60-second backup video of a successful end-to-end run. Live demos break. The video is insurance.

---

## 11. Appendix — file-level change manifest

Complete list of files touched, grouped by track.

### Track 1 — Consolidation plumbing
- `supabase/migrations/0002_multi_source_consolidation.sql` (NEW)
- `backend/agents/consolidator.py` (NEW, ~150 LOC)
- `backend/agents/orchestrator.py` (extend: `run_multi_file_parser_until_preview`)
- `backend/api/routes.py` (modify `/upload`: single task per run)
- `backend/domain/entities.py` (extend `MonthlyEntry`, `Report`)
- `backend/domain/contracts.py` (NEW: `ReconciliationItem`, `ReconciliationHints`)
- `backend/adapters/supabase_repos.py` (thread new fields)
- `requirements.txt` (add `rapidfuzz`)

### Track 2 — Classification layer
- `backend/agents/consolidator.py` (emit `ReconciliationHints` per item)
- `backend/prompts/narrative_prompt.txt` (extend schema + classification rules)
- `backend/agents/interpreter.py` (pass reconciliations + hints into prompt)
- `backend/domain/contracts.py` (classification enum on `ReconciliationItem`)

### Track 3 — Finance-trust surface
- `backend/api/routes.py` (NEW route: `/report/{company_id}/{period}/export.xlsx`)
- `backend/tools/excel_export.py` (NEW: 3-sheet workbook builder)
- `frontend/src/components/ReconciliationPanel.tsx` (NEW)
- `frontend/src/components/AnomalyCard.tsx` (surface provenance hover)
- `frontend/src/components/ParsePreviewPanel.tsx` (add Sources column)
- `frontend/src/components/ReportSummary.tsx` (embed ReconciliationPanel, Download Excel button)
- `backend/agents/comparison.py` (tiered materiality)
- `backend/tools/guardrail.py` (tolerance fix)

### Track 4 — Pitch, not build
- `docs/roadmap_slide.md` (NEW — text for pitch deck; does not ship in product)

---

## 12. Bottom line

The brief is right. The 30hr plan is structurally right but under-sells classification. The compass research validates both and adds three surgical improvements (tiered thresholds, dual-LLM naming, tighter guardrail).

**Path to $30K:**
1. Build the consolidation plumbing (Track 1)
2. Build the classification layer on top (Track 2) — **this is the wedge**
3. Ship Excel export + provenance + tiered materiality + tightened guardrail (Track 3)
4. Roadmap slide for the rest (Track 4)
5. Demo Sentinel Secure end-to-end with all six discrepancy categories visible, under 6 minutes

Skip everything else. The classification layer is the only feature on this list that enterprise incumbents cannot match in 2026 — that is the moat the pitch has to lead with.

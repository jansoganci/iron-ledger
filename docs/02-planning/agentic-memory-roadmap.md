# Agentic Memory & Quarterly Reporting — Implementation Roadmap

**Source:** Merged from two independent deep-search analyses (Codex 5.3 and Sonnet 4.6) on 2026-04-26. Conflicts were resolved by reading the actual code; see Section 3.
**Revision (2026-04-26, late):** Section 0 added after a code-walk uncovered the dual-background-task flow that both original analyses missed. Phase 2 was rewritten because `opus_upgrade.py` already implements the trend-context idea it originally proposed. See Section 3, Conflict F.
**Revision (2026-04-26, final):** User confirmed decisions on all open questions:
- Phase 2 → **Option 2a (skip entirely)**. Removed from plan; phase numbering compacted.
- Quarterly trigger → manual button on `/reports` (primary) and `/report/:period` for quarter-end months (secondary).
- Missing months → generate anyway, disclose at top of narrative.
- YoY → enabled when prior-year quarter data exists.
- Guardrail tolerance → 2% (MVP).
- Anomaly grouping in quarterly report → grouped by recurrence frequency (3/3, 2/3, 1/3 months).
- Loading state → progressive disclosure (step-by-step progress).
- Error handling → automatic 1 silent retry, then type-specific error message.
- Button visibility → require ≥2 months uploaded.
- Charts in MVP → none.
- Multi-month anomaly card → single card with inline 3-month summary.

Phase 2 (Quarterly Report) UI/UX specification fully detailed under that phase below.

---

## 0. Current Report Flow (Verified)

This section was added after both original analyses missed the actual narrative-generation flow. Verified by reading `backend/api/routes.py:976-988`, `backend/agents/orchestrator.py:325`, `backend/agents/opus_upgrade.py`, and `backend/adapters/supabase_repos.py:282`.

### The dual-background-task pattern
After the user confirms the upload mapping, `POST /upload/confirm` fires **two background tasks back-to-back, against the same `run_id`** (`routes.py:976-988`):

```python
background_tasks.add_task(run_comparison_and_report, ...)   # Haiku path
background_tasks.add_task(run_opus_upgrade,          ...)   # Opus path
```

These run **in parallel** inside FastAPI's task pool. They both target the same `(company_id, period)` and the same single row in the `reports` table.

### Task 1 — `run_comparison_and_report` (Haiku, ~3-5s)
`backend/agents/orchestrator.py:325`. Sequence:
1. Comparison agent calculates per-account variance (Python only) and writes anomalies.
2. Interpreter agent calls **Claude Haiku** with `narrative_prompt.txt` and the **current month's** `pandas_summary` (no prior months).
3. Guardrail validates Claude's numbers against `pandas_summary`.
4. **Inserts** a `reports` row with `summary = haiku_narrative`, `opus_upgraded = FALSE`.

### Task 2 — `run_opus_upgrade` (Opus, ~10-20s)
`backend/agents/opus_upgrade.py`. Sequence:
1. Sets `runs.opus_status = 'running'` (frontend shows a "Opus is thinking..." banner).
2. Race-condition guard: aborts if a newer run exists for this `(company_id, period)`.
3. Fetches current month's `pandas_summary` AND **prior 3 months** via `runs_repo.get_prior_pandas_summaries(...)` (`opus_upgrade.py:67-72`).
4. Calls **Claude Opus 4.7** with `opus_narrative_prompt.txt` and the multi-month trend context.
5. Guardrail validates against current month's `pandas_summary` only.
6. On success: **atomically overwrites** `reports.summary` via `reports_repo.upgrade_summary(...)` (`supabase_repos.py:282`) and sets `opus_upgraded = TRUE`.
7. On any failure: silent fail. The Haiku narrative survives untouched. `opus_status` set to `failed`.

### Critical implications (these change the plan)
- **There is exactly ONE `reports` row per `(company_id, period)`.** Opus does not create a parallel report — it overwrites the Haiku one in place.
- **What the user reads is whichever finished last AND passed guardrail.** Happy path: Opus prose. Degraded path: Haiku prose. Both possibilities use the same UI components.
- **"Opus upgrade" is not a button.** It is the default automatic post-processing path. The frontend signals it via `runs.opus_status`, not via a user action.
- **Trend context already exists** — but only on the Opus path, and only on the overwrite. The Haiku narrative is single-month-only.
- **Python writes structured data; all prose is Claude.** Comparison writes anomaly rows (numbers + categorical fields). Interpreter (Haiku first, then Opus overwrite) writes the narrative string. The guardrail is the only place numbers and prose meet.

### Why this matters for memory features
Any "agentic memory" UX the user sees on the report page is, in the happy path, **Opus's output**. So Phase 1's recurring-anomaly signal must reach Opus's context, not just Haiku's. Phase 2's original idea ("wire trend context into base interpreter") is partially redundant because Opus already has trend context — see the rewritten Phase 2 below.

---

## 1. Current State Summary

### What the system does today
- **Monthly close pipeline.** User uploads Excel files for a period → Parser maps columns to US GAAP categories and writes `monthly_entries` → Comparison computes per-account variance vs a 6-month historical mean and writes flagged rows to `anomalies` → Interpreter (Claude Opus 4.7) writes a narrative; a numeric guardrail checks every number Claude emits against the `pandas_summary` (2% tolerance).
- **Variance gate is two-tier.** `_TIER2_CATEGORIES = {"REVENUE", "PAYROLL", "DEFERRED_REVENUE"}` uses a lower $10K / 3% gate; everything else uses $50K / 10%. Both gates must be exceeded to flag. (`backend/agents/comparison.py:18`)
- **Severity** is bucketed `high` (>30%), `medium` (>15%), `low` (otherwise). (`comparison.py:48`)

### What's already built (and partly already wired)
- **`SupabaseRunsRepo.get_prior_pandas_summaries()`** (`backend/adapters/supabase_repos.py:444`) returns the last N completed runs' `pandas_summary` JSONB. It is **already called and consumed end-to-end** in the Opus upgrade background task (`backend/agents/opus_upgrade.py:67-87`), which feeds 3 months of trend context to Claude Opus and overwrites `reports.summary` on success. **Trend context is therefore not "unused" — it is the default narrative path in the happy case** (see Section 0). Sonnet's original analysis incorrectly called this dead code; Codex correctly identified the call site; this revision additionally clarifies that the call powers a parallel-overwrite pattern, not a side feature.
- The **Haiku** narrative produced by `run_comparison_and_report` is **single-month-only** — it sees no prior context. This is the only place where adding trend context could still be additive, and even then only as a degraded-mode fallback (see Phase 2 rewrite).
- **`anomalies` table** carries 16+ months of history with `(company_id, account_id, period, severity, variance_pct, status)` — but `AnomaliesRepo` only exposes `list_for_period` and `write_many`. There is no cross-period query method, so the Comparison agent never reads what was flagged in prior months.
- **`pandas_summary` JSONB** is persisted on every completed `runs` row (since migration `0002`), giving us a ready-made trend datasource without any schema change.

### Data already in the DB that can power these features
| Source | Coverage | Used today? |
|---|---|---|
| `anomalies` table | 16+ months | Read only by `list_for_period` for the current run |
| `runs.pandas_summary` JSONB | Every completed run | Read only by `opus_upgrade.py`, not by base interpreter |
| `monthly_entries` | All historical rows | Read by Comparison via `list_history` (capped at `lookback_months * 100` rows) |

**The punchline:** the data and one of the queries already exist. Recurring detection and trend context are mostly wiring, not new infrastructure.

---

## 2. Unified Implementation Plan

### Phase 1 — Recurring Anomaly Detection  (Effort: 3–4 hours)

**What it does**
On each new run, after Comparison flags anomalies for the current period, look up how many of the past N months each flagged account was also flagged. Append a recurrence sentence to the anomaly's `description` (e.g. "Flagged in 3 of the past 6 months — recurring pattern."). The Interpreter consumes `description` verbatim, so Claude will weave the recurrence language into the report with **zero prompt changes**.

**Exact files to change**
1. `backend/domain/ports.py` — add a method to the `AnomaliesRepo` Protocol:
   ```python
   def list_account_flag_counts_before(
       self, company_id: str, before_period: date, lookback_months: int = 6
   ) -> dict[str, int]: ...
   ```
2. `backend/adapters/supabase_repos.py` — implement on `SupabaseAnomaliesRepo`. One SELECT against `anomalies` filtered by `company_id`, `period < before_period`, `period >= before_period - lookback_months`, `severity != 'low'`, grouped by `account_id` with `COUNT(DISTINCT period)`.
3. `backend/agents/comparison.py` — at the top of `ComparisonAgent.run()`, before the per-entry loop, call the new method to get `prior_flag_counts: dict[account_id, int]`. When building each `Anomaly`, if `prior_flag_counts.get(entry.account_id, 0) >= 2`, append the recurrence sentence to `description`.
4. (Optional, not required) `frontend/src/components/AnomalyCard.tsx` — render a "🔁 Recurring" badge if the description contains the recurrence sentinel string.

**DB migration needed? — NO.**
Both analyses noted the optional `is_recurring BOOLEAN` column (Codex: "or add optional metadata field if you prefer schema change"; Sonnet: "Optional: add … via migration `0009_add_recurring_flag.sql`"). For the demo and MVP, **skip the migration**. Reasoning:
- The anomalies table already stores the data needed to derive recurrence; a denormalized boolean is cache, not source-of-truth.
- The `description` field carries the signal into Claude's context without any schema change.
- A boolean column only earns its keep when the UI needs to filter/sort by recurrence — that's a Phase 3 (Persistence) concern.
If we later need first-class filtering, add it as `0009_add_recurring_flag.sql` and backfill from the same query.

**How it surfaces in UI/narrative**
- Narrative: Claude already receives each anomaly's `description` in the prompt context (`interpreter.py:253–262`). Enriched description → recurrence prose for free.
- UI (optional polish): add a badge in `AnomalyCard.tsx` keyed off the description text.

**Risk assessment — Very low.** Read-only addition. The new method is additive; if the lookup returns nothing, descriptions are unchanged. No effect on the guardrail (no new numbers introduced).

---

### ~~Phase 2 — Trend Context~~  (DROPPED — Decision: Option 2a / skip)

**Resolution:** User chose **Option 2a (do nothing)** on 2026-04-26. Phase 2 is removed from the plan because `opus_upgrade.py` already implements the trend-context idea end-to-end (see Section 0), and Phase 1's recurring-pattern signal already reaches Opus via the existing anomaly-description path. No code work needed.

**Why this is safe:**
- Opus already receives 3 months of `pandas_summary` (`opus_upgrade.py:67-72`).
- Phase 1's enriched anomaly descriptions ("Flagged in 3 of past 6 months") flow into Claude's prompt context unchanged.
- The Haiku fallback narrative is only visible during the 5–15 second Opus-thinking window — acceptable for MVP.

**If the demo timing later exposes the Haiku window or if Phase 1's signal needs to be airtight across both narrative paths, two un-shipped options remain in revision history (Options 2b and 2c) — but these are NOT part of the demo plan.**

Phase numbering below is compacted: original Phase 3 → Phase 2 (Quarterly Report); original Phase 4 → Phase 3 (Persisted Quarterly Artifacts).

---

### Phase 2 — Quarterly Report (On-Demand) with full UI/UX spec  (Effort: 2 days)

**What it does**
Aggregate up to three monthly closes within a calendar quarter into a single quarterly trend report with its own Claude Opus narrative. **Stateless / compute-on-demand** for MVP — no new table, no caching. Missing months are tolerated; YoY comparison is included automatically when prior-year quarter exists.

---

#### 2.1 Backend Specification

**New endpoint family (two endpoints required for progressive disclosure):**

1. **`POST /report/{company_id}/quarterly/{year}/{quarter}/generate`**
   - Kicks off a background task. Returns `{job_id, status: "running", progress_pct: 0}` immediately.
   - Generates a `job_id` (UUID v4); stores progress in an in-memory dict keyed by `job_id` (Redis post-MVP).
   - Background task pipeline:
     1. (10%) Fetch runs for 3 months → identify available + missing months
     2. (25%) Aggregate January `pandas_summary` (skip if missing)
     3. (40%) Aggregate February `pandas_summary` (skip if missing)
     4. (55%) Aggregate March `pandas_summary` (skip if missing)
     5. (65%) Fetch prior-year quarter (`{year-1}-Q{quarter}`) — null if not present
     6. (75%) Compute `aggregated_summary` and `yoy_deltas` in Python
     7. (85%) Call Claude Opus 4.7 with `prompts/quarterly_report_prompt.txt`
     8. (95%) Run `verify_guardrail` (2% tolerance) against flat `aggregated_summary` dict
     9. (100%) Return `NarrativeJSON`
   - **On any failure:** automatic 1 silent retry of the failing step. If second attempt also fails, store error metadata `{error_type, message, retry_attempted: true}` and set `status: "failed"`.

2. **`GET /report/{company_id}/quarterly/{year}/{quarter}/status/{job_id}`**
   - Returns current progress: `{status, progress_pct, step_label, result?, error?}`.
   - Frontend polls this every 1 second.
   - On `status == "complete"`: response includes the `NarrativeJSON` result.
   - On `status == "failed"`: response includes `error_type` (one of: `timeout`, `guardrail_failed`, `empty_data`, `internal`) and a user-facing `message`.

**Files to add:**
- `backend/agents/quarterly.py` — new agent (~120 LOC after progress instrumentation). Follows existing Protocol-injection pattern.
- `backend/prompts/quarterly_report_prompt.txt` — new prompt (see Section 2.3).
- `backend/api/routes.py` — add the two endpoints + an in-memory `_quarterly_jobs: dict[str, dict]` for progress tracking.
- `backend/api/deps.py` — wire dependencies for the new agent.

**Files to modify:**
- None for the existing monthly flow. Quarterly is fully additive.

**Aggregation logic (Python, no Claude):**
```python
aggregated_summary = {
    # Per-month entries (preserved for guardrail individual-number checks)
    "jan_revenue": ..., "feb_revenue": ..., "mar_revenue": ...,
    # Quarter aggregates (sums and averages computed here)
    "q_total_revenue": sum_of_available_months,
    "q_total_cogs": ...,
    "q_total_opex": ...,
    "q_avg_gross_margin": weighted_avg_of_available_months,
    "q_mom_revenue_growth": [feb_vs_jan, mar_vs_feb],   # only for adjacent available pairs
    # YoY (null when prior-year quarter incomplete)
    "yoy_revenue_pct": ...,           # or None
    "yoy_gross_margin_delta": ...,    # or None
}
```

**Guardrail handling:** Flatten everything (per-month + quarter aggregates + YoY deltas) into the same dict passed to `verify_guardrail`. 2% tolerance unchanged. Numbers that come back `None` (missing months, missing prior year) are excluded from the guardrail — Claude is forbidden from emitting numbers for them via prompt instruction.

**Missing months handling:**
- If 0 months uploaded: endpoint returns 400 with `error_type: "empty_data"`.
- If 1 month uploaded: endpoint returns 400 with `error_type: "empty_data"` (per UI rule, button only shows for ≥2 months).
- If 2 months uploaded: aggregate from those 2; pass `missing_months: ["2026-01-01"]` to Claude.
- If 3 months uploaded: aggregate all; `missing_months: []`.

---

#### 2.2 Frontend Specification

**New route:**
- `/report/quarterly/:year-:quarter` (e.g. `/report/quarterly/2026-Q1`) in `frontend/src/App.tsx`.

**New page component:**
- `frontend/src/pages/QuarterlyReportPage.tsx`. Reuses existing `ReportSummary.tsx` and `AnomalyCard.tsx`. No new card components.

**Modified components:**
- `frontend/src/pages/ReportsPage.tsx` — add quarter grouping + "Generate Quarterly Summary" CTA button per quarter.
- `frontend/src/pages/ReportPage.tsx` — when `:period` is the last month of a quarter (Mar/Jun/Sep/Dec), show contextual banner with "Q? is complete — Generate Quarterly Summary" CTA.
- `frontend/src/App.tsx` — register new route.

##### Page Layout: `QuarterlyReportPage.tsx`

```
┌─────────────────────────────────────────────────────────┐
│ [Reports] > Q1 2026 Summary             [Regenerate]    │  ← breadcrumb + action
├─────────────────────────────────────────────────────────┤
│ ⚠️  Note: January data is not available. This summary  │  ← missing-months banner (yellow)
│     covers February and March 2026 only.               │     (hidden if missing_months is empty)
├─────────────────────────────────────────────────────────┤
│ Q1 2026 Quarterly Summary                               │
│                                                         │
│ ┌──────────┐  ┌──────────┐  ┌──────────┐                │
│ │ Revenue  │  │ Gross Mg │  │ OpEx     │                │  ← KPI cards (3 columns)
│ │ $14.5M   │  │ 39.4%    │  │ $4.8M    │                │
│ │ +12% YoY │  │ +2.1pp   │  │ -8% YoY  │                │  ← YoY badges (hidden if no prior year)
│ └──────────┘  └──────────┘  └──────────┘                │
├─────────────────────────────────────────────────────────┤
│ Narrative                                               │
│                                                         │
│ "Engineering Salaries continues to run hot, flagged    │  ← Claude prose
│  again this month — the third consecutive month above  │     (from quarterly_report_prompt.txt)
│  the 6-month mean. ..."                                 │
├─────────────────────────────────────────────────────────┤
│ Recurring Issues (3/3 months)                           │  ← red left-border
│ ┌─────────────────────────────────────────────────────┐ │
│ │ 🔴 Engineering Salaries                              │ │
│ │    Flagged 3/3 months · Jan +12% · Feb +18% · Mar  │ │  ← inline 3-month summary
│ │    +22% · trend: increasing                         │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ Persistent Issues (2/3 months)                          │  ← orange left-border
│ ┌─────────────────────────────────────────────────────┐ │
│ │ 🟠 Travel & Entertainment                            │ │
│ │    Flagged 2/3 months · Feb +61% · Mar +55%         │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ One-Off Anomalies (1/3 months)                          │  ← yellow left-border
│ ┌─────────────────────────────────────────────────────┐ │
│ │ 🟡 Office Supplies (Jan)                             │ │
│ │    +120% · likely one-time event                     │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Year-over-Year Comparison                               │  ← entire section hidden if no prior year
│ Q1 2025: $12.9M revenue · 37.3% margin · $5.2M OpEx    │
│ Q1 2026: $14.5M revenue · 39.4% margin · $4.8M OpEx    │
│ → Revenue +12.4% · Margin +2.1pp · OpEx -7.7%          │
├─────────────────────────────────────────────────────────┤
│ Generated 2026-04-26 14:32:17 UTC                       │
└─────────────────────────────────────────────────────────┘
```

##### CTA placement and visibility rules

**Primary CTA — `ReportsPage.tsx`:**
- Group monthly report cards by quarter. Quarter heading shows `Q1 2026` etc.
- Below each quarter heading, render a "Generate Quarterly Summary" button.
- **Visibility:**
  - 0–1 months uploaded for the quarter → button **hidden**.
  - 2 months uploaded → button **visible**, with a small caption beneath: "Generates with available months."
  - 3 months uploaded → button **visible**, no caption.
- On click → navigate to `/report/quarterly/:year-:quarter` and immediately POST to `/generate`.

**Secondary CTA — `ReportPage.tsx`:**
- Only when `:period` resolves to the last month of a calendar quarter (Mar/Jun/Sep/Dec).
- Top of page, dismissible banner: "Q1 2026 is complete — Generate Quarterly Summary" with embedded button.
- Same visibility rule (≥2 months in the quarter).

##### Loading state — Progressive disclosure

The `QuarterlyReportPage` polls `/status/{job_id}` every 1 second. The page renders a centered progress component:

```
       ⏳ Generating Q1 2026 Summary

  ✓  Fetching prior runs                       [10%]
  ✓  Aggregating January                       [25%]
  ✓  Aggregating February                      [40%]
  ⏳  Aggregating March                         [55%]
  ○  Fetching prior year data
  ○  Calling Claude Opus
  ○  Verifying numbers

  ███████████████░░░░░░░░░░░░░░░░  55%
```

- Each step has three states: pending (○), in-progress (⏳), done (✓).
- The `step_label` from the backend drives which row is in-progress.
- Total expected duration: 10–20 seconds.
- New component: `frontend/src/components/QuarterlyProgress.tsx`.

##### Error states

When `/status` returns `status: "failed"`, render an error card based on `error_type`:

| `error_type` | User-facing message | CTA |
|---|---|---|
| `timeout` | "This is taking longer than expected. The Claude API may be slow right now." | "Try Again" button |
| `guardrail_failed` | "We couldn't verify the report's numbers. This usually resolves on a retry." | "Try Again" button |
| `empty_data` | "Not enough months uploaded for Q1 2026 yet. Upload at least 2 months to generate a quarterly summary." | "Go to Reports" button |
| `internal` | "Something went wrong. Please try again or contact support." | "Try Again" + support link |

The backend already retries silently once before emitting `failed`, so the user-facing button triggers the **second** retry (third attempt overall).

##### Empty state — YoY section

If `yoy_deltas` is `null` (prior-year quarter missing or incomplete):
- The "Year-over-Year Comparison" section is **completely hidden** (no placeholder).
- KPI card YoY badges are also hidden.
- No mention of YoY in the narrative (enforced via prompt: "If `yoy_deltas` is null, do NOT include YoY commentary").

##### sessionStorage caching pattern

To prevent the user losing the report on page reload:

```typescript
// On generate completion (status === "complete"):
sessionStorage.setItem(
  `quarterly-${companyId}-${year}-Q${quarter}`,
  JSON.stringify({ result, generatedAt: Date.now() })
);

// On QuarterlyReportPage mount:
const cached = sessionStorage.getItem(`quarterly-${companyId}-${year}-Q${quarter}`);
if (cached) renderResult(JSON.parse(cached).result);
else showGenerateButton();
```

- Cache key: `quarterly-{companyId}-{year}-Q{quarter}`.
- Cleared when: user clicks "Regenerate" (no confirm dialog — instant clear + re-POST).
- Cleared automatically when: tab closes (sessionStorage semantics).
- Not synced across tabs or sessions — acceptable for MVP demo.

##### Anomaly grouping component

Within `QuarterlyReportPage.tsx`, anomalies are grouped client-side by recurrence count returned in the response:

```typescript
const grouped = {
  recurring: anomalies.filter(a => a.recurrence_count === 3),    // 3/3
  persistent: anomalies.filter(a => a.recurrence_count === 2),   // 2/3
  oneOff: anomalies.filter(a => a.recurrence_count === 1),       // 1/3
};
```

For each anomaly with multi-month recurrence (counts 2 or 3), the `AnomalyCard` renders a single card with an inline summary:
- Account name (top)
- "Flagged N/3 months · Jan +X% · Feb +Y% · Mar +Z% · trend: increasing/stable/mixed"
- Trend determination (Python, in the aggregator): `increasing` if monotonically up, `decreasing` if monotonically down, `stable` if all within ±5pp, `mixed` otherwise.

Color/border conventions:
- `recurring` (3/3) — red left-border, 🔴 emoji prefix.
- `persistent` (2/3) — orange left-border, 🟠 emoji prefix.
- `oneOff` (1/3) — yellow left-border, 🟡 emoji prefix.

##### Breadcrumb + navigation
- Breadcrumb at top of page: `[Reports] > Q1 2026 Summary`.
- Click on `Reports` → navigate to `/reports`.
- "Regenerate" button (top-right): clears sessionStorage entry and POSTs to `/generate` again. No confirm dialog.

##### Mobile/responsive
- Inherit the existing pattern from `ReportPage.tsx`. No mobile-specific work in MVP.
- KPI cards: stack vertically below 768px.
- Anomaly section headers and color borders preserved.

---

#### 2.3 Prompt Specification — `quarterly_report_prompt.txt`

**Persona:** CFO writing a board-level quarterly summary.

**Style guidance (from CLAUDE.md, applied):**
- Plain English, no jargon.
- Use ONLY the exact numeric values in `aggregated_summary`, `monthly_summaries`, `prior_year_quarter_summary`, and `yoy_deltas`.
- Never compute new aggregates (no averages, growth rates, sums beyond what's provided).
- No forward-looking forecasts. Descriptive only.

**Structure:**
1. **Quarter at a Glance** — 1 paragraph. If `missing_months` is non-empty, **start with a disclosure**: "**Note:** Data for {month names} is not available. This summary covers {N} of {M} months." Then state top 3 numbers.
2. **Trend Analysis** — 2–3 paragraphs. Direction across available months. Use `q_mom_revenue_growth` if present.
3. **Recurring Issues** — call out accounts in `recurring_anomalies` (recurrence count ≥ 2). Name them.
4. **Year-over-Year** — only if `yoy_deltas` is non-null. Use the deltas verbatim.
5. **Forward Note** — descriptive only ("entering Q2 with..."), no forecasts.

**Output:** Standard `NarrativeJSON` schema (`{narrative: string, numbers_used: number[]}`). No new schema.

**Length target:** 400–700 words.

---

#### 2.4 What changes vs the original Phase 3 sketch

| Aspect | Original (sketch) | Final (this spec) |
|---|---|---|
| Endpoint | Single GET | POST `/generate` + GET `/status` (for progressive disclosure) |
| Loading UX | Implicit / unspecified | Progressive disclosure with 7 steps |
| Error UX | Implicit / unspecified | Type-specific messages, automatic 1 silent retry, manual retry button |
| Missing months | Reject with 404 | Generate with disclosure banner; reject only if 0–1 months |
| YoY | Not in scope | Included; auto-hidden if prior year absent |
| Anomaly display | "Reuse AnomalyCard" | Recurrence-grouped (3/3, 2/3, 1/3) with inline 3-month summary |
| Charts | "Optional" | None for MVP |
| Persistence | Stateless | sessionStorage cache for tab lifetime |
| Effort | "1–2 days" | **2 days** (progressive disclosure + error states added ~3-4 hrs) |

---

#### 2.5 Risk assessment

**Risk — Medium.** The progressive-disclosure pattern adds complexity (background job state, polling endpoint) that the rest of the codebase only partially uses (`runs.opus_status` is similar). Mitigations:
1. Reuse the existing `runs.opus_status` polling pattern as a model — it's proven.
2. Keep all math in Python; the existing 2% guardrail handles aggregated keys without modification.
3. No persistence means a bad quarterly report never pollutes the DB.
4. Automatic silent retry handles transient Anthropic API blips without user-visible failure.

---

### Phase 3 — Persisted Quarterly Artifacts  (Effort: 1 week+, post-demo)

**What it does**
Promote quarterly reports from compute-on-demand to first-class persisted artifacts: cache narratives, expose history, support audit/governance use cases.

**DB migration spec — `0009_add_report_type_and_quarterly.sql`** (next sequence after `0008_opus_upgrade.sql`):
- Add `report_type TEXT NOT NULL DEFAULT 'monthly'` to `reports`.
- Add `quarter SMALLINT NULL` and `year SMALLINT NULL` to `reports` (NULL for monthly).
- Add `is_recurring BOOLEAN DEFAULT FALSE` to `anomalies` (now earns its keep — used for cross-quarter trend queries).
- Backfill `is_recurring` from history.
- New unique constraint: `(company_id, report_type, period)` for monthly; `(company_id, report_type, year, quarter)` for quarterly.

**Lifecycle management**
- Quarterly reports become invalid if any underlying monthly run is re-run (delete-then-insert per CLAUDE.md). Strategy: when a monthly run completes for `period P`, mark any quarterly report whose quarter contains `P` as `status='stale'`. UI shows a "Regenerate" CTA.
- Storage cleanup: quarterly reports do not produce upload artifacts, so existing storage cleanup logic is unaffected.

**When to do this** — Trigger: **after the demo, before production.** The hackathon demo gets all the visible value from Phases 1–3; persistence is an audit/governance requirement that production needs but a demo doesn't.

---

## 3. Conflicts Resolved

### Conflict A — `get_prior_pandas_summaries()` already used?
- **Codex:** "You already have one cross-period narrative path in `backend/agents/opus_upgrade.py`: it fetches up to 3 prior months."
- **Sonnet:** "It was implemented but is **never called** anywhere in the codebase."
- **Resolution: Codex is correct.** Verified via `grep`: `backend/agents/opus_upgrade.py:67` calls `runs_repo.get_prior_pandas_summaries(...)`. Sonnet missed it because the call lives in a non-default narrative path. **Implication for Phase 2:** we are not "lighting up dead code" — we are extending an already-proven pattern from Opus-upgrade into the base Interpreter. Lower risk than Sonnet's framing suggests.

### Conflict B — Is `PAYROLL` in `_TIER2_CATEGORIES`?
- **Codex:** Quoted the snippet but did not enumerate Tier 2 members in prose.
- **Sonnet:** Explicitly stated "Tier 2 (REVENUE/PAYROLL/DEFERRED_REVENUE)".
- **Resolution: Sonnet is correct.** Verified at `comparison.py:18`: `_TIER2_CATEGORIES = {"REVENUE", "PAYROLL", "DEFERRED_REVENUE"}`. This matters because the Comparison gate for payroll variances is the lower $10K/3% threshold — recurring-detection logic should not assume Tier 1 numbers when reasoning about salary anomalies in the demo.

### Conflict C — DB migration needed for recurring flag?
- **Codex:** "Keep writes to same `anomalies` table … no orchestration redesign required" but mentions an optional metadata field.
- **Sonnet:** "No schema migration required" but mentions optional `is_recurring BOOLEAN`.
- **Resolution: Both agree it's optional. The merged answer is NO migration in Phase 1.** Defer to Phase 3 (Persistence) when filtering/sorting by recurrence becomes a UI requirement.

### Conflict D — Path 2 priority (Sonnet's "trend context" vs Codex's "quarterly on-demand")
- **Codex Path 2** = quarterly report on-demand.
- **Sonnet Path 2** = prior trend context in narrative (uses `get_prior_pandas_summaries()`).
- **Resolution: Sonnet's Path 2 is the correct #2.** Reasoning:
  - It's 2–3 hours of work and immediately enriches every narrative — same impact/effort signature as Path 1.
  - It composes with Path 1 to produce the most compelling demo line: "Engineering Salaries flagged again — 3rd consecutive month" comes from Phase 1's recurrence count *and* (already-existing) Opus trend context.
  - Quarterly is a bigger feature (now 2 days with full UI/UX spec) and a separate product surface; treating it as the next phase reflects the actual effort delta.
  - Codex's Path 2 ranking conflated "what's most valuable as a feature" with "what's the next-best impact/effort move."
  - **Final outcome (post-Conflict-F discovery):** Sonnet's Path 2 was correct in spirit but its implementation was redundant. The user opted for **Option 2a (do nothing)** because Opus already provides the trend context Sonnet's Path 2 wanted to add. Net plan: Phase 1 (recurring detection) + Phase 2 (quarterly report). The original Path 2 work is folded into "happens automatically through Opus's existing pipeline."

### Conflict E — "Lookback is mathematically a 6-month window" (Codex) vs "row-count-capped" (Sonnet)
- **Codex:** "in practice it behaves like 'recent history capped around 6 months assuming ~100 accounts/month,' not mathematically strict 6-calendar-month filtering."
- **Sonnet:** "It fetches all periods before the current one, not strictly 6 calendar months."
- **Resolution: They agree.** Both correctly identified that the `limit(lookback_months * 100)` cap is a row count, not a date filter. Phase 1's new `list_account_flag_counts_before` should use a **proper date-window filter** (`period >= before_period - interval '6 months'`) so recurrence math is not subject to the same row-cap quirk. Flagged for implementer awareness.

### Conflict F — Both analyses missed the dual-background-task flow (post-merge correction)
- **Codex:** Found `get_prior_pandas_summaries()` is called in `opus_upgrade.py` but did not document the parallel `run_comparison_and_report` + `run_opus_upgrade` execution model or that Opus **overwrites** `reports.summary`.
- **Sonnet:** Did not find the call site at all.
- **Resolution: Both were incomplete.** Verified by reading `routes.py:976-988`, `opus_upgrade.py:130`, and `supabase_repos.py:282`. The actual flow is:
  - Two background tasks fire in parallel after `POST /upload/confirm`.
  - Haiku writes the initial `reports` row.
  - Opus overwrites `reports.summary` via `reports_repo.upgrade_summary()` and sets `opus_upgraded=TRUE` on success; silent fail otherwise.
  - There is exactly one `reports` row per `(company_id, period)`.
- **Implication:** Phase 2 as originally written was redundant work. After the user chose Option 2a on 2026-04-26, the original Phase 2 was **dropped from the plan entirely**. Phases were renumbered: original Phase 3 → current Phase 2 (Quarterly Report); original Phase 4 → current Phase 3 (Persisted Quarterly Artifacts). This is reflected in Section 0 (verified flow), Section 1 (`get_prior_pandas_summaries` is consumed end-to-end, not unused), the dropped Phase 2 marker in Section 2, and Section 5 (Gantt updated).

### What only one analysis caught
| Finding | Source | Why it matters |
|---|---|---|
| `opus_upgrade.py` already calls `get_prior_pandas_summaries()` | Codex only | Phase 2 is wiring, not invention. |
| `_TIER2_CATEGORIES` exact membership including PAYROLL | Sonnet only | Demo storyline involves payroll; gate values matter. |
| `description` field flows verbatim into Claude's prompt context — no prompt change required for Phase 1 | Sonnet only (cites `interpreter.py:253–262`) | Cuts Phase 1 scope — no `narrative_prompt.txt` edit. |
| `lookback_months * 100` row cap is the actual DB query shape | Codex (with snippet) | Memory-feature designers should not assume strict date windows when reusing this method. |
| Concrete migration filename `0009_add_recurring_flag.sql` | Sonnet only | Aligns with the project's `0001..0008` sequence convention. |

---

## 4. Quick-Start: What To Build Tomorrow Morning

**Goal: ship a demo where uploading March data produces narrative containing "Engineering Salaries flagged again — 3rd consecutive month, recurring pattern."**

**Minimum viable changes (3 files, ~40 LOC):**

1. **`backend/domain/ports.py`** — extend the `AnomaliesRepo` Protocol:
   ```python
   def list_account_flag_counts_before(
       self, company_id: str, before_period: date, lookback_months: int = 6
   ) -> dict[str, int]: ...
   ```

2. **`backend/adapters/supabase_repos.py`** — implement on `SupabaseAnomaliesRepo`. SQL semantics:
   ```
   SELECT account_id, COUNT(DISTINCT period)
   FROM anomalies
   WHERE company_id = :company_id
     AND period < :before_period
     AND period >= :before_period - interval '6 months'
     AND severity != 'low'
   GROUP BY account_id
   ```
   Return `{account_id: count}`. Use a proper date filter (not a row-count cap).

3. **`backend/agents/comparison.py`** — at the top of `ComparisonAgent.run()`, before the per-entry loop:
   ```python
   prior_flag_counts = self._anomalies.list_account_flag_counts_before(
       company_id, period, lookback_months=6
   )
   ```
   Then in the loop, when `result["flag"]` is true, build the description:
   ```python
   prior = prior_flag_counts.get(entry.account_id, 0)
   if prior >= 2:
       description += f" Flagged in {prior} of the past 6 months — recurring pattern."
   ```

**Optional polish (skip if time-pressed):**
4. `frontend/src/components/AnomalyCard.tsx` — render a 🔁 badge when description contains "recurring pattern".

**Expected demo flow:**
1. User clicks "Upload March 2026" with `drone_mar_2026.xlsx`.
2. Pipeline runs Parser → Comparison → Interpreter.
3. Comparison sees Engineering Salaries was flagged in Jan and Feb → appends "Flagged in 2 of the past 6 months — recurring pattern" to its description.
4. Claude receives the enriched description and writes prose like: *"Engineering Salaries continues to run hot, flagged again this month — the third consecutive month above the 6-month mean."*
5. Guardrail passes (no new numbers introduced by Claude).
6. Report renders; UI optionally shows the 🔁 badge.

This is the agentic-memory story in three files and zero migrations.

---

## 5. Implementation Sequence (Gantt-style)

```
Day 1 (3-4 hr)              ████████  Phase 1: Recurring Anomaly Detection
                                      (backend-only: ports.py, supabase_repos.py, comparison.py)

Day 2 (full day, ~8 hr)     ━━━━━━━━━━━━━━━━━  Phase 2 backend
                                      (quarterly.py agent + 2 endpoints + prompt + Python aggregation + YoY)

Day 3 (full day, ~8 hr)                       ━━━━━━━━━━━━━━━━━  Phase 2 frontend
                                      (QuarterlyReportPage + QuarterlyProgress + ReportsPage CTA + ReportPage banner + sessionStorage + error states)
DEMO ▼
Post-demo (1 week+)                                                ──────────────  Phase 3: Persisted Quarterly Artifacts
```

**Dependencies**
- **Phase 1 → Phase 2:** Phase 2 reuses Phase 1's recurrence signal in the anomaly grouping and the narrative prompt. Ship Phase 1 first; Phase 2 then inherits a richer baseline. **Phase 2 backend before Phase 2 frontend** — frontend cannot be built until the `/generate` and `/status` endpoints are stable.
- **Phase 2 → Phase 3:** Phase 3 promotes Phase 2's stateless endpoint into a persisted artifact. Phase 2 must ship first; Phase 3 is purely additive.

**Demo cut-line:** end of Day 3. Phase 1 + Phase 2 give the full agentic-memory story:
- Recurring anomalies surfaced through Opus's existing trend-context narrative.
- Quarterly summary with progressive-disclosure loading, missing-month tolerance, YoY comparison, and recurrence-grouped anomaly display.

Phase 3 (Persistence) is post-demo hardening, not required for the hackathon.

---

## Flagged uncertainties

- **Date arithmetic in Postgres:** the `period >= before_period - interval '6 months'` snippet uses Postgres date arithmetic; if the project uses Supabase RPCs vs raw SQL through PostgREST, the implementer may need to express this via two `.gte` / `.lt` filters in the supabase-py builder. Verify against existing patterns in `supabase_repos.py` before committing.
- **Severity filter in recurrence query:** chose `severity != 'low'` to avoid noise. If the demo's flagged accounts trip on `low` severity in some months, this filter could undercount. Adjust empirically against the seed data.
- **Guardrail key collisions in Phase 2 quarterly aggregation:** flattening per-month + quarter aggregates + YoY deltas into the same `aggregated_summary` dict requires unique keys (`jan_revenue`, `q_total_revenue`, `yoy_revenue_pct`, etc.). Confirm no collisions during implementation. Suggested prefixes already designed to be collision-free.
- **In-memory `_quarterly_jobs` dict:** Phase 2 stores progress state in a process-local dict. If Render restarts the container mid-job, the user's polling loop will 404. For MVP this is acceptable (rare, retryable). Production needs Redis (post-MVP).
- **Anthropic Opus latency variance:** the 10–20 second estimate is empirical. If Opus runs >30 seconds, the progressive-disclosure UX still works but feels slow. Consider showing a "This is taking longer than usual" message after 25s.

# Discovery & Mapping Layer — Implementation Plan
*IronLedger post-hackathon work — pivots the Parser from rigid schema-first to LLM-first preprocessing*

A twelve-step plan for introducing a Discovery & Mapping Layer between raw file upload and database writes. The layer is LLM-first for structure interpretation, deterministic for transformation. Written as a durable reference: each step documents **goal, files, changes, rationale, deliverable, and verification**, so a future reader can resume mid-sprint without re-deriving context.

Related: [`risks.md`](./risks.md) for cross-cutting risks · [`../agent-flow.md`](../agent-flow.md) for the existing parser flow · [`../../CLAUDE.md`](../../CLAUDE.md) for the Golden Rule.

---

## 0. Context

### Why we are doing this
The current parser fails on real QuickBooks Online / NetSuite exports because it assumes a clean tabular file: `pd.read_excel(..., engine="openpyxl")` at `backend/tools/file_reader.py:32` takes row 0 as the header, and `_SCHEMA` at `backend/tools/validator.py:13-20` hard-codes three canonical column names (`amount`, `period`, `account`) before any LLM has had a chance to interpret what the file *is*. QBO files ship with a 4-row metadata preamble, banner rows (`"Cost of Goods Sold"` with no amount), subtotal rows (`"Gross Profit"`, `"Net Income"`), per-transaction dates rather than a `period` column, and account labels with embedded codes (`"4000 - HobiFly X1"`). None of this survives the current pipeline.

The fix is structural: move LLM interpretation **upstream** of schema validation. Let Haiku identify the file's shape, then let Python apply the plan deterministically, then let pandera validate the *output* of normalization rather than the raw import.

### Decomposition philosophy
Claude reaches ~99% accuracy when each prompt has a single narrow scope. The system already has three Claude calls — Discovery (structure), Category Mapping (semantics), Narrative (prose) — each with a tightly bounded responsibility. Further sub-splitting (e.g. "find the header" as its own call, "classify each row" as a second) is a tool we reach for **only if** a specific prompt starts failing on real production files. Splitting pre-emptively costs 3–4× API calls, latency, and orchestration complexity for no measurable accuracy gain on well-formed files. Ship three, measure, decompose further only where data demands it.

### Golden Rule (restated, non-negotiable)
**Numbers come from pandas. Prose comes from Claude. A numeric guardrail verifies both match.**
- Discovery identifies *structure*. It does not produce numbers (except row indices and confidence).
- Normalization is pure Python. No LLM call may ever be added here.
- Category Mapping produces *labels*. It does not produce numbers.
- Every dollar amount in the final narrative passes through the guardrail at `backend/tools/guardrail.py`.

---

## 1. Architecture Overview

### Pipeline — before
```
read (whole file)
  → skip metadata (absent)
  → detect header (absent)
  → STRIP PII (columns only)
  → pandera validate (rigid: amount/period/account required)
  → column map (Claude Haiku, aggregated per account)
  → normalize
  → write
```
Pandera is the gatekeeper. Claude is only allowed to interpret *after* the frame already matches the Golden Schema — which it never does for real QBO exports.

### Pipeline — after
```
download
  → raw cell-level read (100 rows × 10 cols)
  → PII sanitize (sample — value-level regex)           [sanitize_sample]
  → DISCOVERY (Claude Haiku) ← new
       │
       ├─ confidence ≥ 0.80  → auto-advance, mode='auto'
       └─ confidence < 0.80  → halt @ AWAITING_DISCOVERY_CONFIRMATION
                                (user clicks Confirm → resume, mode='manual')
  → full file read
  → PII sanitize (full — column-level blacklist)
  → NORMALIZE (pure Python) → (DataFrame, NormalizerDropReport)  ← new
  → pandera validate (Golden Schema, strict=True)
  → CATEGORY MAP (Claude Haiku, enriched with parent_category + department)
  → build parse_preview { rows, source_column, drops }
  → halt @ AWAITING_CONFIRMATION                                  (existing gate)
  → user clicks Confirm → write monthly_entries → COMPARING → ...
```
Pandera moves to the back door. Strictness now enforces the shape of *our own* output, not the shape of the user's file. Claude sees the file first; deterministic code sees the plan second. **Two distinct user-confirmation gates** — one for Discovery's plan, one for the category mapping preview — with distinct states so the frontend never has to guess which modal to render.

### Folder changes summary

| Path | Action | Purpose |
|---|---|---|
| `backend/agents/discovery.py` | **NEW** | `DiscoveryAgent` use case — one Haiku call, returns `DiscoveryPlan` |
| `backend/tools/normalizer.py` | **NEW** | Pure Python. Applies a `DiscoveryPlan` to a DataFrame. No LLM. |
| `backend/prompts/discovery_prompt.txt` | **NEW** | Structure-detection prompt. JSON-only output. |
| `backend/prompts/discovery_prompt_reinforced.txt` | **NEW** | Semantic-retry prompt when first plan is invalid |
| `backend/tools/file_reader.py` | **MODIFIED** | Add `read_raw_cells(path, max_rows)` using `openpyxl` cell API |
| `backend/tools/pii_sanitizer.py` | **MODIFIED** | Add `sanitize_sample(rows)` — value-level regex for the pre-Discovery sample |
| `backend/tools/validator.py` | **MODIFIED** | Extend pandera schema with nullable extras; flip `strict=True` |
| `backend/agents/parser.py` | **MODIFIED** | Orchestrates: raw read → DiscoveryAgent → normalize → existing mapping flow |
| `backend/domain/contracts.py` | **MODIFIED** | Add `DiscoveryPlan`, `HierarchyHint`, `GoldenSchemaRow` Pydantic models |
| `backend/domain/errors.py` | **MODIFIED** | Add `DiscoveryFailed`, `DiscoveryLowConfidence` |
| `backend/domain/run_state_machine.py` | **MODIFIED** | Add `DISCOVERING` + `DISCOVERY_FAILED` states |
| `backend/messages.py` | **MODIFIED** | Add user-facing strings for discovery states |
| `backend/api/deps.py` | **MODIFIED** | Wire `DiscoveryAgent` into `ParserAgent` constructor |
| `supabase/migrations/0006_add_discovery_plan.sql` | **NEW** | `runs.discovery_plan` JSONB column |
| `tests/fixtures/discovery/*` | **NEW** | Fixture Excel files covering QBO / NetSuite / flat CSV / PII-laced |
| `tests/agents/test_discovery.py`, `tests/tools/test_normalizer.py` | **NEW** | Unit + contract tests |

No new subdirectories. No changes to the three-agent mental model — Discovery lives *inside* the Parser agent's orchestration because it shares `run_id`, `company_id`, and `storage_key` with the rest of parsing.

---

## 2. Where AI is Used (by stage)

Three Claude calls in the full pipeline after this work ships. Two of those are now inside the Parser agent (Discovery + Category Mapping); one is the existing Interpreter (Narrative).

| # | Stage | AI? | Model | Responsibility | Why AI | What AI does NOT do |
|---|---|---|---|---|---|---|
| 1 | **Discovery** (new) | ✅ | `claude-haiku-4-5-20251001` | Identify structure: header row, skip rows, column → Golden Schema, parent_category per line item | Regex/heuristics don't generalize across QBO/NetSuite/Xero/user Excel. Formatting + semantic signals require language understanding. | Arithmetic. Category semantics (deferred to stage 3). Any numbers beyond row indices + confidence. |
| 2 | **Normalization** | ❌ | — | Apply DiscoveryPlan deterministically | — | This is the determinism firewall. Code review rule: no LLM call may ever be added here. |
| 3 | **Category Mapping** (existing, enriched) | ✅ | `claude-haiku-4-5-20251001` | Assign US GAAP category per account, now disambiguated by `parent_category` + `department` | `"Freight-In"` under COGS vs. Sales is semantic, not structural | Arithmetic. Inventing categories outside the fixed enum. |
| 4 | **Comparison** | ❌ | — | Variance vs. history, anomaly flags | — | Called out deliberately: "anomaly detection" is pandas thresholds, not AI. Golden Rule. |
| 5 | **Narrative + anomaly reasons** | ✅ | `claude-opus-4-7` | CFO-facing prose referencing pandas numbers only | Human-readable synthesis | Arithmetic. Every number in prose must match `PandasSummary` within 2% via guardrail. |
| 6 | **Guardrail + Email** | ❌ | — | Verification + delivery | — | Deterministic. The thing that catches AI mistakes can't itself be AI. |

**Pattern to remember:** AI handles language tasks (structure, semantics, prose). Pandas owns every number. The guardrail enforces the boundary.

---

## 3. Contracts (locked — Phase 1 shipped)

Defined in `backend/domain/contracts.py`. Pure Python — no pandas, anthropic, or supabase imports (per CLAUDE.md `domain/` rule). Pydantic v2 `Literal` + `Annotated[Field]` enforce enums and bounds at the boundary.

```python
GoldenField = Literal[
    "account", "account_code", "amount", "date",
    "parent_category", "department", "description",
]
Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
RowIndex   = Annotated[int, Field(ge=0)]

class HierarchyHint(BaseModel):
    row_index: RowIndex
    parent_category: str               # e.g. "Cost of Goods Sold"

class DiscoveryPlan(BaseModel):
    header_row_index: RowIndex
    skip_row_indices: list[RowIndex]
    column_mapping: dict[str, GoldenField | None]
    hierarchy_hints: list[HierarchyHint]
    discovery_confidence: Confidence
    notes: str = ""

class GoldenSchemaRow(BaseModel):      # what Normalizer produces per row
    account: str
    account_code: str | None = None
    amount: float
    date: date
    parent_category: str | None = None
    department: str | None = None
    description: str | None = None


class DropReason(BaseModel):           # per-row drop record from the Normalizer
    row_index: int
    account_snippet: str                # ≤40 chars, PII-scrubbed
    reason: Literal["amount_coerce_failed", "subtotal_safety_net"]


class NormalizerDropReport(BaseModel):
    entries: list[DropReason]
    total_dropped: int
```

**Allowed Golden Schema field names** (enforced by `GoldenField` Literal — Claude cannot invent new ones):
`account | account_code | amount | date | parent_category | department | description | None`

Nothing else. Any other value in `column_mapping` → Pydantic `ValidationError` → semantic retry in `DiscoveryAgent` → fail.

**Deliberate exclusions** (do not re-add without a migration):
- `period` — renamed to `date` (US market convention)
- `parent_section` — renamed to `parent_category`
- `source_row_index` — dropped per strict Golden Schema freeze. Provenance via `AnomalyCard` tooltip uses `source_column` (already on `monthly_entries`) plus filename. Row-level provenance is post-MVP.

---

## 4. Eleven-Step Implementation Plan

Each step is a single PR. After each step, run the **Verification** block to catch syntax errors and broken imports before moving on. Never skip verification — the whole point of eleven steps instead of one is that errors stay small and local.

**Progress at a glance:**

| Phase | Steps | Status |
|---|---|---|
| 1 — Foundation (contracts, reader, prompt) | 1, 2, 3 | ✅ Shipped 2026-04-23 |
| 2 — Agent + Normalizer + Schema | 4, 5, 6 | ✅ Shipped 2026-04-23 |
| 2.5 — Sample PII sanitizer | 3.5 | ✅ Shipped 2026-04-23 |
| 3 — State machine + migration + routes + parser rewire + drop report | 7, 8, 9, 10 | ✅ Shipped 2026-04-23 |
| 4 — Fixtures + integration tests | 11 | ✅ Shipped 2026-04-23 |

**Deferred from original plan (must land before Phase 3's parser rewire):** sample-level PII sanitizer (`sanitize_sample()` in `backend/tools/pii_sanitizer.py`). Required to keep **R-006** mitigated once the Parser actually ships the raw sample to Claude. ✅ Shipped 2026-04-23 as Phase 2.5.

---

### §4a — Phase 3 integration primer (locked 2026-04-23)

The ten product decisions that drive Phase 3's concrete design. Everything in Steps 7-11 is a consequence of these — change one and the steps ripple.

| # | Decision |
|---|---|
| **D1** | Two new states: `DISCOVERING`, `AWAITING_DISCOVERY_CONFIRMATION`. `PARSING → MAPPING` transition is **removed** (Discovery is now mandatory on every run). |
| **D2** | `PARSING_FAILED` absorbs all pre-Interpreter failures including `DiscoveryFailed` and user rejection. No `DISCOVERY_FAILED` enum (R-012 precedent). |
| **D3** | Migration 0006: `discovery_plan JSONB` (nullable) + `discovery_approval_mode TEXT CHECK IN ('auto','manual')` (nullable). |
| **D4** | `ParserAgent` splits into `.discover()` and `.resume_from_plan()`. Orchestrator grows `run_parser_after_discovery_approval()`. |
| **D5** | Two new routes: `POST /runs/{id}/confirm-discovery` (body: `{plan_override: DiscoveryPlan | null}`), `POST /runs/{id}/reject-discovery`. |
| **D6** | `normalizer.apply_plan` returns `tuple[DataFrame, NormalizerDropReport]`. Report attached to `parse_preview["drops"]` (shape `{entries, total_dropped}`). `account_snippet` passed through `_scrub_value` (substring-level `re.sub`) **then** truncated to 40 chars. Order is load-bearing: truncating first would let a partial PII match (e.g. `"alice@"` with no TLD) escape the email regex. Enforced by `test_scrub_before_truncate_prevents_partial_email_leak`. |
| **D7** | `discovery_plan._preview` (underscore-prefixed, DB-only) stores first 20×10 sanitized cell values so `DiscoveryConfirmationModal` renders without a second file fetch. Not part of the `DiscoveryPlan` Pydantic model — added/stripped in the adapter layer. |
| **D8** | V1 ships Confirm/Reject only. V2 editing is endpoint-ready (accepts `plan_override`) but no frontend editor. |
| **D9** | Audit: `discovery_approval_mode` column + structured log at approval with counts only (never cell values, never column names — column names themselves can leak PII-like headers). |
| **D10** | Rejection path = re-upload only. Storage file stays (accepted per R-015). No manual-override UI, no retry-with-Sonnet. |

### Transition graph (post-Phase 3)

```
pending ──► parsing ──► discovering ──► mapping ──► awaiting_confirmation ──► comparing ──► generating ──► complete
                            │                            (mapping-review)          │              │
                            ├── awaiting_discovery_confirmation ──► mapping        │              │
                            │        (plan-review)                                 │              │
                            └─────────────── parsing_failed ───────────────────────┘              └──► guardrail_failed
```

### Integration timeline (where state + DB + code land)

| Time | status | discovery_plan | approval_mode | parse_preview |
|---|---|---|---|---|
| t0 | `pending` | NULL | NULL | NULL |
| t1 | `parsing` | NULL | NULL | NULL |
| t2 | `discovering` | NULL | NULL | NULL |
| t3 (low-conf) | `awaiting_discovery_confirmation` | **set** | NULL | NULL |
| t3 (high-conf) | *(skipped — auto-advance)* | **set** | `'auto'` | NULL |
| t4 | `mapping` | set | set | NULL |
| t5 | `awaiting_confirmation` | set | set | **set** (incl. `drops`) |
| t6+ | `comparing` → `complete` | preserved | preserved | preserved |

Everything after t5 is unchanged from today — the existing `confirm_run` route and `run_comparison_and_report` orchestrator flow both work without modification.

---

---

### Step 1 — Freeze the contracts ✅ SHIPPED

**Goal:** Commit the Pydantic shapes for `DiscoveryPlan`, `HierarchyHint`, `GoldenSchemaRow`. Everything downstream hangs on these.

**Files:**
- MODIFY `backend/domain/contracts.py` — append three Pydantic models
- MODIFY `backend/domain/errors.py` — add `DiscoveryFailed`, `DiscoveryLowConfidence`

**Changes:**
- Add the three models as specified in §3 above. No logic, no behavior — just shapes.
- `DiscoveryFailed` subclasses `Exception`, mirrors `MappingAmbiguous` style at `backend/domain/errors.py`.
- `DiscoveryLowConfidence` subclasses `Exception` — raised when plan's `discovery_confidence < 0.80` and user confirmation is required.

**Why:** Contract-first. Later steps depend on these imports resolving. A mistake here cascades; fixing it now costs one PR rather than twelve.

**Deliverable:** `from backend.domain.contracts import DiscoveryPlan, HierarchyHint, GoldenSchemaRow` succeeds in a Python REPL.

**Verification:**
```bash
black backend/domain/ && flake8 backend/domain/
python -c "from backend.domain.contracts import DiscoveryPlan, HierarchyHint, GoldenSchemaRow; print('OK')"
python -c "from backend.domain.errors import DiscoveryFailed, DiscoveryLowConfidence; print('OK')"
pytest tests/domain/ -v   # existing domain tests must still pass
```

---

### Step 2 — Cell-level raw reader ✅ SHIPPED

**Goal:** Add `read_raw_cells()` to capture the first 100 rows × 10 columns with bold/indent/merged-cell flags. This is the sample Discovery will scan.

**Files:**
- MODIFIED `backend/tools/file_reader.py`

**What shipped:**
```python
def read_raw_cells(
    filepath: Path,
    max_rows: int = 100,
    max_cols: int = 10,
) -> list[dict[str, Any]]:
    """Return raw rows with visual formatting flags for the Discovery sample."""
```
- `.xlsx` / `.xlsm`: full formatting via openpyxl `load_workbook(data_only=True, read_only=False)`. Captures `font.bold`, `alignment.indent`, and merged-range membership.
- `.csv` / XML spreadsheet / `.xls` binary: fallback via pandas with `header=None`. Flags default to `False / 0.0 / False` — prompt tolerates missing hints.
- Leaves existing `read_file()` unchanged (still the full-file reader after Discovery returns).

**Why:** Without bold/indent, Haiku has no signal distinguishing a banner from a line item. Those cues are how a human accountant recognises hierarchy; we give Claude the same signal.

**Verified against `Drone Inc - Mar 26.xlsx`** (2026-04-23):
- Rows 0-3 (metadata): `bold=False`, single value per row, no indent — prompt's Rule 1 handles this shape correctly.
- Row 5 (real header): `bold=True`, 7 non-null values — prompt's Rule 2.
- Row 6 `REVENUE`: `bold=True`, single value — banner (Rule 3).
- Rows 7-12 (line items): `bold=False`, `indent_level=1.0` — Rule 4.
- Row 13 `Total Revenue`: `bold=True`, multi-value — subtotal (Rule 5).

**Verification:**
```bash
black backend/tools/file_reader.py && flake8 backend/tools/file_reader.py
python -c "
from pathlib import Path
from backend.tools.file_reader import read_raw_cells
rows = read_raw_cells(Path('docs/demo_data/Drone Inc - Mar 26.xlsx'))
assert len(rows) > 0
assert 'is_bold' in rows[0]
assert 'indent_level' in rows[0]
print(f'OK — {len(rows)} rows')
"
pytest tests/tools/test_file_reader.py -v
```

---

### Step 3 — Discovery prompt ✅ SHIPPED

**Goal:** Author the structure-detection prompt that Haiku consumes.

**Files:**
- CREATED `backend/prompts/discovery_prompt.txt` (135 lines)

**What shipped:**
1. Role statement: "You identify structure. You do NOT calculate."
2. Input schema: `{rows: [{row_index, values, is_bold, indent_level, is_merged}]}`.
3. Output schema: `DiscoveryPlan` JSON, no prose, no markdown fences.
4. Allowed Golden Schema fields enumerated (matches `GoldenField` Literal).
5. **Six visual-cue rules** (metadata / header / banner / data / subtotal / tiebreaker).
6. **Golden Rule reinforcement** as its own section: "The only numbers you emit are row indices, and discovery_confidence."
7. **Confidence calibration ladder** (0.95+ / 0.85-0.94 / 0.80-0.84 / <0.80 = halt for user confirmation).
8. Three worked examples: flat CSV / QBO with hierarchy (real DRONE shape) / NetSuite with department column.

**Self-validation:** All three example outputs were parsed against `DiscoveryPlan.model_validate()` at write time — the prompt's own answers pass its own schema.

---

### Step 3.5 — Sample-level PII sanitizer ✅ SHIPPED

**Goal:** Strip PII values from the raw sample before it leaves for Claude. Must land before Phase 3 parser rewire actually sends the sample over the wire.

**Why skipped from Phase 1:** User decision to move fast on contracts/reader/prompt. Safe to defer only as long as nothing actually calls the LLM with a user-supplied sample. Phase 2 (this one) still doesn't wire the agent to the parser, so R-006 stays mitigated-by-absence. **Must not ship Phase 3 without this.**

**Files (when landed):**
- MODIFY `backend/tools/pii_sanitizer.py` — add `sanitize_sample(rows: list[dict]) -> list[dict]`
- Value-level regex: SSN (existing `_SSN_REGEX`) + bank-account (10+ consecutive digits) + capitalized-bigram name heuristic (false-positive tolerant)
- Replaces matched values with `"[REDACTED]"`. Never logs cell values; logs `event="pii_sanitization_sample"`, `trace_id`, `cells_redacted`, `categories`.

---

### Step 4 — Build `DiscoveryAgent` ✅ SHIPPED

**Goal:** The use case that calls Haiku, validates the returned plan semantically, performs a single retry with an error hint, and surfaces low-confidence results so the caller can transition the run to `AWAITING_CONFIRMATION`.

**Files:**
- CREATE `backend/agents/discovery.py`

**Design:**
- Class `DiscoveryAgent` with dependencies: `LLMClient` only (no `RunsRepo` — agent stays stateless, orchestrator handles persistence). Mirrors the minimal shape of `interpreter.py`.
- Method `discover(run_id: str, sample: list[dict]) -> DiscoveryPlan`:
  1. Call `self._llm.call(prompt="discovery_prompt.txt", model="claude-haiku-4-5-20251001", context={"rows": sample}, schema=DiscoveryPlan)`. Pydantic rejects malformed plans automatically (bad `GoldenField` Literal, out-of-range `RowIndex`, etc.).
  2. Apply **semantic validation**: `header_row_index < len(sample)`; at least one `column_mapping` value is `"amount"`; at least one is `"account"`.
  3. **On validation failure (Pydantic or semantic): retry once** with the same prompt, but pack the rejection reason into `context` as `{"rows": sample, "previous_error": "<reason>"}`. The prompt tolerates the extra key. If retry also fails → raise `DiscoveryFailed`.
  4. If `plan.discovery_confidence < 0.80`: raise `DiscoveryLowConfidence(plan)`. The exception carries the plan so the orchestrator can persist it to `runs.discovery_plan` and transition to `AWAITING_CONFIRMATION`.
  5. Otherwise return the plan.
- **Scope boundary:** the agent does **not** transition run state or write to any repo. That happens in Phase 3's parser rewire, where `DISCOVERING` is added to the state machine and `runs.discovery_plan` gets its JSONB column. Keeping the agent stateless in Phase 2 lets it ship and be unit-tested before the DB schema catches up.
- **I/O retries stay in the adapter** (`anthropic_llm.py`). Semantic retry is the agent's responsibility, per CLAUDE.md §Retry ("the use case retries bad content").
- Why no separate `discovery_prompt_reinforced.txt`: packing the error hint into `context` achieves the same effect with zero extra prompt surface to maintain. A second file can come back post-MVP if retry accuracy is insufficient.

**Why:** Separation of semantic vs. I/O retry mirrors the existing guardrail retry in `agents/interpreter.py`. One retry discipline across all three agents — future readers reason about it once, not three times.

**Deliverable:** `DiscoveryAgent(mock_llm).discover("run-xyz", fixture_sample)` returns a valid `DiscoveryPlan` for a clean fixture, raises `DiscoveryLowConfidence` for a conf=0.5 plan, raises `DiscoveryFailed` when both the initial and retry plans are semantically invalid.

**Verification:**
```bash
black backend/agents/discovery.py && flake8 backend/agents/discovery.py
python3 -c "from backend.agents.discovery import DiscoveryAgent; print('OK')"
```
Planned tests (land with Phase 4 fixture suite):
- `test_discovery_returns_plan_for_clean_sample`
- `test_discovery_retries_once_on_missing_amount_mapping`
- `test_discovery_raises_failed_after_retry_still_invalid`
- `test_discovery_raises_low_confidence_at_0_79`
- `test_discovery_exception_carries_plan_object` (orchestrator needs `.plan`)

---

### Step 5 — Build the Normalizer ✅ SHIPPED (drop-report extension shipped in Step 10)

**Goal:** Pure Python function that applies a `DiscoveryPlan` to a raw DataFrame. No LLM. This is the determinism firewall.

**Files:**
- CREATE `backend/tools/normalizer.py`

**Changes:**
- Single public function:
  ```python
  def apply_plan(
      df_raw: pd.DataFrame,
      plan: DiscoveryPlan,
      period: date,
  ) -> pd.DataFrame:
      """Deterministically transform a raw DataFrame using the given plan.
      Returns a DataFrame conforming to the Golden Schema (seven fields)."""
  ```
- Sequence:
  1. Drop rows whose index ∈ `plan.skip_row_indices`.
  2. Promote `plan.header_row_index` to the column header; drop rows above and including it.
  3. Rename columns per `plan.column_mapping`; drop columns mapped to `None`.
  4. Parse account-code prefix via regex `^(\d{3,5})\s*[-–—]\s*(.+)$` → `account_code` column + stripped `account`.
  5. Attach `parent_category` by joining `plan.hierarchy_hints` on row index. (If Discovery mapped a file column to `parent_category`, that column takes precedence.)
  6. Inject `date` uniformly from the upload's `period` argument (month-start). This matches today's `monthly_entries.period` semantics — per-row dates from the file are out of scope for MVP.
  7. Fill missing optional columns (`account_code`, `parent_category`, `department`, `description`) as `None` so pandera's nullable check passes.
  8. Coerce `amount` to float; rows where coercion fails are **logged by row index only** (never value) and dropped.
  9. **Belt + suspenders subtotal check** (per §Risk Mitigations): if any surviving row's `account` matches regex `^(Total|Gross|Net)\b|.*%$`, drop it and log a warning. This protects against a Discovery mistake.

**Why:** This function is where the Golden Rule is enforced architecturally. A malicious or hallucinated `DiscoveryPlan` can only skip / rename / drop — it cannot compute. No dollar amount originates here.

**Deliverable:** Fixture test: given the DRONE Mar 2026 file + a hand-authored `DiscoveryPlan`, `apply_plan` returns a DataFrame with 20-25 rows, all required Golden Schema columns present, no subtotal rows surviving.

**Verification:**
```bash
black backend/tools/normalizer.py && flake8 backend/tools/normalizer.py
python -c "from backend.tools.normalizer import apply_plan; print('OK')"
pytest tests/tools/test_normalizer.py -v
```
Must-pass tests:
- `test_apply_plan_produces_golden_schema_shape`
- `test_apply_plan_parses_account_code_prefix`
- `test_apply_plan_drops_total_gross_net_rows_as_safety_net`
- `test_apply_plan_never_calls_llm` (patches `LLMClient` and asserts zero calls)

---

### Step 6 — Extend pandera validator ✅ SHIPPED

**Goal:** Widen the schema to the full seven-field Golden Schema; flip `strict=True` since we now own the input shape.

**Files:**
- MODIFY `backend/tools/validator.py`

**Changes:**
```python
_SCHEMA = DataFrameSchema(
    {
        "account":         Column(str,  nullable=False),
        "account_code":    Column(str,  nullable=True),
        "amount":          Column(float, nullable=False),
        "date":            Column(pa.DateTime, nullable=False),
        "parent_category": Column(str,  nullable=True),
        "department":      Column(str,  nullable=True),
        "description":     Column(str,  nullable=True),
    },
    strict=True,
    coerce=True,
)
```

**Why:** Strictness was inverted before — it guarded the *input*. Now it guards the *output* of normalization, which is where strictness belongs. A stray column in the Normalizer output is a loud failure instead of a silent pass-through.

**Known breakage during transition:** `parser.py` today injects a `period` column and calls `validator.validate()`. With the new schema, strict mode will reject that DataFrame until Phase 3 swaps the Parser path to call the Normalizer (which produces `date`). Existing `tests/agents/test_parser.py` will fail between Phase 2 landing and Phase 3 landing. This is expected — flag it in the PR description.

**Deliverable:** `validator.validate()` accepts a Normalizer output DataFrame with all seven fields; rejects any DataFrame missing `date` or containing extra columns.

**Verification:**
```bash
black backend/tools/validator.py && flake8 backend/tools/validator.py
pytest tests/tools/test_validator.py -v
# tests/agents/test_parser.py will fail — see Known breakage above
```

---

### Step 7 — State machine + messages ⏸ Phase 3

**Goal:** Two new enum values, three new transitions, one removed transition, user-facing copy.

**Files:**
- MODIFY `backend/domain/run_state_machine.py`
- MODIFY `backend/messages.py`
- MODIFY `backend/agents/parser.py:74` — the existing `PARSING → MAPPING` transition becomes `PARSING → DISCOVERING`. This is the only call site for that transition (verified by grep).

**Changes:**

```python
# RunStatus additions
DISCOVERING = "discovering"
AWAITING_DISCOVERY_CONFIRMATION = "awaiting_discovery_confirmation"

# _ALLOWED updates
RunStatus.PARSING: frozenset({
    RunStatus.DISCOVERING,         # was: RunStatus.MAPPING (REMOVED)
    RunStatus.PARSING_FAILED,
}),
RunStatus.DISCOVERING: frozenset({
    RunStatus.MAPPING,
    RunStatus.AWAITING_DISCOVERY_CONFIRMATION,
    RunStatus.PARSING_FAILED,
}),
RunStatus.AWAITING_DISCOVERY_CONFIRMATION: frozenset({
    RunStatus.MAPPING,
    RunStatus.PARSING_FAILED,
}),
```

**Messages:**
- `DISCOVERY_LOW_CONFIDENCE`: "We need you to review how we read this file before continuing."
- `DISCOVERY_REJECTED`: "You rejected our reading of this file. Please try a different export."
- `DISCOVERING_STEP_LABEL`: "Understanding your file..." (frontend progress bar copy)

**Why `PARSING → MAPPING` is removed, not supplemented:** Discovery is now mandatory. Leaving the old transition in would let a caller bypass Discovery by accident. Failing loud with `InvalidRunTransition` on any stale caller is the right discipline.

**Verification:**
```bash
black backend/domain/ backend/messages.py backend/agents/parser.py
flake8 backend/domain/ backend/messages.py backend/agents/parser.py
grep -rn "PARSING.*MAPPING" backend/    # must return nothing
pytest tests/domain/ -v                 # allowed transitions test
```

**Goal:** Insert `DISCOVERING` + `DISCOVERY_FAILED` states and their user-facing strings.

**Files:**
- MODIFY `backend/domain/run_state_machine.py`
- MODIFY `backend/messages.py`

**Changes:**
- Add enum members `DISCOVERING`, `DISCOVERY_FAILED`.
- Allowed transitions:
  ```
  pending → parsing → discovering
  discovering → (awaiting_confirmation | mapping | discovery_failed)
  ```
  Re-use the existing `awaiting_confirmation` state for low-confidence plans — avoids state explosion.
- `messages.py`: add `DISCOVERY_FAILED = "We couldn't understand the structure of your file. Please try a different export or contact support."` and `DISCOVERY_LOW_CONFIDENCE = "We need you to review how we read this file before continuing."`

**Why:** Status drives the frontend progress bar. Without these states, the UX shows "Parsing..." for the whole Discovery step and the user sees no feedback when Discovery is the slow part.

**Deliverable:** State machine unit tests cover every new transition.

**Verification:**
```bash
black backend/domain/ backend/messages.py && flake8 backend/domain/ backend/messages.py
pytest tests/domain/test_run_state_machine.py -v
```

---

### Step 8 — Migration + repo methods ⏸ Phase 3

**Goal:** Two nullable columns on `runs`, one new repo method with port declaration.

**Files:**
- CREATE `supabase/migrations/0006_add_discovery_plan.sql`
- MODIFY `backend/adapters/supabase_repos.py` — add `SupabaseRunsRepo.set_discovery_plan()`
- MODIFY `backend/domain/ports.py` — add `RunsRepo.set_discovery_plan()` Protocol method

**Migration:**

```sql
-- supabase/migrations/0006_add_discovery_plan.sql
ALTER TABLE runs
  ADD COLUMN discovery_plan JSONB,
  ADD COLUMN discovery_approval_mode TEXT
    CHECK (discovery_approval_mode IN ('auto', 'manual'));
```

No default. No index. Both nullable. Inherits RLS through `runs_via_company`.

**Repo method signature:**
```python
def set_discovery_plan(
    self,
    run_id: str,
    plan: dict,                                           # DiscoveryPlan.model_dump()
    approval_mode: Literal["auto", "manual"] | None = None,
) -> None:
    """Persist the plan (always) and approval mode (when known).

    approval_mode=None is used when setting the plan at DISCOVERING time
    before user review — it stays NULL until either auto-advance sets 'auto'
    or confirm-discovery route sets 'manual'.
    """
```

**DB-only `_preview` convention (D7):** The adapter adds `plan_dict["_preview"]` = sanitized first 20×10 values before the JSONB write, and strips it on read back into `DiscoveryPlan`. Keeps the Pydantic model pure while giving the frontend what it needs for the modal.

**Read path:** existing `get_by_id()` returns a dict including `discovery_plan` and `discovery_approval_mode` as keys. No new reader needed.

**Verification:**
```bash
supabase db push
psql $DATABASE_URL -c "\\d runs"     # expect: discovery_plan jsonb, discovery_approval_mode text
psql $DATABASE_URL -c "INSERT INTO runs (company_id, period, discovery_approval_mode) \
  VALUES (gen_random_uuid(), '2026-03-01', 'bogus');"  # expect: CHECK violation
```

**Goal:** Store the Discovery plan per run for debugging and for the low-confidence confirmation modal.

**Files:**
- CREATE `supabase/migrations/0006_add_discovery_plan.sql`

**Changes:**
```sql
ALTER TABLE runs
  ADD COLUMN discovery_plan JSONB;
```
No RLS changes — inherits from `runs`. No index — queries join on `run_id` which is already the primary key.

**Why:** When a run fails, we need the plan to reproduce the bug without re-running Discovery. When confidence is low, the frontend reads this column to render the confirmation UI.

**Deliverable:** Migration applies cleanly against a fresh Supabase.

**Verification:**
```bash
supabase db push
psql $DATABASE_URL -c "SELECT column_name FROM information_schema.columns WHERE table_name='runs' AND column_name='discovery_plan';"
# expect: discovery_plan
```

Persistence helper on the runs repo: add `RunsRepo.set_discovery_plan(run_id, plan_dict)` in `backend/adapters/supabase_repos.py`. Mirror existing `set_low_confidence_columns`.

---

### Step 9 — Routes + Orchestrator + ParserAgent split ⏸ Phase 3

**Goal:** Two new HTTP endpoints, one new orchestrator function, split ParserAgent into two public methods. Enrich `mapping_prompt.txt` (merged in here for cohesion).

**Files:**
- MODIFY `backend/api/routes.py` — add `/confirm-discovery` and `/reject-discovery`
- MODIFY `backend/agents/orchestrator.py` — add `run_parser_after_discovery_approval()`, fix `DiscoveryLowConfidence` swallow bug
- MODIFY `backend/agents/parser.py` — split into `discover()` + `resume_from_plan()`; integrate `Normalizer`, `validator`, `NormalizerDropReport`
- MODIFY `backend/prompts/mapping_prompt.txt` — accept `parent_category` + `account_code` + `department` in input

**9a — Routes (`backend/api/routes.py`)**

```python
@router.post("/runs/{run_id}/confirm-discovery")
@limiter.limit("30/minute")
async def confirm_discovery(
    request: Request,
    run_id: str,
    body: ConfirmDiscoveryRequest,              # {plan_override: DiscoveryPlan | None}
    background_tasks: BackgroundTasks,
    company_id: str = Depends(get_company_id),
):
    """V1 accepts empty body; V2 will accept plan_override for in-modal edits."""
    # Guards (copy pattern from existing confirm_run lines 676-688):
    #   - runs_repo.get_by_id → RLSForbiddenError → 403
    #   - run.company_id != company_id → 403
    #   - run.status != AWAITING_DISCOVERY_CONFIRMATION → 422
    #
    # Persist: if plan_override present, validate via DiscoveryPlan.model_validate()
    # and set_discovery_plan(run_id, override.model_dump(), approval_mode='manual')
    # If not present: set_discovery_plan(run_id, existing_plan, approval_mode='manual')
    #
    # Transition: AWAITING_DISCOVERY_CONFIRMATION → MAPPING
    # BackgroundTask: orchestrator.run_parser_after_discovery_approval(run_id, ...)


@router.post("/runs/{run_id}/reject-discovery")
@limiter.limit("30/minute")
async def reject_discovery(
    request: Request,
    run_id: str,
    company_id: str = Depends(get_company_id),
):
    # Same guards.
    # Transition: AWAITING_DISCOVERY_CONFIRMATION → PARSING_FAILED
    # error_message = messages.DISCOVERY_REJECTED
    # Storage file stays (R-015 accepted leak).
```

**9b — Orchestrator (`backend/agents/orchestrator.py`)**

Two changes:

1. **Fix the `DiscoveryLowConfidence` swallow bug** (currently `run_parser_until_preview:48-73` catches bare `Exception` and forces `PARSING_FAILED`):

```python
try:
    parser.discover(run_id, company_id, storage_key, period)
except DiscoveryLowConfidence as exc:
    # NOT a failure — halt for user review.
    runs_repo = get_runs_repo()
    runs_repo.set_discovery_plan(run_id, exc.plan.model_dump(mode="json"))
    new_status = RunStateMachine.transition(
        RunStatus.DISCOVERING, RunStatus.AWAITING_DISCOVERY_CONFIRMATION
    )
    runs_repo.update_status(run_id, new_status, extra={
        "step": 2, "step_label": "Waiting for your review...", "progress_pct": 30,
    })
    return
except Exception as exc:
    # Existing PARSING_FAILED path.
```

2. **New function:**
```python
def run_parser_after_discovery_approval(
    run_id: str,
    company_id: str,
    period: date,
    storage_key: str,
) -> None:
    """Called from confirm-discovery BackgroundTask. Resumes the pipeline
    from the approved plan. Re-downloads the file (still in storage per
    R-015), runs normalize → validate → map → preview → AWAITING_CONFIRMATION.
    """
```

**9c — ParserAgent split (`backend/agents/parser.py`)**

```python
class ParserAgent:
    def discover(self, run_id, company_id, storage_key, period) -> None:
        """Download → sample → sanitize_sample → DiscoveryAgent.discover().
        On high confidence: set approval_mode='auto', persist plan, inline
        into resume_from_plan(). On DiscoveryLowConfidence: persist plan,
        raise for orchestrator to handle."""

    def resume_from_plan(
        self,
        run_id, company_id, storage_key, period,
        plan: DiscoveryPlan,
    ) -> ParserOutput:
        """Re-download → pii_sanitizer.sanitize → normalizer.apply_plan →
        validator.validate → _map_accounts → build parse_preview → transition
        to AWAITING_CONFIRMATION."""
```

Shared private helpers: `_map_accounts` and the parse_preview builder stay as-is; both `discover()` and `resume_from_plan()` call them.

**9d — `mapping_prompt.txt` enrichment**

New input shape:
```json
{
  "accounts": [
    {"name": "Component Costs", "total": 210000,
     "parent_category": "Cost of Goods Sold",
     "account_code": "5000", "department": null}
  ],
  "known_mappings": {...}
}
```

Update the three worked examples to demonstrate `parent_category` disambiguating `"Freight-In"`-class ambiguity.

**Verification:**
```bash
black backend/api/routes.py backend/agents/orchestrator.py backend/agents/parser.py \
      backend/prompts/mapping_prompt.txt
flake8 backend/api/ backend/agents/ backend/prompts/ --max-line-length=100 --extend-ignore=E203
# Contract sanity — plan_override validates end-to-end:
python3 -c "
from backend.domain.contracts import DiscoveryPlan
DiscoveryPlan.model_validate({'header_row_index': 5, ...})
"
# Manual smoke (after all files land):
curl -X POST http://localhost:8000/runs/<id>/confirm-discovery -H "Auth..." -d '{}'
curl -X POST http://localhost:8000/runs/<id>/reject-discovery -H "Auth..."
```

**Goal:** Pass `parent_category` + `account_code` + `department` to the Category Mapping call so ambiguous names like `"Freight-In"` resolve correctly.

**Files:**
- MODIFY `backend/prompts/mapping_prompt.txt`
- MODIFY `backend/agents/parser.py::_map_accounts` (input context shape)

**Changes:**
- New input schema in the prompt:
  ```json
  {
    "accounts": [
      {"name": "Component Costs", "total": 210000,
       "parent_category": "Cost of Goods Sold",
       "account_code": "5000", "department": null}
    ],
    "known_mappings": {"...": "..."}
  }
  ```
- Update the three existing examples to show the richer input and demonstrate `parent_category` disambiguating identical names.
- In `parser._map_accounts`, replace the current `{account_totals, known_mappings}` context with the richer `{accounts, known_mappings}` shape. `accounts` is built by grouping the normalized DF by `account` and taking `parent_category`/`account_code`/`department` from the first row of each group.

**Why:** Today's mapper sees only account name + total. After Normalizer, we have hierarchy — feeding it in raises mapping accuracy for ambiguous accounts from ~80% to ~95% on the DRONE fixtures in expected results.

**Deliverable:** `test_mapping_prompt_disambiguates_freight_in` passes: the same account name `"Freight-In"` under two different `parent_category` values maps to two different categories.

**Verification:**
```bash
black backend/prompts/ backend/agents/parser.py && flake8 backend/prompts/ backend/agents/parser.py
pytest tests/agents/test_parser.py::test_mapping_prompt_disambiguates_freight_in -v
```

---

### Step 10 — Normalizer drop report + Parser rewire glue ✅ SHIPPED

Step 9 already did the heavy parser rewire. Step 10 closes the loop by extending the Normalizer to emit `NormalizerDropReport` and wiring that into `parse_preview`.

**Files:**
- MODIFY `backend/tools/normalizer.py` — signature change: `apply_plan(...) -> tuple[DataFrame, NormalizerDropReport]`
- MODIFY `backend/agents/parser.py::resume_from_plan` — store drops in `parse_preview["drops"]`
- MODIFY `backend/tools/pii_sanitizer.py` — expose a `_scrub_value(s: str) -> str` helper for the `account_snippet` scrubbing (re-uses the three existing regexes)

**Contract update:**
```python
# Return shape change
def apply_plan(df_raw, plan, period) -> tuple[pd.DataFrame, NormalizerDropReport]:
    ...
```

**Drop report population points (already present in current Normalizer as logs — now also structured):**
- `amount_coerce_failed` — rows dropped at step 8 (float coercion)
- `subtotal_safety_net` — rows dropped at step 9 (regex safety net)

**`account_snippet` construction:**
```python
raw = str(row_value)
scrubbed = pii_sanitizer._scrub_value(raw)   # SSN/email/CC → [REDACTED]
snippet = scrubbed[:40]                       # truncate
```

**`parse_preview` shape after Step 10:**
```json
{
  "rows": [...],                  // existing, per-account aggregates
  "source_column": "Amount",      // existing
  "drops": {                      // NEW
    "drops": [
      {"row_index": 14, "account_snippet": "Gross Margin %",
       "reason": "subtotal_safety_net"}
    ],
    "total_dropped": 1
  }
}
```

**Frontend:** `ParsePreviewPanel` renders `drops` as a collapsible "N rows skipped" section beneath the per-account table. Collapsed by default.

**Verification:**
```bash
pytest tests/tools/test_normalizer.py -v
# Expanded tests:
#   - test_apply_plan_returns_dataframe_and_report
#   - test_drop_report_tracks_amount_coerce_failures
#   - test_drop_report_tracks_subtotal_safety_net
#   - test_account_snippet_scrubs_email_pii
#   - test_account_snippet_truncates_at_40_chars
```

**Goal:** The actual integration. Replace the current `_read_file` body with the new five-phase flow.

**Files:**
- MODIFY `backend/agents/parser.py`
- MODIFY `backend/api/deps.py`

**Changes:**
- `ParserAgent.__init__` gains a new dependency: `discovery_agent: DiscoveryAgent`.
- Replace the body of `_read_file` with:
  1. `raw_bytes = self._storage.download(storage_key)` → tempfile (unchanged)
  2. `sample = file_reader.read_raw_cells(tmp_path)`
  3. `sample = pii_sanitizer.sanitize_sample(sample)`
  4. `plan = self._discovery.discover(run_id, sample)` — may raise `DiscoveryLowConfidence` (caller handles)
  5. `self._runs.set_discovery_plan(run_id, plan.model_dump())`
  6. `df_raw = file_reader.read_file(tmp_path)` (existing full-file path)
  7. `df_raw = pii_sanitizer.sanitize(df_raw, run_id=run_id)` (existing column-level sanitize)
  8. `df_normalized = normalizer.apply_plan(df_raw, plan, period)`
  9. `df_validated = validator.validate(df_normalized)`
  10. Return `(df_validated, metadata_rows_skipped=len(plan.skip_row_indices), source_column=...)`
- Wire `DiscoveryAgent` construction in `api/deps.py`.

**Why:** This is the step where everything previous comes together. Doing it last, not first, is deliberate: steps 1–10 shipped contracts, helpers, and tests that let this final wire-up land as a small diff rather than a rewrite.

**Deliverable:** End-to-end upload of `docs/demo_data/Drone Inc - Mar 26.xlsx` produces 20-25 `monthly_entries` rows, no subtotals, all categories assigned with confidence ≥0.80.

**Verification:**
```bash
black backend/agents/parser.py backend/api/deps.py && flake8 backend/agents/parser.py backend/api/deps.py
pytest tests/agents/test_parser.py -v
pytest tests/integration/test_parser_end_to_end.py -v   # uses real fixtures, mocked LLMClient
# Manual smoke test:
uvicorn backend.main:app --reload
curl -F file=@"docs/demo_data/Drone Inc - Mar 26.xlsx" -H "Authorization: Bearer $TEST_JWT" \
  http://localhost:8000/upload
# poll /runs/{id}/status until complete; inspect monthly_entries in Supabase
```

---

### Step 11 — Fixture suite + safety nets ✅ SHIPPED

**Goal:** Comprehensive test coverage. If this plan ships without these fixtures, we'll hit regressions the first time a user uploads a non-DRONE file.

**Files:**
- CREATE `tests/fixtures/discovery/drone_qbo_clean.xlsx` (copy of demo data)
- CREATE `tests/fixtures/discovery/drone_netsuite_xml.xls` (XML Spreadsheet 2003 variant)
- CREATE `tests/fixtures/discovery/drone_flat_csv.csv` (trivial case, no metadata)
- CREATE `tests/fixtures/discovery/drone_no_hierarchy.xlsx` (flat chart, no banners)
- CREATE `tests/fixtures/discovery/drone_pii_laced.xlsx` (SSN, employee names)
- CREATE `tests/integration/test_parser_end_to_end.py`

**Changes:**
- Six fixture files committed to the repo.
- `test_parser_end_to_end.py` must cover:
  - `test_qbo_clean_happy_path` — ends with correct `monthly_entries` count
  - `test_netsuite_xml_falls_back_without_formatting_hints`
  - `test_flat_csv_trivial_plan`
  - `test_no_hierarchy_file_still_maps_categories`
  - `test_pii_never_reaches_claude` — records `LLMClient` payload, asserts no PII
  - `test_low_confidence_pauses_run_at_awaiting_confirmation`
  - `test_discovery_failure_transitions_to_discovery_failed`
  - `test_subtotal_safety_net_catches_misplan` — feed a hand-crafted bad plan that leaves "Total Revenue" in; Normalizer's belt-and-suspenders drops it

**Why:** Every failure mode identified in the audit needs a regression test. Without fixtures, the next LLM upgrade or prompt tweak silently breaks something we already fixed. **R-020** (guardrail fires unexpectedly during demo) is mitigated by having this suite green before any live rehearsal.

**Deliverable:** `pytest tests/` passes clean on main.

**Verification:**
```bash
pytest tests/ -v
pytest tests/integration/ -v
# Coverage check (optional but recommended):
pytest --cov=backend.agents.discovery --cov=backend.tools.normalizer tests/
# expect: >90% line coverage on both new modules
```

---

## 5. Risk Mitigations (cross-reference to `risks.md`)

| Risk | How this plan mitigates it |
|---|---|
| **R-006** PII leak to Anthropic | `sanitize_sample` runs before Discovery LLM call. ✅ Shipped Phase 2.5 with 7 tests including `test_values_never_appear_in_log_payload` and `test_legitimate_accounting_values_survive_unchanged`. Drop-report `account_snippet` scrubbed via the same `_scrub_value` helper (Step 10). |
| **R-002** Anthropic quota exhaustion | Discovery adds **one** Haiku call per upload. Fixture tests use mocked `LLMClient`; only integration tests hit real Anthropic. Caching post-MVP per D3. |
| **R-009** MappingConfirmModal non-blocking | **Superseded by D1.** Discovery's low-confidence path uses a dedicated `AWAITING_DISCOVERY_CONFIRMATION` state, **not** the existing `AWAITING_CONFIRMATION`. Two distinct confirmation gates with distinct UX. |
| **R-012** `comparing_failed` terminal state missing | **Consistent pattern applied.** Discovery failure and user-rejected plan both use `PARSING_FAILED` as the catch-all terminal. No new `*_FAILED` states. |
| **R-014** Regenerate flow is re-upload | **Extended to Discovery rejection.** Plan rejection exits via re-upload. No manual-mapping override in V1 (D10). |
| **R-020** Guardrail fires in demo | Belt-and-suspenders subtotal filter in Normalizer (shipped Phase 2). `NormalizerDropReport` surfaces caught rows to the UI so regressions are visible, not silent (Step 10). |

**New risk surface introduced by Phase 3** and how it's mitigated:

| New risk | Mitigation |
|---|---|
| Orchestrator silently treats `DiscoveryLowConfidence` as a failure (bug in today's `run_parser_until_preview`) | Step 9b explicitly requires catching it BEFORE the bare `Exception` clause. Listed as a must-pass verification. |
| `account_snippet` in drop report leaks PII into `runs.parse_preview` JSONB | Step 10 requires scrubbing via existing `sanitize_sample` regexes + 40-char truncation. Privacy guardrail enforced in code review. |
| Auto-advanced low-confidence plans (threshold too loose) | `discovery_approval_mode='auto'` column + structured log enable post-demo analytics to recalibrate the 0.80 threshold based on downstream guardrail-failure correlation. |
| Pre-Phase-3 runs with NULL `discovery_plan` surfacing through the new modal | Frontend treats `status == awaiting_discovery_confirmation` as the sole trigger for the modal; the `discovery_plan IS NOT NULL` check is enforced by the state machine, not the frontend. |

---

## 6. Open Decisions (answer before Step 1)

Resolved 2026-04-23 by product decision:

1. **Discovery pause/resume UX** → **Option (b) — block at `AWAITING_CONFIRMATION`.** On `discovery_confidence < 0.80` the run halts; `runs.discovery_plan` is persisted (Phase 3 migration); frontend reads the plan and renders a manual review modal. Backend MUST account for this integration point.

2. **Sample size** → **First 100 rows × 10 columns, fixed.** Non-negotiable for capturing full context in messy files. No tail sampling.

3. **Caching** → **Skipped for MVP.** Discovery runs on every upload. Accuracy over speed; cache is post-MVP.

4. **Golden Schema** → **Frozen at seven fields**: `account | account_code | amount | date | parent_category | department | description`. US market conventions applied (`date` not `period`, `parent_category` not `parent_section`). `source_row_index` dropped. Adding any new field post-freeze requires a migration PR and a `CHANGELOG` note on this document.

---

## 7. Cut Line (if time runs out)

Ordered by what we give up least painfully first:

1. **Step 11 PII fixture (`drone_pii_laced.xlsx`)** — unit tests on `sanitize_sample` cover the logic; integration fixture is confirmation, not discovery. *Do not cut PII unit tests.*
2. **Step 11 `drone_no_hierarchy.xlsx` fixture** — flat charts are the easy case; if DRONE-shape works, flat works.
3. **Step 9 mapping prompt enrichment** — keep the old `{account_totals, known_mappings}` shape for now; accept that `"Freight-In"`-class ambiguity stays at ~80% accuracy.
4. **Step 8 `runs.discovery_plan` JSONB column** — Discovery can run without persisting the plan; we lose debuggability but lose the manual-review modal too, since it reads the plan. **Cut only if R-009 already shipped in some other form.**

Never cut:
- **Step 3.5 `sanitize_sample`.** R-006 is disqualifying. Required before Phase 3 ships.
- **Step 5 subtotal safety net** in the Normalizer. R-020 becomes catastrophic without it.
- **Step 11 `test_pii_never_reaches_claude`.** Non-negotiable.

---

## 8. Change Log

| Date | Author | Change |
|---|---|---|
| 2026-04-23 | Initial plan | Document created after audit of `parser.py`, `validator.py`, `file_reader.py` |
| 2026-04-23 | Phase 1 delivery | Steps 1–3 shipped. Contracts frozen with `Literal`-enforced `GoldenField`; `read_raw_cells` verified against DRONE fixture (bold/indent/merged captured); `discovery_prompt.txt` self-validates against `DiscoveryPlan`. |
| 2026-04-23 | Product decisions | §6 Open Decisions resolved: sample 100×10, caching off, block-on-low-confidence UX, Golden Schema frozen at seven US-market fields (`date` / `parent_category` / `department` added; `period` / `parent_section` / `source_row_index` removed). Plan renumbered to 11 steps (original Step 3 PII sanitizer deferred as Step 3.5). |
| 2026-04-23 | Phase 2 delivery | Steps 4, 5, 6 shipped. DiscoveryAgent (5 verified branches), Normalizer (6 verified scenarios including R-020 safety net), validator (strict=True, nullable extras). Known transitional breakage of legacy parser.py path — resolves in Phase 3. |
| 2026-04-23 | Phase 2.5 delivery | Step 3.5 shipped. `sanitize_sample()` with SSN/email/CC regex, `[REDACTED]` placeholder, 7 pytest tests including the `"4000 - HobiFly"` over-redaction regression guard. R-006 mitigated on the value-level surface. |
| 2026-04-23 | Phase 3 architecture lock | Deep-thinking session. D1-D10 decisions recorded in §4a. Two new states (`DISCOVERING`, `AWAITING_DISCOVERY_CONFIRMATION`), `PARSING → MAPPING` transition removed, `NormalizerDropReport` + `DropReason` contracts added, `ParserAgent` split into `.discover()` + `.resume_from_plan()`, two new routes (`/confirm-discovery`, `/reject-discovery`), migration 0006 adds two nullable columns with CHECK constraint, V1 ships Confirm/Reject (V2 endpoint-ready for editing), rejection = re-upload per R-014. Steps 7-10 rewritten with finalized architecture. |
| 2026-04-23 | Phase 3 Step 7 delivery | State machine: `DISCOVERING` + `AWAITING_DISCOVERY_CONFIRMATION` enums, three new transitions, `PARSING → MAPPING` removed. `messages.py` gains 3 constants. `parser.py:74` transition rewired `PARSING → DISCOVERING → MAPPING`. |
| 2026-04-23 | Phase 3 Step 8 delivery | Migration 0006 landed in Supabase. `RunsRepo.set_discovery_plan` port method + `SupabaseRunsRepo` impl; `approval_mode=None` leaves the column untouched. Protocol conformance verified. |
| 2026-04-23 | Phase 3 Step 9a delivery | `/confirm-discovery` + `/reject-discovery` routes, `ConfirmDiscoveryRequest` model (V2-ready with optional `plan_override`). Orchestrator `DiscoveryLowConfidence` swallow-bug fix + `run_parser_after_discovery_approval` skeleton. `_fmt_ts` hoisted (F821 drive-by fix). 7 route scenarios verified. |
| 2026-04-23 | Phase 3 Step 9b delivery | `ParserAgent.discover()` + `.resume_from_plan()` shipped. `.run()` now a two-call delegator. Enriched `_map_accounts` sends `{name, total, parent_category, account_code, department}` per account. `mapping_prompt.txt` rewritten. `read_file()` flipped to `header=None` so raw row indices align with Discovery. End-to-end verified on DRONE Mar fixture across high-conf, low-conf, and resume-direct paths. |
| 2026-04-23 | Phase 3 Step 10 delivery | `NormalizerDropReport.drops → entries` rename. `apply_plan(...) -> tuple[DataFrame, NormalizerDropReport]`. `_scrub_value` substring helper added with 200-char input cap. Scrub-first-truncate-second order locked by `test_scrub_before_truncate_prevents_partial_email_leak`. Frontend `ParsePreviewPanel` renders collapsible "N rows skipped" section; TS types extended in `LoadingProgress`. 15 new Normalizer tests, 22/22 total suite green. **Phase 3 complete.** |
| 2026-04-23 | Phase 4 Step 11 delivery | Integration test suite shipped. `tests/integration/conftest.py` synthesizes 4 fixtures in-memory (flat CSV, no-hierarchy xlsx, PII-laced xlsx, merged-cells xlsx) + reuses real DRONE Mar fixture. 8 passing tests (qbo_clean, flat_csv, no_hierarchy, **pii_never_reaches_claude** as end-to-end R-006 audit with captured LLM payloads, low_confidence_pauses, discovery_failure → parsing_failed rename per D2, **subtotal_safety_net_catches_misplan** surfacing drop_report entries, bonus **merged_cells_in_banner_row_detected**) + 1 skipped (NetSuite XML, post-MVP with explicit reason). 30/31 total suite green (1 intentional skip). **Phase 4 complete — Discovery & Mapping Layer plan fully shipped.** |

Append entries as the plan evolves. Never delete history — future-you will thank present-you.

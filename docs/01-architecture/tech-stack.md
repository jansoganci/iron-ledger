# IronLedger — Tech Stack
*Built with Opus 4.7 Hackathon — April 2026*
*v2 — Updated with Deep Search findings*

---

## Stack Summary

| Layer | Tool | Why |
|---|---|---|
| Backend API | FastAPI (Python) | Async, fast, Python-native |
| File processing | pandas + openpyxl + xlrd | Excel/CSV reading and manipulation |
| PII sanitization | `tools/pii_sanitizer.py` (custom) | Header blacklist + SSN regex; drops columns pre-pandera so Claude never sees PII values |
| Schema validation | pandera | Lightweight, pandas-native, fast — not Great Expectations |
| Numeric guardrail | Python (custom) | Checks whether Claude's interpretation matches pandas output |
| Agentic layer | Anthropic Python SDK — Claude Opus 4.7 | Orchestration, plain language — not LangChain |
| Database | Supabase (PostgreSQL) | Data storage, historical reference |
| Auth | Supabase Auth (email + password, JWT) | Native, zero-setup; RLS enforces `companies.owner_id = auth.uid()` |
| Rate limiting | `slowapi==0.1.9` (in-memory) | FastAPI-native 429 handling; composite key (user_id → IP fallback); single Railway container for hackathon, Redis post-MVP |
| Vector memory | Supabase pgvector | Long-term pattern recognition — Post-MVP, not in hackathon scope |
| Frontend | React + TypeScript | Dashboard |
| Email | Resend | Report email delivery |
| Deploy | Vercel (frontend) + Railway (backend) | Fast deployment |

Week 1 memory is handled entirely with standard Supabase SQL joins. pgvector is a future enhancement.

---

## Why These Tools, Why Not Others

**pandera, not Great Expectations:**
Great Expectations is too complex for a week-one build. pandera validates pandas DataFrames directly in about 10 lines of code. Same result, zero overhead.

**Anthropic SDK loop, not LangChain:**
LangChain agent executor adds unnecessary abstraction. Anthropic SDK's tool-use loop can be written in 50 lines of pure Python. Fewer dependencies, easier debugging.

**xlrd in addition:**
NetSuite's default Export button produces `.xls` files in XML Spreadsheet 2003 format — not real xlsx, and openpyxl cannot open them. Handle with xlrd or direct XML parsing.

---

## Golden Rule

> **Numbers come from pandas. Prose comes from Claude. A numeric guardrail checks that the prose matches the pandas.**

Claude must never do math. All calculations are done in Python, and Claude only interprets the result. The numeric guardrail checks that the numbers in Claude's interpretation are consistent with pandas output.

---

## Model Strategy

| Task | Model | Notes |
|---|---|---|
| Column mapping | claude-haiku-4-5-20251001 | Hard-coded in parser.py. No toggle. |
| Narrative + anomaly reasons | claude-opus-4-7 | Hard-coded in interpreter.py. No toggle. |

No user-selectable model toggle in MVP.
Post-hackathon: expose MODEL constants at top of each agent file for easy refactor.

---

## Orchestration

Three sequential agents. Each agent is a separate Python file. They communicate via Supabase — not direct function calls.

1. `parser.py` — reads file, maps columns, writes to `monthly_entries`
2. `comparison.py` — reads `monthly_entries`, calculates variance in Python, writes to `anomalies`
3. `interpreter.py` — reads `anomalies` + `monthly_entries` summary, calls Claude Opus 4.7, runs guardrail, writes to `reports`

No LangChain. No single orchestrator loop. Supabase is the message bus.

---

## Architecture Layers (lightweight ports & adapters)

The backend is split into four layers. Dependencies only point inward (`api` → `agents` → `domain`; `adapters` implement interfaces defined in `domain.ports`). No layer below imports from a layer above.

### `domain/` — pure Python, no I/O
Has no dependency on pandas, anthropic, supabase, or resend. If you can't unit-test it with plain Python, it doesn't belong here.

- `entities.py` — dataclasses for core concepts (`Company`, `MonthlyEntry`, `Anomaly`, `Report`, `Run`, etc.)
- `contracts.py` — Pydantic models that form cross-agent contracts. Most important: `PandasSummary` (the exact shape the Comparison agent hands to the Interpreter agent) and `NarrativeJSON` (Claude's structured output before guardrail).
- `run_state_machine.py` — `RunStatus` enum + allowed-transitions table + `RunStateMachine.transition()` which raises on invalid moves. Every `runs.status` write goes through this class.
- `ports.py` — `Protocol` interfaces: `EntriesRepo`, `AnomaliesRepo`, `ReportsRepo`, `RunsRepo`, `CompaniesRepo`, `AccountsRepo`, `FileStorage`, `LLMClient`, `EmailSender`. Agents depend on these, never on concrete classes.
- `errors.py` — `GuardrailError`, `InvalidTransition`, `MappingAmbiguous`, etc. User-facing error strings stay in `messages.py`; this file just holds exception types.

### `adapters/` — I/O implementations of `domain.ports`
This is where every third-party SDK import lives. Changing vendors means rewriting an adapter, not an agent.

- `supabase_repos.py` — all 6 repo implementations share one Supabase client
- `supabase_storage.py` — `FileStorage` port backed by `storage.objects` (RLS-scoped per user)
- `anthropic_llm.py` — `LLMClient` port. Loads prompts from `prompts/` by filename, calls the Anthropic SDK, returns typed responses.
- `resend_email.py` — `EmailSender` port (replaces the retired `tools/mailer.py`)

### `agents/` — use cases
Each agent is a class or function that accepts ports via its constructor. Zero direct SDK imports. Parser, Comparison, and Interpreter live here — same three-agent model as before, just injected.

### `api/` — FastAPI layer
Thin handlers only. No business logic.

- `deps.py` — builds adapters once, injects them into agents via FastAPI `Depends`
- `middleware.py` — request middleware that generates/reads `trace_id` and stamps it into a `contextvar` for the JSON logger
- `auth.py` — JWT verification dependency. Resolves `user_id → company_id` via `companies.owner_id`
- `routes.py` — the existing endpoints, nothing new

### Cross-cutting (root of `backend/`)
- `main.py` — app factory; wires middleware, logging, and routes
- `messages.py` — single source of truth for every user-facing error string
- `logger.py` — JSON log formatter + `trace_id` contextvar. Every log line carries a trace_id for end-to-end request tracing.
- `settings.py` — Pydantic `BaseSettings` reading `.env`

### What this refactor does NOT do
- It does NOT touch `prompts/` or `tools/guardrail.py`.
- It does NOT add new endpoints — the API surface from `docs/api.md` is unchanged.
- It does NOT introduce a `services/` or `usecases/` layer — agents ARE the use cases.

---

## Numeric Guardrail — How It Works

```python
def numeric_guardrail(pandas_output: dict, claude_narrative: str) -> bool:
    # Extract numbers from Claude's written text
    numbers_in_narrative = extract_numbers(claude_narrative)
    # Compare with pandas output
    for num in numbers_in_narrative:
        if not is_close(num, pandas_output):
            raise GuardrailError(f"Narrative says {num}, pandas says {pandas_output}")
    return True
```

Without this layer, reports shown to the CFO are not reliable.

---

## File Format Support

| Format | Tool | Notes |
|---|---|---|
| `.xlsx` | openpyxl | Standard, every ERP |
| `.xlsm` | openpyxl | Macro-enabled FP&A workbooks |
| `.csv` | pandas | ADP payroll, NetSuite export |
| `.xls` (real) | xlrd ≤1.2 | Legacy QuickBooks, SAP |
| `.xls` (NetSuite) | xlrd or XML parse | XML Spreadsheet 2003, openpyxl cannot open |

---

## Supabase Memory Layer

| Layer | What It Stores | How |
|---|---|---|
| Short-term | Active session data | Claude context window |
| Mid-term | Last 3 months snapshot | Supabase JSON column |
| Long-term | Full history, patterns | Supabase pgvector |

---

## Folder Structure

```
ironledger/
├── backend/
│   ├── main.py                  # FastAPI app
│   ├── agents/
│   │   ├── parser.py            # Parser agent
│   │   ├── comparison.py        # Comparison agent
│   │   └── interpreter.py       # Interpretation agent
│   ├── tools/
│   │   ├── file_reader.py       # pandas + openpyxl + xlrd
│   │   ├── validator.py         # pandera schema validation
│   │   ├── guardrail.py         # numeric guardrail
│   │   └── mailer.py            # Resend
│   ├── prompts/                 # Claude prompts — not inline
│   │   ├── mapping_prompt.txt
│   │   └── narrative_prompt.txt
│   └── db/
│       └── supabase.py          # DB client
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── FileUpload.tsx
│   │   │   ├── ReportView.tsx
│   │   │   └── Dashboard.tsx
│   │   └── pages/
│   │       ├── index.tsx
│   │       └── report.tsx
└── docs/
    ├── scope.md
    ├── tech-stack.md
    ├── db-schema.md
    ├── agent-flow.md
    ├── sprint.md
    └── design.md
```

**Note:** Prompts are not written inline in code. They are stored as separate files in the `prompts/` folder and logged with git SHA.

---

## Development Tools

- **IDE:** Cursor (with Claude Code)
- **API testing:** Bruno (Postman alternative, lightweight)
- **DB management:** Supabase Studio
- **Version control:** GitHub

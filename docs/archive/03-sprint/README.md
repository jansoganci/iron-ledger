# Month Proof — Sprint System
*Built with Opus 4.7 Hackathon — April 2026*

This folder is the **living plan** for the 6-day sprint. One file per day, plus a completed-work log and a cross-day risk register.

The file `docs/sprint.md` at the repo root is the **one-page overview** — strategy + day-goal table. Read it first if you're landing cold. Then come here for the detailed per-day plan.

---

## File Index

| File | Purpose |
|---|---|
| `README.md` | This file — how the sprint system works + index |
| `day-1-foundation.md` | Backend foundation — Clean Architecture, Supabase, Auth, Storage, infrastructure |
| `day-2-parser.md` | Parser agent (PII + Haiku mapping) + Comparison agent (pure Python) |
| `day-3-interpreter.md` | Interpreter agent + Numeric guardrail + full API surface |
| `day-4-frontend.md` | Frontend — Login, upload, report, all component states |
| `day-5-polish.md` | Mail + E2E tests + polish |
| `day-6-demo.md` | Demo prep + deploy + submit |
| `completed.md` | Append-only log of shipped work, decisions, deviations, cuts |
| `risks.md` | Cross-day risk register — live, updated as risks fire |

---

## Overall Strategy

- **Day 1:** Backend foundation — Clean Architecture scaffold, Supabase + Auth + Storage, infrastructure (logger, rate limiter, messages), file reading
- **Day 2:** Parser agent (PII + Haiku mapping) + Comparison agent (pure Python)
- **Day 3:** Interpreter agent + Numeric guardrail + full API surface
- **Day 4:** Frontend — Login, upload UI, report view, all component states
- **Day 5:** Mail + E2E tests + polish
- **Day 6:** Demo prep + deploy + submit

---

## Golden Rules (apply every day)

1. **Numbers come from pandas. Prose comes from Claude. A numeric guardrail verifies both.** No Claude math, ever.
2. **Prompts are never inline.** They live in `backend/prompts/`, and the git SHA is logged per call.
3. **PII never reaches Anthropic.** `tools/pii_sanitizer.py` runs before pandera and before any Claude call.
4. **Domain layer has zero I/O imports.** No `pandas`, `anthropic`, `supabase`, `resend` inside `backend/domain/`.
5. **Agents depend on ports, never on concrete adapters.** Wire-up happens in `api/deps.py`.
6. **Every `runs.status` write goes through `RunStateMachine.transition()`.**
7. **Every third-party SDK call lives in `adapters/`.**
8. **Every log line carries `trace_id`.** Never log DataFrame cell values — column names and counts only.
9. **All user-facing strings live in `backend/messages.py`.** Exceptions never hold user copy.
10. **At the end of each day, something working must be delivered.** Incomplete work does not spill.

---

## How to Read a Day File

Each day file follows the same schema:

| Section | Purpose |
|---|---|
| **Goal** | One sentence describing what "done" looks like at end of day |
| **End-of-Day Acceptance Check** | Single yes/no test the user can run to confirm the day is done |
| **Preconditions (from prior days)** | What must already be true before this day starts. Cross-day dependencies visible on the receiving side. |
| **Tasks** | Grouped, checkboxed tasks. Each task has **Files** / **Why** / **Blocks** where non-obvious. |
| **Internal Sequencing** | Which tasks must be done first within this day, and why |
| **Contracts Produced Today** | Any Pydantic model, Protocol, or endpoint shape that downstream days consume — frozen snapshot |
| **Cut Line** | Minimum viable subset if time runs out + what gets deferred and to which day |
| **Risks (this day)** | Day-specific risks + fallbacks. Cross-day risks live in `risks.md`. |
| **Reference Docs** | Which sections of which root docs to read for context |

---

## How to Update This System

**Day files are the plan** — edit them freely as scope evolves. Mark tasks `- [x]` when shipped.

**`completed.md` is the log** — append-only. Four subsections per day:
- **Shipped** — what actually got done (with commit SHAs where possible)
- **Decisions Made** — choices not yet reflected in the root docs
- **Deviations from Plan** — where reality diverged from the day file, and why
- **Cut / Deferred** — items explicitly pushed to a later day or post-MVP
- **Known Issues / Tech Debt** — surfaced during the day

**`risks.md`** — update when a risk materializes or a new cross-day risk is identified.

**`docs/sprint.md`** (root) — the single-file overview. Keep in sync with day-level changes, but don't duplicate per-task detail.

### Rules

- **Append, don't delete.** A reversed decision stays visible (struck through) because the reasoning is itself context.
- **Strike-through for reversed decisions:** `- [x] ~~Old task~~` → followed by a new entry noting the pivot.
- **Mark cuts explicitly.** A task that didn't ship goes in `completed.md` under Cut / Deferred with its new home.
- **Update at end of each working session.** Do not batch — context decays fast.

---

## Cross-Document Map

When a day file says "per `scope.md`" or "from `design.md`", consult these:

| Doc | Lives at | Contains |
|---|---|---|
| Overall sprint plan | `docs/sprint.md` | One-page overview + expanded task lists per day |
| Context for Claude Code | `CLAUDE.md` (repo root) | Project structure, repo layer, retry & error handling, Golden Rule |
| Scope | `docs/scope.md` | Problem, MVP INCLUDED / EXCLUDED, architectural constraints |
| Tech stack | `docs/tech-stack.md` | Tool choices + rationale + Clean Architecture layers |
| Agent flow | `docs/agent-flow.md` | Parser / Comparison / Interpreter pipelines, guardrail mechanics |
| DB schema | `docs/db-schema.md` | 7 tables, indexes, RLS, Storage layout |
| API contract | `docs/api.md` | Every endpoint shape + CORS + error code reference |
| Design | `docs/design.md` | Screens, components, states, toast system, responsive, formatting |
| Demo runbook | `docs/runbook.md` | Day 6 demo script + pre-demo checklist |

---

## Post-Sprint

At sprint end, `completed.md` becomes the submission audit trail and the **Post-Sprint Backlog** at its bottom becomes the Day-7+ plan for post-hackathon work.

# Portfolio Case Study — Agentic AI for Finance Operations

**Project name:** Month Proof (Iron Ledger codebase)  
**Category:** Agentic AI · FinOps automation · Full-stack product  
**Audience:** Upwork clients hiring for AI agents, LLM workflows, and production-grade AI systems.

---

## One-line pitch

A multi-agent system that ingests messy month-end spreadsheets, runs deterministic financial analysis in Python, and uses Claude only for interpretation—verified by an automated numeric guardrail before anything is saved or emailed.

---

## The problem

Finance teams repeat the same close routine: open exports, reconcile periods, hunt spikes, write narrative for leadership, and distribute reports. Much of that work is pattern recognition plus careful arithmetic—but generic chatbots are risky because models can “sound right” while the numbers are wrong.

---

## What I delivered

1. **Three sequential agents (orchestrated pipeline)**  
   - **Parser:** Reads Excel/CSV, validates schema (pandera), strips sensitive columns (PII-safe headers + rules), maps columns to accounting categories via a dedicated LLM step.  
   - **Comparison:** Pure Python—variances, thresholds, anomaly flags. No model math.  
   - **Interpreter:** Claude writes CFO-style plain-language narrative and anomaly explanations from structured summaries only.

2. **Trust layer clients actually care about**  
   - **Golden rule:** All figures in the report must trace back to pandas output.  
   - **Numeric guardrail:** Before persisting a report, the system checks that every number the model cited matches the computed summary within tolerance (e.g. 2%). Mismatch → semantic retry or failure path—no silent hallucinated totals.

3. **Production-shaped backend**  
   - FastAPI API with auth (JWT → tenant), rate limiting, structured logging with trace IDs.  
   - Supabase for Postgres + Row Level Security (company isolation), file storage, and auth.  
   - Anthropic SDK with prompts kept in versioned files (not buried in code).  
   - Email delivery abstracted behind a port (e.g. Resend adapter).

4. **Frontend workflow**  
   - Upload, run status, anomaly cards, guardrail warnings, mapping confirmation for low-confidence columns—so operators stay in control.

5. **Real-world file hygiene**  
   - Handles awkward exports (including NetSuite-style XML spreadsheets detected by signature).  
   - Deliberate pipeline order: sanitize → validate → map—so validation and AI never see columns that should never leave the building.

---

## Why this is “agentic AI” (not a wrapper)

- **Autonomous stages:** Each agent owns a phase and persists state; the product behaves like a workflow, not a single prompt.  
- **Tools & boundaries:** File I/O, DB, and calculators are code; the LLM is constrained to roles where language adds value (mapping suggestions, narrative).  
- **Verification loop:** The guardrail is an explicit agent-loop pattern—generate → validate → retry or stop—appropriate for regulated or number-critical domains.

---

## Tech stack (summary)

| Layer | Choices |
|--------|--------|
| API | Python, FastAPI |
| Data & validation | pandas, pandera |
| AI | Anthropic Claude (e.g. Haiku-class for mapping, Opus-class for narrative—task-specific) |
| Database / auth / storage | Supabase (Postgres, RLS, Storage, Auth) |
| Frontend | React (Vite), TypeScript |
| Email | Resend (via adapter) |

---

## Demo scenarios (how buyers can evaluate)

- **Single-file variance:** Month-over-month commentary with flagged lines (e.g. expense categories with unusual swings).  
- **Multi-file reconciliation (where implemented):** Consolidation across GL and supporting schedules with reconciliation-style findings.

*(Demo datasets ship with the repo under `docs/demo_data/` for repeatable walks.)*

---

## Honest MVP scope (sets expectations)

This build is intentionally narrow for speed-to-demo: Excel/CSV ingestion (not a full ERP connector suite), single-company tenancy in MVP form, and guardrails focused on numeric fidelity—not legal or audit sign-off. Buyers hire me to extend this pattern to **their** sources, policies, and integrations.

---

## What you can hire me to build next

- Multi-step **agent workflows** with **verification gates** (finance, ops, compliance narratives).  
- **RAG + tools** where retrieval and calculators stay in code; the model explains and summarizes.  
- **Supabase / Postgres** apps with **RLS**, uploads, and background jobs.  
- **Prompt systems** maintained as assets (versioned prompts, eval hooks, retry policies).

---

## How to use this text on Upwork

- **Portfolio title:** e.g. *Agentic AI month-end close — guarded LLM + Python analytics*  
- **Short description:** Paste the one-line pitch + first bullet list under “What I delivered.”  
- **Skills to tag:** AI Agents, LLM Application Development, Python, FastAPI, React, Supabase, API Integration, Data Analysis  
- **Attachment:** Export this file to PDF or paste sections; keep proprietary client names out unless you have permission.

---

*This document describes a representative production-style codebase developed for demonstration and iteration. Engagement terms, SLAs, and integrations are scoped per client.*

# Day 4 — Frontend
*Month Proof 6-Day Sprint — Built with Opus 4.7 Hackathon, April 2026*

## Goal

Complete browser flow end-to-end. User signs in → uploads DRONE Excel → watches 4-step progress → lands on verified report with "Verified · Guardrail Passed" badge, US-accounting-formatted numbers, provenance hover on every figure, and severity-colored anomaly cards. Edge paths (guardrail failure, low-confidence mapping, empty state for first-time users, client-side file rejection) all render correctly. Toast system surfaces transient events; ErrorBoundary catches React errors. Desktop-first layout with responsive collapse for tablet and mobile.

## End-of-Day Acceptance Check

> In a real browser (not Bruno), with DRONE Feb 2026 baseline already loaded:
> 1. Navigate to `/upload` → redirected to `/login` (auth guard).
> 2. Sign in as `demo@dronedemo.com` → redirected to `/upload`.
> 3. Drag `drone_mar_2026.xlsx` onto the dropzone. Verify dragging state (teal border, tinted background, "Release to upload" copy).
> 4. Drop the file. Click **Analyze**. Watch 4-step progress bar: "Reading files..." → "Mapping accounts..." → "Comparing to history..." → "Generating report..." Each step shows ✓ when complete, ● (with linear progress) when active, ○ when pending.
> 5. Land on report screen. Verify: "Verified · Guardrail Passed" badge next to "Mar 2026 — DRONE Inc." header. G&A and Travel rendered as AnomalyCards with correct severity (high) and direction colors (G&A favorable green chip, Travel unfavorable red chip).
> 6. Hover a number in the narrative → provenance popover shows `drone_mar_2026.xlsx — column '<original header>'`.
> 7. Click **Send Email**. Toast appears top-right: "Report emailed to ..." (Day 5 wires real send; Day 4 confirms the UI flow).
> 8. **Force guardrail failure** (re-use Day 3's bad prompt). Upload. Land on `GuardrailWarning` screen (screen 3b). Verify Retry Analysis button + Download Raw Data link (downloads a file prefixed `raw_`).
> 9. **Trigger MappingConfirmModal post-hoc review panel**: upload a file with an ambiguous column (< 0.80 confidence). After report renders, a non-blocking review panel appears showing only the flagged columns (max 3). Confirm a mapping → persists to `accounts`.
> 10. **Empty state**: sign out. Sign in as a second user with zero `monthly_entries`. Land on the "Let's set up your baseline" screen — neutral palette only, no red/amber.
> 11. **Client-side rejection**: drop `report.pdf` → inline error under dropzone: "`report.pdf` is not a supported format — upload an Excel or CSV file." File never hits backend.
> 12. **Client-side size rejection**: drop a 15 MB xlsx → inline error: "`<file>` is larger than 10 MB — please split the file."
> 13. **Responsive**: resize viewport to 900px (tablet) — left nav collapses to top bar + hamburger, report page single column. Resize to 400px (mobile) — Dashboard/TrendChart/MetricCard/HistoryList hidden. Dropzone + report still render.
> 14. **Accessibility**: open MappingConfirmModal. Press Esc → closes. Tab order loops within modal. All severity chips show color + text (not color alone).
> 15. **Rate limit**: spam Analyze button 6× in under a minute → warning toast ("You're sending a lot of requests — please wait a moment.") with auto-dismiss at 6s. Button disabled for the `retry_after_seconds` countdown.
> 16. **ErrorBoundary**: manually throw inside a component during dev → plain-English fallback renders ("Something went wrong. Please refresh — your data is safe."), not a white screen. ✅

## Preconditions (from Day 1–3)

From Day 3 (most critical):
- [x] `GET /runs/{run_id}/status` returns the full shape including `low_confidence_columns`
- [x] `GET /runs/{run_id}/raw` serves unverified dump with `raw_` prefix
- [x] `GET /report/{company_id}/{period}` returns verified narrative + anomalies (verified only)
- [x] `GET /anomalies/{company_id}/{period}` returns anomaly list
- [x] `POST /mail/send` scaffold accepts shape (real send wires Day 5)
- [x] Every endpoint rate-limited with 429 returning `Retry-After` + `messages.RATE_LIMITED`
- [x] HTTP status mapping returns user-facing strings (not stack traces)
- [x] CORS verified cross-origin for `http://localhost:5173`
- [x] `trace_id` in every response header

From Day 1–2:
- [x] Supabase Auth email + password live, `demo@dronedemo.com` exists
- [x] DRONE Feb 2026 baseline loaded (needed for Comparison history)
- [x] `messages.py` strings align with exception taxonomy

External pre-requisites:
- Node 20+ installed
- Supabase project anon key for frontend (`VITE_SUPABASE_ANON_KEY`)
- Backend running on `localhost:8000` with CORS allowing `localhost:5173`

Contract decisions — **locked** (pre-work batch):
- **Provenance** — `supabase/migrations/0003_add_source_column.sql` adds `monthly_entries.source_column TEXT`. Parser writes it per row (verbatim original header). `/anomalies` and `/report` JOIN and include it on each anomaly.
- **AnomalyCard direction** — **backend-only**. Computed in `/report` and `/anomalies` serializers. `OTHER` category → `direction="neutral"`. Frontend consumes `direction` as a string; no frontend computation, no `category` field needed in the anomaly response.
- **MappingConfirmModal URL** — `POST /runs/{run_id}/mapping/confirm` (run-scoped, matches `api.md` §6). Day 2 chose the post-hoc review panel (non-blocking) over the blocking modal. Day 4 implements accordingly.
- **Storage key** — `supabase/migrations/0004_add_storage_key.sql` adds `runs.storage_key TEXT`. `POST /upload` persists it at run creation. `POST /runs/{run_id}/retry` reads from it.

---

## Tasks

### 1. Project Setup

- [ ] `cd frontend && npm create vite@latest . -- --template react-ts`
- [ ] Install dependencies:
  ```
  @supabase/supabase-js
  react-router-dom
  @tanstack/react-query        # fetch + polling
  @tanstack/react-table        # data tables
  tailwindcss postcss autoprefixer
  class-variance-authority clsx tailwind-merge lucide-react  # shadcn deps
  @radix-ui/react-dialog @radix-ui/react-dropdown-menu @radix-ui/react-toast
    @radix-ui/react-tooltip @radix-ui/react-select @radix-ui/react-slot  # shadcn primitives
  ```
- [ ] `npx tailwindcss init -p` — generate config
- [ ] Initialize shadcn: `npx shadcn@latest init` — when prompted:
  - Base color: neutral (customized below)
  - CSS variables: yes
  - Tailwind config location: default
- [ ] Install shadcn components used: `button`, `dialog`, `dropdown-menu`, `toast`, `tooltip`, `select`, `badge`, `card`, `skeleton`
- [ ] `.env`:
  ```
  VITE_SUPABASE_URL=<supabase_url>
  VITE_SUPABASE_ANON_KEY=<supabase_anon_key>
  VITE_API_URL=http://localhost:8000
  ```
- [ ] `.env.example` — same keys, no secrets

### 2. Design System Foundation

- [ ] `tailwind.config.js` — palette tokens from `design.md`:
  ```js
  theme: {
    extend: {
      colors: {
        canvas: "#FAFAF9",
        surface: "#FFFFFF",
        border: "#E5E4E2",
        text: { primary: "#1A1A1A", secondary: "#6B6B6B" },
        accent: "#0D9488",           // teal — primary CTAs
        severity: {
          high:   { bg: "#FEE2E2", fg: "#C53030" },
          medium: { bg: "#FEF3C7", fg: "#B45309" },
          normal: { bg: "#F3F4F6", fg: "#6B7280" },   // gray, NOT green
        },
        favorable: { bg: "#ECFDF5", fg: "#166534" },  // used for variance direction
      },
      fontFamily: { sans: ["Inter", "sans-serif"] },
      fontFeatureSettings: { tabular: '"tnum"' },
    }
  }
  ```
- [ ] Global CSS: `font-feature-settings: "tnum"` on every numeric element class (use `.tabular-nums` utility or a global `[data-numeric]` selector)
- [ ] Import Inter font (via Google Fonts or `@fontsource/inter`)
- [ ] Create `src/lib/formatCurrency.ts`:
  ```ts
  const formatter = new Intl.NumberFormat("en-US", {
    style: "currency", currency: "USD", currencySign: "accounting"
  });
  export const formatCurrency = (n: number) => formatter.format(n);
  // Yields $1,234 and ($1,234) for negatives — accounting style
  ```
- [ ] Create `src/lib/formatPeriod.ts`:
  ```ts
  // "2026-03-01" → "Mar 2026" for UI; keep ISO for API
  export const formatPeriod = (iso: string) => { /* ... */ };
  ```
- [ ] Create `src/lib/formatNarrativeNumber.ts`:
  ```ts
  // Abbreviated form for narrative prose: $4,730,000 → "$4.73M", $128,000 → "$128K"
  ```
- [ ] Verify: the exact hex values from `design.md` §Palette are used. No `green-500` shortcuts from Tailwind defaults.

### 3. Auth, Routing, Fetch Client

- [ ] `src/lib/supabase.ts` — Supabase client singleton with session persistence (default behavior; no config needed)
- [ ] `src/lib/auth.ts` — `signIn(email, password)`, `signOut()`, `getSession()`, `onAuthStateChange` listener
- [ ] `src/contexts/AuthContext.tsx` — React context providing `{ session, user, loading }` to the app
- [ ] `src/App.tsx` — wraps app in `AuthProvider`, `QueryClientProvider`, `ToastProvider`, `ErrorBoundary`, `BrowserRouter`
- [ ] Routes (react-router):
  - `/login` → `LoginPage`
  - `/upload` → `UploadPage` (auth-guarded; empty-state aware)
  - `/report/:period` → `ReportPage` (auth-guarded)
  - `*` → redirect to `/upload`
- [ ] **Auth guard** (`ProtectedRoute` wrapper):
  - Unauthenticated → `<Navigate to="/login?next=<current>" />`
  - Loading session → skeleton loader (no flash to login)
- [ ] **Post-login redirect**: if `?next=` is present and points to a same-origin path, honor it; else go to `/upload`
- [ ] `src/lib/api.ts` — centralized fetch client:
  - Pulls `supabase.auth.getSession()` before each call; attaches `Authorization: Bearer <access_token>`
  - Base URL from `VITE_API_URL`
  - Response handling:
    - 401 → `supabase.auth.signOut()` + redirect to `/login?next=<current>`
    - 403 → throw `ForbiddenError` (components handle — usually show inline "you don't have access")
    - 429 → throw `RateLimitedError` with `retry_after_seconds` from header; Toast surface + button cooldown
    - 5xx → throw `ServerError`; components surface via ErrorBoundary or inline
    - All errors carry `trace_id` from response body for dev debugging
- [ ] `src/components/ErrorBoundary.tsx`:
  - Route-level wrapper
  - `componentDidCatch`: log to `console.error` with current `trace_id` (if available)
  - Fallback UI: "Something went wrong. Please refresh — your data is safe." + refresh button
  - **Never render a white screen.**

### 4. Login Screen

Per `design.md` §5 — full spec implementation.

- [ ] `src/pages/LoginPage.tsx`:
  - Single centered card, `max-width: 400px`, 24px padding, `#FFFFFF` surface on `#FAFAF9` canvas, 1px `#E5E4E2` border
  - Headline: "Month Proof" + subhead "Month-end close, verified."
  - Email input: `type="email"`, `autoComplete="username"`, required
  - Password input: `type="password"`, `autoComplete="current-password"`, required
  - Sign in button: full-width, teal `#0D9488`, white text, disabled while request in flight
  - Loading state: label swaps to "Signing in…" with spinner, fields become read-only, button desaturates
  - **Error state**: inline above the Sign in button. Severity=high palette (`#FEE2E2` bg / `#C53030` text). Copy: "Email or password is incorrect. Please try again." (**never specify which field** — don't leak account existence)
  - **No toast for auth errors.** Auth errors are blocking, not transient.
  - **No social login, forgot-password, or sign-up for MVP.**
  - Post-login: redirect to `?next=` (if same-origin) else `/upload`
- [ ] **Demo pre-warming**: Supabase persists session by default. The demo laptop will land pre-logged-in on Day 6; Day 4 just needs to make sure sign-in works and the session survives reload.

### 5. Toast System

Per `design.md` §Toast / Notification System.

- [ ] `src/components/ToastProvider.tsx` — built on `@radix-ui/react-toast` (via shadcn)
- [ ] 4 types with exact behaviors:
  | Type | Bg | Fg/Icon | Auto-dismiss | Example |
  |---|---|---|---|---|
  | success | `#ECFDF5` | `#166534` ✓ | 4s | "Report emailed to cfo@drone.com." |
  | error   | `#FEE2E2` | `#C53030` ⚠ | **manual only** | "Network error — couldn't send email." |
  | warning | `#FEF3C7` | `#B45309` ⚠ | 6s | "You're sending a lot of requests — please wait a moment." |
  | info    | `#F3F4F6` | `#6B7280` ⓘ | 4s | "Your baseline has been saved." |
- [ ] Positioning: top-right, 16px offset, 360px wide, max 3 stacked; overflow queued
- [ ] Slide-in from right 150ms, slide-out + fade 150ms. Respect `prefers-reduced-motion` (skip slide, fade only).
- [ ] Dedup: identical text + type within 1s → no double-fire. Useful for retry spam on 429.
- [ ] `role="status"` for success/info; `role="alert"` for warning/error.
- [ ] Mobile (≤375px): full width minus 16px gutters, still top-anchored.
- [ ] Export `toast.success/error/warning/info` hooks consumed by fetch client and components.
- [ ] **Hard rule**: do NOT surface guardrail failures, auth errors, or mapping low-confidence via toast. Those are inline / modal / screen.

### 6. Schema Extension — Provenance (small migration)

This resolves the "column-level provenance" contract gap flagged in §Preconditions.

- [ ] Extend schema:
  ```sql
  ALTER TABLE monthly_entries ADD COLUMN source_column TEXT;
  ```
- [ ] Parser (Day 2) — after column mapping, write `source_column` per entry (original column header from the uploaded file)
- [ ] Backend — extend `GET /report/{company_id}/{period}` and `GET /anomalies/{company_id}/{period}` to include:
  ```json
  "anomalies": [
    {
      ...,
      "source_file": "drone_mar_2026.xlsx",
      "source_column": "Amount"
    }
  ]
  ```
- [ ] Document this as a **Day 4 schema extension + API contract extension** in `completed.md` (doc sync Day 6)

### 7. Upload Flow

#### `FileUpload` component — 6 states per `design.md`
- [ ] `src/components/FileUpload.tsx`:
  - **Idle** (default): dashed 1px `#E5E4E2` border, white surface, copy "Drop your files here or click to select. Excel · CSV"
  - **Dragging**: solid teal `#0D9488` 2px border, background tints `#ECFDF5` faintly, copy swaps to "Release to upload"
  - **Uploading**: border returns to idle, inline linear progress bar in teal under dropzone, filename list with per-file spinner, dropzone disabled
  - **Wrong file type (client-side)**: inline red text `#C53030` on `#FEE2E2` background under dropzone. Copy: `` `report.pdf` is not a supported format — upload an Excel or CSV file. ``
  - **File too large (client-side)**: same inline pattern. Copy: `` `huge_export.xlsx` is larger than 10 MB — please split the file. ``
  - **Server-side upload failure**: error toast "We couldn't upload `filename.xlsx`. Please try again." Dropzone returns to idle. Retry via re-drop.
- [ ] Accepted extensions (client-side): `.xlsx`, `.csv`, `.xls`, `.xlsm`. **Rejected files never hit the backend.**
- [ ] Max size per file: 10 MB. Enforce client-side.
- [ ] Emit POST with auth header (fetch client handles)

#### `PeriodSelector`
- [ ] `src/components/PeriodSelector.tsx`: month/year dropdown rendering `MMM YYYY` labels (e.g. `Mar 2026`); value held as ISO (`2026-03-01`)
- [ ] Default to previous calendar month relative to today

#### `CompanySelector`
- [ ] Single-company MVP — if user owns exactly 1 company, render as read-only label (not a dropdown). Dropdown shape retained for future multi-company.

#### `LoadingProgress` (4-step polling)
- [ ] `src/components/LoadingProgress.tsx`:
  - Polls `GET /runs/{run_id}/status` every 1000ms via `@tanstack/react-query`
  - 4 steps per `api.md` / `design.md`:
    | step | status mapped to | label |
    |---|---|---|
    | 1 | parsing | Reading files... |
    | 2 | mapping | Mapping accounts... |
    | 3 | comparing | Comparing to history... |
    | 4 | generating | Generating report... |
  - Completed steps: ✓ icon in `#166534`
  - Active step: ● in teal `#0D9488` + linear progress bar under the label
  - Pending steps: ○ empty circle in `#6B6B6B`
  - On `status === "complete"`: stop polling, navigate to `/report/:period`
  - On `status === "guardrail_failed"`: stop polling, render `GuardrailWarning` screen inline
  - On any `*_failed` terminal: stop polling, surface `error_message` via inline error + toast
  - **Cleanup**: cancel polling on unmount (react-query handles)

#### `UploadPage` (orchestration)
- [ ] `src/pages/UploadPage.tsx`:
  - Renders `FileUpload` + `PeriodSelector` + `CompanySelector` + `Analyze` button
  - On submit: POST `/upload` → receives `run_id` → swap to `LoadingProgress` view (same page, no navigation)
  - On `complete`: navigate to `/report/:period`
  - On `guardrail_failed`: render `GuardrailWarning` (see §9)
  - Empty-state aware: if user's company has zero `monthly_entries`, render `EmptyState` instead of the default upload UI (see §10)

### 8. Report View

#### `ReportSummary` — 4 states per `design.md`
- [ ] `src/components/ReportSummary.tsx`:
  - **Generating**: header shows period + "Generating verified report…" with teal spinner in place of Verified badge. Body replaced by skeleton paragraphs (two 90%-width shimmer bars, one 70%, one 50%).
  - **Verified**: full narrative renders. **"Verified · Guardrail Passed" badge** next to period header — checkmark icon + teal accent `#0D9488`. Every number is hoverable (provenance popover via `@radix-ui/react-tooltip`). Numbers visually distinguishable: tabular numerals + subtle underline on hover.
  - **Stale**: Verified badge replaced by amber "Out of date" chip (`#FEF3C7`/`#B45309`). Copy above body: "This report was generated before you re-uploaded the source file. [Regenerate report]." Triggered when `reports.created_at < latest monthly_entries.created_at` for the same `(company_id, period)`.
  - **Guardrail failed**: ReportSummary is **not rendered.** `GuardrailWarning` takes over. **Hard rule: no partial or muted ReportSummary that could be mistaken for verified.**
- [ ] Number rendering: parse narrative and wrap each detected number in a `<span>` with tooltip. Tooltip shows `source_file — column '<source_column>'` from the matching anomaly.
  - **Implementation**: simpler approach — render anomalies as structured cards (not prose), so every number is inside a known component with provenance props. Narrative prose shows summary sentences; numbers inside cards are where hover lives.
  - **If time is tight**: ship card-level provenance only (hover the card, not the number). Narrative prose renders plain. Document as MVP shortcut.

#### `AnomalyCard` — API per `design.md`
- [ ] `src/components/AnomalyCard.tsx`:
  ```ts
  interface AnomalyCardProps {
    account: string;
    value: number;
    variance_pct: number;
    historical_avg: number;
    direction: "favorable" | "unfavorable" | "neutral";  // FROM backend /anomalies response
    severity: "high" | "medium" | "normal";
    description: string;
    source_file: string;
    source_column: string;
  }
  ```
- [ ] **Direction comes from backend.** The `/anomalies` and `/report` serializers compute it server-side using this rule (authoritative — do NOT re-derive in the frontend):
  - REVENUE / OTHER_INCOME: ↑ → favorable; ↓ → unfavorable
  - COGS / OPEX / G&A / R&D: ↑ → unfavorable; ↓ → favorable
  - OTHER: always `neutral`
  - `variance_pct is None` (no history): always `neutral`
- [ ] **Direction drives chip color**: favorable = `#ECFDF5/#166534`; unfavorable = severity palette (high/medium/normal); neutral = `#F3F4F6/#6B7280`
- [ ] **Severity drives chip label**: "HIGH"/"MEDIUM"/"NORMAL"
- [ ] **Do NOT color by sign of `value`** — a negative variance can be favorable (G&A −34%) or unfavorable (revenue −12%) depending on direction. This is the #1 bug risk in finance UX.
- [ ] **Severity chips show color + text label** (never color alone) for accessibility
- [ ] Provenance hover: Radix Tooltip showing `drone_mar_2026.xlsx — column 'Amount'`
- [ ] **4 states**:
  - **Loaded**: chip + value (tabular numerals) + variance %
  - **Loading skeleton**: card shell at correct height with shimmer placeholders (`#F3F4F6` base, `#E5E4E2` highlight). Prevents layout shift.
  - **Empty — no anomalies in category**: **not a card — a summary row**. "✅ All 36 items within normal range." Neutral palette. Collapsed by default with "Show details" link.
  - **Report has zero anomalies total**: full-card placeholder — teal check icon, "No anomalies this period." Celebratory, not empty.

#### `MailButton`
- [ ] `src/components/MailButton.tsx`:
  - Opens a small modal or inline input for recipient email
  - POST `/mail/send` with `{report_id, to_email}`
  - On success: success toast "Report emailed to `<email>`."
  - On failure: error toast (manual dismiss) with retry
  - Disabled on Stale state until regenerate

### 9. GuardrailWarning (screen 3b)

Per `design.md` §3b.

- [ ] `src/components/GuardrailWarning.tsx`:
  - Renders **inline, never as a toast** (blocking state, needs dedicated screen)
  - Headline: "⚠️ Report Validation Warning"
  - Copy: "We detected a number inconsistency in the generated report. The system tried twice and could not produce a verified report."
  - Actions:
    - **Retry Analysis** button (primary, teal) — POSTs to a new endpoint or re-triggers the pipeline with the same `period` and the storage key of the prior upload. Per `design.md`: creates a new `runs` row with `status=pending` and a fresh `run_id`; the failed `run_id` keeps `guardrail_failed` for audit.
    - **Download Raw Data** link → `GET /runs/{run_id}/raw` → triggers download of the `raw_`-prefixed file
    - **Contact Support** link (placeholder — `mailto:` is fine for MVP)
  - Developer error detail: e.g. "Narrative value $4.8M does not match pandas output $4.73M" — shown in a collapsed `<details>` element so jurors can see the guardrail working transparently
- [ ] **Never render a muted/partial ReportSummary alongside** — GuardrailWarning fully replaces the report view
- [ ] **Retry Analysis backend contract**: Day 4 needs a way to re-trigger the pipeline with an existing storage key without re-uploading. Options:
  - A: `POST /runs/{old_run_id}/retry` creates a fresh run on the same file
  - B: `POST /upload` with a `storage_key` param instead of `files[]`
  - **Decision**: ship A. Smaller surface, clearer semantics. Backend adds this endpoint today (small addition to §4 below).
- [ ] Add `POST /runs/{run_id}/retry` to backend:
  - Preconditions: old run exists and is in `guardrail_failed`; auth user owns the company; storage key exists
  - Creates new `runs` row (`status=pending`), schedules BG task reusing the stored file
  - Rate limit: reuse `/upload` limit (5/min per user)

### 10. MappingConfirmModal (post-hoc review panel — MVP fallback)

Day 2 chose the non-blocking post-hoc review approach. Day 4 renders it after the report lands.

- [ ] `src/components/MappingConfirmPanel.tsx`:
  - Triggered when `runs.low_confidence_columns` (from `/runs/{id}/status`) is non-empty
  - Renders **below the report summary** as a non-blocking review card (not a modal over the report)
  - Title: "We auto-mapped these columns. Please review."
  - Max 3 rows shown at a time (lowest confidence first)
  - Per-row fields:
    - Column name (verbatim from source file)
    - Agent's guess (mapped category) — currently `OTHER` (MVP fallback auto-mapped low-confidence to OTHER)
    - Confidence %, secondary text `#6B6B6B`
    - Dropdown: REVENUE, COGS, OPEX, G&A, R&D, OTHER_INCOME, OTHER, SKIP
    - "Skip this column" link
  - **Confirm Mappings** button (teal) — disabled until every row is approved or explicitly skipped
  - On confirm: POST to `POST /runs/{run_id}/mapping/confirm` with `[{column, category}]` (run-scoped per `api.md` §6)
  - Backend persists to `accounts` table; next upload auto-maps same column without prompting
  - Per `design.md`: the **aspirational** blocking `MappingConfirmModal` (that stops the pipeline mid-parse) is post-MVP. Flagged in `risks.md`.
- [ ] Add `POST /runs/{run_id}/mapping/confirm` endpoint (run-scoped, matches `api.md` §6):
  - Path param: `run_id` — UUID. `company_id` derived from run ownership check; client does NOT send it.
  - Body: `{mappings: [{column: str, category: str}]}`
  - Updates `accounts` table for the run's company
  - Rate limit: 30/min per user
  - **This regenerates the report?** No — the report already exists and is verified. Confirming mappings only affects future uploads. (MVP tradeoff; full regeneration is post-MVP.)

### 11. Empty State (screen 6)

Per `design.md` §6. Rendered when `UploadPage` detects zero `monthly_entries` across all periods for this company.

- [ ] `src/components/EmptyState.tsx`:
  - Headline: "Let's set up your baseline." (Semibold, `#1A1A1A`)
  - Body copy: two short paragraphs (secondary text `#6B6B6B`). Explains *why* (comparison requires history) and *what next* (upload one prior month).
  - Muted folder glyph (lucide-react `Folder` icon, desaturated) — **not a warning icon**
  - Same `FileUpload` dropzone + `PeriodSelector` below
  - Period default: previous calendar month relative to today (e.g. today = April 2026 → default `Feb 2026`)
  - **Primary CTA**: "Upload baseline" (teal, full-width, disabled until file + period chosen)
  - Secondary link: "Not sure what to upload? → See a sample Excel file" (downloads a pre-filled template) — **optional; cut if Day 4 runs tight**
  - **No severity colors** (no red/amber). All neutral palette.
  - Nav items (Dashboard, History, Reports) visible but dimmed + tooltip: "Available after your first upload."
  - After successful baseline upload: redirect to a confirmation screen ("Baseline saved. Come back at month-end to run your first close.") — NOT to the full report page (nothing to compare yet).
- [ ] Trigger: add a backend check or use `GET /anomalies/{company_id}/<any_period>` + `/report` to infer zero state. Simplest: add a single query to `GET /runs/{run_id}/status` OR a new lightweight `GET /companies/me/has-history` returning `{has_history: bool}`. **Decision: add `GET /companies/me/has-history`** — clean semantics, 1-line endpoint.

### 12. Cross-Cutting

#### Responsive breakpoints
Per `design.md` §Responsive Breakpoints. Desktop-first.

- [ ] Breakpoints (Tailwind):
  - Mobile: 375px+ (iPhone SE and up)
  - Tablet: 768px (`md`)
  - Desktop: 1024px (`lg`) — **primary target**
- [ ] Layout rules:
  | Region | ≥1024px | 768–1023 | <768 |
  |---|---|---|---|
  | App shell | Left nav + content | Top bar + content | Top bar + content |
  | Dashboard | 2-col | 1-col stacked | **Hidden — redirect** |
  | Report | 1-col 960px max | 1-col fluid | 1-col fluid |
  | AnomalyCard grid | 2-col @ 1280px+, 1 below | 1-col | 1-col |
  | LoadingProgress | 480px wide | Full width 32px gutters | Full width 16px gutters |
  | Toast stack | Top-right 360px | Top-right 360px | Top full-width minus 16px |
  | MappingConfirmPanel | Inline 560px | Inline 90vw | Full-width sheet |
- [ ] Mobile deep-link to `/dashboard` → redirect to `/` with info toast: "Dashboard is available on larger screens."
- [ ] Data tables (`@tanstack/react-table`) **horizontally scroll** inside container below 1024px — never reflow. Columns stay aligned.
- [ ] **Severity chips, variance colors, Verified badge: never hidden at any breakpoint.** Shrink labels, keep colors.
- [ ] Touch targets ≥44×44px on touch breakpoints (shadcn defaults comply).

#### Accessibility
- [ ] All severity chips: color + text label (not color alone)
- [ ] Focus trap in all modals (Radix handles)
- [ ] Esc closes modals / cancels runs
- [ ] `role="status"` / `role="alert"` on toasts
- [ ] Form inputs: proper `<label>` + `autocomplete` attributes (already specified in Login)
- [ ] `prefers-reduced-motion`: toast slide → fade only

#### Error copy routing
- [ ] Frontend does NOT write its own error strings. Every user-facing error string is:
  - From backend `messages.py` (via response body), OR
  - A known frontend-only string mirror (client-side file rejection, network-error fallback) defined in `src/lib/messages.ts` — kept in sync with backend `messages.py`
- [ ] No technical jargon anywhere ("pandera SchemaError: column 'amount' failed dtype check" → "We couldn't read the 'Amount' column. Please check for non-numeric values.")

### 13. Integration Smoke Tests

In-browser, on localhost:

- [ ] Full happy path: login → upload DRONE Mar → progress bar → verified report → send email
- [ ] Forced guardrail failure → GuardrailWarning → Retry Analysis → (if prompts are fixed) verified report
- [ ] Low-confidence upload → MappingConfirmPanel renders → confirm → persists
- [ ] Empty state: user with zero entries → baseline upload flow
- [ ] Client-side PDF rejection → inline error, no backend call
- [ ] Client-side 15MB rejection → inline error
- [ ] Rate-limit: 6× upload → 429 warning toast + button cooldown
- [ ] Tablet view at 900px, mobile at 400px
- [ ] ErrorBoundary: throw inside a component → fallback renders
- [ ] Provenance: hover a number → tooltip with source_file + source_column

---

## Internal Sequencing

1. **Project Setup (§1)** + **Design System Foundation (§2)** — Tailwind tokens, Intl formatter. Nothing else works without these.
2. **Fetch Client + Auth (§3)** — Supabase + fetch client + auth context + ErrorBoundary + routes. Every other component depends on auth + fetch.
3. **Toast System (§5)** — consumed by fetch client (429 warning) and every component that reports events. Build before upload flow.
4. **Schema Extension (§6)** — `source_column` column + Parser update + API extension. Small but blocks AnomalyCard provenance (§8).
5. **Login Screen (§4)** — isolated, can be done in parallel with §5 once auth is wired.
6. **Upload Flow (§7)** — FileUpload (6 states) + PeriodSelector + LoadingProgress polling. Blocks Report View.
7. **Report View (§8)** — ReportSummary + AnomalyCard + MailButton. Needs §6 contract in place.
8. **Edge Screens (§9, §10, §11)** — GuardrailWarning, MappingConfirmPanel, EmptyState. Each depends on its backend contract addition (retry endpoint, mapping confirm endpoint, has-history endpoint).
9. **Responsive + Accessibility (§12)** — apply across all components last; easier to audit all at once.
10. **Smoke tests (§13)** — full in-browser coverage of every path.

Rule of thumb: **tokens → fetch → toast → login → upload → report → edge paths → responsive.** Stacking bottom-up means the bottom layer is proven before the next layer depends on it.

---

## Contracts Produced Today

### Frontend → Backend (new endpoints added today)

| Endpoint | Purpose | Day-3 foundation extended |
|---|---|---|
| `POST /runs/{run_id}/retry` | Re-trigger pipeline on an existing file after guardrail failure. Reads `runs.storage_key`. | new — see `api.md` §7 |
| `POST /runs/{run_id}/mapping/confirm` | Persist user-confirmed mappings to `accounts` | new — see `api.md` §6 (run-scoped URL) |
| `GET /companies/me/has-history` | Tell frontend whether to render EmptyState | new — see `api.md` §8 |

### Schema extension

```sql
ALTER TABLE monthly_entries ADD COLUMN source_column TEXT;
```

Populated by Parser (Day 2, retrofit). Consumed by `/report` and `/anomalies` responses.

### API response extension (Day 3 surface extended)

`GET /report/...` and `GET /anomalies/...` anomalies now include:
```json
{
  ...,
  "source_file": "drone_mar_2026.xlsx",
  "source_column": "Amount",
  "direction": "unfavorable"     // computed backend-side (REVENUE/OTHER_INCOME/OTHER/expense rule)
}
```

`category` is NOT added to the response — `direction` is computed server-side so the frontend doesn't need it.

### Frontend contracts

- `AnomalyCardProps` — direction + severity both from backend; two independent axes, no frontend derivation
- `fetch client` — handles 401/403/429/5xx uniformly
- Toast API — `toast.success/error/warning/info` with exact auto-dismiss rules
- Auth context shape — `{ session, user, loading }`
- `LoadingProgress` polling contract — 1000ms interval, stops on terminal status
- US accounting formatter — `Intl.NumberFormat` with `currencySign: "accounting"`; `"tnum"` globally

---

## Cut Line

### Must ship today (non-negotiable)
- Login screen + auth guard + fetch client with JWT
- ErrorBoundary + Toast system (success + error minimum; warning + info nice-to-have)
- Schema extension for `source_column` + API extension (blocks provenance)
- FileUpload (idle + dragging + uploading + wrong-type inline + too-large inline)
- PeriodSelector + LoadingProgress polling
- ReportSummary verified state + Verified badge
- AnomalyCard loaded state with direction/severity axes correct + provenance hover
- MailButton (wires to Day 3's scaffolded `/mail/send`)
- GuardrailWarning screen + `POST /runs/{id}/retry` backend endpoint

### Deferrable to Day 5
- MappingConfirmPanel (post-hoc review) — useful but not demo-critical if DRONE's headers all map clean
- EmptyState — only matters for brand-new users; DRONE demo has baseline pre-loaded
- Stale state on ReportSummary — edge case
- Rate-limit cooldown countdown on Analyze button (toast warning is enough for MVP)
- Tablet/mobile polish passes beyond the basic responsive collapse
- Accessibility fine-tuning (beyond color+text chips and focus trap)

### Defer to post-MVP
- TrendChart, MetricCard, HistoryList (per design.md "Optional (if time permits)")
- Number-level provenance in narrative prose (card-level provenance is enough for MVP demo)
- Aspirational blocking MappingConfirmModal that pauses the pipeline mid-parse
- Sample-Excel-download link on EmptyState
- Regenerate-report flow on mapping confirmation

---

## Risks (this day)

| Risk | Impact | Mitigation |
|---|---|---|
| shadcn install friction on new Vite app | Day 4 burns 1–2 hours on config before writing components | Follow shadcn docs step-by-step; don't deviate from defaults; commit after init |
| Tailwind palette drift from `design.md` exact hex values | Severity colors "look wrong"; finance UX trust broken | Copy hex values verbatim from design.md; lint with a test that asserts key colors |
| Provenance contract gap (column-level) | Hover shows only filename, not column | §6 schema extension ships today; if schema migration lags, fallback to filename-only is acceptable |
| Direction axis conflated with severity | G&A −34% renders red (looks bad) instead of green (favorable) | Explicit separation in AnomalyCardProps; integration smoke test verifies G&A chip color |
| CORS issue discovered only in browser, not Bruno | Day 4 burns time on a Day-1/3 misconfiguration | Day 3 preflight test (already done); first Day 4 smoke is "does /health return from browser?" |
| Supabase session not persisted across reload | User has to re-login constantly; bad demo flow | `createClient` defaults persist; verify with a hard reload test |
| react-query polling leaks after unmount | Memory/network leak | react-query handles via query keys + component unmount; no manual cleanup needed |
| Fetch client doesn't handle `trace_id` from body | Hard to debug cross-stack errors in dev | Fetch client always logs `trace_id` from response body to console |
| Guardrail retry endpoint omitted | GuardrailWarning Retry button doesn't work | `POST /runs/{id}/retry` ships Day 4 alongside the button |
| MappingConfirmPanel vs aspirational modal confusion | Scope creep | Decision locked: ship post-hoc panel; modal blocking is post-MVP; explicit in risks.md |
| EmptyState not reachable without a 2nd user | Demo never hits this path; bug goes undiscovered | Create a 2nd demo user Day 4 purely for empty-state smoke test |
| Number-level provenance in prose is ambitious | Day 4 burns time on regex parsing | MVP fallback: card-level provenance only; narrative prose renders plain. Document as MVP shortcut. |
| Responsive layout pass skipped | Mobile looks broken in demo (judges often open on phone) | Tailwind responsive classes ship per-component; audit pass Day 5 |
| Error copy goes out of sync with backend messages.py | User sees two different strings for the same error | Centralize frontend strings in `src/lib/messages.ts`, treat as a mirror; reconciliation check Day 5 |

Cross-day risks (tracked in `risks.md`): aspirational blocking MappingConfirmModal post-MVP, number-level prose provenance post-MVP, TrendChart/MetricCard/HistoryList post-MVP.

---

## Reference Docs

Read these before starting Day 4 tasks.

- **`CLAUDE.md`** — Project Structure (frontend folder), Critical Files (no math, no inline prompts), Model Strategy (no user toggle)
- **`docs/scope.md`** — INCLUDED list (frontend items: ErrorBoundary, client-side file validation, toast notifications, verified badge, provenance, US formatting, responsive, login, empty state)
- **`docs/api.md`** — Every endpoint (response shapes + rate limits) + Error Codes Reference + CORS Configuration
- **`docs/design.md`** — **entire file** — palette, severity system, typography, all 7 screens (home, loading, report, GuardrailWarning, login, dashboard, empty state, mapping modal), component list, US number formatting, component library, toast system, component states (FileUpload, AnomalyCard, ReportSummary, LoadingProgress), responsive breakpoints
- **`docs/db-schema.md`** — `monthly_entries.source_file`, `anomalies` fields (for AnomalyCard data), `runs.status` values (for GuardrailWarning trigger)
- **`docs/agent-flow.md`** — Agent 3 (for narrative format), Numeric Guardrail (for GuardrailWarning error detail)
- **`docs/sprint.md`** — Day 4 section (reconciled v3)

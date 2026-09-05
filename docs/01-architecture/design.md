# Month Proof — Design Decisions
*Built with Opus 4.7 Hackathon — April 2026*

---

## General Principles

1. **Zero friction** — the user should not need to think
2. **Plain language** — no financial jargon, English only
3. **Errors first** — show issues before good news
4. **Minimal UI** — demo quality, not production
5. **Visible trust signal** — every verified report displays a "Verified" badge (checkmark + "Guardrail Passed") next to the period header. Unverified/raw data downloads are visually distinct — muted palette, no badge, filename prefixed `raw_` — and must never look like a verified report.

---

## Design Language

Inspired by Mercury (finance calm), Notion (content density), Airtable (color with meaning).

**Palette**

| Token | Hex | Use |
|---|---|---|
| Background | `#FAFAF8` | Warm off-white app canvas |
| Surface / Card | `#FFFFFF` | Cards, modals, report body |
| Border | `#E9E8E4` | 1px card and divider borders |
| Text — primary | `#252421` | Headings, numeric values |
| Text — secondary | `#787670` | Labels, metadata, hints |
| Primary accent | `#F08408` | Primary actions, links, and focus rings (amber) |
| Agent activity | `#6651D4` | Discovery/mapping progress (violet) |
| Utility / verified | `#0D9488` | Verified/guardrail trust signals (teal) |

The current v2 system uses warm stone neutrals, amber for primary actions, violet for agent activity, emerald for favorable outcomes, and teal only for utility/verified trust signals. These meanings are kept separate from severity colors.

**Severity system**

Color carries meaning, not decoration. Severity describes an anomaly's status. Variance direction (favorable/unfavorable/neutral) is a separate axis — green is reserved for *favorable variance only*.

| State | Background | Text/Icon | Use |
|---|---|---|---|
| High (severity) | `#FEF0F0` | `#B91C1C` | Critical anomaly chip |
| Medium (severity) | `#FFF8ED` | `#9A4D00` | Needs-attention anomaly chip |
| Normal (severity) | `#F4F3F0` | `#787670` | Within-range items — neutral gray, **not green** |
| Favorable variance | `#EDFAF3` | `#0A613C` | Variance that moved in the right direction (e.g. G&A −34%) |

Severity chips are always color + text label (never color alone) for accessibility.

**Typography**

- Font family: Inter (all weights)
- Numerics: `font-feature-settings: "tnum"` enabled globally for any numeric cell or value (tabular numerals — see Number Formatting Standards)

---

## Screens

### 1. Home Page — Upload
```
┌────────────────────────────────────────┐
│  Month Proof                           │
│  Financial Intelligence Agent          │
├────────────────────────────────────────┤
│                                        │
│   ┌──────────────────────────────┐     │
│   │                              │     │
│   │   Drop your files here       │     │
│   │   or click to select         │     │
│   │                              │     │
│   │   Excel · CSV                │     │
│   └──────────────────────────────┘     │
│                                        │
│   Which period? [March 2026 ▼]         │
│   Company: Redhawk Alarm & Security LLC  │
│                                        │
│   [Analyze]                            │
│                                        │
└────────────────────────────────────────┘
```

### 2. Loading State
```
┌────────────────────────────────────────┐
│                                        │
│   Reading files...              ████░  │
│   Mapping accounts...           ██░░░  │
│   Comparing to history...       ░░░░░  │
│   Generating report...          ░░░░░  │
│                                        │
└────────────────────────────────────────┘
```

### 3. Report Page
```
┌────────────────────────────────────────┐
│  March 2026 — Redhawk Alarm & Security LLC │
│  Reconciliation items and variances       │
├────────────────────────────────────────┤
│                                        │
│  ⚠️ SERVICE REVENUE        HIGH    │
│  GL $3,540.00 / Contract roster $3,825.00 │
│  $285.00 reconciliation gap             │
│  → Reconcile active accounts           │
│                                        │
│  ℹ️ RENT EXPENSE          COVERAGE │
│  Present in the GL; no supporting file  │
│                                        │
├────────────────────────────────────────┤
│  [Download Excel]  [Open in Email]      │
└────────────────────────────────────────┘
```

### 3b. Guardrail Warning Screen
Shown when numeric guardrail fails after retry. User sees what went wrong and can choose to retry or download raw data.

```
┌────────────────────────────────────────┐
│  ⚠️ Report Validation Warning          │
├────────────────────────────────────────┤
│                                        │
│  We detected a number inconsistency    │
│  in the generated report.              │
│                                        │
│  The system tried twice and could      │
│  not produce a verified report.        │
│                                        │
│  What you can do:                      │
│  → [Retry Analysis]                    │
│  → [Download Raw Data] (unverified)    │
│  → [Contact Support]                   │
│                                        │
│  Error detail (for developers):        │
│  Narrative value $4.8M does not        │
│  match pandas output $4.73M            │
│                                        │
└────────────────────────────────────────┘
```

**Retry Analysis button — behavior:**
Clicking **Retry Analysis** starts a **fresh run with a new `run_id`**. It does NOT reuse the failed `run_id` and does NOT resume from a checkpoint. The previously uploaded file is still in Supabase Storage (it is intentionally not cleaned up on guardrail failure) so the user does not need to re-upload. Flow:
1. Frontend POSTs to the retry endpoint (or re-triggers the pipeline) with the same `period` and the storage key of the prior upload.
2. Backend creates a new `runs` row with `status=pending` and a fresh `run_id`.
3. Parser deletes any `monthly_entries` rows for `(company_id, period)` before inserting (same rule as any re-upload).
4. The failed run_id keeps its `guardrail_failed` status for audit — it is not mutated or deleted.

**Download Raw Data** downloads the pandas summary that was handed to Claude. Unverified — clearly labeled as such in the file header.

### 5. Login Screen

Email + password. Shown at `/login`; it is the normal entry point for the seeded demo user and returning users.

**Default state**

```
┌────────────────────────────────────────┐
│                                        │
│             Month Proof                │
│     Month-end close, verified.         │
│                                        │
│   ┌──────────────────────────────┐     │
│   │                              │     │
│   │  Email                       │     │
│   │  ┌────────────────────────┐  │     │
│   │  │ you@company.com        │  │     │
│   │  └────────────────────────┘  │     │
│   │                              │     │
│   │  Password                    │     │
│   │  ┌────────────────────────┐  │     │
│   │  │ ••••••••••             │  │     │
│   │  └────────────────────────┘  │     │
│   │                              │     │
│   │  ┌────────────────────────┐  │     │
│   │  │       Sign in          │  │ ← primary, amber #F08408
│   │  └────────────────────────┘  │     │
│   │                              │     │
│   └──────────────────────────────┘     │
│                                        │
└────────────────────────────────────────┘
```

**Error state — wrong credentials**

Inline error above the Sign in button. Plain English, no mention of which field was wrong (standard auth hygiene — don't leak whether the email exists).

```
┌────────────────────────────────────────┐
│                                        │
│             Month Proof                │
│     Month-end close, verified.         │
│                                        │
│   ┌──────────────────────────────┐     │
│   │                              │     │
│   │  Email                       │     │
│   │  ┌────────────────────────┐  │     │
│   │  │ you@company.com        │  │     │
│   │  └────────────────────────┘  │     │
│   │                              │     │
│   │  Password                    │     │
│   │  ┌────────────────────────┐  │     │
│   │  │ ••••••••••             │  │     │
│   │  └────────────────────────┘  │     │
│   │                              │     │
│   │  ⚠ Email or password is      │ ← inline, #B91C1C text
│   │    incorrect. Please try     │    on #FEF0F0 background
│   │    again.                    │     │
│   │                              │     │
│   │  ┌────────────────────────┐  │     │
│   │  │       Sign in          │  │     │
│   │  └────────────────────────┘  │     │
│   │                              │     │
│   └──────────────────────────────┘     │
│                                        │
└────────────────────────────────────────┘
```

**Spec**

| Element | Detail |
|---|---|
| Layout | Single centered card, `max-width: 400px`, surface `#FFFFFF` on `#FAFAF8` canvas, 1px `#E9E8E4` border, 24px internal padding |
| Fields | Email (`type="email"`, autocomplete `username`), Password (`type="password"`, autocomplete `current-password`). Both required. |
| Sign in button | Full-width primary. Background `#F08408` (amber accent). White text. Disabled while request is in flight. |
| Disabled / loading state | Button label swaps to "Signing in…" with a spinner. Button background desaturates; fields become read-only. |
| Error message | Inline above the button. Severity = high palette (`#FEF0F0` bg / `#B91C1C` text). Do NOT use a toast — auth errors are blocking, not transient. |
| Social login | **None for MVP.** |
| Forgot password | **None for MVP.** Add post-hackathon. |
| Sign up | Links to the implemented `/register` route. New users continue through onboarding. |
| Demo behavior | The seeded demo user is `demo@redhawkdemo.com`; authentication still uses the normal login flow. |
| Post-login redirect | Users with completed onboarding go to a safe same-origin `?next=` path or `/upload`; incomplete users go to `/onboarding`. |

---

### 4. Dashboard

Route: `/dashboard` (auth-guarded, inside `AppShell`). Entry from the **Dashboard** item in the SideNav or mobile drawer. The implemented dashboard includes monthly/quarterly tabs, financial KPI cards, month-over-month comparisons, anomaly counts, and report history.

**Scope question this screen answers**
1. What data do I have?
2. What's my latest state?
3. Are there open issues?

```
┌──────────────────────────────────────────────────────────┐
│  Dashboard                                               │
│  Redhawk Alarm & Security LLC · Loaded data and reports │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Revenue · Gross Margin · Net Income                 │
│  Operating Expenses · Critical Issues · Health       │
│                                                          │
│  Recent reports                  [Monthly] [Quarterly]    │
│  ┌──────────────────────────────────────────────────┐    │
│  │ Mar 2026                                        →│    │
│  │ Current anomaly count · generated timestamp       │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│                              [ ↑ Upload new period ]     │
└──────────────────────────────────────────────────────────┘
```

**Sections**

| Region | Content |
|---|---|
| Header | `<h1>` "Dashboard", company name + tagline in secondary-text below. |
| **Metric grid** | Six `MetricCard` tiles: revenue, gross margin, net income, operating expenses, critical anomalies, and financial health. Current-vs-previous values use favorable/unfavorable direction styling. |
| **Recent reports** | `HistoryList` is fed by `GET /reports?limit=50` and filtered by the selected monthly/quarterly tab. Monthly rows link to `/report/:period`; quarterly rows use the quarterly report route. |
| **Action** | Single primary CTA `Upload new period` → `/upload`. Amber `#F08408`, right-aligned. No competing secondary action — dashboard is a read surface, not a control panel. |

**Metric tiles (current — six)**

| Tile | Source | Fallback |
|---|---|---|
| Revenue, gross margin, net income, OpEx | Latest monthly `GET /report/{company_id}/{period}` financials; prior report supplies MoM comparison | `—` when unavailable |
| Critical anomalies | High/medium anomalies in the latest monthly report | `0` |
| Financial health | Latest net income and net margin | `—` when unavailable |

**Empty state (first-time users)**

The Dashboard itself is still reachable with zero reports — it doesn't gate behind `has_history`. The metrics display zeros/em-dashes, and `HistoryList` renders its own empty card ("No reports yet. Upload your first period to see analysis here."). This mirrors the Profile page posture: neutral palette, no red/amber, not an error.

**Responsive behavior** (per §Responsive Breakpoints table)

| Breakpoint | Layout |
|---|---|
| **≥1024px** (desktop) | 3-col `MetricCard` row (`lg:grid-cols-3`). `HistoryList` full-width inside `max-w-5xl` container. |
| **768–1023** (tablet) | 2-col `MetricCard` row (`md:grid-cols-2`) — the third tile wraps to the next line. `HistoryList` unchanged. |
| **<768** (mobile) | **Not rendered.** `AppShell` detects `max-width: 767px` on route change and redirects `/dashboard` → `/upload` with an info toast: "Dashboard is available on larger screens." |

**Data freshness**
- `has-history` and `/reports` both use a 30s React Query `staleTime`. Opening the page twice in quick succession hits the cache. The Dashboard is a soft overview; stale-by-30s is fine. Hard refresh on an upload completion is handled elsewhere (UploadPage triggers `queryClient.invalidateQueries(["has-history"])` when a run finishes).

**What this screen is explicitly NOT** (post-MVP)

- **TrendChart** — ≥6 periods required for a meaningful bar chart; demo has 2.
- **Date range picker / filters** — dashboard shows everything; filtering happens on a future `/reports` page.
- **PDF export** — the monthly close package exports as a three-sheet `.xlsx`; PDF remains post-MVP.

---

### 4b. Earlier dashboard concept (superseded)
```
┌─────────────┬──────────────────────────┐
│  Summary       │  Monthly Trend             │
│             │                          │
│  Revenue      │  ████████████            │
│  $120,000   │  ▓▓▓▓▓▓▓▓▓▓             │
│             │                          │
│  Expenses      │  Jan  Feb  Mar           │
│  $87,000    │                          │
│             ├──────────────────────────┤
│  Net        │  Anomalies              │
│  $33,000    │  • Electricity +%53 ⚠️      │
│             │  • Payroll +%18 ⚠️      │
└─────────────┴──────────────────────────┘
```

### 6. Empty State — First Upload, No History

Shown to a freshly signed-up user whose company has no prior `monthly_entries` for any period. The Comparison agent requires at least one prior period to compute variance — without a baseline there is nothing to compare against, so the full pipeline cannot run yet. This is expected, not an error.

Tone: friendly, inviting, not alarming. The user has done nothing wrong.

```
┌────────────────────────────────────────┐
│  Month Proof                           │
│  Month-end close, verified.            │
├────────────────────────────────────────┤
│                                        │
│              ┌──────┐                  │
│              │  📂  │                  │ ← muted illustration,
│              └──────┘                  │   not an alert icon
│                                        │
│        Let's set up your baseline      │
│                                        │
│  Month Proof compares each month to    │
│  your history. You haven't uploaded    │
│  anything yet, so there's nothing to   │
│  compare against.                      │
│                                        │
│  Start by uploading one prior month    │
│  (for example, February 2026). We'll   │
│  use it as the baseline. Next month,   │
│  drop in March and you'll get your     │
│  first variance report.                │
│                                        │
│   ┌──────────────────────────────┐     │
│   │                              │     │
│   │   Drop your baseline file    │     │
│   │   or click to select         │     │
│   │                              │     │
│   │   Excel · CSV                │     │
│   └──────────────────────────────┘     │
│                                        │
│   Which period is this? [Feb 2026 ▼]   │
│                                        │
│   ┌────────────────────────┐           │
│   │  Upload baseline       │           │ ← primary, amber #F08408
│   └────────────────────────┘           │
│                                        │
│   ─────────────────────────────        │
│                                        │
│   Not sure what to upload?             │
│   → See a sample Excel file            │ ← link, amber
│                                        │
└────────────────────────────────────────┘
```

**Spec**

| Element | Detail |
|---|---|
| Headline | "Let's set up your baseline." Semibold, primary text `#252421`. |
| Body copy | Two short paragraphs. Secondary text `#787670`. Explains *why* (comparison requires history) and *what next* (upload one prior month, then the current month next time). |
| Illustration | Muted folder glyph. Do NOT use warning/alert iconography — the empty state is not an error. |
| Period default | Defaults to the previous calendar month relative to today (e.g. today = Apr 2026 → default = `Feb 2026`). User can change via the `PeriodSelector`. |
| Primary CTA | "Upload baseline" — full-width below the dropzone. Amber `#F08408`. Disabled until a file is selected and a period chosen. |
| Sample file link | Secondary text-link. Downloads a pre-filled Excel template so hesitant first-time users have something concrete to mimic. Optional for MVP if time is tight. |
| Severity / alert colors | **None.** The empty state uses only neutral palette. No red, no amber. Anything hinting at failure would confuse a brand-new user. |
| Dashboard link / nav | Dashboard, Data, and Reports remain available in the navigation; their own empty states handle a company with no loaded data. |
| Trigger | Rendered when the authenticated user's `company_id` has zero rows in `monthly_entries` across all periods. |
| After upload | On successful baseline upload, redirect to a confirmation screen ("Baseline saved. Come back at month-end to run your first close.") — NOT to the full report page, since there is still no comparison to show. |

---

### 7. Mapping Confirmation Surfaces

`MappingReview` pauses multi-source runs when source values need a canonical GL account. `MappingConfirmPanel` handles up to three low-confidence column/category mappings. The compact panel shows only the lowest-confidence columns so review stays focused.

Blocks the pipeline until resolved. Background is dimmed; rest of the UI is non-interactive.

```
┌──────────────────────────────────────────────────┐
│  Help us map 2 columns            [ × ]          │
├──────────────────────────────────────────────────┤
│                                                  │
│  Most of your file mapped cleanly. We're not     │
│  sure about these — please confirm.              │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │ Column: "Misc Acct Adj"                    │  │
│  │ Agent's guess: OTHER_INCOME    72% conf.   │  │
│  │                                            │  │
│  │ Map to: [ OTHER_INCOME       ▼ ]           │  │
│  │ [ Skip this column ]                       │  │
│  └────────────────────────────────────────────┘  │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │ Column: "T&E Reclass"                      │  │
│  │ Agent's guess: OPEX             68% conf.  │  │
│  │                                            │  │
│  │ Map to: [ OPEX               ▼ ]           │  │
│  │ [ Skip this column ]                       │  │
│  └────────────────────────────────────────────┘  │
│                                                  │
├──────────────────────────────────────────────────┤
│                   [ Cancel ]   [ Confirm Mapping ] ← primary amber
└──────────────────────────────────────────────────┘
```

**Spec**

| Element | Detail |
|---|---|
| Trigger | Any column mapped with confidence < 80%. Columns ≥ 80% are accepted silently and never shown here. |
| Maximum rows shown at once | **3.** If more than 3 columns are below threshold, show the 3 lowest-confidence first. The remainder are mapped to `OTHER` and surfaced post-run as a non-blocking review item (out of scope for MVP if it slips). |
| Row layout | Card per column. Fields: `column name` (from the uploaded file, verbatim), `agent's guess` (mapped category), `confidence %` (secondary text), `Map to` dropdown (US GAAP categories from `account_categories`), `Skip this column` link (skipped columns are not loaded into `monthly_entries`). |
| Dropdown options | `REVENUE`, `COGS`, `OPEX`, `G&A`, `R&D`, `OTHER_INCOME`, `OTHER`, `SKIP`. Default = agent's guess. **OTHER** is a real seeded `account_categories` row (id=7) — selecting it writes the column to the import as the OTHER bucket. **SKIP** is a frontend-only sentinel — selecting it removes the column from the persisted mapping; the column is **never written to `accounts` or `monthly_entries`**. The backend `POST /runs/{run_id}/mapping/confirm` handler accepts `SKIP` in the request body and treats it as a delete-by-omission. |
| Confidence display | Plain percentage, secondary text color `#787670`. No progress bar — keeps the density Notion-like. |
| Primary CTA | **Confirm Mapping** — amber `#F08408`, right-aligned in footer. Disabled until every flagged row has either an approved dropdown choice or an explicit Skip. |
| Secondary CTA | **Cancel** — text button, left of the primary. Cancels the current run; the uploaded file stays in Supabase Storage for retry. |
| Close ("×") behavior | Same as Cancel. |
| Accessibility | Focus trapped inside modal. `Esc` = Cancel. Tab order: rows top-to-bottom, then footer. |
| Persistence | Confirmed mappings are persisted to `accounts` for this `company_id` so the same column header from the same source file will auto-map next month without re-prompting. |

---

### 8. Profile Page

Account surface with read-only identity/company fields plus an editable typical-monthly-revenue band. It consumes `GET /companies/me`, `GET /companies/me/has-history`, the Supabase Auth session, and `PATCH /companies/me` for the revenue-band setting.

**Route:** `/profile` (auth-guarded, inside `AppShell`).

**Entry point:** clicking the company-name / email block at the bottom of the `AppShell` sidebar (desktop) or drawer (mobile). The block gets a `bg-canvas` hover state and a focus ring; active-route highlight uses the same `bg-canvas` background while on `/profile`. The separate Sign out button below remains independent — a dedicated action, not a nav target.

```
┌──────────────────────────────────────────────────┐
│  Your account                         [ 👤 ]     │
│  Company identity and close-scale settings.     │
├──────────────────────────────────────────────────┤
│                                                  │
│  ┌─ ✉ Account ───────────────────────────────┐   │
│  │  Email         demo@redhawkdemo.com       │   │
│  │  User ID       8ab2…f9e1  (monospace)     │   │
│  └───────────────────────────────────────────┘   │
│                                                  │
│  ┌─ 🏢 Company ──────────────────────────────┐   │
│  │  Name          Redhawk Alarm & Security LLC │ │
│  │  Sector        Field Service — Alarm & Security │ │
│  │  Currency      USD                        │   │
│  │  Monthly rev.  Under $100K          [Save]│   │
│  └───────────────────────────────────────────┘   │
│                                                  │
│  ┌─ 🕘 Usage ────────────────────────────────┐   │
│  │  Periods loaded          3                │   │
│  │  Baseline status  ⦁ Active                │   │
│  └───────────────────────────────────────────┘   │
│                                                  │
│  ┌───────────────────────────────────────────┐   │
│  │            [ ⎋  Sign out ]                │   │
│  └───────────────────────────────────────────┘   │
│                                                  │
└──────────────────────────────────────────────────┘
```

**Layout**

| Property | Value |
|---|---|
| Page width | Single column, `max-w-6xl` (72rem), centered; cards remain stacked. |
| Padding | `px-4` always; `py-6` mobile, `py-8` md+. |
| Card radius / border | `rounded-lg` + `border border-border` (`#E9E8E4`) on `bg-surface`. Matches ReportSummary + AnomalyCard. |
| Section header | Icon (lucide, `h-4 w-4`, `text-text-secondary`) + section label (14px, semibold, `text-text-primary`). Bottom border divides header from `<dl>`. |
| Key/value row | `<dt>` left (14px, `text-text-secondary`), `<dd>` right (14px, `text-text-primary`). Dividers between rows via `divide-y divide-border`. Numeric values carry `tabular-nums` + `data-numeric`. |
| Baseline chip | `favorable` palette if `has_history === true` ("Active"). `severity.normal` palette if false ("Not set up"). Never red — this is not a warning state. |
| Sign out button | Full-width, bordered, non-accent (sign-out is a neutral action, not primary). Amber is reserved for primary CTAs. `min-h-[44px]` on touch, `min-h-[40px]` on `lg`. |

**Fields displayed**

| Section | Field | Source | Notes |
|---|---|---|---|
| Account | Email | `useAuth().user.email` (Supabase session) | Read-only. |
| Account | User ID | `useAuth().user.id` | Monospace, truncated. Useful for support/debug. |
| Company | Name | `GET /companies/me` → `name` | |
| Company | Sector | `GET /companies/me` → `sector` | `—` when null. |
| Company | Currency | `GET /companies/me` → `currency` | Tabular numerals in case of non-USD codes. |
| Company | Typical monthly revenue | `GET /companies/me` → `monthly_revenue_band` | Editable via `PATCH /companies/me`; drives scaled materiality thresholds. |
| Usage | Periods loaded | `GET /companies/me/has-history` → `periods_loaded` | |
| Usage | Baseline status | `GET /companies/me/has-history` → `has_history` | Chip: favorable / normal. |

**Actions (MVP)**

| Action | Behavior |
|---|---|
| Save revenue band | Sends `PATCH /companies/me` and refreshes the cached company record. |
| Sign out | Calls `supabase.auth.signOut()`, navigates to `/login`. Redundant with the sidebar/drawer Sign out button — kept here because users expect it on an account page. |

**Explicitly NOT in MVP** (post-hackathon):
- Change password (via `supabase.auth.updateUser`)
- Edit company name / sector / currency (the revenue band is editable)
- Delete account
- Team members / role management
- Billing / subscription
- API keys / integrations
- 2FA settings

These remain outside the current profile surface; the revenue-band field is the sole supported company-setting write.

**Responsive behavior**

| Breakpoint | Behavior |
|---|---|
| ≥1024px | Profile renders right of the fixed SideNav inside the 72rem content cap. |
| 768–1023px | No sidebar; content takes full width under the top bar inside the same cap. |
| <768px | Same as tablet. Card gutters `px-4` give ~16px to screen edge. Sign out button spans full card width. |

**Accessibility**
- Single `<h1>` per page ("Your account").
- Each section uses `<section>` + `<h2>` + `<dl>` semantics.
- Sign out button is a real `<button>` with visible focus ring (`focus:ring-2 focus:ring-accent`).
- Read-only fields are not rendered as disabled form inputs — they're plain text to avoid the visual weight of form controls that can't be edited.

---

## Component List

### Required (MVP)
- `ErrorBoundary` — route-level React error boundary wrapping every page. Catches render and lifecycle exceptions, renders a plain-English fallback ("Something went wrong. Please refresh — your data is safe."), and logs the error with the current `trace_id` if one is present.
- `FileUpload` — drag & drop, multiple file. Performs **client-side validation before upload**:
  - Accepted extensions: `.xlsx`, `.csv`, `.xls`, `.xlsm`
  - Max size per file: **10 MB**
  - On rejection, show a plain-English toast/inline message (e.g. "`report.pdf` is not a supported format — upload an Excel or CSV file." or "`huge_export.xlsx` is larger than 10 MB — please split the file.")
  - Rejected files never hit `POST /upload`. Valid files are POSTed with the JWT `Authorization` header.
- `PeriodSelector` — month/year selection
- Company identity is display-only; `company_id` is resolved from the authenticated user and is never selected or supplied by the browser.
- `LoadingProgress` — 5-step progress display (reading, discovery, mapping, comparison, generation)
- `AnomalyCard` — single anomaly card.
  - **API:** `{ value: number, direction: 'favorable' | 'unfavorable' | 'neutral', severity: 'high' | 'medium' | 'normal', ... }`. Direction drives color (favorable = emerald chip `#EDFAF3/#0A613C`; unfavorable = severity red/amber; neutral = warm gray). Severity drives the chip label. Do NOT color by sign of `value` — a negative variance can be favorable (e.g. G&A −34%) or unfavorable (e.g. revenue −12%) depending on direction.
  - **Provenance:** every figure rendered inside the card is hoverable. The hover/popover shows the source filename and original column name, e.g. `redhawk_gl_mar_2026.xlsx — column 'Amount'`. This surfaces the guardrail story to the user — each number is traceable back to the file it came from.
- `ReportSummary` — plain-language summary.
  - **Verified badge:** renders the "Verified · Guardrail Passed" badge (checkmark icon + teal accent) next to the period header whenever the report was produced by a run whose guardrail passed. Never render this badge on raw/unverified downloads.
  - **Provenance:** every number in the narrative prose is hoverable. Hover reveals source filename and original column name (e.g. `redhawk_gl_mar_2026.xlsx — column 'Amount'`). Numbers are visibly distinguishable from surrounding prose (tabular numerals + subtle underline on hover) so the user learns they are inspectable.
- `MailButton` — builds a prefilled `mailto:` URL and opens the user's local email client; it does not call the stub backend email route
- `GuardrailWarning` — shown when numeric validation fails after retry, offers retry/download raw options
- `DiscoveryReview`, `MappingReview`, `MappingConfirmPanel`, and `ParsePreviewPanel` — staged review surfaces for structure, source-value mapping, low-confidence categories, and parsed rows
- `AppShell` — two-column responsive shell (fixed left `SideNav` ≥1024px / top bar + hamburger-drawer below). Houses the main nav and the clickable user footer that navigates to `/profile`. Per `§Responsive Breakpoints`.
- `ProfilePage` — account view at `/profile` per §8 above. Surfaces Auth identity, company/history data, editable revenue band, and sign-out.

`MetricCard` and `HistoryList` are implemented dashboard components.

### Optional (if time permits)
- `TrendChart` — monthly bar chart

---

## UX Decisions

**File upload:**
Multiple files can be selected. Revenue and expenses can be uploaded separately. The agent identifies each file correctly.

**Error messages:**
No technical jargon. Not "Column mismatch", but "We couldn't map these columns. Please review."

**Loading:**
While the agent runs, the user sees what is happening. Not a black box.

**Report language:**
English only. Demo is in English (hackathon jury).

**Mail:**
`MailButton` opens a prefilled `mailto:` draft containing the period, anomaly count, and summary, and reminds the user to attach the exported Excel package. `/mail/send` and the Resend adapter remain unused stubs.

**Guardrail failure:**
If the numeric guardrail fails, the system retries once automatically. If the second attempt also fails, show the GuardrailWarning screen. Never show an unverified report as if it were verified. The raw pandas data can be offered as a download so the user is never left empty-handed.

**Column mapping confirmation:**
Columns mapped with 80%+ confidence are accepted silently. Lower-confidence category mappings are shown in `MappingConfirmPanel`; source-value-to-GL decisions use the separate `MappingReview` screen. Both use explicit approve/reassign controls.

---

## Number Formatting Standards

US accounting conventions. Apply everywhere — tables, cards, narrative, exported reports, email bodies.

| Rule | Value |
|---|---|
| Currency | USD only |
| Thousands separator | comma (`1,234,567`) |
| Decimal separator | period (`1,234.56`) |
| Decimal places — tables | 2 (`$45,000.00`) |
| Decimal places — narrative | Exact source values with `$`, separators, and/or two decimals; do not abbreviate or re-round (`$4,730,000.00`, not `$4.73M`) |
| Negative numbers | parentheses, **never** a minus sign — `($1,234.00)`, not `-$1,234.00` |
| Tabular numerals | `font-feature-settings: "tnum"` on ALL numeric cells |
| Fiscal year | January–December (US standard) |
| Period label — headers / UI | `MMM YYYY` (e.g. `Mar 2026`) |
| Period label — metadata / API | ISO 8601 (`2026-03-01`) |

Implementation note: centralize formatting in a single helper. `Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', currencySign: 'accounting' })` yields the accounting-style parenthesized negatives automatically.

---

## Component Library

- **Library:** shadcn/ui (Radix UI primitives + Tailwind). Chosen for speed + full style control with no opinionated design system to fight.
- **Data tables:** `@tanstack/react-table` integration for any financial table (sort, sticky header, frozen first column, right-aligned numerics). **Do not hand-roll tables** — financial data has too many edge cases (tabular nums, negative formatting, column alignment) to reinvent in a sprint.
- **Error patterns:**
  - **Inline, with context** — for guardrail failures and any error that ties to a specific number, row, or field. The user needs to see *where* the problem is, not a toast that disappears.
  - **Toast** — for transient, non-blocking events only (mail sent, rate limit hit, file rejected client-side). Never for guardrail or validation failures.
- **Theming discipline:** do NOT heavily theme shadcn components. Set the palette + typography tokens once in `tailwind.config` and otherwise use shadcn defaults. Every hour spent polishing a Button variant is an hour not spent on the parser.

---

## Toast / Notification System

Global, non-blocking surface for transient events. Toasts are for events the user should be aware of but does not have to act on. Anything that blocks the workflow or ties to a specific number/field goes **inline**, never into a toast.

**Guardrail failures are INLINE, not toasts.** A failed numeric guardrail is blocking (no verified report is produced), needs the dedicated `GuardrailWarning` screen with retry/download-raw options, and must remain on screen — it cannot auto-dismiss. Never surface guardrail state through the toast system.

**Positioning**

Top-right of the viewport, stacked vertically (newest on top). Offset 16px from the top and right edges. Stacks up to 3 visible at once; additional toasts queue and appear as the visible stack clears.

**Types**

| Type | Background | Icon/Accent | Dismiss | Example |
|---|---|---|---|---|
| success | `#EDFAF3` | `#0A613C` ✓ check | auto after **4s**; also dismissible manually | "Report generated and verified." |
| error | `#FEF0F0` | `#B91C1C` ⚠ alert | **manual dismiss only** — no auto-timeout | "Network error — please try again." |
| warning | `#FFF8ED` | `#9A4D00` ⚠ alert | auto after **6s**; dismissible manually | "You're sending a lot of requests — please wait a moment." (429 rate limit) |
| info | `#F4F3F0` | `#787670` ⓘ info | auto after **4s**; dismissible manually | "Your baseline has been saved." |

**When to use each**

| Event | Type |
|---|---|
| Mail sent | Not emitted today; `MailButton` hands off to the local email client |
| Report generated & verified (if user was on a different screen) | success |
| Rate limit hit (HTTP 429) | warning |
| Network error / unreachable API | error |
| File rejected client-side (wrong type, too large) | error |
| Transient Supabase/Resend 5xx | error |
| Non-blocking informational ("We saved your draft") | info |
| **Guardrail failure** | **NOT a toast** — inline on the GuardrailWarning screen |
| **Auth error (wrong password)** | **NOT a toast** — inline on the Login screen |
| **Column mapping confidence low** | **NOT a toast** — opens the appropriate mapping review surface |

**Wireframe**

```
                                   top-right of viewport
                                                   │
                                                   ▼
                       ┌─────────────────────────────────┐
                       │ ✓  Report generated and         │
                       │    verified.            [ × ]   │  ← success, auto 4s
                       └─────────────────────────────────┘
                       ┌─────────────────────────────────┐
                       │ ⚠  Network error — please       │
                       │    try again.            [ × ]   │  ← error, manual
                       └─────────────────────────────────┘
```

**Spec**

| Element | Detail |
|---|---|
| Width | 360px. Body text wraps, toast grows vertically to fit. |
| Typography | Body 14px, Inter, primary text color depends on type (see table). |
| Dismiss button | `×` icon, secondary color. Always present. |
| Animation | Slide-in from right, 150ms ease-out. Slide-out + fade on dismiss, 150ms. |
| Accessibility | `role="status"` for success/info, `role="alert"` for warning/error. Respect `prefers-reduced-motion`: skip slide, fade only. |
| Stacking | Max 3 visible. Overflow queues in order. A new toast with identical text & type within 1s dedupes (no double-fire on retry spam). |
| Positioning on mobile | Full width minus 16px gutters at ≤375px; still top-anchored. |

---

## Component States

Every component ships with these states defined. A component with no defined loading/empty/error state will default to "looks broken" — specify every one.

### `FileUpload`

| State | Visual | Notes |
|---|---|---|
| Idle / default | Dashed 1px border `#E9E8E4`, surface `#FFFFFF`, copy "Drop your files here or click to select. Excel · CSV". | Baseline state. |
| Dragging (file over zone) | Border becomes solid amber `#F08408` 2px, background tints favorable emerald, copy swaps to "Release to upload". | Triggered by `dragenter`/`dragover`. Revert on `dragleave`. |
| Uploading | Border returns to `#E9E8E4`. Inline linear progress bar in amber under the dropzone. Filename list visible with per-file spinner. Dropzone is disabled during upload. | No toast — progress is local to the component. |
| Wrong file type (client-side reject) | **Inline** message under dropzone: red text `#B91C1C` on `#FEF0F0` background, 8px padding. Copy: `` `report.pdf` is not a supported format — upload an Excel or CSV file. `` Also emit an error toast if the rejection happens via the hidden file input (out-of-view drop). Rejected file is NOT added to the pending list. | Accepted extensions: `.xlsx`, `.csv`, `.xls`, `.xlsm`. |
| File too large (client-side reject) | Same inline pattern. Copy: `` `huge_export.xlsx` is larger than 10 MB — please split the file. `` | 10 MB per-file cap. |
| Server-side upload failure | Error toast: "We couldn't upload `filename.xlsx`. Please try again." Dropzone returns to idle. | Retry button inside the toast (or re-drop). |

### `AnomalyCard`

| State | Visual | Notes |
|---|---|---|
| Loaded (default) | Chip with severity color (high/medium/normal) + text label; value with tabular numerals; variance % with favorable/unfavorable/neutral direction color; provenance underline on hover. | See Component List for API. |
| Loading skeleton | Card shell rendered at correct height with shimmer placeholders for chip, number, label. Uses `#F4F3F0` base and `#E9E8E4` highlight. No icons, no text. | Prevents layout shift when data arrives. |
| Empty — no anomalies in category | **Not a card — a summary row.** Copy: "✅ All 36 items within normal range." Neutral palette, no severity color. Collapsed by default with a text-link "Show details" to expand. | Avoids printing 36 "normal" cards which would drown the real anomalies. |
| Report has zero anomalies total | Full-card placeholder: teal check icon, headline "No anomalies this period." Secondary copy: "Every account is within expected range vs. your history." | Rare but should look celebratory, not empty. |

### `ReportSummary`

| State | Visual | Notes |
|---|---|---|
| Generating | Header shows period + "Generating verified report…" with a teal spinner in place of the Verified badge. Body is replaced by skeleton paragraphs (two 90%-width shimmer bars, one 70%, one 50%). | Shown while interpreter + guardrail are running. |
| Guardrail failed | ReportSummary is **not rendered.** The GuardrailWarning screen (3b) replaces it. Do not render a partial or muted ReportSummary that could be mistaken for a verified one. | Hard rule: no unverified prose ever appears in this component. |
| Verified | Full narrative renders. "Verified · Guardrail Passed" badge next to the period header — checkmark icon + teal accent `#0D9488`. Every number is hoverable (provenance popover). | This is the only state where the Verified badge renders. |
| Stale (report exists but source file re-uploaded since) | Verified badge replaced by an amber "Out of date" chip (`#FFF8ED/#9A4D00`). Copy above body: "This report was generated before you re-uploaded the source file. [Regenerate report]." | Prevents the user from emailing a stale verified report. |

### `LoadingProgress`

Five sequential steps, each with a label and an integer % (0–100). One step is active at a time; review states can pause after discovery, mapping, or parsing. Parent polls `/runs/{run_id}/status`.

```
┌────────────────────────────────────────┐
│  ✓ Reading files                 100%  │ ← complete
│  ✓ Analyzing structure            100%  │ ← complete
│  ● Mapping accounts               62%  │ ← active, violet progress
│  ○ Comparing to history            0%  │ ← pending, dimmed
│  ○ Generating report               0%  │ ← pending, dimmed
└────────────────────────────────────────┘
```

| Step | Label | Backend signal | Notes |
|---|---|---|---|
| 1 | Reading files | Parser: file read + PII sanitize + pandera validate complete | `%` = rows processed ÷ total rows |
| 2 | Analyzing structure | Discovery plan produced or awaiting user approval | Backend-reported progress |
| 3 | Mapping accounts | Category/source-value mapping and preview preparation | Backend-reported progress |
| 4 | Comparing to history | Comparison agent running after preview confirmation | Backend-reported progress |
| 5 | Generating report | Interpreter + guardrail running | Completes only after guardrail passes. |

Completed steps use an emerald ✓. Active steps use violet `#6651D4` with a violet-to-emerald progress treatment. Pending steps use warm gray `#787670`.

---

## Responsive Breakpoints

Month Proof is desktop-first — the target user is a controller sitting at a workstation with a 1440px+ monitor. Tablet and mobile are supported for the critical path only (upload + read report); dense exploratory views are desktop-only.

**Breakpoints**

| Name | Min width | Target device |
|---|---|---|
| Mobile | 375px | Phones (iPhone SE and up) |
| Tablet | 768px | iPad portrait, small laptops |
| Desktop | 1024px+ | Primary target |

Tailwind tokens: `sm` = 640px (unused), `md` = 768px (tablet), `lg` = 1024px (desktop), `xl` = 1280px.

**Layout behavior**

| Region | ≥1024px (desktop) | 768–1023px (tablet) | <768px (mobile, min 375px) |
|---|---|---|---|
| App shell (nav + content) | Two-column: left nav + content | Top nav bar + single column content | Top nav bar + single column content |
| Dashboard (screen 4) | Six KPI cards in a 3-column grid + report history | KPI cards in a 2-column grid + report history | **Hidden — not a supported mobile screen** |
| Report page (screen 3) | Single column, max-width 960px centered | Same, fluid width | Same, fluid width |
| AnomalyCard grid | 2 columns on 1280px+, 1 column below | 1 column | 1 column |
| LoadingProgress | Inline, 480px wide | Full width, 32px gutters | Full width, 16px gutters |
| Mapping review surfaces | Centered content/modal as appropriate | Fluid centered content | Full-width review flow |
| Toast stack | Top-right, 360px wide | Top-right, 360px | Top, full width minus 16px gutters |

**Which components are hidden per breakpoint**

| Component | Desktop | Tablet | Mobile |
|---|---|---|---|
| `FileUpload` | ✅ | ✅ | ✅ |
| `ReportSummary` | ✅ | ✅ | ✅ |
| `AnomalyCard` | ✅ | ✅ | ✅ |
| `LoadingProgress` | ✅ | ✅ | ✅ |
| `GuardrailWarning` | ✅ | ✅ | ✅ |
| `MailButton` | ✅ | ✅ | ✅ |
| Mapping review surfaces | ✅ | ✅ | ✅ |
| `TrendChart` (not implemented) | — | — | — |
| `MetricCard` (Dashboard) | ✅ | ✅ | ❌ hidden |
| `HistoryList` | ✅ | ✅ | ❌ hidden |
| Left nav rail | ✅ | ❌ collapsed to top bar + hamburger | ❌ collapsed to top bar + hamburger |

**Rules**

- **Mobile (<768px)** is upload + report only. Dashboard, history, trends are hidden. If a user deep-links to `/dashboard` on mobile, redirect to `/` with an info toast: "Dashboard is available on larger screens."
- **Tablet (768–1023px)** keeps every screen but collapses two-column layouts to single column (stacked, content-first).
- **Tables** (data-heavy `@tanstack/react-table` views) always horizontally scroll inside their container below 1024px — never reflow. A controller reading numbers needs the columns to stay aligned, even if it means scrolling.
- **Tap targets** are minimum 44×44px on touch breakpoints. Dropdown and chip components from shadcn meet this by default.
- **Do not hide severity chips, variance colors, or the Verified badge at any breakpoint.** Trust and severity signals are non-negotiable — if the screen is narrow, shrink the label, keep the color.

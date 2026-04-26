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
| Background | `#FAFAF9` | Warm off-white app canvas |
| Surface / Card | `#FFFFFF` | Cards, modals, report body |
| Border | `#E5E4E2` | 1px card and divider borders |
| Text — primary | `#1A1A1A` | Headings, numeric values |
| Text — secondary | `#6B6B6B` | Labels, metadata, hints |
| Accent | `#0D9488` | Primary actions, links, focus ring (Tailwind `teal-600`) |

Purple is avoided (too AI-consumer). Navy is avoided (too corporate ERP). Warm off-white over pure white — less clinical, Mercury-inspired. Accent is teal — trustworthy, non-alarming, and visually separated from all severity hues so CTAs never read as warnings.

**Severity system**

Color carries meaning, not decoration. Severity describes an anomaly's status. Variance direction (favorable/unfavorable/neutral) is a separate axis — green is reserved for *favorable variance only*.

| State | Background | Text/Icon | Use |
|---|---|---|---|
| High (severity) | `#FEE2E2` | `#C53030` | Critical anomaly chip |
| Medium (severity) | `#FEF3C7` | `#B45309` | Needs-attention anomaly chip |
| Normal (severity) | `#F3F4F6` | `#6B7280` | Within-range items — neutral gray, **not green** |
| Favorable variance | `#ECFDF5` | `#166534` | Variance that moved in the right direction (e.g. G&A −34%) |

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
│   Company: [DRONE Inc. ▼]             │
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
│  March 2026 — DRONE Inc.              │
│  2 critical, 1 needs attention        │
├────────────────────────────────────────┤
│                                        │
│  ⚠️ ELECTRICITY EXPENSE      HIGH    │
│  This month $18,400 / Avg. $12,000         │
│  +53% vs last month                  │
│  → Check vendor pricing    │
│                                        │
│  ⚠️ PAYROLL EXPENSE          MEDIUM  │
│  This month $45,000 / Avg. $38,000         │
│  +18% vs last month                  │
│  → Normal if new hires were planned  │
│                                        │
│  ✅ Other 36 items within normal range│
│                                        │
├────────────────────────────────────────┤
│  [Download Report]  [Send Email]       │
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

Email + password. Shown at `/login`. For the hackathon demo the session is pre-warmed (demo user already signed in), but the screen ships for completeness and is the entry point for any first-time sign-in.

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
│   │  │       Sign in          │  │ ← primary, teal #0D9488
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
│   │  ⚠ Email or password is      │ ← inline, #C53030 text
│   │    incorrect. Please try     │    on #FEE2E2 background
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
| Layout | Single centered card, `max-width: 400px`, surface `#FFFFFF` on `#FAFAF9` canvas, 1px `#E5E4E2` border, 24px internal padding |
| Fields | Email (`type="email"`, autocomplete `username`), Password (`type="password"`, autocomplete `current-password`). Both required. |
| Sign in button | Full-width primary. Background `#0D9488` (teal accent). White text. Disabled while request in flight. |
| Disabled / loading state | Button label swaps to "Signing in…" with a spinner. Button background desaturates; fields become read-only. |
| Error message | Inline above the button. Severity = high palette (`#FEE2E2` bg / `#C53030` text). Do NOT use a toast — auth errors are blocking, not transient. |
| Social login | **None for MVP.** |
| Forgot password | **None for MVP.** Add post-hackathon. |
| Sign up | **None on this screen for MVP.** Accounts are provisioned out-of-band for the demo. |
| Demo behavior | The demo environment is pre-logged-in; users will not see this screen during the jury walkthrough. The screen exists for completeness and to round-trip auth for reviewers who log out. |
| Post-login redirect | Success → `/upload` (Home Page — Upload, screen 1). If a `?next=` param is present and points to a same-origin path, honor it. |

---

### 4. Dashboard

Route: `/dashboard` (auth-guarded, inside `AppShell`). Entry from the **Dashboard** item in the SideNav (desktop) or drawer (tablet). Kept deliberately "basit" — no trend charts, no P&L aggregates — because the demo corpus is two months and those visualisations would look absurd at that sample size.

**Scope question this screen answers**
1. What data do I have?
2. What's my latest state?
3. Are there open issues?

```
┌──────────────────────────────────────────────────────────┐
│  Dashboard                                               │
│  DRONE Inc. · Overview of your loaded data and recent    │
│  reports.                                                │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─ Periods loaded ─┐ ┌─ Latest report ─┐ ┌─ Total ─────┐│
│  │       3          │ │  Mar 2026       │ │     3       ││
│  │  months of data  │ │  2 items flagged│ │  across 3   ││
│  └──────────────────┘ └─────────────────┘ │  periods    ││
│                                           └─────────────┘│
│                                                          │
│  Recent reports                                          │
│  ┌──────────────────────────────────────────────────┐    │
│  │ Mar 2026                                        →│    │
│  │ 2 anomalies · Generated Mar 15, 2026             │    │
│  ├──────────────────────────────────────────────────┤    │
│  │ Feb 2026                                        →│    │
│  │ No anomalies · Generated Feb 14, 2026            │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│                              [ ↑ Upload new period ]     │
└──────────────────────────────────────────────────────────┘
```

**Sections**

| Region | Content |
|---|---|
| Header | `<h1>` "Dashboard", company name + tagline in secondary-text below. |
| **Metric strip** | Three `MetricCard` tiles. Each tile: icon + uppercase label + large tabular-numeral value + secondary-text subtext. Never color-coded — severity chips do color; metric tiles are neutral. |
| **Recent reports** | `HistoryList` fed by `GET /reports?limit=12`. One row per verified report: `{formatPeriod}` title + "N anomalies · Generated {date}" subtext + chevron. Click → `/report/:period`. |
| **Action** | Single primary CTA `Upload new period` → `/upload`. Teal `#0D9488`, right-aligned. No competing secondary action — dashboard is a read surface, not a control panel. |

**Metric tiles (MVP — three)**

| Tile | Source | Fallback |
|---|---|---|
| Periods loaded | `GET /companies/me/has-history` → `periods_loaded` | `0` + "—" subtext |
| Latest report | `GET /reports[0]` — formatted period, anomaly-count subtext | "—" + "Upload a file to generate your first report" |
| Total anomalies | Sum of `anomaly_count` across all reports in the `/reports` response | `0` + "—" |

**Empty state (first-time users)**

The Dashboard itself is still reachable with zero reports — it doesn't gate behind `has_history`. The metrics display zeros/em-dashes, and `HistoryList` renders its own empty card ("No reports yet. Upload your first period to see analysis here."). This mirrors the Profile page posture: neutral palette, no red/amber, not an error.

**Responsive behavior** (per §Responsive Breakpoints table)

| Breakpoint | Layout |
|---|---|
| **≥1024px** (desktop) | 3-col `MetricCard` row (`lg:grid-cols-3`). `HistoryList` full-width inside `max-w-5xl` container. |
| **768–1023** (tablet) | 2-col `MetricCard` row (`md:grid-cols-2`) — the third tile wraps to the next line. `HistoryList` unchanged. |
| **<768** (mobile) | **Not rendered.** `AppShell` detects `max-width: 767px` on route change and redirects `/dashboard` → `/upload` with an info toast: "Dashboard is available on larger screens." Dashboard destination UX is desktop-first by explicit spec (line 623). |

**Data freshness**
- `has-history` and `/reports` both use a 30s React Query `staleTime`. Opening the page twice in quick succession hits the cache. The Dashboard is a soft overview; stale-by-30s is fine. Hard refresh on an upload completion is handled elsewhere (UploadPage triggers `queryClient.invalidateQueries(["has-history"])` when a run finishes).

**What this screen is explicitly NOT** (post-MVP)

- **TrendChart** — ≥6 periods required for a meaningful bar chart; demo has 2.
- **Total revenue / COGS / OpEx KPIs** — needs category-aware aggregation of `monthly_entries`; net-new backend work.
- **Date range picker / filters** — dashboard shows everything; filtering happens on a future `/reports` page.
- **Export** — CSV/PDF download is post-MVP.

These remain listed under `Optional (if time permits)` in the Component List so they can return when the TrendChart, MetricCard, HistoryList components are promoted out of post-MVP status.

---

### 4b. Dashboard — post-MVP additions (not in scope for hackathon)
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
│   │  Upload baseline       │           │ ← primary, teal #0D9488
│   └────────────────────────┘           │
│                                        │
│   ─────────────────────────────        │
│                                        │
│   Not sure what to upload?             │
│   → See a sample Excel file            │ ← link, teal
│                                        │
└────────────────────────────────────────┘
```

**Spec**

| Element | Detail |
|---|---|
| Headline | "Let's set up your baseline." Semibold, primary text `#1A1A1A`. |
| Body copy | Two short paragraphs. Secondary text `#6B6B6B`. Explains *why* (comparison requires history) and *what next* (upload one prior month, then the current month next time). |
| Illustration | Muted folder glyph. Do NOT use warning/alert iconography — the empty state is not an error. |
| Period default | Defaults to the previous calendar month relative to today (e.g. today = Apr 2026 → default = `Feb 2026`). User can change via the `PeriodSelector`. |
| Primary CTA | "Upload baseline" — full-width below the dropzone. Teal `#0D9488`. Disabled until a file is selected and a period chosen. |
| Sample file link | Secondary text-link. Downloads a pre-filled Excel template so hesitant first-time users have something concrete to mimic. Optional for MVP if time is tight. |
| Severity / alert colors | **None.** The empty state uses only neutral palette. No red, no amber. Anything hinting at failure would confuse a brand-new user. |
| Dashboard link / nav | Dashboard, history, and reports nav items may be visible but are disabled/dimmed until the baseline upload completes. Hovering shows a tooltip: "Available after your first upload." |
| Trigger | Rendered when the authenticated user's `company_id` has zero rows in `monthly_entries` across all periods. |
| After upload | On successful baseline upload, redirect to a confirmation screen ("Baseline saved. Come back at month-end to run your first close.") — NOT to the full report page, since there is still no comparison to show. |

---

### 7. Mapping Confirm Modal

Triggered mid-parse when the column-mapping step (Claude Haiku) returns a confidence below 80% on one or more columns. **Never show the full column list** — only the flagged ones. Goal is to feel like "the agent needs two taps of help," not "the user has to audit 40 columns."

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
│                   [ Cancel ]   [ Confirm Mapping ] ← primary teal
└──────────────────────────────────────────────────┘
```

**Spec**

| Element | Detail |
|---|---|
| Trigger | Any column mapped with confidence < 80%. Columns ≥ 80% are accepted silently and never shown here. |
| Maximum rows shown at once | **3.** If more than 3 columns are below threshold, show the 3 lowest-confidence first. The remainder are mapped to `OTHER` and surfaced post-run as a non-blocking review item (out of scope for MVP if it slips). |
| Row layout | Card per column. Fields: `column name` (from the uploaded file, verbatim), `agent's guess` (mapped category), `confidence %` (secondary text), `Map to` dropdown (US GAAP categories from `account_categories`), `Skip this column` link (skipped columns are not loaded into `monthly_entries`). |
| Dropdown options | `REVENUE`, `COGS`, `OPEX`, `G&A`, `R&D`, `OTHER_INCOME`, `OTHER`, `SKIP`. Default = agent's guess. **OTHER** is a real seeded `account_categories` row (id=7) — selecting it writes the column to the import as the OTHER bucket. **SKIP** is a frontend-only sentinel — selecting it removes the column from the persisted mapping; the column is **never written to `accounts` or `monthly_entries`**. The backend `POST /runs/{run_id}/mapping/confirm` handler accepts `SKIP` in the request body and treats it as a delete-by-omission. |
| Confidence display | Plain percentage, secondary text color `#6B6B6B`. No progress bar — keeps the density Notion-like. |
| Primary CTA | **Confirm Mapping** — teal `#0D9488`, right-aligned in footer. Disabled until every flagged row has either an approved dropdown choice or an explicit Skip. |
| Secondary CTA | **Cancel** — text button, left of the primary. Cancels the current run; the uploaded file stays in Supabase Storage for retry. |
| Close ("×") behavior | Same as Cancel. |
| Accessibility | Focus trapped inside modal. `Esc` = Cancel. Tab order: rows top-to-bottom, then footer. |
| Persistence | Confirmed mappings are persisted to `accounts` for this `company_id` so the same column header from the same source file will auto-map next month without re-prompting. |

---

### 8. Profile Page

Read-only account surface. Not a "settings" screen — no editable fields in MVP. Destination for the user footer click in the `AppShell` (both desktop sidebar and mobile drawer). Pure consumer of existing endpoints (`GET /companies/me`, `GET /companies/me/has-history`) plus the Supabase Auth session — **no new backend work**.

**Route:** `/profile` (auth-guarded, inside `AppShell`).

**Entry point:** clicking the company-name / email block at the bottom of the `AppShell` sidebar (desktop) or drawer (mobile). The block gets a `bg-canvas` hover state and a focus ring; active-route highlight uses the same `bg-canvas` background while on `/profile`. The separate Sign out button below remains independent — a dedicated action, not a nav target.

```
┌──────────────────────────────────────────────────┐
│  Your account                         [ 👤 ]     │
│  Read-only for MVP. Edit controls ship post-     │
│  hackathon.                                      │
├──────────────────────────────────────────────────┤
│                                                  │
│  ┌─ ✉ Account ───────────────────────────────┐   │
│  │  Email         demo@dronedemo.com         │   │
│  │  User ID       8ab2…f9e1  (monospace)     │   │
│  └───────────────────────────────────────────┘   │
│                                                  │
│  ┌─ 🏢 Company ──────────────────────────────┐   │
│  │  Name          DRONE Inc.                 │   │
│  │  Sector        Industrial                 │   │
│  │  Currency      USD                        │   │
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
| Page width | Single column, `max-width: 640px`, centered. Same constraint across desktop / tablet / mobile — the card-stack layout doesn't benefit from wider columns. |
| Padding | `px-4` always; `py-6` mobile, `py-8` md+. |
| Card radius / border | `rounded-lg` + `border border-border` (#E5E4E2) on `bg-surface`. Matches ReportSummary + AnomalyCard. |
| Section header | Icon (lucide, `h-4 w-4`, `text-text-secondary`) + section label (14px, semibold, `text-text-primary`). Bottom border divides header from `<dl>`. |
| Key/value row | `<dt>` left (14px, `text-text-secondary`), `<dd>` right (14px, `text-text-primary`). Dividers between rows via `divide-y divide-border`. Numeric values carry `tabular-nums` + `data-numeric`. |
| Baseline chip | `favorable` palette if `has_history === true` ("Active"). `severity.normal` palette if false ("Not set up"). Never red — this is not a warning state. |
| Sign out button | Full-width, bordered, non-accent (sign-out is a neutral action, not primary). Accent teal is reserved for primary CTAs like Analyze / Send / Confirm. `min-h-[44px]` on touch, `min-h-[40px]` on `lg`. |

**Fields displayed (MVP read-only)**

| Section | Field | Source | Notes |
|---|---|---|---|
| Account | Email | `useAuth().user.email` (Supabase session) | Read-only. |
| Account | User ID | `useAuth().user.id` | Monospace, truncated. Useful for support/debug. |
| Company | Name | `GET /companies/me` → `name` | |
| Company | Sector | `GET /companies/me` → `sector` | `—` when null. |
| Company | Currency | `GET /companies/me` → `currency` | Tabular numerals in case of non-USD codes. |
| Usage | Periods loaded | `GET /companies/me/has-history` → `periods_loaded` | |
| Usage | Baseline status | `GET /companies/me/has-history` → `has_history` | Chip: favorable / normal. |

**Actions (MVP)**

| Action | Behavior |
|---|---|
| Sign out | Calls `supabase.auth.signOut()`, navigates to `/login`. Redundant with the sidebar/drawer Sign out button — kept here because users expect it on an account page. |

**Explicitly NOT in MVP** (post-hackathon):
- Change password (via `supabase.auth.updateUser`)
- Edit company name / sector / currency
- Delete account
- Team members / role management
- Billing / subscription
- API keys / integrations
- 2FA settings

Any of these would require new backend endpoints and auth flows that are out of hackathon scope. The MVP profile page is deliberately a consumer-only view — it proves the nav destination works without opening a write surface.

**Responsive behavior**

| Breakpoint | Behavior |
|---|---|
| ≥1024px | Profile renders right of the fixed SideNav; content column capped at 640px. |
| 768–1023px | No sidebar; content takes full width under the top bar, still capped at 640px. |
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
- `CompanySelector` — company selection
- `LoadingProgress` — 4-step progress bar
- `AnomalyCard` — single anomaly card.
  - **API:** `{ value: number, direction: 'favorable' | 'unfavorable' | 'neutral', severity: 'high' | 'medium' | 'normal', ... }`. Direction drives color (favorable = green chip `#ECFDF5/#166534`; unfavorable = severity red/amber; neutral = gray). Severity drives the chip label. Do NOT color by sign of `value` — a negative variance can be favorable (e.g. G&A −34%) or unfavorable (e.g. revenue −12%) depending on direction.
  - **Provenance:** every figure rendered inside the card is hoverable. The hover/popover shows the source filename and original column name, e.g. `drone_mar_2026.xlsx — column 'Amount'`. This surfaces the guardrail story to the user — each number is traceable back to the file it came from.
- `ReportSummary` — plain-language summary.
  - **Verified badge:** renders the "Verified · Guardrail Passed" badge (checkmark icon + teal accent) next to the period header whenever the report was produced by a run whose guardrail passed. Never render this badge on raw/unverified downloads.
  - **Provenance:** every number in the narrative prose is hoverable. Hover reveals source filename and original column name (e.g. `drone_mar_2026.xlsx — column 'Amount'`). Numbers are visibly distinguishable from surrounding prose (tabular numerals + subtle underline on hover) so the user learns they are inspectable.
- `MailButton` — send email
- `GuardrailWarning` — shown when numeric validation fails after retry, offers retry/download raw options
- `MappingConfirmModal` — shown when column mapping confidence is below 80%, lists only the flagged columns for user confirmation
- `AppShell` — two-column responsive shell (fixed left `SideNav` ≥1024px / top bar + hamburger-drawer below). Houses the main nav and the clickable user footer that navigates to `/profile`. Per `§Responsive Breakpoints`.
- `ProfilePage` — read-only account view at `/profile` per §8 above. Surfaces Supabase Auth email + user ID, `GET /companies/me` fields, and `GET /companies/me/has-history` usage stats. Sign-out action. No editable fields in MVP.

### Optional (if time permits)
- `TrendChart` — monthly bar chart
- `MetricCard` — revenue/expenses/net summary
- `HistoryList` — past reports

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
Report summary + anomaly list. Also include full report link.

**Guardrail failure:**
If the numeric guardrail fails, the system retries once automatically. If the second attempt also fails, show the GuardrailWarning screen. Never show an unverified report as if it were verified. The raw pandas data can be offered as a download so the user is never left empty-handed.

**Column mapping confirmation:**
Columns mapped with 80%+ confidence are accepted silently. Only columns below 80% confidence are shown to the user in the MappingConfirmModal. The modal shows: column name, what the agent thinks it is, and a simple approve/reassign dropdown. Goal: user sees at most 2-3 flagged columns, never the full list.

---

## Number Formatting Standards

US accounting conventions. Apply everywhere — tables, cards, narrative, exported reports, email bodies.

| Rule | Value |
|---|---|
| Currency | USD only |
| Thousands separator | comma (`1,234,567`) |
| Decimal separator | period (`1,234.56`) |
| Decimal places — tables | 2 (`$45,000.00`) |
| Decimal places — narrative | abbreviated (`$4.73M`, `$128K`) |
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
| success | `#ECFDF5` | `#166534` ✓ check | auto after **4s**; also dismissible manually | "Report emailed to cfo@drone.com." |
| error | `#FEE2E2` | `#C53030` ⚠ alert | **manual dismiss only** — no auto-timeout | "Network error — couldn't send email. Please try again." |
| warning | `#FEF3C7` | `#B45309` ⚠ alert | auto after **6s**; dismissible manually | "You're sending a lot of requests — please wait a moment." (429 rate limit) |
| info | `#F3F4F6` | `#6B7280` ⓘ info | auto after **4s**; dismissible manually | "Your baseline has been saved." |

**When to use each**

| Event | Type |
|---|---|
| Mail sent (Resend success) | success |
| Report generated & verified (if user was on a different screen) | success |
| Rate limit hit (HTTP 429) | warning |
| Network error / unreachable API | error |
| File rejected client-side (wrong type, too large) | error |
| Transient Supabase/Resend 5xx | error |
| Non-blocking informational ("We saved your draft") | info |
| **Guardrail failure** | **NOT a toast** — inline on the GuardrailWarning screen |
| **Auth error (wrong password)** | **NOT a toast** — inline on the Login screen |
| **Column mapping confidence low** | **NOT a toast** — opens the MappingConfirmModal |

**Wireframe**

```
                                   top-right of viewport
                                                   │
                                                   ▼
                       ┌─────────────────────────────────┐
                       │ ✓  Report emailed to            │
                       │    cfo@drone.com.       [ × ]   │  ← success, auto 4s
                       └─────────────────────────────────┘
                       ┌─────────────────────────────────┐
                       │ ⚠  Network error — couldn't     │
                       │    send email. Please try       │
                       │    again.               [ × ]   │  ← error, manual
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
| Idle / default | Dashed 1px border `#E5E4E2`, surface `#FFFFFF`, copy "Drop your files here or click to select. Excel · CSV". | Baseline state. |
| Dragging (file over zone) | Border becomes solid teal `#0D9488` 2px, background tints `#ECFDF5` faintly, copy swaps to "Release to upload". | Triggered by `dragenter`/`dragover`. Revert on `dragleave`. |
| Uploading | Border returns to `#E5E4E2`. Inline linear progress bar in teal under the dropzone. Filename list visible with per-file spinner. Dropzone is disabled during upload. | No toast — progress is local to the component. |
| Wrong file type (client-side reject) | **Inline** message under dropzone: red text `#C53030` on `#FEE2E2` background, 8px padding. Copy: `` `report.pdf` is not a supported format — upload an Excel or CSV file. `` Also emit an error toast if the rejection happens via the hidden file input (out-of-view drop). Rejected file is NOT added to the pending list. | Accepted extensions: `.xlsx`, `.csv`, `.xls`, `.xlsm`. |
| File too large (client-side reject) | Same inline pattern. Copy: `` `huge_export.xlsx` is larger than 10 MB — please split the file. `` | 10 MB per-file cap. |
| Server-side upload failure | Error toast: "We couldn't upload `filename.xlsx`. Please try again." Dropzone returns to idle. | Retry button inside the toast (or re-drop). |

### `AnomalyCard`

| State | Visual | Notes |
|---|---|---|
| Loaded (default) | Chip with severity color (high/medium/normal) + text label; value with tabular numerals; variance % with favorable/unfavorable/neutral direction color; provenance underline on hover. | See Component List for API. |
| Loading skeleton | Card shell rendered at correct height with shimmer placeholders for chip, number, label. Uses `#F3F4F6` base and `#E5E4E2` highlight. No icons, no text. | Prevents layout shift when data arrives. |
| Empty — no anomalies in category | **Not a card — a summary row.** Copy: "✅ All 36 items within normal range." Neutral palette, no severity color. Collapsed by default with a text-link "Show details" to expand. | Avoids printing 36 "normal" cards which would drown the real anomalies. |
| Report has zero anomalies total | Full-card placeholder: teal check icon, headline "No anomalies this period." Secondary copy: "Every account is within expected range vs. your history." | Rare but should look celebratory, not empty. |

### `ReportSummary`

| State | Visual | Notes |
|---|---|---|
| Generating | Header shows period + "Generating verified report…" with a teal spinner in place of the Verified badge. Body is replaced by skeleton paragraphs (two 90%-width shimmer bars, one 70%, one 50%). | Shown while interpreter + guardrail are running. |
| Guardrail failed | ReportSummary is **not rendered.** The GuardrailWarning screen (3b) replaces it. Do not render a partial or muted ReportSummary that could be mistaken for a verified one. | Hard rule: no unverified prose ever appears in this component. |
| Verified | Full narrative renders. "Verified · Guardrail Passed" badge next to the period header — checkmark icon + teal accent `#0D9488`. Every number is hoverable (provenance popover). | This is the only state where the Verified badge renders. |
| Stale (report exists but source file re-uploaded since) | Verified badge replaced by an amber "Out of date" chip (`#FEF3C7/#B45309`). Copy above body: "This report was generated before you re-uploaded the source file. [Regenerate report]." | Prevents the user from emailing a stale verified report. |

### `LoadingProgress`

Four sequential steps, each with a label and an integer % (0–100). One step active at a time; previous steps show ✓; future steps are dimmed. Parent polls the `/runs/{run_id}` endpoint to drive updates.

```
┌────────────────────────────────────────┐
│  ✓ Reading files                 100%  │ ← complete
│  ● Mapping accounts               62%  │ ← active, teal progress
│  ○ Comparing to history            0%  │ ← pending, dimmed
│  ○ Generating report               0%  │ ← pending, dimmed
└────────────────────────────────────────┘
```

| Step | Label | Backend signal | Notes |
|---|---|---|---|
| 1 | Reading files | Parser: file read + PII sanitize + pandera validate complete | `%` = rows processed ÷ total rows |
| 2 | Mapping accounts | Parser: Haiku mapping done + `monthly_entries` written | `%` = columns mapped ÷ total columns |
| 3 | Comparing to history | Comparison agent running | `%` = accounts compared ÷ total accounts |
| 4 | Generating report | Interpreter + guardrail running | `%` hits 100 only after guardrail passes. On guardrail fail, switch to GuardrailWarning screen. |

Completed steps use ✓ icon in `#166534`. Active step uses a filled circle ● in teal `#0D9488` with a linear progress bar under the label. Pending steps use an empty circle ○ in `#6B6B6B`.

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
| Dashboard (screen 4) | Two-column: Summary + Trend | Single column, stacked | **Hidden — not a supported mobile screen** |
| Report page (screen 3) | Single column, max-width 960px centered | Same, fluid width | Same, fluid width |
| AnomalyCard grid | 2 columns on 1280px+, 1 column below | 1 column | 1 column |
| LoadingProgress | Inline, 480px wide | Full width, 32px gutters | Full width, 16px gutters |
| MappingConfirmModal | Centered, 560px wide | Centered, 90vw | Full-screen sheet, slide-up from bottom |
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
| `MappingConfirmModal` | ✅ | ✅ | ✅ (as full-screen sheet) |
| `TrendChart` (Dashboard) | ✅ | ✅ | ❌ hidden |
| `MetricCard` (Dashboard) | ✅ | ✅ | ❌ hidden |
| `HistoryList` | ✅ | ✅ | ❌ hidden |
| Left nav rail | ✅ | ❌ collapsed to top bar + hamburger | ❌ collapsed to top bar + hamburger |

**Rules**

- **Mobile (<768px)** is upload + report only. Dashboard, history, trends are hidden. If a user deep-links to `/dashboard` on mobile, redirect to `/` with an info toast: "Dashboard is available on larger screens."
- **Tablet (768–1023px)** keeps every screen but collapses two-column layouts to single column (stacked, content-first).
- **Tables** (data-heavy `@tanstack/react-table` views) always horizontally scroll inside their container below 1024px — never reflow. A controller reading numbers needs the columns to stay aligned, even if it means scrolling.
- **Tap targets** are minimum 44×44px on touch breakpoints. Dropdown and chip components from shadcn meet this by default.
- **Do not hide severity chips, variance colors, or the Verified badge at any breakpoint.** Trust and severity signals are non-negotiable — if the screen is narrow, shrink the label, keep the color.

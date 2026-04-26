# Landing + Register Plan

Planning document. Nothing is built yet. Wait for approval before implementation.

Palette and type are locked to the existing system: teal `#0D9488` accent, off-white `#FAFAF9` canvas, `#FFFFFF` surface, `#E5E4E2` border, primary text `#1A1A1A`, secondary `#6B6B6B`, Inter sans. The landing page is an *editorial* treatment of this same palette — serif body type for the long-form sections to set it apart from the app, but tokens and accent colors stay identical so the handoff from landing → register feels like one product, not two.

---

## 1. Landing Page Plan (`landing.html`)

### File placement
Static file at `frontend/public/landing.html`. Served directly by Vite. Uses Tailwind via the Play CDN with a small inline `tailwind.config` that mirrors the tokens from `frontend/tailwind.config.js` (so `bg-canvas`, `bg-accent`, `text-text-primary` behave identically to the React app). This avoids touching the Vite build and lets the page ship without any route changes.

Type: Inter for UI chrome (nav, button), serif for body — load one editorial serif from Google Fonts. Recommended: **Source Serif 4** (free, broad weights, reads like a financial memo). Fallback stack `Georgia, serif`.

### Global page shell
- `<body class="bg-canvas text-text-primary font-serif antialiased">` — serif is the DEFAULT on this page; Inter overrides only on nav + CTA button.
- Single column, max width `max-w-[680px]` centered (`mx-auto px-6`) — memo column width, not dashboard width.
- A thin top bar: small Month Proof wordmark left (Inter, `font-semibold`), no nav links, no "Log in" button in the top-right (keeps the page feeling like a document, not a marketing funnel — the only CTA is Section 4). Optional: subtle "Sign in →" link in small secondary-text type top-right only for returning users.
- Section numbers in the left margin (`§1`, `§2`, `§3`, `§4`, `§5`) in `text-text-secondary` monospace — this is the visual signature that makes a juror say "oh this is different" in 5 seconds.

---

### §1 — The Cold Open

**Purpose.** Drop the reader into a specific 11:47 PM month-end scene in concrete dollars before the product is named or pitched. No claim has been made yet, so there is nothing to disbelieve. Trust is built before the sell begins.

**Copy direction.**
- No hero image. No dashboard screenshot.
- Wordmark "Month Proof" at the very top in small Inter weight, then a thin divider rule.
- One editorial paragraph, ~60–80 words, written in second person ("You're still in the spreadsheet. Travel is up $38K. You can't tell if it's the Denver offsite or a miscoded Amex batch...").
- Closes with the headline, pulled from Hook A: *"It's 11:47 PM. One number moved. You're the only one who's noticed."* Set large, serif, left-aligned, not centered.
- One sub-line under the headline in `text-text-secondary`: *"Month Proof is a month-end close agent for US finance teams. This page explains how it works before it asks you to trust it."*

**Visual / layout.**
- Massive top padding (`pt-32`) — the page should feel like a memo, not a landing.
- Headline sits around the visual fold, so the editorial paragraph is what the eye reads first.
- No buttons in this section. None.

**Rough HTML / Tailwind.**
- `<header class="max-w-[680px] mx-auto px-6 pt-10 pb-6 flex items-center justify-between">` — wordmark left, small `Sign in` link right (`text-sm text-text-secondary hover:text-text-primary`).
- `<section class="max-w-[680px] mx-auto px-6 pt-20 pb-24">`
  - `<p class="font-mono text-xs text-text-secondary mb-6">§1</p>`
  - `<p class="text-lg leading-relaxed text-text-primary mb-10">...scene paragraph...</p>`
  - `<h1 class="text-4xl md:text-5xl font-semibold leading-tight tracking-tight text-text-primary">It's 11:47 PM...</h1>`
  - `<p class="text-base text-text-secondary mt-4 max-w-[560px]">...sub-line...</p>`

---

### §2 — The Single Anomaly Card (simplified per decision)

**Purpose.** Show *one* concrete thing the product produces, using the DRONE Inc. demo data. Replaces the full annotated-document idea. One card the reader can inspect in 10 seconds is more persuasive than a flashy demo they half-watch.

**Copy direction.**
- A single short intro line above the card: *"Here's what Month Proof flagged in DRONE Inc.'s March close."*
- The card contains, in order:
  - Severity pill: **HIGH** (uses `severity-high-bg` / `severity-high-fg` from the existing token set — visual continuity with the actual app).
  - Account name: **Travel & Entertainment**
  - Variance line: **+$38,420 (+61%)** vs. February — monospace, large.
  - A two-sentence plain-English explanation in the CFO-assistant voice (the kind of thing the Interpreter agent actually produces): e.g. *"Travel spending nearly doubled against the 6-month baseline of $24K/month. The increase concentrates in the final week of March — consistent with an offsite, not a steady-state change."*
  - A tiny footer row: `Verified against source · Guardrail passed ✓` — the `✓` is the ONE teal element in this section. This is where the reader first learns that the teal mark means "checked."
- Below the card, one paragraph of prose (~40 words): *"No screenshots of dashboards on this page. This is the actual shape of what Month Proof writes after it reads your file — one card per flagged account, one paragraph per anomaly, every number traceable to a cell."*

**Visual / layout.**
- Card is the only "boxed" element on the landing page. Everything else is flowing text. This creates emphasis purely through contrast — no decoration needed.
- Card style mirrors the app's `AnomalyCard` look: `bg-surface border border-border rounded-lg p-6 shadow-sm` (same classes as the login card — intentional visual echo).
- Variance number set in `font-mono` — the rest of the card is serif body + Inter for chrome (severity pill).

**Rough HTML / Tailwind.**
- `<section class="max-w-[680px] mx-auto px-6 py-20">`
  - `<p class="font-mono text-xs text-text-secondary mb-6">§2</p>`
  - `<p class="text-lg text-text-primary mb-8">Here's what Month Proof flagged...</p>`
  - `<article class="bg-surface border border-border rounded-lg p-6 shadow-sm">`
    - `<span class="inline-block rounded-md bg-severity-high-bg text-severity-high-fg text-xs font-semibold uppercase tracking-wide px-2 py-0.5 font-sans">HIGH</span>`
    - `<h3 class="text-xl font-semibold mt-3 font-sans">Travel &amp; Entertainment</h3>`
    - `<p class="font-mono text-2xl text-text-primary mt-2">+$38,420 <span class="text-text-secondary text-base">(+61%)</span></p>`
    - `<p class="text-base text-text-primary mt-4 leading-relaxed">...explanation...</p>`
    - `<p class="text-xs text-text-secondary mt-6 flex items-center gap-1.5 font-sans">Verified against source · Guardrail passed <span class="text-accent font-semibold">✓</span></p>`
  - `</article>`
  - `<p class="text-base text-text-secondary mt-8 leading-relaxed">...the "no screenshots" paragraph...</p>`

---

### §3 — "How We Know the Numbers Are Right"

**Purpose.** The Golden Rule, in plain English. This is the paragraph a CFO will screenshot and forward to their team. It converts "AI-powered" from a warning sign into a defensible claim.

**Copy direction.**
- Section heading, serif, slightly smaller than §1: *"How we know the numbers are right."*
- Three short prose paragraphs (not bullet points — paragraphs read as considered, bullets read as marketing):
  1. *"Every number in the report is calculated in Python. Not by the model. Totals, variances, anomaly thresholds — all pandas, all deterministic, all reproducible from your source file."*
  2. *"The model only writes the sentences around those numbers. Its job is to interpret, not to compute. Before any report is saved, a numeric guardrail compares every figure the model used against the pandas output. If they disagree by more than 2%, the report is rejected and rewritten."*
  3. *"That's it. No benchmarks. No accuracy percentage. Just a rule that is either satisfied or the report does not leave the system."*
- A small inline callout underneath — not a card, just offset type — showing a real rejected example:
  > *"Rejected draft · The report said '$4.8M revenue' — pandas had $4,730,000. Difference 1.46%, within tolerance. Accepted on second pass."*
  > *"Rejected draft · The report said '$5.1M revenue' — pandas had $4,730,000. Difference 7.8%, outside tolerance. Rewritten with the correct figure."*
- Teal `✓` reappears here beside the accepted line, teal nowhere else.

**Visual / layout.**
- Pure prose. No icons, no graphic.
- The rejected/accepted examples set in `font-mono text-sm` with a left border (`border-l-2 border-border pl-4`) — looks like a blockquote in a legal memo.

**Rough HTML / Tailwind.**
- `<section class="max-w-[680px] mx-auto px-6 py-20">`
  - `<p class="font-mono text-xs text-text-secondary mb-6">§3</p>`
  - `<h2 class="text-3xl font-semibold leading-tight text-text-primary mb-8">How we know the numbers are right.</h2>`
  - Three `<p class="text-lg leading-relaxed text-text-primary mb-5">` paragraphs.
  - `<div class="border-l-2 border-border pl-4 mt-10 space-y-3 font-mono text-sm text-text-secondary">...rejected/accepted...</div>`

---

### §4 — Try It On A Real Month (CTA — simplified per decision)

**Purpose.** One action. One button. Respect the reader's time.

**Copy direction.**
- Short heading: *"Try it on a real month."*
- One sentence: *"Create an account and upload last month's trial balance. You'll see the first draft of the close report in under two minutes."*
- Primary button: **"Get Started"** → links to `/register`.
- No secondary button. No email field. No demo upload for unauthenticated users. No "Watch a demo" link.
- Below the button, in small secondary-text, one honest reassurance: *"Your files stay private. We never train on customer data."*

**Visual / layout.**
- Generous vertical breathing room above and below (`py-24` or more).
- Button is the ONE large teal element on the whole page. Because teal has been reserved for the guardrail `✓` checkmarks up to this point, the eye already associates teal with "verified" — so the CTA inherits that association without a word.
- Button uses Inter (matches the app's button), not serif.
- Centered text alignment in this section only — everything else on the page is left-aligned. The alignment shift signals "this is the moment of decision."

**Rough HTML / Tailwind.**
- `<section class="max-w-[680px] mx-auto px-6 py-24 text-center">`
  - `<p class="font-mono text-xs text-text-secondary mb-6">§4</p>`
  - `<h2 class="text-3xl font-semibold leading-tight text-text-primary mb-4">Try it on a real month.</h2>`
  - `<p class="text-lg text-text-secondary max-w-[480px] mx-auto mb-10 leading-relaxed">Create an account...</p>`
  - `<a href="/register" class="inline-block rounded-md bg-accent text-white px-8 py-3 text-base font-medium font-sans hover:opacity-95 transition-opacity">Get Started</a>`
  - `<p class="text-sm text-text-secondary mt-6">Your files stay private. We never train on customer data.</p>`

---

### §5 — The Memo: "What We Won't Do"

**Purpose.** Inverts the standard SaaS promise. A signed, dated memo of explicit non-goals. Earns trust by admitting limits — the single most disarming posture for a skeptical finance audience.

**Copy direction.**
- Format as a real memo: `TO:` / `FROM:` / `RE:` / `DATE:` header in monospace, then a numbered list of non-goals in prose, then signed names.
- Header:
  - `TO: Finance directors evaluating Month Proof`
  - `FROM: The Month Proof team`
  - `RE: What this tool will not do`
  - `DATE: April 2026`
- Body paragraphs (numbered, one short paragraph each — not bullets):
  1. *"We do not do arithmetic. Every number in every report comes from pandas operating on your source file. The model writes sentences; it does not calculate totals."*
  2. *"We do not train on your data. Your files are not used to improve any model, ours or a vendor's."*
  3. *"We do not replace your judgment. Month Proof produces a first draft of the close narrative. The decision of what to send — and what to change — is yours."*
  4. *"We do not claim to close your books. We claim to get you to a defensible first draft faster than rewriting last month's commentary by hand."*
- Closing line: *"If any of the above stops being true, this page will be updated the same day."*
- Signed — real first names + role (e.g. *"— Jan, Founder"*). For a hackathon a single signature is fine.

**Visual / layout.**
- Memo header in `font-mono text-sm text-text-secondary`, aligned left with a `uppercase tracking-wider` treatment on the labels.
- The numbered non-goals in serif body.
- A thin rule (`border-t border-border`) above this section separates it from the CTA — this is the afterword, not the pitch.

**Rough HTML / Tailwind.**
- `<section class="max-w-[680px] mx-auto px-6 py-20 border-t border-border">`
  - `<p class="font-mono text-xs text-text-secondary mb-6">§5</p>`
  - `<div class="font-mono text-sm text-text-secondary mb-8 space-y-1">`
    - 4 lines with `<span class="uppercase tracking-wider">TO:</span> ...`
  - `</div>`
  - `<ol class="space-y-6 text-lg leading-relaxed text-text-primary list-decimal list-outside pl-6">` — each `<li>` is one short paragraph.
  - `<p class="text-base text-text-primary mt-10">If any of the above stops being true...</p>`
  - `<p class="text-base font-mono text-text-secondary mt-8">— Jan, Founder</p>`
- Page footer below: tiny copyright in `text-xs text-text-secondary` — no nav, no social links, no newsletter signup.

---

## 2. Register Page Plan (`/register`)

### File
`frontend/src/pages/RegisterPage.tsx` — default export `RegisterPage`.

### Design parity with LoginPage
The component must mirror `LoginPage.tsx` exactly at the structural level. That means:
- Same outer wrapper: `<div className="min-h-screen flex items-center justify-center bg-canvas px-4">`.
- Same inner width: `<div className="w-full max-w-[400px]">`.
- Same masthead block: centered `Month Proof` h1 (`text-2xl font-semibold text-text-primary`), same sub-line (`Month-end close, verified.`).
- Same card shell: `<form className="bg-surface border border-border rounded-lg p-6 shadow-sm">`.
- Same field component pattern: label in `text-sm font-medium text-text-primary mb-1.5`, input in the full class string already used on LoginPage's email input (including `read-only:opacity-60` during loading).
- Same inline error container: `role="alert" className="rounded-md bg-severity-high-bg px-3 py-2 text-sm text-severity-high-fg"`. Never toast.
- Same submit button: `w-full rounded-md bg-accent text-white py-2 px-4 text-sm font-medium` with identical disabled + spinner behavior.
- Add a "Already have an account? Sign in →" link underneath the form, same styling as the link LoginPage will gain in part 3 — symmetric.

### Fields (in order)
1. **Full name** — `type="text"`, `autoComplete="name"`, `required`, placeholder `"Jane Doe"`.
2. **Email** — `type="email"`, `autoComplete="email"`, `required`, placeholder `"you@company.com"`.
3. **Password** — `type="password"`, `autoComplete="new-password"`, `required`, placeholder `"••••••••••"`, minLength enforced in state validation (see below).
4. **Confirm password** — `type="password"`, `autoComplete="new-password"`, `required`, placeholder `"••••••••••"`.

### State and validation
- Local `useState` for each of the four fields + `loading` + `error: string | null`, matching LoginPage.
- `disabled = loading || !name || !email || !password || !confirm`.
- Client-side validation happens in `handleSubmit` before the Supabase call, in this order:
  1. Password length < 8 → inline error `"Password must be at least 8 characters."`
  2. Password !== confirm → inline error `"Passwords don't match."`
  3. Otherwise clear error and proceed.
- Validation errors set `error` state and return. They do NOT go to toast, matching the login pattern.

### Auth call
- Add a `signUp(email, password, fullName)` helper to `frontend/src/lib/auth.ts` that calls `supabase.auth.signUp({ email, password, options: { data: { full_name: fullName } } })`. The full name lands in `user_metadata.full_name` for later use by the profile page; no new table required.
- On success: `navigate("/upload", { replace: true })` (matches LoginPage's post-auth redirect — the `?next=` honoring is login-only).
- On error: catch, set inline error. Use `CLIENT_MESSAGES.AUTH_FAILED` for generic failures. Add one new message to `frontend/src/lib/messages.ts`:
  ```
  EMAIL_ALREADY_REGISTERED: "An account with this email already exists. Sign in instead."
  ```
  Map Supabase's `user_already_registered` error code to this string; fall back to `AUTH_FAILED` otherwise. No other error codes are surfaced (avoids account-enumeration leaks, same policy as LoginPage).

### Masthead variant
Change the sub-line for the register page from `"Month-end close, verified."` to `"Create your account."` — tiny difference, signals context without changing the visual hierarchy.

### Link to login
Below the submit button, inside the card, after a `mt-4 text-center text-sm text-text-secondary` wrapper:
`Already have an account? <a href="/login" class="text-accent hover:underline">Sign in →</a>`
Use `react-router-dom` `<Link to="/login">` instead of a raw `<a>`.

### Router wiring (`App.tsx`)
- Import: `import RegisterPage from "./pages/RegisterPage";`
- Add route, placed directly below the `/login` route, outside any `ProtectedRoute` wrapper:
  ```
  <Route path="/register" element={<RegisterPage />} />
  ```
- Catch-all `<Route path="*" element={<Navigate to="/upload" replace />} />` stays as-is.

### Accessibility notes
- Each input has a matching `<label htmlFor>` — same pattern as LoginPage.
- Error container uses `role="alert"` so screen readers announce it.
- Submit button uses the exact same loading spinner markup LoginPage uses (`border-2 border-white/70 border-t-transparent rounded-full animate-spin`), so the visual language is identical.

---

## 3. Login Page Modification Plan

Single, minimal change to `frontend/src/pages/LoginPage.tsx`.

### What to add
A "Don't have an account? Sign up →" link, placed **inside the form**, immediately after the closing `</button>` of the Sign in button, still inside the `<div className="space-y-4">` wrapper. This keeps it inside the card so the visual grouping stays intact.

### Exact insertion
After the current line 121 (`</button>`), add one `<p>` block:

```tsx
<p className="text-center text-sm text-text-secondary">
  Don't have an account?{" "}
  <Link to="/register" className="text-accent hover:underline">
    Sign up →
  </Link>
</p>
```

### Import change
Add `Link` to the existing react-router-dom import at line 2:

```tsx
import { Link, useNavigate, useSearchParams } from "react-router-dom";
```

### What NOT to change
- The masthead text, the page wrapper, the card classes, the AUTH_FAILED error behavior, the `?next=` redirect logic, the anti-enumeration error copy. All stay identical. This is a one-line addition, not a refactor.

---

## 4. Implementation Order

1. **Build `/register` page first.** The landing page's only CTA points to `/register`, so `/register` must exist and work end-to-end before the landing page is shipped — otherwise the primary button leads to a dead route. Includes: `RegisterPage.tsx`, `signUp` helper in `lib/auth.ts`, `EMAIL_ALREADY_REGISTERED` in `lib/messages.ts`, and the new `<Route>` in `App.tsx`.

2. **Modify `/login` second.** Tiny addition (the "Sign up →" link). Done right after register so the two auth pages have symmetric cross-links — once register exists, this link has somewhere real to go. Low risk, five-minute change.

3. **Build `landing.html` last.** This is the largest surface-area piece and has zero blockers outside itself once `/register` is live. Ship the static file at `frontend/public/landing.html`, verify each section renders at `http://localhost:5173/landing.html`, confirm the Get Started button lands on the working register form, then confirm the full loop: landing → register → upload. No React or Vite config changes needed.

# IronLedger — Onboarding Revision Plan

**Status:** Planning only — no code has been written.  
**Scope:** Registration flow, login flow, onboarding route, company creation endpoint.

---

## 1. Core Design Decisions

These decisions drive every specific change below.

**Decision 1 — `onboarding_done` lives in Supabase user metadata, not a DB column.**  
No migration is needed. Supabase user metadata is JSONB (`auth.users.raw_user_meta_data`), merged on every `supabase.auth.updateUser()` call. Reading it is free — it comes with every `getSession()` response. Writing it costs one Supabase Auth API call.

**Decision 2 — The flag is checked exactly once: at login time.**  
No component in the protected app ever queries for the flag. `ProtectedRoute` loses its company-check logic entirely. This eliminates the "extra query on every page navigation" problem.

**Decision 3 — Registration always goes to `/onboarding`.**  
New users never need a flag check. `RegisterPage` hard-codes the destination. Existing users who log in are the ones that need the flag check.

**Decision 4 — "Skip" on the walkthrough skips the slides, not the form.**  
The three-step walkthrough (HowItWorks) has a Skip link that jumps directly to the company setup form. There is no way to skip the form — the user must complete it. `onboarding_done: true` is written only on successful form submission.

**Decision 5 — `POST /companies` is idempotent.**  
If a company already exists for the user (e.g., they submitted the form, the `updateUser` call failed, and they returned to onboarding), the endpoint returns the existing company rather than creating a duplicate. No DB-level `ON CONFLICT` is needed because the service-key client can run a check-then-insert in the adapter. A `UNIQUE` constraint on `companies.owner_id` is deferred post-MVP.

**Decision 6 — `onboarding_done: true` is written by the frontend, not the backend.**  
`supabase.auth.updateUser()` is a Supabase Auth client call. The backend has no involvement in writing it. The backend only creates the company row.

**Decision 7 — The success screen's 3-second auto-redirect is the only timer in the codebase.**  
It uses `useEffect` + `setTimeout`. The timer is cleared on unmount and on button click.

---

## 2. Database

### What changes
Nothing in the Postgres schema changes.

`onboarding_done` is stored in `auth.users.raw_user_meta_data` (Supabase user metadata), not as a column on any table. This field already exists as JSONB. No migration file is needed.

### Default value
`undefined` (key absent). The flag is only written on successful onboarding completion. Any check must treat `undefined`, `null`, and `false` as "not done."

### No migration
The `companies` table already has `id`, `owner_id`, `name`, `sector`, `currency`, `created_at` — everything the `POST /companies` endpoint needs. No new columns are required.

Post-MVP recommendation: add `UNIQUE (owner_id)` to `companies` via `0002_companies_owner_unique.sql`. Not required for the current plan.

---

## 3. Backend

### 3.1 `backend/messages.py`

Add two new string constants at the bottom of the file:

```
COMPANY_CREATE_FAILED — "We couldn't create your workspace. Please try again."
COMPANY_ALREADY_EXISTS — used internally; the endpoint returns the existing company silently, no error copy needed (logged only)
```

### 3.2 `backend/domain/ports.py`

Add `create()` to the `CompaniesRepo` Protocol:

```python
def create(
    self,
    owner_id: str,
    name: str,
    sector: str | None,
    currency: str,
) -> dict: ...
```

Docstring: "Creates a new company row and returns the full dict. Raises `DuplicateEntryError` if a unique-constraint violation occurs (post-MVP, once the UNIQUE index is added)."

### 3.3 `backend/adapters/supabase_repos.py`

Add `create()` to `SupabaseCompaniesRepo` immediately after `get_by_owner()`:

```python
def create(self, owner_id: str, name: str, sector: str | None, currency: str) -> dict:
    try:
        resp = (
            self._db.table("companies")
            .insert({
                "owner_id": owner_id,
                "name": name,
                "sector": sector,
                "currency": currency,
            })
            .execute()
        )
    except Exception as exc:
        raise _wrap_db(exc) from exc
    return resp.data[0]
```

`_wrap_db` already handles unique violations (code `23505`) → `DuplicateEntryError`. No extra error handling needed.

### 3.4 `backend/api/routes.py`

Add a new Pydantic request model near the top of the request/response models section:

```python
class CreateCompanyRequest(BaseModel):
    name: str
    sector: str | None = None
```

`currency` is not in the request — it defaults to `"USD"` in the endpoint.

Add the new endpoint after the existing `GET /companies/me` block:

```
POST /companies
Rate limit: 5/hour
Auth: get_current_user (NOT get_company_id — user has no company yet)
```

Endpoint logic in order:
1. Receive `user_id` from `get_current_user`.
2. Call `get_companies_repo().get_by_owner(user_id)`.
   - If it succeeds (company already exists): return it with status 200. Log a warning at INFO level: `company_already_exists, user_id=...`. Do not raise an error.
   - If it raises `RLSForbiddenError` (no company exists): proceed to step 3.
3. Call `get_companies_repo().create(owner_id=user_id, name=body.name, sector=body.sector, currency="USD")`.
4. Return `{ "id": ..., "name": ..., "sector": ..., "currency": ... }` with status 201.
5. On any other exception: raise HTTP 503 with `messages.COMPANY_CREATE_FAILED`.

**No cache invalidation is needed.** The `_company_cache` in `auth.py` is only populated on successful `get_by_owner` calls. A user with no company never has an entry in that cache. After company creation, the next authenticated request will call `get_by_owner`, succeed, and populate the cache normally.

**No changes to `auth.py`.**

---

## 4. Frontend

### 4.1 `frontend/src/lib/messages.ts`

Add one new key:

```typescript
ONBOARDING_COMPANY_FAILED: "We couldn't set up your workspace. Please try again.",
```

### 4.2 `frontend/src/pages/RegisterPage.tsx`

**One-line change.**

Line 31: `navigate("/upload", { replace: true })` → `navigate("/onboarding", { replace: true })`

No other changes. The registration form fields stay as-is. The `signUp()` call already stores `full_name` in user metadata — the onboarding form will let the user confirm or change it.

### 4.3 `frontend/src/pages/LoginPage.tsx`

**Change the post-login navigation logic.**

Current (`LoginPage.tsx:33`): `navigate(resolveNext(), { replace: true })`

New logic (replace the `navigate` call inside the `try` block):

```typescript
const data = await signIn(email.trim(), password);
const onboardingDone = data.user?.user_metadata?.onboarding_done === true;
if (onboardingDone) {
  navigate(resolveNext(), { replace: true });
} else {
  navigate("/onboarding", { replace: true });
}
```

`signIn()` in `auth.ts` already returns `data` from `signInWithPassword`, which includes `data.user`. No changes to `auth.ts` needed.

**Why `=== true` and not just truthy:** The field may be absent (`undefined`) or explicitly `false`. Strict equality prevents a `"false"` string from being treated as done.

**`resolveNext()` is only used when `onboarding_done` is true.** If the flag is missing, users always go to `/onboarding` regardless of the `?next=` param. They cannot deep-link past onboarding.

### 4.4 `frontend/src/routes/ProtectedRoute.tsx`

**Remove all company-check logic.** The current file is already clean (session check only). If any company-check code was added before this plan is implemented, revert it completely.

Final `ProtectedRoute` has exactly three responsibilities:
1. While auth is loading → show spinner
2. If no session → `Navigate` to `/login?next=...`
3. Otherwise → render `children`

No `useCompany`, no `ForbiddenError` check, no redirect to `/onboarding`. The file should not change from its current state in the repo.

### 4.5 `frontend/src/App.tsx`

Add the `/onboarding` route. Place it after `/register` and before the protected app routes:

```tsx
import OnboardingPage from "./pages/OnboardingPage";

// In <Routes>:
<Route
  path="/onboarding"
  element={
    <ProtectedRoute>
      <OnboardingPage />
    </ProtectedRoute>
  }
/>
```

No `AppShell` wrapper. Onboarding is full-screen.

### 4.6 `frontend/src/index.css`

Add the step fade animation. Insert before the closing of the file, after the existing `@keyframes` blocks but inside the `@media (prefers-reduced-motion: reduce)` coverage:

```css
@keyframes step-fade-in {
  from { opacity: 0; }
  to   { opacity: 1; }
}

.step-fade-in {
  animation: step-fade-in 0.2s ease;
}
```

The existing `prefers-reduced-motion` block at lines 109–125 already applies `animation-duration: 0.01ms !important` to `*, *::before, *::after`, which covers `.step-fade-in` automatically. No additional media query needed.

### 4.7 `frontend/src/pages/OnboardingPage.tsx` — **New file**

This is the route-level orchestrator. It owns the phase state machine.

**Phases:** `'walkthrough' | 'form' | 'success'`

**State:** `const [phase, setPhase] = useState<'walkthrough' | 'form' | 'success'>('walkthrough')`

**Render logic:**
```
phase === 'walkthrough' → <HowItWorks onDone={() => setPhase('form')} onSkip={() => setPhase('form')} />
phase === 'form'        → <CompanySetupForm onSuccess={() => setPhase('success')} />
phase === 'success'     → <OnboardingSuccess />
```

`OnboardingSuccess` can be a small inline component in the same file or a named export — it is not reused anywhere else.

### 4.8 `frontend/src/components/HowItWorks.tsx` — **New file**

**Props:** `{ onDone: () => void; onSkip: () => void }`

**Layout:** Full-screen centered (`min-h-screen flex items-center justify-center bg-canvas px-4`), matching `LoginPage`'s outer shell.

**Card:** `w-full max-w-[400px] bg-surface border border-border rounded-lg p-8 shadow-sm relative`

**Skip link:** Positioned `absolute top-4 right-4` inside the card. Text: "Skip". Style: `text-sm text-text-secondary hover:text-text-primary`. Calls `onSkip()`.

**Step indicator:** Three dots centered above the icon.
- Active step dot: `h-2 w-2 rounded-full bg-accent`
- Inactive step dot: `h-2 w-2 rounded-full bg-border`
- Transition: `transition-colors`

**Step content:** Wrapped in a `<div key={step} className="step-fade-in">`. The `key` change forces React to remount the div on step change, triggering the CSS animation.

**Steps data (defined as a constant in the file):**

| Step | Icon (lucide-react) | Headline | Description |
|---|---|---|---|
| 0 | `Upload` (48px, `text-accent`) | Upload your file | Drop your Excel or CSV. We read it automatically. |
| 1 | `AlertTriangle` (48px, `text-accent`) | We find the anomalies | Our agent flags anything outside your normal range. |
| 2 | `FileText` (48px, `text-accent`) | Get your report | Plain-language summary, verified, sent to your inbox. |

**Button:**
- Steps 0-1: "Next →" — calls `setStep(s => s + 1)`
- Step 2: "Get Started →" — calls `onDone()`
- Style: `w-full rounded-md bg-accent text-white py-2 px-4 text-sm font-medium hover:opacity-95`

### 4.9 `frontend/src/components/CompanySetupForm.tsx` — **New file**

**Props:** `{ onSuccess: () => void }`

**Layout:** Full-screen centered (`min-h-screen flex items-center justify-center bg-canvas px-4`), matching `LoginPage`.

**Card header:**
- Headline: "Set up your workspace" (`text-2xl font-semibold text-text-primary`)
- Subhead: "Takes 30 seconds." (`text-sm text-text-secondary mt-1`)

**Card:** `w-full max-w-[400px] bg-surface border border-border rounded-lg p-6 shadow-sm`

**Fields (in order):**

1. **Your name** — `type="text"`, `autoComplete="name"`, required, placeholder "Jane Doe"
2. **Company name** — `type="text"`, `autoComplete="organization"`, required, placeholder "Acme Corp"
3. **Work email** — `type="email"`, `autoComplete="email"`, required, placeholder "you@company.com"
   - Pre-filled from `useAuth().user?.email ?? ""`
4. **Industry** — `<select>`, required
   - Options: SaaS, Manufacturing, Real Estate, Professional Services, Other
   - Default: empty (no pre-selection, forces a conscious choice)

**All inputs use the same class pattern as `LoginPage`:**
```
w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary 
placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-accent 
focus:border-accent read-only:opacity-60
```

**Submit handler (in order):**
1. Validate: all 4 fields non-empty. Show inline error if not.
2. Set `loading = true`, clear any existing error.
3. `POST /companies` via `apiFetch("/companies", { method: "POST", json: { name: companyName, sector: industry } })`.
4. On API success: call `supabase.auth.updateUser({ data: { full_name: name, email, onboarding_done: true } })`.
   - If `updateUser` fails: log the error but do not block the user. `onboarding_done` may not be set, meaning they'll see onboarding again on next login, but they have a company and can work. This is an acceptable degraded state.
5. `queryClient.setQueryData(["company-me"], apiResponse)` — populate React Query cache directly without a refetch.
6. Call `onSuccess()`.
7. On API error: set inline error message `CLIENT_MESSAGES.ONBOARDING_COMPANY_FAILED`. Do not call `onSuccess()`.
8. `loading = false` in `finally`.

**Submit button:**
- Text: "Start analyzing →" / "Setting up…" (while loading)
- Style: teal, full-width, `disabled` while `loading` or any required field is empty
- Matches `LoginPage` button pattern exactly

**Error display:** `role="alert"` div with `bg-severity-high-bg text-severity-high-fg` — same as `LoginPage`.

**No toast.** Inline error only. This is a blocking step.

### 4.10 `OnboardingSuccess` component (inside `OnboardingPage.tsx`)

Named component `OnboardingSuccess` in the same file as `OnboardingPage`. Not exported.

**Props:** none (uses `useNavigate` internally)

**Layout:** Full-screen centered, same shell as the other onboarding phases.

**Card content:**
- Headline: "You're all set!" (`text-2xl font-semibold text-text-primary text-center`)
- Subtext: "Now upload your first file to get started." (`text-sm text-text-secondary text-center mt-2`)
- CTA button: "Upload my first file →" (teal, full-width, `mt-6`)

**Auto-redirect:**
```typescript
useEffect(() => {
  const timer = setTimeout(() => {
    navigate("/upload", { replace: true });
  }, 3000);
  return () => clearTimeout(timer);
}, [navigate]);
```

Button `onClick`:
```typescript
() => {
  navigate("/upload", { replace: true });
}
```

The timer cleanup in the effect's return function handles both unmount and button click (button navigates away, causing unmount, which runs cleanup).

---

## 5. Decision Flow

### 5.1 New user (just registered)

```
RegisterPage.handleSubmit
  └─ signUp(email, password, fullName)
       └─ success
            └─ navigate("/onboarding", { replace: true })
                  └─ ProtectedRoute
                       └─ session exists → render OnboardingPage
                            └─ phase: 'walkthrough'
                                 └─ HowItWorks
                                      ├─ "Skip" clicked → phase: 'form'
                                      └─ "Get Started" clicked → phase: 'form'
                                           └─ CompanySetupForm
                                                └─ submit
                                                     ├─ POST /companies → 201 created
                                                     ├─ supabase.auth.updateUser({ onboarding_done: true })
                                                     ├─ queryClient.setQueryData(["company-me"], company)
                                                     └─ onSuccess() → phase: 'success'
                                                          └─ OnboardingSuccess
                                                               ├─ button click → navigate("/upload")
                                                               └─ 3s timer fires → navigate("/upload")
```

### 5.2 Returning user — onboarding complete

```
LoginPage.handleSubmit
  └─ signIn(email, password)
       └─ data.user.user_metadata.onboarding_done === true
            └─ navigate(resolveNext(), { replace: true })
                 └─ "/upload" (or ?next= param if present)
```

### 5.3 Returning user — onboarding incomplete (flag missing or false)

```
LoginPage.handleSubmit
  └─ signIn(email, password)
       └─ data.user.user_metadata.onboarding_done !== true
            └─ navigate("/onboarding", { replace: true })
                 └─ same flow as 5.1, starting at OnboardingPage
                      └─ CompanySetupForm — POST /companies
                           └─ company already exists
                                └─ endpoint returns existing company (200, not 201)
                                └─ onboarding continues normally → success screen
```

### 5.4 User who closed the tab mid-onboarding (no company created)

```
User left at HowItWorks or before form submission.
Returns → logs in → onboarding_done missing → goes to /onboarding → completes form.
POST /companies → company does not exist → creates it (201).
```

### 5.5 User who submitted form but updateUser failed

```
Company row exists. onboarding_done flag not written.
User sees success screen, navigates to /upload, works normally.
Next login → onboarding_done missing → goes to /onboarding.
CompanySetupForm form is shown. User submits.
POST /companies → company already exists → returns existing (200).
supabase.auth.updateUser({ onboarding_done: true }) → succeeds this time.
Redirect to /upload. Flag is now set — onboarding never shown again.
```

---

## 6. What Does NOT Change

| Component | Current behavior | After revision |
|---|---|---|
| `ProtectedRoute` | Session check only | Session check only (unchanged) |
| `useCompany` hook | React Query, 5-min cache | Unchanged |
| `AuthContext` | Exposes session, user, loading | Unchanged |
| `auth.ts` | signIn, signUp, signOut, getSession | Unchanged |
| `backend/api/auth.py` | JWT validation + company cache | Unchanged |
| All protected pages | Render normally | Unchanged |
| DB schema / migrations | `0001_initial_schema.sql` | Unchanged |

---

## 7. File Change Summary

| File | Change type | Change |
|---|---|---|
| `backend/messages.py` | Edit | Add `COMPANY_CREATE_FAILED` |
| `backend/domain/ports.py` | Edit | Add `create()` to `CompaniesRepo` Protocol |
| `backend/adapters/supabase_repos.py` | Edit | Add `create()` to `SupabaseCompaniesRepo` |
| `backend/api/routes.py` | Edit | Add `CreateCompanyRequest` model + `POST /companies` endpoint |
| `frontend/src/lib/messages.ts` | Edit | Add `ONBOARDING_COMPANY_FAILED` |
| `frontend/src/pages/RegisterPage.tsx` | Edit | Change destination from `/upload` to `/onboarding` (1 line) |
| `frontend/src/pages/LoginPage.tsx` | Edit | Check `onboarding_done` flag after signIn; branch navigation |
| `frontend/src/App.tsx` | Edit | Add `/onboarding` route |
| `frontend/src/index.css` | Edit | Add `step-fade-in` keyframe + class |
| `frontend/src/pages/OnboardingPage.tsx` | **New** | Phase state machine + `OnboardingSuccess` component |
| `frontend/src/components/HowItWorks.tsx` | **New** | 3-step walkthrough |
| `frontend/src/components/CompanySetupForm.tsx` | **New** | 4-field form + API call + metadata update |

**`ProtectedRoute.tsx` — no changes.**  
**No DB migrations.**  
**No changes to `guardrail.py`, `schema.sql`, or any agent.**

---

## 8. Implementation Order

Implement in this sequence to avoid broken intermediate states:

1. Backend: `messages.py` → `ports.py` → `supabase_repos.py` → `routes.py`
2. Frontend strings: `messages.ts`
3. Frontend new components: `HowItWorks.tsx` → `CompanySetupForm.tsx`
4. Frontend new page: `OnboardingPage.tsx` (depends on both components)
5. Frontend routing: `App.tsx` (add `/onboarding` route)
6. Frontend login: `LoginPage.tsx` (flag check — safe to add now that `/onboarding` exists)
7. Frontend register: `RegisterPage.tsx` (redirect — safe now that `/onboarding` exists)
8. Styles: `index.css` (step-fade-in — safe to add at any point)

At no step in this order is a half-built feature reachable by an existing user.

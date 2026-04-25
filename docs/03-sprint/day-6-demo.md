# Day 6 — Demo + Deploy + Submit
*IronLedger 6-Day Sprint — Built with Opus 4.7 Hackathon, April 2026*

## Goal

Live demo URL works end-to-end on Railway (backend) + Vercel (frontend). Production Supabase has DRONE Feb 2026 baseline pre-loaded so the Mar 2026 live upload produces the target anomalies (G&A −34% favorable, Travel +61% high). Demo laptop is pre-warmed with the demo user's Supabase session so `/login` is skipped on stage. 3-minute demo rehearsed twice from `docs/runbook.md`. Backup Loom video uploaded in case live demo fails. GitHub repo is public with a README that explains setup, the Golden Rule, and links to the live demo. Submission filed on Cerebral Valley **before April 26, 8:00 PM EST**.

## End-of-Day Acceptance Check

> Today's finish line is a submitted hackathon entry, not a code change. Verify all of these before submitting:
> 1. `GET https://<railway-url>/health` returns `{"status": "ok"}` in under 2 seconds (post cold-start)
> 2. `https://<vercel-url>.vercel.app` loads in a clean browser with zero console errors and correct Inter font
> 3. Sign in as `demo@dronedemo.com` on the live Vercel URL. Upload `drone_mar_2026.xlsx`. Watch 4-step progress bar complete. Verified report renders with Verified badge, G&A favorable green chip, Travel high unfavorable chip, provenance on hover.
> 4. Click Send Email. Real email arrives in the demo inbox within 30s with correct HTML formatting, tabular numerals, parenthesized negatives.
> 5. CORS sanity: browser devtools Network tab shows no CORS errors on any XHR.
> 6. Production Supabase: `SELECT COUNT(*) FROM monthly_entries WHERE company_id=<drone>` returns Feb + Mar totals (baseline + Mar upload). DRONE Inc. row in `companies` has `owner_id` = demo user UUID.
> 7. Demo laptop has the Vercel URL open, **session already persisted** (no login prompt on reload). Browser zoom at 125%. Other tabs/notifications closed.
> 8. `docs/runbook.md` demo script rehearsed **at least twice** end-to-end on the live URL with a timer. Final rehearsal completed in ≤3:00.
> 9. Backup Loom video is uploaded, link tested in an incognito tab, plays cleanly at 1080p.
> 10. `README.md` shows: live demo link, `ANTHROPIC_API_KEY` setup steps, the Golden Rule prominently, architecture diagram link, demo video link.
> 11. GitHub repo is **public**. No `.env` or secrets committed (`git log -p | grep -iE "SUPABASE_SERVICE_KEY|ANTHROPIC_API_KEY|RESEND_API_KEY"` returns empty).
> 12. `backend/prompts/*.txt` all committed — `mapping_prompt.txt`, `narrative_prompt.txt`, `narrative_prompt_reinforced.txt`.
> 13. Cerebral Valley submission form filled + submitted **before 8:00 PM EST**. Receipt confirmation captured (email or screenshot). ✅

## Preconditions (from Day 1–5)

From Day 5:
- [x] Real email sends via Resend to a verified sender domain (DNS propagated)
- [x] `pytest` passes — all ~40 tests green (PII, guardrail, RLS, storage, state machine, rate limit, empty state, stale, mapping confirm, parser pipeline)
- [x] `black --check .`, `flake8`, `npm run lint` all clean
- [x] Inline-prompt audit passes (zero inline prompts)
- [x] Day-4 deferrals landed (MappingConfirmPanel, EmptyState, Stale state, rate-limit countdown)
- [x] Backup demo video recorded (Day-5 evening insurance)
- [x] `docs/runbook.md` updated against final product

From Day 1–4:
- [x] Clean Architecture scaffold intact, Supabase + Auth + Storage + RLS correct
- [x] `POST /upload`, `GET /runs/{id}/status`, `GET /report/...`, `GET /anomalies/...`, `POST /mail/send`, `GET /runs/{id}/raw`, `POST /runs/{id}/retry`, `POST /mapping/confirm`, `GET /companies/me/has-history` all live
- [x] Frontend: Login, Upload, LoadingProgress, ReportSummary (Verified + Stale), AnomalyCard, GuardrailWarning, MappingConfirmPanel, EmptyState, Toast, ErrorBoundary

External pre-requisites:
- Railway account with a project linked to the GitHub repo
- Vercel account with a project linked to the GitHub repo
- Second Supabase project OR same Supabase with distinct schema? — **MVP decision: reuse single Supabase project for simplicity.** Prod and dev share the same DB. Not ideal for post-hackathon, fine for 3-minute demo. Flagged in `risks.md`.
- Domain for verified Resend sender (from Day 5)
- Cerebral Valley submission platform credentials ready

---

## Tasks

### 1. Backend Deploy — Railway

- [ ] Link GitHub repo to Railway project. Select branch: `main`.
- [ ] Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- [ ] **Environment variables** (complete list — every key in `backend/settings.py`):
  ```
  ANTHROPIC_API_KEY=sk-ant-...
  SUPABASE_URL=https://<project>.supabase.co
  SUPABASE_SERVICE_KEY=eyJh...
  RESEND_API_KEY=re_...
  FRONTEND_URL=https://<project>.vercel.app
  ```
- [ ] **CORS allowlist** on Railway must include the **production Vercel URL**. `backend/main.py` reads `FRONTEND_URL` — set it here before first deploy.
- [ ] Python version pin: `runtime.txt` with `python-3.11.x` (Railway reads this)
- [ ] Deploy. Watch logs for startup errors. Fix any import / env errors.
- [ ] `curl https://<railway-url>/health` — expect `{"status": "ok"}`
- [ ] Measure cold-start: hit `/health` after 15 min of inactivity. Record the duration. **Expected ~10s on Railway free tier** (per `docs/runbook.md`).
- [ ] Hit every endpoint once via Bruno with the demo JWT to warm caches before the first Day-6 rehearsal.

### 2. Frontend Deploy — Vercel

- [ ] Link GitHub repo to Vercel project. Root directory: `frontend/`. Build command: `npm run build`. Output: `dist/`.
- [ ] **Environment variables**:
  ```
  VITE_SUPABASE_URL=https://<project>.supabase.co
  VITE_SUPABASE_ANON_KEY=eyJh...   # anon, not service
  VITE_API_URL=https://<railway-url>
  ```
- [ ] Trigger deploy. Verify build succeeds.
- [ ] Open the Vercel URL in an incognito tab. Open devtools. Verify:
  - No console errors
  - `/login` renders
  - Sign-in flow calls Supabase (check Network tab)
  - After sign-in, `/upload` renders and `GET /companies/me/has-history` call to Railway succeeds (confirms CORS + auth round-trip on prod)
- [ ] If any production-only issues appear (env var typos, CORS, https vs http): fix before rehearsing.

### 3. Production Data — Pre-Load DRONE Baseline

Without a pre-loaded Feb 2026 baseline, Mar 2026 comparison has no history — the demo will hit the Empty State branch instead of showing anomalies.

- [ ] On prod Supabase, verify demo user `demo@dronedemo.com` exists. If not, create via Supabase Auth UI.
- [ ] Verify DRONE Inc. row: `SELECT id, name, owner_id FROM companies WHERE name='DRONE Inc.'`. If missing, INSERT with `owner_id=<demo_user_uuid>`.
- [ ] Sign in as `demo@dronedemo.com` on the **live Vercel URL** (not localhost). Upload `drone_feb_2026.xlsx` with period `2026-02-01`. Wait for `complete`.
- [ ] Verify via SQL: `SELECT COUNT(*) FROM monthly_entries WHERE company_id=<drone> AND period='2026-02-01'` returns the expected Feb row count.
- [ ] **Do NOT pre-load Mar** — that's the live demo upload.
- [ ] **Storage cleanup ran on the baseline upload** — the file is gone from Storage (per Day-3 cleanup-on-complete rule), but the `monthly_entries` rows persist. This is the correct state.

### 4. Demo Laptop — Pre-Warm & Browser Prep

- [ ] On the demo laptop, open the Vercel URL in **Chrome** (not a different browser — familiar DOM on stage)
- [ ] Sign in once as `demo@dronedemo.com`. Supabase persists the session by default — **do not sign out**.
- [ ] Close and reopen the browser. Verify: landing on the Vercel URL goes straight to `/upload` (session survived). If it redirects to `/login`, session persistence is broken — debug before rehearsing.
- [ ] Browser zoom: **125%** (easier for judges to read — per `runbook.md`)
- [ ] Close every other tab and notification. macOS: `Do Not Disturb` on.
- [ ] Position `drone_feb_2026.xlsx` and `drone_mar_2026.xlsx` on the desktop — easy to drag in one motion.
- [ ] Open a second browser tab pre-loaded with the demo inbox (e.g. Gmail) for the email-arrival reveal in the demo.
- [ ] Have Loom backup link in a bookmark, ready to share if live demo fails.

### 5. Demo Script Rehearsal

Per `docs/runbook.md` — 3-minute script with 6 beats (Hook / Upload / Results / Architecture / Email / Scale / Close).

- [ ] Read `docs/runbook.md` end to end. Update any screen references that have drifted from final UI.
- [ ] **Rehearsal 1**: dry run on the live Vercel URL with a timer. Aim for ≤3:00. Note any moments of silence, stumbling, or UI waits that break flow.
- [ ] **Rehearsal 2**: address issues from rehearsal 1. Time it again. Should come in tighter.
- [ ] Specific moments to practice:
  - The drag onto dropzone — one smooth motion, no "where did I put that file" pause
  - The provenance hover — hover on a narrative number, hold for 1s, let the popover render for the judges
  - The architecture moment — briefly open `CLAUDE.md` or the flow diagram (keep it ≤10s; don't lose momentum)
  - The Send Email reveal — click Send, cut to the pre-loaded inbox tab, show the email arriving
- [ ] Record the 2nd rehearsal on Loom as a **secondary backup** if Day-5 primary backup is stale

### 6. Fallback Plans

Per `docs/runbook.md` §Fallback Plans. Verify each fallback is actually usable before demo:

- [ ] **Railway cold start fails** — localhost + ngrok ready on demo laptop. Test the ngrok command before demo: `ngrok http 8000`. Save the tunneled URL; know how to swap `VITE_API_URL` in Vercel env (or run frontend locally on `:5173` pointing to localhost:8000).
- [ ] **File upload hangs** — pre-recorded video segment for that section (from Day-5 backup Loom)
- [ ] **Email doesn't arrive** — show sent confirmation in the UI toast; verbal pivot: "email is also in your dashboard as `mail_sent: true`"
- [ ] **Guardrail fires unexpectedly** — frame it as a feature, not a bug. Rehearse the pivot: "And here's the guardrail working — it caught a number mismatch and refused to save an unverified report. This is the point of IronLedger."
- [ ] **Vercel down** — run frontend locally on `:5173`, backend still on Railway
- [ ] **Entire internet down** — run both locally; judges will understand

### 7. Pre-Demo Checklist (30 minutes before stage)

Run through this list **in order** exactly 30 minutes before go-time.

- [ ] `curl https://<railway-url>/health` — expect 200. If 500 or timeout twice in a row, cut to localhost+ngrok immediately.
- [ ] **Cold-start ping** — even if healthy, fire 3× `/health` to warm container caches.
- [ ] Vercel URL in demo laptop Chrome: confirm session persisted, no `/login` redirect.
- [ ] Supabase: `SELECT COUNT(*) FROM monthly_entries WHERE company_id=<drone>` — expect Feb baseline count.
- [ ] Send a test email to yourself via the UI on live URL (to a non-demo inbox so the demo inbox stays clean). Verify arrival in ≤30s.
- [ ] Demo files on desktop. Both Excel files, not in a compressed folder.
- [ ] Browser zoom 125%. All tabs closed except: Vercel demo tab + demo inbox tab + Loom backup (bookmarked, not open).
- [ ] macOS Do Not Disturb on. Slack and email clients quit.
- [ ] Resend still showing verified sender.
- [ ] Loom backup link tested in incognito — plays cleanly.
- [ ] Bluetooth headphones charged (if using) or wired headphones connected.
- [ ] Water bottle nearby. (No joke. Dry throat on stage is common.)

### 8. README + Repo Finalization

- [ ] `README.md` at repo root — structure:
  ```markdown
  # IronLedger
  AI-powered month-end close agent. Drop messy Excel files → agent finds anomalies, compares to history, writes a verified plain-language report, sends email.
  
  **Live demo:** https://<vercel-url>
  **Demo video:** https://loom.com/<id>
  
  ## The Golden Rule
  > Numbers come from pandas. Prose comes from Claude. A numeric guardrail verifies both.
  
  Claude never does arithmetic. Every number in every report is verified against pandas output within 2% tolerance — or the report is refused.
  
  ## Architecture
  Three sequential agents (Parser → Comparison → Interpreter), Clean Architecture (ports & adapters), Supabase as message bus. See CLAUDE.md for detail.
  
  ## Setup
  ```bash
  pip install -r requirements.txt
  cp .env.example .env  # fill in keys
  uvicorn backend.main:app --reload
  
  cd frontend && npm install && npm run dev
  ```
  
  ## Stack
  FastAPI · Supabase (Postgres + Auth + Storage + RLS) · Claude Opus 4.7 + Haiku 4.5 · pandera · Resend · Vite + React + TypeScript + shadcn/ui · Railway + Vercel
  
  ## Testing
  ```
  pytest
  ```
  ~40 tests across PII, guardrail, RLS isolation, state machine, rate limit, storage.
  
  ## Built with Claude Opus 4.7 — Anthropic Hackathon April 2026
  ```
- [ ] `.env.example` — every env var used, with placeholder values
- [ ] `requirements.txt` — pinned, committed
- [ ] `frontend/package.json` + `package-lock.json` — committed
- [ ] `backend/db/schema.sql` — full schema, committed, runnable fresh
- [ ] `backend/prompts/mapping_prompt.txt`, `narrative_prompt.txt`, `narrative_prompt_reinforced.txt` — all committed
- [ ] Secret scan: `git log -p | grep -iE "SUPABASE_SERVICE_KEY|ANTHROPIC_API_KEY|RESEND_API_KEY" ` — expect empty
- [ ] `.gitignore` includes `.env`, `__pycache__/`, `node_modules/`, `dist/`, `.DS_Store`
- [ ] Make repo **public** on GitHub

### 9. Demo Video Upload

- [ ] If Day 5 backup still current: upload to Loom. Set to public view.
- [ ] If product drifted since Day-5 recording: re-record after rehearsal 2 (same recording serves as both demo video + backup).
- [ ] Video length: ≤3 minutes (submission constraint per `runbook.md`)
- [ ] Resolution: 1080p minimum.
- [ ] Audio: clean, no background noise. Rerecord if audio is bad.
- [ ] Test playback in an **incognito** tab (confirms "public" setting works without sign-in).

### 10. Hackathon Submission

- [ ] Open Cerebral Valley submission form
- [ ] Fields to complete:
  - Team / solo name
  - Project name: IronLedger
  - One-line description: "AI-powered month-end close agent for US finance teams. Drop messy Excel files → verified plain-language variance report → email to the CFO. In under 2 minutes."
  - Live demo URL: `https://<vercel-url>`
  - Video URL: Loom link
  - GitHub URL: public repo link
  - Written summary (100–200 words): adapt the Hook from `runbook.md` + mention the Golden Rule + mention Clean Architecture + PII sanitization
  - Model used: Claude Opus 4.7 (narrative) + Claude Haiku 4.5 (column mapping)
  - Built with Claude Code: yes
- [ ] **Submit before April 26, 8:00 PM EST.** Capture the confirmation screen / email as proof.
- [ ] If the platform is flaky near deadline: submit at 6 PM, not 7:55 PM. The last hour is the riskiest.

---

## Internal Sequencing

Day 6 is time-boxed against the 8 PM EST submission deadline. Sequence deliberately.

1. **Morning (by midday):**
   - Backend deploy to Railway (§1)
   - Frontend deploy to Vercel (§2)
   - Production DRONE baseline pre-load (§3)
   - Smoke test live URL end-to-end
2. **Early afternoon:**
   - Demo laptop pre-warm (§4)
   - Rehearsal 1 on the live URL (§5)
3. **Mid afternoon:**
   - Fix any issues from rehearsal 1
   - README + repo finalization (§8)
   - Demo video upload (§9)
4. **Late afternoon:**
   - Rehearsal 2 (§5)
   - Fallback plan verification (§6)
5. **Evening (by 6 PM EST at latest):**
   - Final pre-submission check (mini version of §7)
   - **Submit to Cerebral Valley (§10)** — do not wait until 7:55 PM
6. **Before stage (if live demo is the same day):**
   - Pre-demo checklist (§7) 30 min before

Rule of thumb: **deploy → data → rehearse → submit → stage.** Submission is a separate milestone from the live demo. Submit early, rehearse late.

---

## Contracts Produced Today

### Production environment
```
Backend:  https://<railway-url>.railway.app
Frontend: https://<project>.vercel.app
Database: Supabase (shared with dev — post-MVP separation)
Storage:  Supabase Storage, bucket financial-uploads
```

### README.md structure
Live link + Golden Rule + Architecture summary + Setup + Stack + Testing + Credit. Frozen content — changes post-submission would be dishonest.

### Submission package
- Live URL
- Demo video URL (Loom, ≤3 min, public)
- GitHub URL (public)
- Written summary (100–200 words) submitted via Cerebral Valley

### Fallback plan
- Primary: live Vercel + Railway
- Secondary: localhost + ngrok (tested before stage)
- Tertiary: Loom backup video (uploaded + tested)

---

## Cut Line

### Must ship today (non-negotiable)
- Backend deployed to Railway, `/health` returns 200
- Frontend deployed to Vercel, end-to-end user flow works on live URL
- DRONE Feb 2026 baseline loaded to production Supabase
- Demo rehearsed at least once on the live URL
- README committed + GitHub repo **public**
- Demo video uploaded (Day 5 backup or fresh recording)
- **Cerebral Valley submission filed before 8:00 PM EST**

### Deferrable (if time is tight)
- Rehearsal 2 (one rehearsal is the floor; two is better)
- Fresh demo video recording (reuse Day-5 backup if still current)
- Ngrok fallback pre-tested (only matters if Railway actually fails)
- Re-record demo video for 1080p / audio quality tweaks (if recording from Day 5 is acceptable)

### Defer to post-MVP
- Separate prod vs dev Supabase projects
- Prod observability / monitoring (Sentry, Datadog, etc.)
- Auto-scaling config
- Custom domain for frontend + backend
- TLS certificate pinning
- CI/CD on main branch push
- Staging environment
- Load testing

---

## Risks (this day)

| Risk | Impact | Mitigation |
|---|---|---|
| Railway cold start on demo day | Judges wait 10s during upload — looks broken | Pre-demo ping (§7). If 2× timeout, switch to localhost+ngrok. |
| Vercel deploy fails on first push | Day-6 deploy time burned on config | Deploy early morning, fix on weekdays; if stuck, local dev server + ngrok tunnel is acceptable for demo |
| Environment variable missing in prod | Silent 500s, CORS errors, auth fails | Cross-check every key in `backend/settings.py` against Railway env; repeat for Vercel |
| CORS missing Vercel URL | Silent Day-6 failure — frontend can't reach backend | Explicit check on first Vercel deploy; `FRONTEND_URL` on Railway matches Vercel URL exactly (including https://) |
| DRONE baseline missing from prod Supabase | Mar upload hits Empty State path instead of showing anomalies | §3 mandatory before rehearsal 1; verify via SQL |
| Demo laptop session not persisted | `/login` blocks demo start | §4 explicit test — close and reopen browser |
| Resend production sender not yet propagated | Live email test fails in prod | Day-5 evening DNS start gives 12+ hours; test a live send before rehearsing |
| Prod DB shared with dev → test data pollutes production | Demo data looks "dirty" with old runs/anomalies | Before rehearsal: `DELETE FROM runs WHERE company_id=<drone>; DELETE FROM monthly_entries ...; DELETE FROM anomalies ...;` reset to just the Feb baseline |
| Demo recording shows old UI | Viewers notice inconsistency between live demo and video | Re-record post rehearsal 2 if UI has drifted since Day 5 |
| Cerebral Valley form crashes near deadline | Submission missed | Submit at 6 PM, not 7:55 PM |
| Secrets committed in git history | Repo going public exposes keys | §8 explicit grep check before making public; if any leaked, rotate keys immediately (Anthropic, Supabase, Resend) and squash history |
| Rehearsal blows past 3:00 | Live demo cut off mid-sentence | Trim the "Scale" section (2:15–2:45) — that's the easiest to shorten without losing the story |
| Opus latency during live demo | 20–30s silence during report generation | Pre-warm: run the pipeline once Day-6 afternoon so prompts + adapter are warm; narrate the architecture during the wait |
| Judges ask unexpected question | Deer-in-headlights | Prepare 3 common Q&A: (1) "Why not LangChain?" → "50 lines of Anthropic SDK; fewer abstractions; easier debugging." (2) "How accurate is the guardrail?" → "2% tolerance on every number; 2 attempts with a reinforced prompt on failure; file-stays-on-fail for manual retry." (3) "What about PII?" → "Header blacklist + SSN regex strips columns before any Claude call. We never send SSN / name / address / bank data to Anthropic." |
| GitHub repo set public without final commit | Stale state frozen in public view | Push final commit FIRST, then flip to public |
| Demo laptop internet flaky on stage | Everything fails live | Mobile hotspot tethering as tertiary backup; Loom video as the ultimate fallback |

Cross-day risks: none today — Day 6 is the last day. Any unresolved cross-day risk in `risks.md` is either mitigated today or accepted as post-MVP.

---

## Reference Docs

Read these before starting Day 6 tasks.

- **`docs/runbook.md`** — **the primary doc today.** 3-minute demo script, pre-demo checklist, cold-start warning, fallback plans, submission checklist
- **`CLAUDE.md`** — referenced during the "Architecture Moment" beat (briefly open on stage)
- **`docs/scope.md`** — Success Criteria checklist (all items should now be green)
- **`docs/api.md`** — Authentication + CORS Configuration (cross-check env vars)
- **`docs/db-schema.md`** — RLS policies (prod Supabase must have all of them applied)
- **`docs/design.md`** — used earlier as the frontend spec; no new action today
- **`docs/sprint.md`** — Day 6 section (reconciled v3)

---

## Post-Submission

After the Cerebral Valley receipt lands:

- [ ] Append the final Day-6 shipping log to `docs/sprint/completed.md`
- [ ] Move `docs/sprint/risks.md` items that resolved into completed; leave unresolved items as the **post-MVP backlog**
- [ ] Tag the submission commit: `git tag -a hackathon-submission -m "IronLedger hackathon submission, Apr 26 2026"`
- [ ] Sleep. Seriously. Judging may run late; be rested for the live demo, if applicable.

Post-hackathon retrospective (Day 7+):
- pgvector for long-term pattern recognition
- ERP API integration (NetSuite, QuickBooks, SAP direct)
- Multi-user / role management (Controller vs CFO view)
- Budget vs actuals comparison layer
- Draft journal entries (auto-generated JE suggestions for ERP upload)
- Aspirational blocking MappingConfirmModal (real pause/resume with `awaiting_mapping` state)
- Prod/dev Supabase separation
- Observability (Sentry, Datadog)
- CI/CD pipeline

# Month Proof — Demo Runbook
*Built with Opus 4.7 Hackathon — April 2026*

This is the exact script for the 3-minute demo video and live judging.
Read this the night before. Do not improvise on demo day.

---

## Pre-Demo Checklist (30 minutes before)

- [ ] Railway backend is running — ping `GET /health`, expect 200
- [ ] Vercel frontend is live — open in browser, check no console errors
- [ ] Supabase has DRONE Inc. baseline data (February 2026) already loaded
- [ ] Demo user seeded in Supabase Auth: `demo@dronedemo.com` — test login once before demo
- [ ] Browser is pre-logged-in with demo user (Supabase persists session) to skip the login step on stage
- [ ] Demo Excel files ready on desktop: `drone_feb_2026.xlsx`, `drone_mar_2026.xlsx`
- [ ] Resend email verified and working — send a test email
- [ ] Screen recording software ready (Loom or QuickTime)
- [ ] Browser zoom at 125% — easier for judges to read
- [ ] Close all other tabs and notifications

---

## Cold Start Warning
Railway free tier cold-starts in ~10 seconds after inactivity.
Ping the backend 5 minutes before demo: `curl https://your-app.railway.app/health`
If it fails twice, switch to localhost fallback immediately (see below).

---

## 3-Minute Demo Script

### [0:00 - 0:20] Hook — The Problem
Say:
> "Finance teams spend 10 to 15 hours every month-end manually consolidating Excel files,
> calculating variances, and writing reports. Month Proof eliminates that.
> Drop your files. Get a verified report. In under 2 minutes."

Show: The upload screen. Clean, minimal.

---

### [0:20 - 0:45] Upload
Action: Drag `drone_mar_2026.xlsx` onto the upload zone.
Select period: March 2026.
Click Analyze.

Say:
> "I'm uploading DRONE Inc.'s March financials. This is a raw export — no formatting required."

Show: 4-step progress bar animating.

---

### [0:45 - 1:15] Results
Show: Anomaly cards appear.

Say:
> "The agent found two items. Travel and Entertainment is 61% above the 3-month average —
> flagged as high severity. G&A expenses dropped 34% — that's a favorable variance,
> but worth noting."

Point to: severity badges (red/yellow).

Say:
> "Every number you see came from Python. Claude only wrote the words.
> A numeric guardrail verified that what Claude wrote matches the pandas output
> before this report was saved."

---

### [1:15 - 1:45] The Architecture Moment
Show: Briefly open CLAUDE.md or the agent-flow diagram.

Say:
> "Three agents. Parser reads the file. Comparison calculates variance in Python —
> Claude never touches the math. Interpreter writes the narrative.
> A guardrail checks every number before anything is saved.
> This is trustworthy AI, not just fast AI."

---

### [1:45 - 2:15] Email
Action: Click Send Email, type a demo email address, send.

Say:
> "One click. The report goes to the CFO. No copy-paste, no formatting."

Show: Email arriving in inbox (have this open in another tab, pre-loaded if needed).

---

### [2:15 - 2:45] Scale
Say:
> "This isn't a demo for one file type or one company.
> The same agent reads QuickBooks exports, NetSuite reports, ADP payroll CSVs —
> even the weird XML files NetSuite disguises as .xls.
> 87% of CFOs say AI will be critical to finance in 2026.
> Only 14% have actually integrated it. Month Proof is the bridge."

---

### [2:45 - 3:00] Close
Say:
> "Month Proof. Built with Claude Opus 4.7.
> Numbers from pandas. Prose from Claude. Trust from the guardrail."

Show: Upload screen again. Clean close.

---

## Fallback Plans

| Problem | Fallback |
|---|---|
| Railway cold-start fails | Switch to localhost + ngrok instantly |
| File upload hangs | Use pre-recorded video segment for that section |
| Email doesn't arrive | Show sent confirmation in UI — enough for demo |
| Guardrail fires unexpectedly | Show GuardrailWarning screen — explain it as a feature, not a bug |
| Vercel down | Run frontend locally on port 5173 |

---

## Pre-Recorded Video Backup
Record a clean full run the night before (Day 5 evening).
Upload to Loom. Have the link ready.
If anything breaks live, share screen with the Loom video.
Judges understand technical issues — a smooth backup is better than a broken live demo.

---

## Submission Checklist (April 26, before 8:00 PM EST)
- [ ] GitHub repo is public
- [ ] All prompts in `backend/prompts/` are committed
- [ ] `schema.sql` is committed and runnable
- [ ] Demo video uploaded to Loom or YouTube (max 3 minutes)
- [ ] Written summary ready (100-200 words)
- [ ] Live demo URL working
- [ ] Submit via Cerebral Valley platform before deadline

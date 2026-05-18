Update `src/Composition.tsx` — change only three values in the `sceneDurations` object:

**Current values:**
```ts
const sceneDurations = {
  intro: 120,
  ingest: 155,
  orchestrate: 165,
  python: 175,     // ← change to 110
  narrative: 170,   // ← change to 105
  guardrail: 170,
  report: 165,      // ← change to 98
  close: 125,
};
```

**New values:**
```ts
const sceneDurations = {
  intro: 120,
  ingest: 155,
  orchestrate: 165,
  python: 110,
  narrative: 105,
  guardrail: 170,
  report: 98,
  close: 125,
};
```

Do NOT change anything else in the file. `TOTAL_FRAMES` will recompute automatically since it reads from `sceneDurations`.

Run `npx tsc --noEmit` after the change to verify it compiles cleanly.

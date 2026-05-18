Fix the GuardrailScene layout in src/Composition.tsx (at /Users/jans/Desktop/nexus/iron-ledger/video). The three phases are stacking on top of each other instead of transitioning cleanly.

### Problems to fix

1. **Phase 1 verifyList never fades out** — `failIn` only enters, never exits. So after frame ~12, the Phase 1 card stays fully opaque forever, and Phase 3 renders on top of it.

2. **Mixed layout models** — Phase 1 & 2 use `position: absolute` without explicit coordinates, Phase 3 uses flex. They don't align.

3. **Phase 2 retryText** — uses `position: absolute` without centering.

### Solution

Replace the entire GuardrailScene body with a single-phase-slot approach:

```tsx
const GuardrailScene = () => {
  const frame = useCurrentFrame();
  const local = frame;
  const passIn = enter(local, 145, 20);
  const counter = Math.min(5, Math.max(0, Math.floor((local - 80) / 14) + 1));

  const numbers = [
    { p: "$4,730,000", a: "$4.73M" },
    { p: "$101,000", a: "$101K" },
    { p: "+61.0%", a: "61%" },
    { p: "$38,420", a: "$38,420" },
    { p: "$48,000", a: "$48K" },
  ];

  // Determine which phase we're in
  const phase1 = local < 40;
  const phase2 = local >= 40 && local < 80;
  const phase3 = local >= 80;

  const failFlashOpacity = phase1
    ? enter(local, 0, 12) * exit(local, 30, 10)
    : 0;

  const phase1Opacity = phase1 ? 1 : 0;
  const phase2Opacity = phase2 ? enter(local - 40, 4, 14) * exit(local - 40, 28, 12) : 0;
  const phase3Opacity = phase3 ? enter(local - 80, 0, 18) : 0;

  return (
    <AbsoluteFill className="scene guardrailScene">
      <SceneLabel index="05" title="The Golden Rule: every number is verified before it ships" />

      {/* Phase 1: Failure demonstration */}
      {phase1 && (
        <div className="verifyList" style={{ opacity: phase1Opacity }}>
          <div className="verifyListInner">
            <div className="verifyingRow">
              <span className="pandasVal">$4,730,000</span>
              <span className="arrow">→</span>
              <span className="aiVal mismatch">$4.80M</span>
              <span className="check" style={{ color: "#b91c1c" }}>✗</span>
            </div>
            <div className="failFlash" style={{ opacity: failFlashOpacity }}>
              Mismatch: $4,800,000 not found in pandas output
            </div>
          </div>
        </div>
      )}

      {/* Phase 2: Retry */}
      {phase2 && (
        <div className="retryText" style={{ opacity: phase2Opacity }}>
          Retrying with reinforced prompt…
        </div>
      )}

      {/* Phase 3: Success - multiple verifications */}
      {phase3 && (
        <>
          <div className="verifyList" style={{ opacity: phase3Opacity }}>
            <div className="verifyListInner">
              {numbers.map((n, i) => {
                const revealed = i < counter;
                return (
                  <div
                    key={i}
                    className="verifyingRow"
                    style={{
                      opacity: revealed ? 1 : 0.2,
                      transform: revealed ? "translateX(0)" : "translateX(-10px)",
                      transition: "opacity 0.3s, transform 0.3s",
                    }}
                  >
                    <span className="pandasVal">{n.p}</span>
                    <span className="arrow">→</span>
                    <span className="aiVal">{n.a}</span>
                    <span className="check">{revealed ? "✓" : ""}</span>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="counterBadge" style={{ opacity: phase3Opacity }}>
            {counter} / 5 numbers verified ✓
          </div>

          <div
            className="passedBanner"
            style={{
              opacity: passIn,
              transform: `scale(${0.92 + passIn * 0.08})`,
            }}
          >
            <strong>Guardrail passed</strong>
            <span>Every reported number independently verified against source data.</span>
          </div>
        </>
      )}
    </AbsoluteFill>
  );
};
```

### Key changes
1. **Phase separation via conditional rendering** — `{phase1 && (...)}`, `{phase2 && (...)}`, `{phase3 && (...)}` — only ONE phase renders at a time. No more stacking.
2. **No `position: absolute`** on any phase element — they all use the parent's flex layout.
3. **`failFlashOpacity` properly exits** — `enter(local, 0, 12) * exit(local, 30, 10)` so it fades in then fades out.
4. **Phase 2 opacity** starts after frame 40, fades in, fades out.
5. **Phase 3 opacity** starts after frame 80, fades in.
6. **VerifyingRow rows** use opacity-based stagger (simpler, no extra component needed).

### Also remove the old VerifyingRow component

Delete the old `VerifyingRow` function component from Composition.tsx (it was only used by the old GuardrailScene).

DO NOT change any CSS in index.css — the existing classes (guardrailScene, verifyList, verifyingRow, pandasVal, arrow, aiVal, check, counterBadge, passedBanner, failFlash, retryText, mismatch) should all still work.

Run `npx tsc --noEmit` after changes to verify.

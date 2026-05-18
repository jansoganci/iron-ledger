Rewrite the GuardrailScene component in src/Composition.tsx and add new CSS to src/index.css (at /Users/jans/Desktop/nexus/iron-ledger/video).

### Background
The Guardrail is MonthProof's central differentiator: every number Claude mentions in the narrative is programmatically verified against pandas output before the report is saved. Currently the scene shows a single number pair ($4,730,000 ↔ $4.73M) with a slow scan line — it looks like a formatting check, not an audit.

### New scene structure
Three phases, total ~170 frames:

### Phase 1: Failure path (frames 0-40)
Start with a brief "failure" visualization to establish stakes:
- Show TWO columns like before, but the right column says "$4.8M" instead of "$4.73M"
- A scan line moves from left to right (fast, ~20 frames)
- When scan reaches the right, show a red "MISMATCH" flash on the right column
- Brief red text: "Mismatch: $4,800,000 not found in pandas output"
- The right column's $4.8M value turns red

### Phase 2: Retry (frames 40-80)
- Red flash fades out
- Show "Retrying with reinforced prompt…" text fading in and out (3 seconds)
- Columns remain faint/ghosted

### Phase 3: Success - Multiple verifications (frames 80-170)
- Both columns come back clean
- Show FIVE number pairs stacked vertically that check-mark one by one:
  1. $4,730,000 → $4.73M ✓
  2. $101,000 → $101K ✓
  3. +61.0% → 61% ✓
  4. $38,420 → $38,420 ✓
  5. $48,000 → $48K ✓
- Each pair uses `enter(local, startFrame + index * 12, 14)` to stagger in
- A counter in the corner: "0 → 5 numbers verified" that increments

### At the end (frames 150-170)
- Show "Guardrail passed" banner with checkmark (same as current but nicer)
- Below it: "Every reported number independently verified against source data."
- The counter shows "5 / 5 numbers verified ✓"

### Implementation details

Remove the current:
- GuardrailScene component
- GuardrailColumn component  
- GuardrailScene CSS classes (compareGrid, guardrailColumn, scanBridge, guardrailResult)

Add a new VerifyingRow component:
```tsx
const VerifyingRow = ({
  pandasValue,
  aiValue,
  verified,
  index,
  local,
  startFrame = 80,
}: {
  pandasValue: string;
  aiValue: string;
  verified: boolean;
  index: number;
  local: number;
  startFrame?: number;
}) => {
  const reveal = enter(local, startFrame + index * 12, 14);
  return (
    <div
      className="verifyingRow"
      style={{ opacity: reveal, transform: `translateX(${px((1 - reveal) * 20)})` }}
    >
      <span className="pandasVal">{pandasValue}</span>
      <span className="arrow">→</span>
      <span className="aiVal">{aiValue}</span>
      <span className="check">{verified ? "✓" : ""}</span>
    </div>
  );
};
```

### New CSS classes needed in index.css

```css
.guardrailScene {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
}

.failFlash {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(185, 28, 28, 0.08);
  border-radius: 18px;
  color: #b91c1c;
  font-size: 24px;
  font-weight: 800;
}

.retryText {
  color: #787670;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.06em;
}

.verifyList {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 28px;
  border: 1px solid rgba(37, 36, 33, 0.12);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: 0 32px 88px rgba(37, 36, 33, 0.12);
}

.verifyingRow {
  display: grid;
  grid-template-columns: 1.4fr 0.3fr 1fr 0.5fr;
  align-items: center;
  gap: 12px;
  min-height: 44px;
  font-family: "JetBrains Mono", ui-monospace, monospace;
  font-variant-numeric: tabular-nums;
  font-size: 20px;
  font-weight: 720;
}

.pandasVal {
  color: #3c3a36;
  text-align: right;
}

.arrow {
  color: #787670;
  text-align: center;
  font-size: 18px;
}

.aiVal {
  color: #252421;
}

.check {
  color: #16a066;
  font-size: 24px;
  font-weight: 800;
}

.counterBadge {
  position: absolute;
  top: 160px;
  right: 180px;
  padding: 8px 16px;
  border-radius: 20px;
  background: rgba(22, 160, 102, 0.1);
  color: #16a066;
  font-size: 14px;
  font-weight: 800;
  font-family: "JetBrains Mono", ui-monospace, monospace;
}

.passedBanner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 24px;
  border: 1px solid rgba(22, 160, 102, 0.28);
  border-radius: 12px;
  background: #edfaf3;
  color: #0a613c;
}

.passedBanner strong {
  font-size: 22px;
  font-weight: 850;
}

.passedBanner span {
  color: #0f7f50;
  font-size: 16px;
  font-weight: 680;
}

/* Mismatch column styling */
.mismatch {
  color: #b91c1c !important;
}

.ghosted {
  opacity: 0.3;
}
```

### The GuardrailScene function

```tsx
const GuardrailScene = () => {
  const frame = useCurrentFrame();
  const local = frame;
  const failIn = enter(local, 0, 12);
  const failOut = exit(local, 30, 10);
  const retryIn = enter(local, 44, 14);
  const retryOut = exit(local, 68, 12);
  const mainIn = enter(local, 80, 18);
  const counter = Math.min(
    5,
    Math.floor(Math.max(0, (local - 80) / 14))
  );
  const counterDisplay = Math.min(5, Math.max(0, Math.floor((local - 80) / 14) + 1));
  const passIn = enter(local, 145, 20);
  
  const numbers = [
    { p: "$4,730,000", a: "$4.73M", check: true },
    { p: "$101,000", a: "$101K", check: true },
    { p: "+61.0%", a: "61%", check: true },
    { p: "$38,420", a: "$38,420", check: true },
    { p: "$48,000", a: "$48K", check: true },
  ];

  return (
    <AbsoluteFill className="scene guardrailScene">
      <SceneLabel index="05" title="The Golden Rule: every number is verified before it ships" />
      
      {/* Phase 1: Failure */}
      <div className="verifyList" style={{ opacity: failIn, position: "absolute" }}>
        <VerifyingRow pandasValue="$4,730,000" aiValue="$4.80M" verified={false} index={0} local={local} startFrame={0} />
        <div className="failFlash" style={{ opacity: failIn * failOut }}>
          <span>Mismatch: $4,800,000 not found in pandas output</span>
        </div>
      </div>
      
      {/* Phase 2: Retry */}
      <div className="retryText" style={{ opacity: retryIn * retryOut, position: "absolute" }}>
        Retrying with reinforced prompt…
      </div>
      
      {/* Phase 3: Success */}
      <div className="verifyList" style={{ opacity: mainIn }}>
        {numbers.map((n, i) => (
          <VerifyingRow
            key={i}
            pandasValue={n.p}
            aiValue={n.a}
            verified={i < counterDisplay}
            index={i}
            local={local}
          />
        ))}
      </div>
      
      <div className="counterBadge" style={{ opacity: mainIn }}>
        {counterDisplay} / 5 numbers verified ✓
      </div>
      
      <div
        className="passedBanner"
        style={{ opacity: passIn, transform: `scale(${0.92 + passIn * 0.08})` }}
      >
        <strong>Guardrail passed</strong>
        <span>Every reported number independently verified against source data.</span>
      </div>
    </AbsoluteFill>
  );
};
```

IMPORTANT: You MUST also add an `exit` function near the top of Composition.tsx if it was removed before. It needs:
```tsx
const exit = (frame: number, from: number, duration = 24) =>
  interpolate(frame, [from, from + duration], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.in(Easing.cubic),
  });
```

Remove the old CSS classes from index.css:
- `.guardrailColumn`, `.compareGrid`, `.scanBridge`, `.guardrailResult`
- Also their sub-elements: `.guardrailColumn strong`, `.guardrailColumn small`, `.guardrailColumn div`, `.guardrailColumn i:nth-child(N)`, `.scanBridge span`, `.scanBridge b`

Run `npx tsc --noEmit` after changes to verify.

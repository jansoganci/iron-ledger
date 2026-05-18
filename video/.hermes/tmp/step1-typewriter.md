Refactor the NarrativeScene component in src/Composition.tsx (at /Users/jans/Desktop/nexus/iron-ledger/video).

### Change 1: Typewriter effect for narrative text
Replace the current static narrative card fade-in with a character-by-character typewriter animation.

Current code (around line 432-475):
```tsx
const NarrativeScene = () => {
  const frame = useCurrentFrame();
  const local = frame;
  const reveal = enter(local, 54, 32);
  // ... renders anomalyCard (static) + narrativeCard (fade-in)
};
```

New implementation:
1. Add a typewriter helper function:
```tsx
const typewriter = (text: string, frame: number, startFrame: number, charsPerFrame: number = 2): string => {
  const charCount = Math.floor(Math.max(0, (frame - startFrame) * charsPerFrame));
  return text.substring(0, Math.min(charCount, text.length));
};
```

2. NarrativeScene changes:
   - Remove `reveal = enter(local, 54, 32)`
   - Remove the `opacity: reveal, transform: translateY(...)` on the narrativeCard div
   - The narrativeCard should be visible from frame 0 
   - The <p> text inside narrativeCard should use:
   ```tsx
   <p>{typewriter("Travel spending increased sharply in the final week of March, matching the timing pattern of an offsite rather than a recurring run-rate change.", local, 12, 2.5)}
   {local >= 12 + Math.ceil(text.length / 2.5) && <span className="cursor">|</span>}
   </p>
   ```
   - Add a blinking cursor animation at the end (a vertical bar "|" with opacity that pulses once typing is complete)

3. Add a CSS class for the cursor:
In src/index.css, add:
```css
.cursor {
  display: inline-block;
  color: #feda9a;
  font-weight: 800;
  animation: blink 0.6s step-end infinite;
}
@keyframes blink {
  50% { opacity: 0; }
}
```

### Change 2: Earlier text start + anomaly card entrance
- The typewriter starts at frame 12 (not 54 as before)
- The anomaly card (the Travel card with the sparkline) should now slide in from the left with `enter(local, 0, 18)` opacity + translateX

### Do NOT change:
- SceneLabel, sparkline bars, metricLine numbers, cardTop labels
- The text content itself - keep exactly: "Travel spending increased sharply in the final week of March, matching the timing pattern of an offsite rather than a recurring run-rate change."

Run `npx tsc --noEmit` after changes to verify.

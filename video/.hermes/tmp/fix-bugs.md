Fix these two bugs in the Remotion video project at /Users/jans/Desktop/nexus/iron-ledger/video.

## Bug 1: TopBar fade-out never triggers (Composition.tsx)

File: `src/Composition.tsx`

Current code (around line 195-200):
```tsx
const TopBar = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [8, 34, 1030, 1080], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
```

The values `[1030, 1080]` are pre-cut source frame numbers, but the edited composition is only ~951 frames long (TOTAL_FRAMES). So the TopBar fade-out at the end of the video never runs.

Fix: Change `[8, 34, 1030, 1080]` to `[8, 34, TOTAL_FRAMES - 50, TOTAL_FRAMES]`.

Note: TOTAL_FRAMES is already imported/exported from Composition.tsx itself. Make sure it's referenced.

## Bug 2: Missing .orchestrate CSS class (index.css)

File: `src/index.css`

The OrchestrationScene uses `className="scene orchestrate"` but `.orchestrate` is missing from the CSS group selector around lines 162-170.

Current:
```css
.splitScene,
.pythonScene,
.narrativeScene,
.guardrailScene,
.reportScene,
.closingScene {
  align-items: center;
  justify-content: center;
}
```

Fix: Add `.orchestrate` to this group:
```css
.splitScene,
.pythonScene,
.narrativeScene,
.guardrailScene,
.reportScene,
.closingScene,
.orchestrate {
  align-items: center;
  justify-content: center;
}
```

Apply both fixes. Do NOT change anything else.

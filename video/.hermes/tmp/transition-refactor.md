Refactor Composition.tsx to use Remotion's built-in `<TransitionSeries>` instead of the manual crossfadeOpacity system.

**Context:** Project at /Users/jans/Desktop/nexus/iron-ledger/video
**Files to change:** src/Composition.tsx, src/Root.tsx
**Package to install:** npm install @remotion/transitions

## What to remove

Delete ALL of these (they become unnecessary):

1. `CROSSFADE_FRAMES` constant (line 11)
2. `CUTS` array (lines 13-17) — no longer needed, we control durations directly
3. `timeline` object (lines 30-69) — TransitionSeries handles timing
4. `SOURCE_TOTAL_FRAMES` and `TOTAL_FRAMES` (lines 71-73) — compute new TOTAL_FRAMES differently
5. `crossfadeOpacity` function (lines 95-97)
6. `SceneKey` type (line 99)
7. `removedBefore` function (lines 101-108)
8. `renderSceneSegments` function (lines 110-151)
9. `TimedSceneProps` type (lines 91-93) — only used by removed code
10. `Sequence` import from "remotion" (no longer needed)
11. `enter()` and `exit()` functions (lines 75-87) — keep these! They are still used for INTERNAL scene element animations (element-by-element fade-ins within each scene).

## What to add

Add these imports to the top:
```tsx
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
```

## How to restructure MonthProofShowcase

Replace the current body:

```tsx
export const MonthProofShowcase = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill className="stage">
      <Background />
      <TopBar />
      <TransitionSeries>
        <TransitionSeries.Sequence durationInFrames={sceneDurations.intro}>
          <IntroScene />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: 15 })} />
        <TransitionSeries.Sequence durationInFrames={sceneDurations.ingest}>
          <IngestScene />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: 15 })} />
        <TransitionSeries.Sequence durationInFrames={sceneDurations.orchestrate}>
          <OrchestrationScene />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: 15 })} />
        <TransitionSeries.Sequence durationInFrames={sceneDurations.python}>
          <PythonScene />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: 15 })} />
        <TransitionSeries.Sequence durationInFrames={sceneDurations.narrative}>
          <NarrativeScene />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: 15 })} />
        <TransitionSeries.Sequence durationInFrames={sceneDurations.guardrail}>
          <GuardrailScene />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: 15 })} />
        <TransitionSeries.Sequence durationInFrames={sceneDurations.report}>
          <ReportScene />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: 15 })} />
        <TransitionSeries.Sequence durationInFrames={sceneDurations.close}>
          <ClosingScene />
        </TransitionSeries.Sequence>
      </TransitionSeries>
      <ProgressRail frame={frame} />
    </AbsoluteFill>
  );
};
```

## Scene component changes

Each scene component (IntroScene, IngestScene, etc.) currently:
- Accepts `{ duration }: TimedSceneProps`
- Uses `crossfadeOpacity(local, duration)` as outer opacity wrapper

**Remove** `duration` prop and the `crossfadeOpacity` outer wrapper from each scene. The scenes should NOT be wrapped in individual fade logic anymore — TransitionSeries handles that.

Remove the `TimedSceneProps` type and use `{}` or no props for each scene component.

For example, IntroScene currently:
```tsx
const IntroScene = ({ duration }: TimedSceneProps) => {
  const frame = useCurrentFrame();
  const local = frame;
  const titleIn = enter(local, 8, 34);
  const proofIn = enter(local, 48, 28);
  const opacity = crossfadeOpacity(local, duration);
  return (
    <AbsoluteFill className="scene intro" style={{ opacity }}>
      ...
    </AbsoluteFill>
  );
};
```

Change to:
```tsx
const IntroScene = () => {
  const frame = useCurrentFrame();
  const local = frame;
  const titleIn = enter(local, 8, 34);
  const proofIn = enter(local, 48, 28);
  return (
    <AbsoluteFill className="scene intro">
      ...
    </AbsoluteFill>
  );
};
```

Do this for ALL scene components: remove `duration` prop, remove `TimedSceneProps` type reference, remove `opacity = crossfadeOpacity(...)` and its `style={{ opacity }}` on the outer element.

Keep ALL internal `enter()` calls and internal animation logic within each scene. Only remove the outer crossfadeOpacity wrapper.

## Update TOTAL_FRAMES for Root.tsx

Root.tsx imports `{ MonthProofShowcase, TOTAL_FRAMES }` and uses `durationInFrames={TOTAL_FRAMES}`.

Export a new TOTAL_FRAMES:
```tsx
export const TOTAL_FRAMES = Object.values(sceneDurations).reduce((a, b) => a + b, 0)
  - (Object.keys(sceneDurations).length - 1) * 15;
```

(8 scenes × 7 transitions = 7 × 15 = 105 frames overlap removed)

## Update Background

Background uses `TOTAL_FRAMES` for drift animation (line 175). Change it to use `useVideoConfig().durationInFrames` instead:
```tsx
const { durationInFrames } = useVideoConfig();
const drift = interpolate(frame, [0, durationInFrames], [0, 80]);
```

## Verify

After changes, run `npx tsc --noEmit` — must exit with code 0.
Run `npm run lint` — must be clean.

## Important notes

- Keep `enter()` and `exit()` functions — still used for per-element animations inside scenes
- Keep `sceneDurations` object — still used for sequence durations
- Keep `px()` helper — still used everywhere
- Keep `spring()` import — used by AgentNode
- Keep `Easing` import — used by enter/exit functions
- Keep `TimedSceneProps` ONLY IF any scene still uses `duration` prop for something other than crossfadeOpacity (check each scene carefully)
- Do NOT change index.css
- Do NOT change any other file

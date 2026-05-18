Refactor the transition system in my Remotion video (`src/Composition.tsx`) to elevate the visual style from a basic, flat cross-fade to a premium, snappy SaaS product video look (similar to Apple or Linear animations).

### Current Setup:
- We are using `@remotion/transitions` inside a `<TransitionSeries>`.
- Currently, every scene transition uses `presentation={fade()}` with `timing={linearTiming({ durationInFrames: 15 })}`. It feels too static and slow.

### Requirements:
1. **Upgrade to Spring Slide:** Replace all `presentation={fade()}` instances with `presentation={slide({ direction: "from-right" })}`.
2. **Apply Premium Spring Timing:** Replace `linearTiming` with `springTiming` using a snappy, high-end configuration to give the transition physical weight and momentum:
   ```tsx
   springTiming({
     config: { damping: 24, stiffness: 140, mass: 0.8 }
   })
   ```
3. **Handle Imports:** Ensure `springTiming` is correctly imported from `@remotion/transitions` and `slide` is imported from `@remotion/transitions/slide`. Clean up unused `fade` and `linearTiming` imports.
4. **Preserve Content:** Only change the `<TransitionSeries.Transition/>` elements and their imports. Do not modify the inner logic, timing, or animations of individual scenes (IntroScene, IngestScene, etc.). Ensure the code compiles cleanly without TypeScript errors.

Run `npx tsc --noEmit` after changes to verify.

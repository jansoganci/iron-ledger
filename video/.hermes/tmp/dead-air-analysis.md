Analyze `src/Composition.tsx` and give feedback about a specific problem.

### Context
This is a Remotion v4 product showcase video (8 scenes, 1920x1080, 30fps). Each scene has internal `enter()` animations that stagger elements in (fade + translateY). Once all elements are in, the scene sits idle until the transition fires.

### The Problem
In three specific scenes, there is dead air — the screen is completely static (no animation happening) for the last ~30-60 frames before the transition. The user wants to identify exactly where this happens and what to do about it.

### Time ranges (in seconds, at 30fps):
1. **Python scene** — around **16.0s to 17.3s** (frames ~480-520): After the code window, ledger table, and python callout have all animated in, the scene sits idle until it transitions to Narrative.
2. **Narrative scene** — around **21.3s to 23.0s** (frames ~640-690): After the anomaly card and narrative card have animated in, the scene sits idle.
3. **Report scene** — around **31.15s to 33.0s** (frames ~935-990): After the 3 mini report cards have animated in, the scene sits idle.

### What the user wants to know
1. Look at each of these three scenes (PythonScene, NarrativeScene, ReportScene) and identify the exact frames where the LAST internal `enter()` animation finishes.
2. Confirm that after that point, the scene has no motion — only the outer crossfade (which is now handled by TransitionSeries, not the scene itself).
3. The user is considering: **reducing sceneDurations** for these three scenes to trim the dead air at the end. Would this work? Would it break anything?
4. Everything OUTSIDE these three time ranges is working correctly — the transitions are smooth, the timing feels right, and the other 5 scenes have no dead air.

### Output format
Please give a structured analysis:
- For each of the 3 scenes: when does the last animation finish?
- How many frames of dead air exist?
- Recommendation: can we safely reduce sceneDurations without breaking internal animations?
- Any alternative suggestions?

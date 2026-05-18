Fix the sparkline bars in NarrativeScene (src/Composition.tsx at /Users/jans/Desktop/nexus/iron-ledger/video).

### The Problem
The sparkline bars are currently computed with `(index * 17) % 44` which produces random oscillating bar heights. A first-time viewer sees noise, not data.

### The Fix
Replace the bar height calculation with actual 6-month trailing average data that tells a story: steady historical values, then a sharp spike.

Current code (around line 450-458):
```tsx
<div className="sparkline">
  {Array.from({ length: 18 }).map((_, index) => (
    <i
      key={index}
      style={{
        height: `${28 + ((index * 17) % 44) + (index > 13 ? 42 : 0)}px`,
      }}
    />
  ))}
</div>
```

Replace with:
```tsx
<div className="sparkline">
  {[48, 50, 52, 49, 51, 48, 50, 53, 47, 52, 50, 49, 55, 62, 78, 101, 118, 130].map((value, index) => (
    <i
      key={index}
      style={{
        height: `${value * 0.85 + 20}px`,
        background: index < 14
          ? "linear-gradient(180deg, #f08408, #feda9a)"
          : "linear-gradient(180deg, #b91c1c, #f08408)",
      }}
    />
  ))}
</div>
```

The data: first 14 bars = steady ~$48-55K range (historical 6-month averages), last 4 bars = spike from $62K → $130K (the March anomaly). The last 4 bars use a red-tinted gradient to visually highlight the anomaly.

Do NOT change anything else in the NarrativeScene.

Run `npx tsc --noEmit` after changes to verify.

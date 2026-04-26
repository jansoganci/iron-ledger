import { CheckCircle, Circle, Loader2 } from "lucide-react";
import { cn } from "../lib/utils";

const QUARTERLY_STEPS = [
  { label: "Fetching quarterly runs..." },
  { label: "Aggregating monthly data..." },
  { label: "Analyzing anomalies..." },
  { label: "Fetching prior year data..." },
  { label: "Computing aggregates..." },
  { label: "Calling Claude Opus..." },
  { label: "Verifying numbers..." },
];

interface QuarterlyProgressProps {
  progressPct: number;
  stepLabel: string;
}

export function QuarterlyProgress({
  progressPct,
  stepLabel,
}: QuarterlyProgressProps) {
  // Map progress % to step index
  const getActiveStepIndex = (): number => {
    if (progressPct <= 10) return 0;
    if (progressPct <= 65) return 1;
    if (progressPct <= 70) return 2;
    if (progressPct <= 75) return 3;
    if (progressPct <= 85) return 4;
    if (progressPct <= 95) return 5;
    return 6;
  };

  const activeStep = getActiveStepIndex();

  function getStepState(idx: number): "done" | "active" | "pending" {
    if (progressPct === 100) return "done";
    if (idx < activeStep) return "done";
    if (idx === activeStep) return "active";
    return "pending";
  }

  return (
    <div className="w-full max-w-md mx-auto space-y-4 px-4">
      <div className="text-center space-y-2">
        <Loader2 className="h-8 w-8 text-accent animate-spin mx-auto" />
        <h2 className="text-lg font-semibold text-text-primary">
          Generating Quarterly Summary
        </h2>
        <p className="text-sm text-text-secondary">{stepLabel}</p>
      </div>

      <div className="space-y-3 mt-6">
        {QUARTERLY_STEPS.map((step, idx) => {
          const state = getStepState(idx);

          return (
            <div
              key={idx}
              className={cn(
                "flex items-center gap-3 transition-all duration-300",
                state === "active" && "scale-[1.02]"
              )}
            >
              {state === "done" ? (
                <CheckCircle
                  className="h-4 w-4 text-favorable-fg shrink-0"
                  aria-hidden
                />
              ) : state === "active" ? (
                <Loader2
                  className="h-4 w-4 text-accent shrink-0 animate-spin"
                  aria-hidden
                />
              ) : (
                <Circle
                  className="h-4 w-4 text-text-secondary shrink-0 opacity-40"
                  aria-hidden
                />
              )}
              <span
                className={cn(
                  "text-sm flex-1 transition-all duration-300",
                  state === "done" && "text-text-secondary line-through",
                  state === "active" && "text-text-primary font-medium",
                  state === "pending" && "text-text-secondary"
                )}
              >
                {step.label}
              </span>
            </div>
          );
        })}
      </div>

      <div className="mt-6 space-y-2">
        <div className="flex justify-between text-xs text-text-secondary">
          <span>Progress</span>
          <span className="tabular-nums font-medium text-accent">
            {progressPct}%
          </span>
        </div>
        <div className="h-2 rounded-full bg-border overflow-hidden">
          <div
            className="h-full rounded-full bg-accent transition-all duration-500 ease-out"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>
    </div>
  );
}

import { Check, Clock, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { apiFetch, RateLimitedError } from "../lib/api";
import { useToast } from "./ToastProvider";
import { cn } from "../lib/utils";

const STEPS = [
  { status: "parsing", label: "Reading files..." },
  { status: "discovering", label: "Analyzing structure..." },
  { status: "mapping", label: "Mapping accounts..." },
  { status: "comparing", label: "Comparing to history..." },
  { status: "generating", label: "Generating report..." },
];

const TERMINAL_FAILED = new Set([
  "upload_failed",
  "parsing_failed",
]);

import type { LowConfidenceColumn } from "./MappingConfirmPanel";

export interface PreviewRowSource {
  source_file: string;
  amount: number;
}

export interface PreviewRow {
  account: string;
  amount: number;
  category: string;
  confidence: number;
  source_breakdown?: PreviewRowSource[];
}

export interface DropReason {
  row_index: number;
  account_snippet: string;
  reason: "amount_coerce_failed" | "subtotal_safety_net";
}

export interface NormalizerDropReport {
  entries: DropReason[];
  total_dropped: number;
}

export interface ParsePreview {
  rows: PreviewRow[];
  source_column: string;
  // Optional so pre-Step-10 runs render without crashing.
  drops?: NormalizerDropReport;
}

interface RunStatusResponse {
  run_id: string;
  status: string;
  step: number;
  total_steps: number;
  progress_pct: number;
  step_label: string;
  error_message: string | null;
  report_id: string | null;
  raw_data_url: string | null;
  low_confidence_columns: LowConfidenceColumn[];
  parse_preview: ParsePreview | null;
  mapping_draft: MappingDraft | null;
  discovery_plan: DiscoveryPlanPayload | null;
}

export interface MappingDraftItem {
  source_pattern: string;
  source_file: string;
  file_type: string;
  suggested_gl_account: string | null;
  confident: boolean;
}

export interface MappingDraft {
  items: MappingDraftItem[];
  gl_account_pool: string[];
}

export interface DiscoveryHierarchyHint {
  row_index: number;
  parent_category: string;
}

export interface DiscoveryPlanPayload {
  header_row_index: number;
  skip_row_indices: number[];
  column_mapping: Record<string, string | null>;
  hierarchy_hints: DiscoveryHierarchyHint[];
  discovery_confidence: number;
  notes?: string;
  _preview?: string[][];
}

interface LoadingProgressProps {
  runId: string;
  period: string;
  processingMode?: "default" | "post-discovery";
  onGuardrailFailed: (runId: string, rawDataUrl: string | null, errorMessage: string | null) => void;
  onAwaitingConfirmation?: (runId: string, preview: ParsePreview) => void;
  onAwaitingMappingConfirmation?: (runId: string, draft: MappingDraft) => void;
  onAwaitingDiscoveryConfirmation?: (
    runId: string,
    plan: DiscoveryPlanPayload
  ) => void;
  onTerminalFailure: (status: string, message: string) => void;
}

function statusToStepIndex(status: string): number {
  // awaiting_confirmation and awaiting_discovery_confirmation are not discrete 
  // steps — the parent swaps to preview view. For progress, they sit inside their steps.
  if (status === "awaiting_confirmation") {
    return STEPS.findIndex((s) => s.status === "mapping");
  }
  if (status === "awaiting_discovery_confirmation") {
    return STEPS.findIndex((s) => s.status === "discovering");
  }
  return STEPS.findIndex((s) => s.status === status);
}

export function LoadingProgress({
  runId,
  period,
  processingMode = "default",
  onGuardrailFailed,
  onAwaitingConfirmation,
  onAwaitingMappingConfirmation,
  onAwaitingDiscoveryConfirmation,
  onTerminalFailure,
}: LoadingProgressProps) {
  const navigate = useNavigate();
  const toast = useToast();
  const [smoothProgress, setSmoothProgress] = useState<Record<number, number>>({});
  const [optimisticProgress, setOptimisticProgress] = useState(40);
  const [elapsedWarning, setElapsedWarning] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setElapsedWarning(true), 90_000);
    return () => clearTimeout(timer);
  }, []);

  const isTerminal = (status: string) =>
    status === "complete" ||
    status === "guardrail_failed" ||
    status === "awaiting_mapping_confirmation" ||
    status === "awaiting_confirmation" ||
    status === "awaiting_discovery_confirmation" ||
    TERMINAL_FAILED.has(status);

  const shouldUseFastPolling = (status?: string) => {
    // Fast polling is only needed during the short post-discovery handoff.
    if (processingMode !== "post-discovery") return false;
    return status === "mapping" || status === "discovering" || status === "pending";
  };

  const { data, error, isFetchedAfterMount } = useQuery<RunStatusResponse>({
    queryKey: ["run-status", runId],
    queryFn: () => apiFetch<RunStatusResponse>(`/runs/${runId}/status`),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (!status || isTerminal(status)) return false;
      return shouldUseFastPolling(status) ? 800 : 4000;
    },
    retry: (count, err) => {
      if (err instanceof RateLimitedError) return false;
      return count < 3;
    },
  });

  const isPostDiscoveryOptimistic =
    processingMode === "post-discovery" && !isFetchedAfterMount;

  // Immediately show "working" motion on post-discovery remount, even before
  // the first network poll completes.
  useEffect(() => {
    if (!isPostDiscoveryOptimistic) return;

    setOptimisticProgress(40);
    const interval = setInterval(() => {
      setOptimisticProgress((prev) => Math.min(prev + 2, 58));
    }, 220);

    return () => clearInterval(interval);
  }, [isPostDiscoveryOptimistic]);

  useEffect(() => {
    if (!data) return;
    const {
      status,
      raw_data_url,
      error_message,
      parse_preview,
      mapping_draft,
      discovery_plan,
    } = data;

    if (status === "complete") {
      navigate(`/report/${period}`, {
        state: {
          runId,
          lowConfidenceColumns: data.low_confidence_columns ?? [],
        },
      });
      return;
    }
    if (status === "guardrail_failed") {
      onGuardrailFailed(runId, raw_data_url, error_message);
      return;
    }
    if (status === "awaiting_mapping_confirmation" && mapping_draft) {
      onAwaitingMappingConfirmation?.(runId, mapping_draft);
      return;
    }
    if (status === "awaiting_discovery_confirmation") {
      if (discovery_plan) {
        onAwaitingDiscoveryConfirmation?.(runId, discovery_plan);
      } else {
        onTerminalFailure(
          status,
          "We need your review, but we could not load the file structure preview. Please try uploading again."
        );
      }
      return;
    }
    if (status === "awaiting_confirmation" && parse_preview) {
      onAwaitingConfirmation?.(runId, parse_preview);
      return;
    }
    if (TERMINAL_FAILED.has(status)) {
      onTerminalFailure(
        status,
        error_message ?? "Something went wrong. Please try uploading again."
      );
    }
  }, [data?.status]);

  // Smooth progress animation
  useEffect(() => {
    if (!data) return;
    
    const activeStep = statusToStepIndex(data.status);
    if (activeStep === -1) return;
    
    const targetProgress = data.progress_pct;
    const currentProgress = smoothProgress[activeStep] ?? 0;
    
    if (currentProgress >= targetProgress) {
      setSmoothProgress(prev => ({ ...prev, [activeStep]: targetProgress }));
      return;
    }
    
    const interval = setInterval(() => {
      setSmoothProgress(prev => {
        const current = prev[activeStep] ?? 0;
        if (current < targetProgress) {
          const increment = Math.max(1, Math.ceil((targetProgress - current) / 20));
          return { ...prev, [activeStep]: Math.min(current + increment, targetProgress) };
        }
        return prev;
      });
    }, 50);
    
    return () => clearInterval(interval);
  }, [data?.progress_pct, data?.status]);

  useEffect(() => {
    if (!error) return;
    if (error instanceof RateLimitedError) {
      toast.warning("You're sending a lot of requests — please wait a moment.");
    } else {
      toast.error("We lost connection while checking your report. Please refresh.");
    }
  }, [error]);

  const currentStatus = data?.status ?? "pending";
  const effectiveStatus = isPostDiscoveryOptimistic ? "mapping" : currentStatus;
  const activeStep = statusToStepIndex(effectiveStatus);

  function getStepState(idx: number): "done" | "active" | "pending" {
    if (activeStep === -1) {
      if (effectiveStatus === "complete") return "done";
      return "pending";
    }
    if (idx < activeStep) return "done";
    if (idx === activeStep) return "active";
    return "pending";
  }

  return (
    <div className="w-full">
      {/* ── Header: eyebrow + title + time hint ─────────────────────────── */}
      <div className="text-center mb-8">
        <div className="font-data text-xs text-violet-500 uppercase tracking-[0.10em] flex items-center justify-center gap-1.5 mb-3">
          <span
            className="step-dot-blink inline-block w-1.5 h-1.5 rounded-full bg-violet-500 shrink-0"
            aria-hidden
          />
          Agent · Processing
        </div>
        <h2 className="font-hero-num text-2xl font-semibold text-text-primary">
          Analyzing your data
        </h2>
        <p className="text-xs text-text-secondary mt-2 flex items-center justify-center gap-1.5">
          <Clock className="h-3 w-3 shrink-0" aria-hidden />
          {elapsedWarning
            ? "Still working — complex files take a bit longer"
            : "Usually under 2 minutes"}
        </p>
      </div>

      {/* ── Steps ──────────────────────────────────────────────────────── */}
      <div>
        {STEPS.map((step, idx) => {
          const state = getStepState(idx);
          const isLast = idx === STEPS.length - 1;
          const displayProgress =
            isPostDiscoveryOptimistic && idx === activeStep
              ? optimisticProgress
              : (smoothProgress[idx] ?? 0);
          const isCompleting = state === "active" && displayProgress >= 99;

          return (
            <div key={step.status} className="flex gap-4">
              {/* Left col: icon + connector */}
              <div className="flex flex-col items-center w-9 shrink-0">
                <div
                  className={cn(
                    "w-9 h-9 rounded-full flex items-center justify-center shrink-0",
                    "[transition:background-color,box-shadow]",
                    "[transition-duration:var(--duration-base)]",
                    state === "pending" && "bg-neutral-100 border border-border",
                    state === "active" && "bg-violet-500 step-icon-active",
                    state === "done" && "bg-emerald-500 step-icon-done"
                  )}
                >
                  {state === "active" && (
                    <Loader2
                      className={cn(
                        "h-4 w-4 text-white shrink-0",
                        isCompleting ? "animate-pulse" : "animate-spin"
                      )}
                      aria-hidden
                    />
                  )}
                  {state === "done" && (
                    <Check className="h-4 w-4 text-white shrink-0" aria-hidden />
                  )}
                </div>

                {!isLast && (
                  <div className="relative w-0.5 flex-1 min-h-[24px] my-1 bg-border overflow-hidden">
                    {state === "done" && <div className="step-connector-fill" />}
                  </div>
                )}
              </div>

              {/* Right col: label + microcopy + progress bar */}
              <div className={cn("flex-1 pt-2", !isLast && "pb-6")}>
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      "text-sm [transition:color_var(--duration-base)]",
                      state === "done" && "text-emerald-700 line-through",
                      state === "active" && "text-text-primary font-medium",
                      state === "pending" && "text-text-secondary"
                    )}
                  >
                    {step.label}
                  </span>
                  {state === "active" && (
                    <span
                      className="font-data text-xs text-violet-500 ml-auto tabular-nums"
                      data-numeric
                    >
                      {displayProgress}%
                    </span>
                  )}
                  {state === "done" && (
                    <span className="font-data text-xs text-emerald-600 font-medium ml-auto animate-in fade-in">
                      ✓
                    </span>
                  )}
                </div>

                {/* Active step microcopy from API */}
                {state === "active" && data?.step_label && !isPostDiscoveryOptimistic && (
                  <p
                    key={data.step_label}
                    className="font-data text-xs text-violet-600 mt-1 step-microcopy-in truncate"
                  >
                    {data.step_label}
                  </p>
                )}

                {/* Per-step progress bar */}
                {state === "active" && (
                  <div className="mt-2 h-1 rounded-full bg-border overflow-hidden">
                    <div
                      className={cn(
                        "h-full rounded-full",
                        "[transition:width_var(--duration-base)_var(--ease-out)]",
                        isCompleting
                          ? "bg-gradient-to-r from-violet-500 to-emerald-400 animate-pulse"
                          : "bg-violet-500"
                      )}
                      style={{ width: `${displayProgress}%` }}
                    />
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* ── Footer: skip button ─────────────────────────────────────────── */}
      <div className="mt-8 text-center">
        <button
          onClick={() => navigate(`/report/${period}`)}
          className={cn(
            "text-xs text-text-secondary hover:text-text-primary",
            "[transition:color_var(--duration-base)]",
            "focus:outline-none focus-ring-agent rounded-sm px-1"
          )}
        >
          Skip for now →
        </button>
      </div>
    </div>
  );
}

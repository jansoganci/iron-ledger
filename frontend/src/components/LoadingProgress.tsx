import { CheckCircle, Circle, Loader2 } from "lucide-react";
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
    <div className="w-full md:max-w-sm md:mx-auto space-y-3 px-0 md:px-0">
      <p className="text-sm font-medium text-text-secondary text-center">
        Analyzing your file…
      </p>

      {STEPS.map((step, idx) => {
        const state = getStepState(idx);
        const displayProgress =
          isPostDiscoveryOptimistic && idx === activeStep
            ? optimisticProgress
            : (smoothProgress[idx] ?? 0);
        const isCompleting = state === "active" && displayProgress >= 99;
        
        return (
          <div 
            key={step.status} 
            className={cn(
              "space-y-1 transition-all duration-300",
              state === "active" && "scale-[1.02]"
            )}
          >
            <div className="flex items-center gap-3">
              {state === "done" ? (
                <div className="relative">
                  <CheckCircle 
                    className={cn(
                      "h-4 w-4 text-favorable-fg shrink-0 transition-all duration-300",
                      "animate-in zoom-in-50"
                    )} 
                    aria-hidden 
                  />
                  <div className="absolute inset-0 h-4 w-4 rounded-full bg-favorable-fg/20 animate-ping" />
                </div>
              ) : state === "active" ? (
                <div className="relative">
                  <Loader2 
                    className={cn(
                      "h-4 w-4 text-accent shrink-0",
                      isCompleting ? "animate-pulse" : "animate-spin"
                    )} 
                    aria-hidden 
                  />
                  {!isCompleting && (
                    <div className="absolute inset-0 h-4 w-4 rounded-full bg-accent/10 animate-pulse" />
                  )}
                </div>
              ) : (
                <Circle className="h-4 w-4 text-text-secondary shrink-0 opacity-40" aria-hidden />
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
              {state === "done" && (
                <span className="text-xs text-favorable-fg font-medium animate-in fade-in slide-in-from-right-2">
                  100%
                </span>
              )}
              {state === "active" && (
                <span className="text-xs text-accent font-medium tabular-nums" data-numeric>
                  {displayProgress}%
                </span>
              )}
            </div>

            {state === "active" && (
              <div className="ml-7 h-1.5 rounded-full bg-border overflow-hidden">
                <div
                  className={cn(
                    "h-full rounded-full transition-all duration-300 ease-out",
                    isCompleting 
                      ? "bg-gradient-to-r from-accent to-favorable-fg animate-pulse" 
                      : "bg-accent"
                  )}
                  style={{ width: `${displayProgress}%` }}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

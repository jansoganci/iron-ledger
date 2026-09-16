import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { AlertCircle } from "lucide-react";
import { apiFetch, ApiError, RateLimitedError } from "../lib/api";
import { formatPeriod, monthsAgo } from "../lib/formatters";
import { FileUpload } from "../components/FileUpload";
import { PeriodSelector } from "../components/PeriodSelector";
import { LoadingProgress } from "../components/LoadingProgress";
import { GuardrailWarning } from "../components/GuardrailWarning";
import { EmptyState } from "../components/EmptyState";
import { ParsePreviewPanel } from "../components/ParsePreviewPanel";
import { MappingReview } from "../components/MappingReview";
import { DiscoveryReview } from "../components/DiscoveryReview";
import { useToast } from "../components/ToastProvider";
import { useCompany } from "../hooks/useCompany";
import { cn } from "../lib/utils";
import type {
  DiscoveryPlanPayload,
  MappingDraft,
  ParsePreview,
} from "../components/LoadingProgress";

interface HasHistoryResponse {
  has_history: boolean;
  periods_loaded: number;
}

type PageView =
  | "upload"
  | "processing"
  | "discovery-review"
  | "mapping-review"
  | "preview"
  | "guardrail-failed"
  | "terminal-failed";

type ProcessingMode = "default" | "post-discovery";

interface GuardrailState {
  runId: string;
  rawDataUrl: string | null;
  errorMessage: string | null;
}

interface TerminalFailureState {
  status: string;
  message: string;
}

export default function UploadPage() {
  const toast = useToast();
  const { data: company } = useCompany();
  const [searchParams] = useSearchParams();

  const [view, setView] = useState<PageView>("upload");
  const [period, setPeriod] = useState(monthsAgo(0));
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [processingMode, setProcessingMode] = useState<ProcessingMode>("default");
  const [parsePreview, setParsePreview] = useState<ParsePreview | null>(null);
  const [discoveryPlan, setDiscoveryPlan] = useState<DiscoveryPlanPayload | null>(null);
  const [mappingDraft, setMappingDraft] = useState<MappingDraft | null>(null);
  const [guardrailState, setGuardrailState] = useState<GuardrailState | null>(null);
  const [terminalFailure, setTerminalFailure] =
    useState<TerminalFailureState | null>(null);
  const [showRegenerateModal, setShowRegenerateModal] = useState(false);
  const [previewRegenerate, setPreviewRegenerate] = useState(false);
  const [cooldownUntil, setCooldownUntil] = useState<number | null>(null);
  const [cooldownLeft, setCooldownLeft] = useState(0);
  // Track runs that have already been confirmed so we don't re-show preview on remount
  const [confirmedRuns, setConfirmedRuns] = useState<Set<string>>(new Set());
  // Track runs whose mapping has been confirmed — prevents MappingReview re-appearing
  // while Phase B is still running (APPLYING_MAPPING status, ~20s re-parse window).
  const [confirmedMappingRuns, setConfirmedMappingRuns] = useState<Set<string>>(new Set());

  const { data: historyData, refetch: refetchHistory } = useQuery<HasHistoryResponse>({
    queryKey: ["has-history"],
    queryFn: () => apiFetch<HasHistoryResponse>("/companies/me/has-history"),
    staleTime: 30_000,
  });

  useEffect(() => {
    const fromQuery = searchParams.get("period");
    if (fromQuery) setPeriod(fromQuery);
  }, [searchParams]);

  // Rate-limit countdown ticker
  useEffect(() => {
    if (!cooldownUntil) return;
    const tick = () => {
      const left = Math.ceil((cooldownUntil - Date.now()) / 1000);
      if (left <= 0) {
        setCooldownUntil(null);
        setCooldownLeft(0);
      } else {
        setCooldownLeft(left);
      }
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [cooldownUntil]);

  const cooldownActive = cooldownLeft > 0;
  const canSubmit = selectedFiles.length > 0 && !!period && !isUploading && !cooldownActive;

  async function periodHasVerifiedReport(): Promise<boolean> {
    if (!company?.id || !period) return false;
    try {
      await apiFetch(`/report/${company.id}/${period}`);
      return true;
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) return false;
      throw err;
    }
  }

  async function startUpload(regenerate: boolean) {
    if (selectedFiles.length === 0 || !period || cooldownActive) return;
    setIsUploading(true);
    setUploadError(null);

    const fd = new FormData();
    selectedFiles.forEach((f) => fd.append("files", f));
    fd.append("period", period);
    fd.append("regenerate", regenerate ? "true" : "false");

    try {
      const res = await apiFetch<{ run_id: string }>("/upload", {
        method: "POST",
        body: fd,
      });
      setCurrentRunId(res.run_id);
      setProcessingMode("default");
      setView("processing");
    } catch (err) {
      if (err instanceof RateLimitedError) {
        setCooldownUntil(Date.now() + err.retryAfterSeconds * 1000);
        toast.warning(
          `You're sending a lot of requests — please wait ${err.retryAfterSeconds} seconds.`
        );
      } else {
        const msg =
          err instanceof Error ? err.message : "Upload failed. Please try again.";
        setUploadError(msg);
      }
    } finally {
      setIsUploading(false);
    }
  }

  async function handleAnalyze() {
    if (!canSubmit) return;
    setIsUploading(true);
    setUploadError(null);
    try {
      const exists = await periodHasVerifiedReport();
      if (exists) {
        setIsUploading(false);
        setShowRegenerateModal(true);
        return;
      }
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Upload failed. Please try again.";
      setUploadError(msg);
      setIsUploading(false);
      return;
    }
    await startUpload(false);
  }

  function handleRegenerateCancel() {
    setShowRegenerateModal(false);
  }

  async function handleRegenerateConfirm() {
    setShowRegenerateModal(false);
    await startUpload(true);
  }

  function handleAwaitingMappingConfirmation(runId: string, draft: MappingDraft) {
    if (confirmedRuns.has(runId)) return;
    if (confirmedMappingRuns.has(runId)) return; // already confirmed, Phase B still running
    setMappingDraft(draft);
    setView("mapping-review");
  }

  function handleAwaitingDiscoveryConfirmation(runId: string, plan: DiscoveryPlanPayload) {
    if (confirmedRuns.has(runId)) return;
    setDiscoveryPlan(plan);
    setView("discovery-review");
  }

  function handleDiscoveryApproved() {
    setDiscoveryPlan(null);
    // Speed up polling right after discovery approval so mapping progress
    // is visible even when this stage completes quickly.
    setProcessingMode("post-discovery");
    setView("processing");
  }

  function handleDiscoveryRejected() {
    setDiscoveryPlan(null);
    setTerminalFailure({
      status: "parsing_failed",
      message: "You rejected our reading of this file. Please try a different export.",
    });
    setView("terminal-failed");
  }

  function handleMappingConfirmed() {
    // Record that this run's mapping was confirmed so we don't re-show MappingReview
    // if polling fires again before Phase B transitions the status away from
    // applying_mapping.
    if (currentRunId) {
      setConfirmedMappingRuns((prev) => new Set([...prev, currentRunId]));
    }
    setMappingDraft(null);
    setProcessingMode("default");
    setView("processing");
  }

  function handleAwaitingConfirmation(runId: string, preview: ParsePreview, regenerate: boolean) {
    if (confirmedRuns.has(runId)) return;
    setParsePreview(preview);
    setPreviewRegenerate(regenerate);
    setView("preview");
  }

  function handleConfirmed() {
    if (currentRunId) {
      setConfirmedRuns((prev) => new Set([...prev, currentRunId]));
    }
    setProcessingMode("default");
    setView("processing");
  }

  function handleGuardrailFailed(
    runId: string,
    rawDataUrl: string | null,
    errorMessage: string | null
  ) {
    setProcessingMode("default");
    setGuardrailState({ runId, rawDataUrl, errorMessage });
    setView("guardrail-failed");
  }

  function handleTerminalFailure(status: string, message: string) {
    setProcessingMode("default");
    setTerminalFailure({ status, message });
    setView("terminal-failed");
  }

  function handleTryAgain() {
    setTerminalFailure(null);
    setCurrentRunId(null);
    setParsePreview(null);
    setPreviewRegenerate(false);
    setProcessingMode("default");
    setSelectedFiles([]);
    setUploadError(null);
    setView("upload");
  }

  function handleRetry(newRunId: string) {
    setCurrentRunId(newRunId);
    setProcessingMode("default");
    setGuardrailState(null);
    setParsePreview(null);
    setView("processing");
  }

  function handleBaselineUploaded() {
    refetchHistory();
    setView("upload");
    setSelectedFiles([]);
  }

  // EmptyState bypass: multi-file reconciliation doesn't require prior history.

  // Guardrail failure screen
  if (view === "guardrail-failed" && guardrailState) {
    return (
      <div className="px-4 py-10">
        <GuardrailWarning
          runId={guardrailState.runId}
          period={period}
          rawDataUrl={guardrailState.rawDataUrl}
          errorMessage={guardrailState.errorMessage}
          onRetry={handleRetry}
        />
      </div>
    );
  }

  // Preview screen — user reviews parsed data before DB write
  if (view === "preview" && parsePreview && currentRunId) {
    return (
      <div className="px-4 py-8 md:py-10">
        <div className="max-w-2xl mx-auto bg-surface border border-border rounded-lg p-4 md:p-6 shadow-sm">
          <ParsePreviewPanel
            runId={currentRunId}
            preview={parsePreview}
            regenerate={previewRegenerate}
            onConfirmed={handleConfirmed}
          />
        </div>
      </div>
    );
  }

  // Terminal-failed view — inline error card with retry, no toast
  if (view === "terminal-failed" && terminalFailure) {
    return (
      <div className="px-4 py-10">
        <div
          role="alert"
          className="max-w-md mx-auto rounded-lg border border-severity-high-fg bg-severity-high-bg text-severity-high-fg p-6 space-y-4"
        >
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 mt-0.5 shrink-0" aria-hidden />
            <div className="space-y-1">
              <h2 className="text-base font-semibold">
                We couldn't finish analyzing your file
              </h2>
              <p className="text-sm">{terminalFailure.message}</p>
            </div>
          </div>
          <button
            onClick={handleTryAgain}
            className={cn(
              "w-full rounded-md bg-severity-high-fg px-4 py-2 text-sm font-medium text-white",
              "hover:opacity-90 transition-opacity",
              "focus:outline-none focus:ring-2 focus:ring-severity-high-fg focus:ring-offset-2"
            )}
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  if (view === "discovery-review" && discoveryPlan && currentRunId) {
    return (
      <DiscoveryReview
        runId={currentRunId}
        plan={discoveryPlan}
        onApproved={handleDiscoveryApproved}
        onRejected={handleDiscoveryRejected}
      />
    );
  }

  // Mapping review — AI suggested GL accounts, user approves before consolidation
  if (view === "mapping-review" && mappingDraft && currentRunId) {
    return (
      <MappingReview
        runId={currentRunId}
        draft={mappingDraft}
        onConfirmed={handleMappingConfirmed}
      />
    );
  }

  // Processing view
  if (view === "processing" && currentRunId) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-3.5rem)] px-4">
        <div className="w-full max-w-sm bg-surface border border-border rounded-lg p-8 shadow-sm">
          <LoadingProgress
            runId={currentRunId}
            period={period}
            processingMode={processingMode}
            onGuardrailFailed={handleGuardrailFailed}
            onAwaitingConfirmation={handleAwaitingConfirmation}
            onAwaitingMappingConfirmation={handleAwaitingMappingConfirmation}
            onAwaitingDiscoveryConfirmation={handleAwaitingDiscoveryConfirmation}
            onTerminalFailure={handleTerminalFailure}
          />
        </div>
      </div>
    );
  }

  // Default upload form
  return (
    <div className="px-4 py-8 md:py-10">
      <div className="max-w-md lg:max-w-2xl mx-auto bg-surface border border-border rounded-lg p-4 md:p-6 shadow-sm space-y-5">
        <FileUpload
          onFilesSelected={setSelectedFiles}
          isUploading={isUploading}
          serverError={uploadError}
          disabled={isUploading}
        />

        <PeriodSelector value={period} onChange={setPeriod} disabled={isUploading} />

        {company && (
          <div className="space-y-1">
            <span className="block text-sm font-medium text-text-primary">Company</span>
            <span className="block text-sm text-text-secondary">{company.name}</span>
          </div>
        )}

        <button
          onClick={handleAnalyze}
          disabled={!canSubmit}
          className={cn(
            "w-full rounded-md bg-accent px-4 py-2.5 text-sm font-medium text-white",
            "hover:bg-accent/90 transition-colors",
            "focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2",
            !canSubmit && "opacity-50 cursor-not-allowed"
          )}
        >
          {cooldownActive
            ? `Wait ${cooldownLeft}s…`
            : isUploading
            ? "Uploading…"
            : "Analyze"}
        </button>
      </div>

      {showRegenerateModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4"
          role="presentation"
          onClick={handleRegenerateCancel}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="regenerate-title"
            className="w-full max-w-md rounded-lg border border-border bg-surface p-6 shadow-sm space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="regenerate-title" className="text-base font-semibold text-text-primary">
              Replace the {formatPeriod(period)} report?
            </h2>
            <p className="text-sm text-text-secondary">
              This month already has a verified report. If you continue, you will
              review the new files first. After you confirm the preview, the
              numbers change. If verification passes, this report is replaced.
            </p>
            <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
              <button
                type="button"
                onClick={handleRegenerateCancel}
                className={cn(
                  "w-full sm:w-auto rounded-md border border-border px-4 py-2 text-sm font-medium text-text-primary",
                  "hover:bg-neutral-100 transition-colors",
                  "focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2"
                )}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleRegenerateConfirm}
                className={cn(
                  "w-full sm:w-auto rounded-md bg-accent px-4 py-2 text-sm font-medium text-white",
                  "hover:bg-accent/90 transition-colors",
                  "focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2"
                )}
              >
                Replace this report
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

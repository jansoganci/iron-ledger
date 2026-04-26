import { CheckCircle, Folder } from "lucide-react";
import { useState } from "react";
import { apiFetch } from "../lib/api";
import { monthsAgo } from "../lib/formatters";
import { FileUpload } from "./FileUpload";
import { PeriodSelector } from "./PeriodSelector";
import { cn } from "../lib/utils";

interface EmptyStateProps {
  onBaselineUploaded: () => void;
}

export function EmptyState({ onBaselineUploaded }: EmptyStateProps) {
  const [period, setPeriod] = useState(monthsAgo(2));
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploaded, setUploaded] = useState(false);

  const canSubmit = selectedFiles.length > 0 && period && !isUploading;

  async function handleUpload() {
    if (!canSubmit) return;
    setIsUploading(true);
    setUploadError(null);

    const fd = new FormData();
    selectedFiles.forEach((f) => fd.append("files", f));
    fd.append("period", period);

    try {
      await apiFetch("/upload", { method: "POST", body: fd });
      setUploaded(true);
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Upload failed. Please try again.";
      setUploadError(msg);
    } finally {
      setIsUploading(false);
    }
  }

  if (uploaded) {
    return (
      <div className="max-w-lg mx-auto text-center space-y-5">
        <div className="flex justify-center">
          <div className="rounded-full bg-favorable-bg p-4">
            <CheckCircle className="h-8 w-8 text-favorable-fg" aria-hidden />
          </div>
        </div>
        <div className="space-y-2">
          <h1 className="text-xl font-semibold text-text-primary">Baseline received</h1>
          <p className="text-sm text-text-secondary">
            Come back at month-end and upload the next period — Month Proof will compare it
            against this baseline and surface any anomalies.
          </p>
        </div>
        <button
          onClick={onBaselineUploaded}
          className="text-sm text-accent hover:underline"
        >
          Back to upload page
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto space-y-6">
      <div className="text-center space-y-3">
        <div className="flex justify-center">
          <div className="rounded-full bg-severity-normal-bg p-4">
            <Folder className="h-8 w-8 text-text-secondary" aria-hidden />
          </div>
        </div>
        <h1 className="text-xl font-semibold text-text-primary">
          Let's set up your baseline
        </h1>
        <div className="space-y-2 text-sm text-text-secondary">
          <p>
            Month Proof compares each month to your history. You haven't uploaded anything
            yet, so there's nothing to compare against.
          </p>
          <p>
            Start by uploading one prior month — we'll use it as the baseline. Next
            month, drop in the new period and you'll get your first variance report.
          </p>
        </div>
      </div>

      <FileUpload
        onFilesSelected={setSelectedFiles}
        isUploading={isUploading}
        serverError={uploadError}
        disabled={isUploading}
      />

      <PeriodSelector
        value={period}
        onChange={setPeriod}
        label="Which period is this?"
        disabled={isUploading}
      />

      <button
        onClick={handleUpload}
        disabled={!canSubmit}
        className={cn(
          "w-full rounded-md bg-accent px-4 py-2.5 text-sm font-medium text-white",
          "hover:bg-accent/90 transition-colors",
          "focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2",
          !canSubmit && "opacity-50 cursor-not-allowed"
        )}
      >
        {isUploading ? "Uploading baseline…" : "Upload baseline"}
      </button>
    </div>
  );
}

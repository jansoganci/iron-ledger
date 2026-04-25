import { Upload, X } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import { CLIENT_MESSAGES } from "../lib/messages";
import { cn } from "../lib/utils";

const ACCEPTED_EXTENSIONS = [".xlsx", ".xls", ".xlsm", ".csv"];
const MAX_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB

interface FileUploadProps {
  onFilesSelected: (files: File[]) => void;
  isUploading?: boolean;
  serverError?: string | null;
  disabled?: boolean;
}

type DropState = "idle" | "dragging";

export function FileUpload({
  onFilesSelected,
  isUploading = false,
  serverError = null,
  disabled = false,
}: FileUploadProps) {
  const [dropState, setDropState] = useState<DropState>("idle");
  const [clientError, setClientError] = useState<string | null>(null);
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [sourceLabels, setSourceLabels] = useState<Record<string, string>>({});
  const inputRef = useRef<HTMLInputElement>(null);

  const isDisabled = disabled || isUploading;

  function validateAndAccept(rawFiles: File[]) {
    setClientError(null);
    const valid: File[] = [];

    for (const f of rawFiles) {
      const ext = "." + f.name.split(".").pop()?.toLowerCase();
      if (!ACCEPTED_EXTENSIONS.includes(ext)) {
        setClientError(CLIENT_MESSAGES.UNSUPPORTED_FORMAT(f.name));
        return;
      }
      if (f.size > MAX_SIZE_BYTES) {
        setClientError(CLIENT_MESSAGES.FILE_TOO_LARGE(f.name));
        return;
      }
      valid.push(f);
    }

    if (valid.length === 0) return;

    // Merge with any already-queued files (dedup by name)
    setPendingFiles((prev) => {
      const existingNames = new Set(prev.map((f) => f.name));
      const merged = [...prev, ...valid.filter((f) => !existingNames.has(f.name))];
      onFilesSelected(merged);
      return merged;
    });
  }

  function removeFile(name: string) {
    setPendingFiles((prev) => {
      const updated = prev.filter((f) => f.name !== name);
      onFilesSelected(updated);
      return updated;
    });
    setSourceLabels((prev) => {
      const next = { ...prev };
      delete next[name];
      return next;
    });
  }

  function setLabel(name: string, label: string) {
    setSourceLabels((prev) => ({ ...prev, [name]: label }));
  }

  const onDragEnter = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      if (!isDisabled) setDropState("dragging");
    },
    [isDisabled]
  );

  const onDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      if (!isDisabled) setDropState("dragging");
    },
    [isDisabled]
  );

  const onDragLeave = useCallback((e: React.DragEvent) => {
    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
      setDropState("idle");
    }
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDropState("idle");
      if (isDisabled) return;
      const files = Array.from(e.dataTransfer.files);
      if (files.length > 0) validateAndAccept(files);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [isDisabled]
  );

  const onInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files ?? []);
      if (files.length > 0) validateAndAccept(files);
      // Reset so same file can be re-selected
      e.target.value = "";
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [isDisabled]
  );

  const isDragging = dropState === "dragging";
  const displayError = clientError ?? serverError;

  return (
    <div className="space-y-3">
      <div
        role="button"
        tabIndex={isDisabled ? -1 : 0}
        aria-label="File upload dropzone"
        aria-disabled={isDisabled}
        onClick={() => !isDisabled && inputRef.current?.click()}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === " ") && !isDisabled) {
            inputRef.current?.click();
          }
        }}
        onDragEnter={onDragEnter}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        className={cn(
          "relative rounded-lg border transition-all duration-150",
          "flex flex-col items-center justify-center gap-2",
          "min-h-[140px] px-6 py-7 text-center",
          isDragging
            ? "border-2 border-accent bg-favorable-bg cursor-copy"
            : "border border-dashed border-border bg-surface cursor-pointer hover:border-accent/50",
          isDisabled && "opacity-60 cursor-not-allowed pointer-events-none"
        )}
      >
        <Upload
          className={cn("h-8 w-8", isDragging ? "text-accent" : "text-text-secondary")}
          aria-hidden
        />
        <div className="space-y-1">
          <p
            className={cn(
              "text-sm font-medium",
              isDragging ? "text-accent" : "text-text-primary"
            )}
          >
            {isDragging
              ? "Release to add files"
              : pendingFiles.length > 0
              ? "Drop more files or click to add"
              : "Drop your files here or click to select"}
          </p>
          <p className="text-xs text-text-secondary">Excel · CSV · Multiple files supported</p>
        </div>

        {/* Uploading overlay */}
        {isUploading && (
          <div className="absolute inset-x-0 bottom-0 px-6 pb-4">
            <div className="w-full bg-border rounded-full h-1.5 overflow-hidden">
              <div className="h-full bg-accent rounded-full animate-pulse w-2/3" />
            </div>
          </div>
        )}

        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPTED_EXTENSIONS.join(",")}
          className="sr-only"
          tabIndex={-1}
          onChange={onInputChange}
        />
      </div>

      {/* File chips — shown while pending or uploading */}
      {pendingFiles.length > 0 && !clientError && (
        <ul className="space-y-2">
          {pendingFiles.map((f) => (
            <li
              key={f.name}
              className={cn(
                "flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2",
                isUploading && "opacity-80"
              )}
            >
              {/* Status indicator */}
              {isUploading ? (
                <span className="inline-block h-3 w-3 shrink-0 rounded-full border-2 border-accent border-t-transparent animate-spin" />
              ) : (
                <span className="text-accent text-sm shrink-0">✓</span>
              )}

              {/* Filename */}
              <span
                className="text-xs text-text-primary font-medium truncate flex-1 min-w-0"
                title={f.name}
              >
                {f.name}
              </span>

              {/* Optional source label input */}
              {!isUploading && (
                <input
                  type="text"
                  value={sourceLabels[f.name] ?? ""}
                  onChange={(e) => setLabel(f.name, e.target.value)}
                  placeholder="Label (optional)"
                  className={cn(
                    "w-32 shrink-0 rounded border border-border bg-canvas px-2 py-0.5 text-xs",
                    "text-text-secondary placeholder:text-text-secondary/50",
                    "focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent"
                  )}
                />
              )}

              {/* Remove button */}
              {!isUploading && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    removeFile(f.name);
                  }}
                  aria-label={`Remove ${f.name}`}
                  className="shrink-0 rounded p-0.5 text-text-secondary hover:text-text-primary hover:bg-severity-normal-bg transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                >
                  <X className="h-3.5 w-3.5" aria-hidden />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {/* Client-side or server-side error */}
      {displayError && (
        <div
          role="alert"
          className="rounded-md bg-severity-high-bg text-severity-high-fg px-3 py-2 text-sm"
        >
          {displayError}
        </div>
      )}
    </div>
  );
}

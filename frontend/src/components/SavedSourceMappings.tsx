import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useToast } from "./ToastProvider";
import { apiFetch } from "../lib/api";
import { cn } from "../lib/utils";

interface SavedMapping {
  id: string;
  file_type: string;
  source_pattern: string;
  gl_account: string;
  updated_at: string | null;
}

interface SourceMappingsResponse {
  mappings: SavedMapping[];
  gl_account_pool: string[];
}

const FILE_TYPE_LABELS: Record<string, string> = {
  supplier_invoices: "Vendors & expenses",
  contracts: "Contracts",
  bank_statement: "Bank",
  processor_settlement: "Processor",
};

export function SavedSourceMappings() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  const { data, isLoading } = useQuery<SourceMappingsResponse>({
    queryKey: ["source-mappings"],
    queryFn: () => apiFetch<SourceMappingsResponse>("/source-mappings"),
    staleTime: 15_000,
  });

  const pool = useMemo(() => {
    const names = new Set(data?.gl_account_pool ?? []);
    for (const row of data?.mappings ?? []) {
      names.add(row.gl_account);
    }
    return [...names].sort();
  }, [data]);

  const updateMutation = useMutation({
    mutationFn: ({ id, gl_account }: { id: string; gl_account: string }) =>
      apiFetch(`/source-mappings/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ gl_account }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["source-mappings"] });
      toast.push("success", "Saved name updated");
    },
    onError: (err: unknown) => {
      toast.push(
        "error",
        "Could not update that name",
        err instanceof Error ? err.message : undefined
      );
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/source-mappings/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      setPendingDeleteId(null);
      queryClient.invalidateQueries({ queryKey: ["source-mappings"] });
      toast.push("success", "Saved name removed");
    },
    onError: (err: unknown) => {
      toast.push(
        "error",
        "Could not remove that name",
        err instanceof Error ? err.message : undefined
      );
    },
  });

  if (isLoading) {
    return (
      <div className="rounded-lg border border-border bg-surface p-8 text-center">
        <p className="text-sm text-text-secondary">Loading saved names…</p>
      </div>
    );
  }

  const mappings = data?.mappings ?? [];
  if (mappings.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-surface p-8 text-center">
        <p className="text-sm font-medium text-text-primary">No saved names yet</p>
        <p className="text-sm text-text-secondary mt-1">
          When you confirm a vendor or expense during upload, it is remembered
          here so next month does not start from scratch.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-surface overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead className="border-b border-border bg-canvas">
            <tr>
              <th className="px-4 py-2.5 text-xs font-medium text-text-secondary uppercase tracking-wide">
                Source name
              </th>
              <th className="px-4 py-2.5 text-xs font-medium text-text-secondary uppercase tracking-wide">
                Type
              </th>
              <th className="px-4 py-2.5 text-xs font-medium text-text-secondary uppercase tracking-wide">
                GL account
              </th>
              <th className="px-4 py-2.5 text-xs font-medium text-text-secondary uppercase tracking-wide text-right">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {mappings.map((row) => (
              <tr key={row.id} className="hover:bg-canvas transition-colors">
                <td className="px-4 py-3 text-sm font-data text-text-primary">
                  {row.source_pattern}
                </td>
                <td className="px-4 py-3 text-xs text-text-secondary">
                  {FILE_TYPE_LABELS[row.file_type] ?? row.file_type}
                </td>
                <td className="px-4 py-3">
                  <select
                    aria-label={`GL account for ${row.source_pattern}`}
                    className="w-full max-w-xs rounded border border-border bg-surface px-2 py-1 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent"
                    value={row.gl_account}
                    disabled={updateMutation.isPending}
                    onChange={(e) =>
                      updateMutation.mutate({
                        id: row.id,
                        gl_account: e.target.value,
                      })
                    }
                  >
                    {pool.map((acct) => (
                      <option key={acct} value={acct}>
                        {acct}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-4 py-3 text-right">
                  {pendingDeleteId === row.id ? (
                    <span className="inline-flex items-center gap-2">
                      <button
                        type="button"
                        className="text-xs font-medium text-severity-high-fg hover:underline"
                        onClick={() => deleteMutation.mutate(row.id)}
                        disabled={deleteMutation.isPending}
                      >
                        Confirm delete
                      </button>
                      <button
                        type="button"
                        className="text-xs text-text-secondary hover:text-text-primary"
                        onClick={() => setPendingDeleteId(null)}
                      >
                        Cancel
                      </button>
                    </span>
                  ) : (
                    <button
                      type="button"
                      className="text-xs font-medium text-text-secondary hover:text-severity-high-fg"
                      onClick={() => setPendingDeleteId(row.id)}
                    >
                      Forget
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

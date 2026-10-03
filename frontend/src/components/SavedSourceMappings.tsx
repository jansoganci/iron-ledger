import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useToast } from "./ToastProvider";
import { apiFetch } from "../lib/api";

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
  gl_account_options?: { name: string; code: string | null }[];
}

const FILE_TYPE_LABELS: Record<string, string> = {
  payroll: "Payroll",
  supplier_invoices: "Vendors",
  contracts: "Contracts",
};

function sourceName(row: SavedMapping): string {
  return row.source_pattern === "(entire file)" && row.file_type === "contracts"
    ? "All contracts"
    : row.source_pattern;
}

function accountOptionLabel(account: { name: string; code: string | null }): string {
  const name = account.name.trim();
  const code = account.code?.trim();
  return code ? `${code} ${name}` : name;
}

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

  const accountOptions = useMemo(() => {
    const options = data?.gl_account_options ?? [];
    const byName = new Map(options.map((account) => [account.name, account]));
    for (const name of pool) {
      if (!byName.has(name)) byName.set(name, { name, code: null });
    }
    return [...byName.values()].sort((a, b) => a.name.localeCompare(b.name));
  }, [data?.gl_account_options, pool]);

  const updateMutation = useMutation({
    mutationFn: ({ id, gl_account }: { id: string; gl_account: string }) =>
      apiFetch(`/source-mappings/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ gl_account }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["source-mappings"] });
      toast.success("Match updated");
    },
    onError: (err: unknown) => {
      toast.error(
        "Could not update that match",
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
      toast.success("Match removed");
    },
    onError: (err: unknown) => {
      toast.error(
        "Could not remove that match",
        err instanceof Error ? err.message : undefined
      );
    },
  });

  if (isLoading) {
    return (
      <div className="rounded-lg border border-border bg-surface p-8 text-center">
        <p className="text-sm text-text-secondary">Loading matches…</p>
      </div>
    );
  }

  const mappings = data?.mappings ?? [];
  if (mappings.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-surface p-8 text-center">
        <p className="text-sm font-medium text-text-primary">
          No saved matches yet. They appear after you confirm names on an upload.
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
                Name in your file
              </th>
              <th className="px-4 py-2.5 text-xs font-medium text-text-secondary uppercase tracking-wide">
                Type
              </th>
              <th className="px-4 py-2.5 text-xs font-medium text-text-secondary uppercase tracking-wide">
                Account in your books
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
                  {sourceName(row)}
                </td>
                <td className="px-4 py-3 text-xs text-text-secondary">
                  {FILE_TYPE_LABELS[row.file_type] ?? "Vendors"}
                </td>
                <td className="px-4 py-3">
                  <select
                    aria-label={`Account in your books for ${sourceName(row)}`}
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
                    {accountOptions.map((account) => (
                      <option key={account.name} value={account.name}>
                        {accountOptionLabel(account)}
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

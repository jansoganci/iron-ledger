import { FormEvent, useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  History as HistoryIcon,
  LogOut,
  Mail,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { useCompany } from "../hooks/useCompany";
import type { Company } from "../hooks/useCompany";
import { apiFetch } from "../lib/api";
import { signOut } from "../lib/auth";
import { CLIENT_MESSAGES } from "../lib/messages";
import {
  RevenueBandField,
  bandLabel,
  type RevenueBand,
} from "../components/RevenueBandField";

interface HasHistoryResponse {
  has_history: boolean;
  periods_loaded: number;
}

export default function ProfilePage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const { data: company, isLoading: companyLoading } = useCompany();
  const { data: history } = useQuery<HasHistoryResponse>({
    queryKey: ["has-history"],
    queryFn: () => apiFetch<HasHistoryResponse>("/companies/me/has-history"),
    staleTime: 30_000,
  });
  const navigate = useNavigate();

  const [band, setBand] = useState<RevenueBand | "">("");
  const [saving, setSaving] = useState(false);
  const [bandError, setBandError] = useState<string | null>(null);

  useEffect(() => {
    if (company?.monthly_revenue_band) {
      setBand(company.monthly_revenue_band as RevenueBand);
    }
  }, [company?.monthly_revenue_band]);

  async function handleSignOut() {
    await signOut();
    navigate("/login", { replace: true });
  }

  async function handleSaveBand(e: FormEvent) {
    e.preventDefault();
    if (!band) return;
    setBandError(null);
    setSaving(true);
    try {
      const updated = await apiFetch<Company>("/companies/me", {
        method: "PATCH",
        json: { monthly_revenue_band: band },
      });
      queryClient.setQueryData<Company>(["company-me"], updated);
    } catch {
      setBandError(CLIENT_MESSAGES.PROFILE_BAND_FAILED);
    } finally {
      setSaving(false);
    }
  }

  const bandUnset = !companyLoading && company != null && !company.monthly_revenue_band;

  return (
    <div className="px-4 py-6 md:py-8">
      <div className="max-w-6xl mx-auto space-y-5">
        <div>
          <h1 className="text-lg font-semibold text-text-primary">
            Your account
          </h1>
        </div>

        {/* Account */}
        <section className="rounded-lg border border-border bg-surface overflow-hidden">
          <header className="border-b border-border px-4 py-3 flex items-center gap-2">
            <Mail className="h-4 w-4 text-text-secondary" aria-hidden />
            <h2 className="text-sm font-semibold text-text-primary">Account</h2>
          </header>
          <dl className="divide-y divide-border">
            <div className="flex items-center justify-between gap-4 px-4 py-3">
              <dt className="text-sm text-text-secondary shrink-0">Email</dt>
              <dd className="text-sm text-text-primary truncate">
                {user?.email ?? "—"}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-4 px-4 py-3">
              <dt className="text-sm text-text-secondary shrink-0">User ID</dt>
              <dd className="font-data text-xs text-text-secondary truncate">
                {user?.id ?? "—"}
              </dd>
            </div>
          </dl>
        </section>

        {/* Company */}
        <section className="rounded-lg border border-border bg-surface overflow-hidden">
          <header className="border-b border-border px-4 py-3 flex items-center gap-2">
            <Building2 className="h-4 w-4 text-text-secondary" aria-hidden />
            <h2 className="text-sm font-semibold text-text-primary">Company</h2>
          </header>
          <dl className="divide-y divide-border">
            <div className="flex items-center justify-between gap-4 px-4 py-3">
              <dt className="text-sm text-text-secondary shrink-0">Name</dt>
              <dd className="text-sm text-text-primary truncate">
                {companyLoading ? "Loading…" : company?.name ?? "—"}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-4 px-4 py-3">
              <dt className="text-sm text-text-secondary shrink-0">Sector</dt>
              <dd className="text-sm text-text-primary truncate">
                {company?.sector ?? "—"}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-4 px-4 py-3">
              <dt className="text-sm text-text-secondary shrink-0">Currency</dt>
              <dd
                className="text-sm text-text-primary tabular-nums"
                data-numeric
              >
                {company?.currency ?? "—"}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-4 px-4 py-3">
              <dt className="text-sm text-text-secondary shrink-0">
                Typical monthly revenue
              </dt>
              <dd className="text-sm text-text-primary">
                {companyLoading
                  ? "Loading…"
                  : bandLabel(company?.monthly_revenue_band ?? null)}
              </dd>
            </div>
          </dl>
          {bandUnset && (
            <div
              role="status"
              className="mx-4 mt-3 rounded-md bg-severity-medium-bg px-3 py-2 text-sm text-severity-medium-fg"
            >
              Set typical monthly revenue so close flags match your shop size.
            </div>
          )}
          <form onSubmit={handleSaveBand} className="px-4 py-4 space-y-3">
            <RevenueBandField
              value={band}
              onChange={setBand}
              disabled={saving || companyLoading}
            />
            {bandError && (
              <div
                role="alert"
                className="rounded-md bg-severity-high-bg px-3 py-2 text-sm text-severity-high-fg"
              >
                {bandError}
              </div>
            )}
            <button
              type="submit"
              disabled={saving || !band || companyLoading}
              className="rounded-md bg-accent text-white py-2 px-4 text-sm font-medium transition-opacity hover:opacity-95 disabled:opacity-60 disabled:cursor-not-allowed min-h-[44px] lg:min-h-[40px]"
            >
              {saving ? "Saving…" : "Save"}
            </button>
          </form>
        </section>

        {/* Usage */}
        <section className="rounded-lg border border-border bg-surface overflow-hidden">
          <header className="border-b border-border px-4 py-3 flex items-center gap-2">
            <HistoryIcon className="h-4 w-4 text-text-secondary" aria-hidden />
            <h2 className="text-sm font-semibold text-text-primary">Usage</h2>
          </header>
          <dl className="divide-y divide-border">
            <div className="flex items-center justify-between gap-4 px-4 py-3">
              <dt className="text-sm text-text-secondary shrink-0">
                Periods loaded
              </dt>
              <dd
                className="text-sm text-text-primary tabular-nums"
                data-numeric
              >
                {history?.periods_loaded ?? 0}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-4 px-4 py-3">
              <dt className="text-sm text-text-secondary shrink-0">
                Baseline status
              </dt>
              <dd className="text-sm">
                {history?.has_history ? (
                  <span className="inline-flex items-center rounded-full bg-favorable-bg text-favorable-fg px-2 py-0.5 text-xs font-medium">
                    Active
                  </span>
                ) : (
                  <span className="inline-flex items-center rounded-full bg-severity-normal-bg text-severity-normal-fg px-2 py-0.5 text-xs font-medium">
                    Not set up
                  </span>
                )}
              </dd>
            </div>
          </dl>
        </section>

        {/* Actions */}
        <section className="rounded-lg border border-border bg-surface p-4">
          <button
            type="button"
            onClick={handleSignOut}
            className="w-full flex items-center justify-center gap-2 rounded-md border border-border bg-surface px-4 py-2 text-sm font-medium text-text-primary hover:bg-canvas transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-accent min-h-[44px] lg:min-h-[40px]"
          >
            <LogOut className="h-4 w-4" aria-hidden />
            Sign out
          </button>
        </section>
      </div>
    </div>
  );
}

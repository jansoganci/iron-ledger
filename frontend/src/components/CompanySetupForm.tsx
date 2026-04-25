import { FormEvent, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../lib/api";
import { CLIENT_MESSAGES } from "../lib/messages";
import { supabase } from "../lib/supabase";
import { useAuth } from "../contexts/AuthContext";
import type { Company } from "../hooks/useCompany";

interface Props {
  onSuccess: () => void;
}

export function CompanySetupForm({ onSuccess }: Props) {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const [name, setName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [email, setEmail] = useState(user?.email ?? "");
  const [sector, setSector] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const disabled =
    loading || !name.trim() || !companyName.trim() || !email.trim() || !sector;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const company = await apiFetch<Company>("/companies", {
        method: "POST",
        json: { name: companyName.trim(), sector },
      });

      // Populate the cache so ProtectedRoute / other pages don't need a refetch
      queryClient.setQueryData<Company>(["company-me"], company);

      // Write onboarding_done and user display info to auth metadata.
      // If this fails, the company row already exists — the user can work.
      // They will see onboarding again on next login and the flag write will
      // succeed on that attempt.
      await supabase.auth.updateUser({
        data: {
          full_name: name.trim(),
          email: email.trim(),
          onboarding_done: true,
        },
      });

      onSuccess();
    } catch {
      setError(CLIENT_MESSAGES.ONBOARDING_COMPANY_FAILED);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-canvas px-4">
      <div className="w-full max-w-[400px]">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-semibold text-text-primary">
            Set up your workspace
          </h1>
          <p className="text-sm text-text-secondary mt-1">Takes 30 seconds.</p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-surface border border-border rounded-lg p-6 shadow-sm"
          noValidate
        >
          <div className="space-y-4">
            <div>
              <label
                htmlFor="ob-name"
                className="block text-sm font-medium text-text-primary mb-1.5"
              >
                Your name
              </label>
              <input
                id="ob-name"
                type="text"
                autoComplete="name"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                readOnly={loading}
                className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent read-only:opacity-60"
                placeholder="Jane Doe"
              />
            </div>

            <div>
              <label
                htmlFor="ob-company"
                className="block text-sm font-medium text-text-primary mb-1.5"
              >
                Company name
              </label>
              <input
                id="ob-company"
                type="text"
                autoComplete="organization"
                required
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                readOnly={loading}
                className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent read-only:opacity-60"
                placeholder="Acme Corp"
              />
            </div>

            <div>
              <label
                htmlFor="ob-email"
                className="block text-sm font-medium text-text-primary mb-1.5"
              >
                Work email
              </label>
              <input
                id="ob-email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                readOnly={loading}
                className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent read-only:opacity-60"
                placeholder="you@company.com"
              />
            </div>

            <div>
              <label
                htmlFor="ob-sector"
                className="block text-sm font-medium text-text-primary mb-1.5"
              >
                Industry
              </label>
              <input
                id="ob-sector"
                type="text"
                required
                value={sector}
                onChange={(e) => setSector(e.target.value)}
                readOnly={loading}
                className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent read-only:opacity-60"
                placeholder="e.g. SaaS, Real Estate, Healthcare…"
              />
            </div>

            {error && (
              <div
                role="alert"
                className="rounded-md bg-severity-high-bg px-3 py-2 text-sm text-severity-high-fg"
              >
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={disabled}
              className="w-full rounded-md bg-accent text-white py-2 px-4 text-sm font-medium transition-opacity hover:opacity-95 disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading && (
                <span
                  aria-hidden
                  className="h-4 w-4 border-2 border-white/70 border-t-transparent rounded-full animate-spin"
                />
              )}
              <span>{loading ? "Setting up…" : "Start analyzing →"}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

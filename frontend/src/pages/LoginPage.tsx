import { FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { signIn } from "../lib/auth";
import { CLIENT_MESSAGES } from "../lib/messages";

/**
 * Login screen per docs/design.md §5.
 * Centered card, email + password, teal CTA. Auth errors are inline
 * (never toast) and never specify which field was wrong — avoids leaking
 * account-existence information.
 */
export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [params] = useSearchParams();
  const navigate = useNavigate();

  const resolveNext = (): string => {
    const next = params.get("next");
    if (!next) return "/upload";
    // Only honor same-origin paths — reject protocol-relative or absolute URLs
    if (next.startsWith("/") && !next.startsWith("//")) return next;
    return "/upload";
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const data = await signIn(email.trim(), password);
      const onboardingDone =
        data.user?.user_metadata?.onboarding_done === true;
      navigate(onboardingDone ? resolveNext() : "/onboarding", {
        replace: true,
      });
    } catch {
      setError(CLIENT_MESSAGES.AUTH_FAILED);
    } finally {
      setLoading(false);
    }
  };

  const disabled = loading || !email || !password;

  return (
    <div className="min-h-screen flex items-center justify-center bg-canvas px-4">
      <div className="w-full max-w-[400px]">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-semibold text-text-primary">IronLedger</h1>
          <p className="text-sm text-text-secondary mt-1">
            Month-end close, verified.
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-surface border border-border rounded-lg p-6 shadow-sm"
          noValidate
        >
          <div className="space-y-4">
            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium text-text-primary mb-1.5"
              >
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="username"
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
                htmlFor="password"
                className="block text-sm font-medium text-text-primary mb-1.5"
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                readOnly={loading}
                className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent read-only:opacity-60"
                placeholder="••••••••••"
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
              <span>{loading ? "Signing in…" : "Sign in"}</span>
            </button>

            <p className="text-center text-sm text-text-secondary">
              Don't have an account?{" "}
              <Link to="/register" className="text-accent hover:underline">
                Sign up →
              </Link>
            </p>
          </div>
        </form>
      </div>
    </div>
  );
}

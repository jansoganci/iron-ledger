import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { signUp } from "../lib/auth";
import { CLIENT_MESSAGES } from "../lib/messages";

export default function RegisterPage() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password.length < 8) {
      setError(CLIENT_MESSAGES.PASSWORD_TOO_SHORT);
      return;
    }
    if (password !== confirm) {
      setError(CLIENT_MESSAGES.PASSWORDS_DONT_MATCH);
      return;
    }

    setLoading(true);
    try {
      await signUp(email.trim(), password, fullName.trim());
      navigate("/onboarding", { replace: true });
    } catch (err: unknown) {
      const code =
        typeof err === "object" && err !== null && "code" in err
          ? String((err as { code?: unknown }).code ?? "")
          : "";
      const message =
        typeof err === "object" && err !== null && "message" in err
          ? String((err as { message?: unknown }).message ?? "").toLowerCase()
          : "";
      if (
        code === "user_already_exists" ||
        code === "user_already_registered" ||
        message.includes("already registered") ||
        message.includes("already exists")
      ) {
        setError(CLIENT_MESSAGES.EMAIL_ALREADY_REGISTERED);
      } else {
        setError(CLIENT_MESSAGES.SIGNUP_FAILED);
      }
    } finally {
      setLoading(false);
    }
  };

  const disabled = loading || !fullName || !email || !password || !confirm;

  return (
    <div className="min-h-screen flex items-center justify-center bg-canvas px-4">
      <div className="w-full max-w-[400px]">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-semibold text-text-primary">IronLedger</h1>
          <p className="text-sm text-text-secondary mt-1">Create your account.</p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-surface border border-border rounded-lg p-6 shadow-sm"
          noValidate
        >
          <div className="space-y-4">
            <div>
              <label
                htmlFor="full-name"
                className="block text-sm font-medium text-text-primary mb-1.5"
              >
                Full name
              </label>
              <input
                id="full-name"
                type="text"
                autoComplete="name"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                readOnly={loading}
                className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent read-only:opacity-60"
                placeholder="Jane Doe"
              />
            </div>

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
                htmlFor="password"
                className="block text-sm font-medium text-text-primary mb-1.5"
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="new-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                readOnly={loading}
                className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent read-only:opacity-60"
                placeholder="••••••••••"
              />
            </div>

            <div>
              <label
                htmlFor="confirm-password"
                className="block text-sm font-medium text-text-primary mb-1.5"
              >
                Confirm password
              </label>
              <input
                id="confirm-password"
                type="password"
                autoComplete="new-password"
                required
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
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
              <span>{loading ? "Creating account…" : "Create account"}</span>
            </button>

            <p className="text-center text-sm text-text-secondary">
              Already have an account?{" "}
              <Link to="/login" className="text-accent hover:underline">
                Sign in →
              </Link>
            </p>
          </div>
        </form>
      </div>
    </div>
  );
}

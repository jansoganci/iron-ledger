import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

/**
 * Route guard: redirects unauthenticated users to /login?next=<current>.
 * While the session is still loading, shows a skeleton spinner so the user
 * does not get a flash-to-login on every reload.
 */
export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { session, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-canvas">
        <div
          className="h-6 w-6 border-2 border-accent border-t-transparent rounded-full animate-spin"
          aria-label="Loading session"
        />
      </div>
    );
  }
  if (!session) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  return <>{children}</>;
}

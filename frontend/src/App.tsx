import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { ToastProvider } from "./components/ToastProvider";
import { AppShell } from "./components/AppShell";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import OnboardingPage from "./pages/OnboardingPage";
import UploadPage from "./pages/UploadPage";
import ReportPage from "./pages/ReportPage";
import QuarterlyReportPage from "./pages/QuarterlyReportPage";
import ProfilePage from "./pages/ProfilePage";
import DashboardPage from "./pages/DashboardPage";
import DataPage from "./pages/DataPage";
import ReportsPage from "./pages/ReportsPage";
import { ProtectedRoute } from "./routes/ProtectedRoute";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  },
});

function HomeRoute() {
  const { session, loading } = useAuth();

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
  if (session) {
    return <Navigate to="/upload" replace />;
  }
  return <LandingPage />;
}

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <ToastProvider>
            <BrowserRouter>
              <Routes>
                <Route path="/" element={<HomeRoute />} />
                <Route path="/landing" element={<Navigate to="/" replace />} />
                <Route path="/login" element={<LoginPage />} />
                <Route path="/register" element={<RegisterPage />} />
                <Route
                  path="/onboarding"
                  element={
                    <ProtectedRoute>
                      <OnboardingPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/upload"
                  element={
                    <ProtectedRoute>
                      <AppShell>
                        <UploadPage />
                      </AppShell>
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/data"
                  element={
                    <ProtectedRoute>
                      <AppShell>
                        <DataPage />
                      </AppShell>
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/report/:period"
                  element={
                    <ProtectedRoute>
                      <AppShell>
                        <ReportPage />
                      </AppShell>
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/profile"
                  element={
                    <ProtectedRoute>
                      <AppShell>
                        <ProfilePage />
                      </AppShell>
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/dashboard"
                  element={
                    <ProtectedRoute>
                      <AppShell>
                        <DashboardPage />
                      </AppShell>
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/reports"
                  element={
                    <ProtectedRoute>
                      <AppShell>
                        <ReportsPage />
                      </AppShell>
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/report/quarterly/:yearQuarter"
                  element={
                    <ProtectedRoute>
                      <AppShell>
                        <QuarterlyReportPage />
                      </AppShell>
                    </ProtectedRoute>
                  }
                />
                <Route path="*" element={<Navigate to="/upload" replace />} />
              </Routes>
            </BrowserRouter>
          </ToastProvider>
        </AuthProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

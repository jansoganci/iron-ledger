import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { HowItWorks } from "../components/HowItWorks";
import { CompanySetupForm } from "../components/CompanySetupForm";

type Phase = "walkthrough" | "form" | "success";

function OnboardingSuccess() {
  const navigate = useNavigate();

  useEffect(() => {
    const timer = setTimeout(() => {
      navigate("/upload", { replace: true });
    }, 3000);
    return () => clearTimeout(timer);
  }, [navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-canvas px-4">
      <div className="w-full max-w-[400px]">
        <div className="bg-surface border border-border rounded-lg p-8 shadow-sm text-center">
          <div className="text-4xl mb-4">✓</div>
          <h1 className="text-2xl font-semibold text-text-primary mb-2">
            You're all set!
          </h1>
          <p className="text-sm text-text-secondary mb-8">
            Now upload your first file to get started.
          </p>
          <button
            type="button"
            onClick={() => navigate("/upload", { replace: true })}
            className="w-full rounded-md bg-accent text-white py-2 px-4 text-sm font-medium hover:opacity-95 transition-opacity"
          >
            Upload my first file →
          </button>
        </div>
      </div>
    </div>
  );
}

export default function OnboardingPage() {
  const [phase, setPhase] = useState<Phase>("walkthrough");

  if (phase === "walkthrough") {
    return (
      <HowItWorks
        onDone={() => setPhase("form")}
        onSkip={() => setPhase("form")}
      />
    );
  }

  if (phase === "form") {
    return <CompanySetupForm onSuccess={() => setPhase("success")} />;
  }

  return <OnboardingSuccess />;
}

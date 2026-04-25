import { AlertTriangle, FileText, Upload } from "lucide-react";
import { useState } from "react";

const STEPS = [
  {
    Icon: Upload,
    headline: "Upload your file",
    description: "Drop your Excel or CSV. We read it automatically.",
  },
  {
    Icon: AlertTriangle,
    headline: "We find the anomalies",
    description: "Our agent flags anything outside your normal range.",
  },
  {
    Icon: FileText,
    headline: "Get your report",
    description: "Plain-language summary, verified, sent to your inbox.",
  },
] as const;

interface Props {
  onDone: () => void;
  onSkip: () => void;
}

export function HowItWorks({ onDone, onSkip }: Props) {
  const [step, setStep] = useState(0);
  const { Icon, headline, description } = STEPS[step];
  const isLast = step === STEPS.length - 1;

  return (
    <div className="min-h-screen flex items-center justify-center bg-canvas px-4">
      <div className="w-full max-w-[400px]">
        <div className="relative bg-surface border border-border rounded-lg p-8 shadow-sm">
          <button
            type="button"
            onClick={onSkip}
            className="absolute top-4 right-4 text-sm text-text-secondary hover:text-text-primary transition-colors"
          >
            Skip
          </button>

          {/* Step dots */}
          <div className="flex items-center justify-center gap-2 mb-8">
            {STEPS.map((_, i) => (
              <div
                key={i}
                className={`h-2 w-2 rounded-full transition-colors ${
                  i === step ? "bg-accent" : "bg-border"
                }`}
              />
            ))}
          </div>

          {/* Step content — key change triggers CSS fade */}
          <div key={step} className="step-fade-in text-center">
            <div className="flex justify-center mb-5">
              <Icon size={48} className="text-accent" strokeWidth={1.5} />
            </div>
            <h2 className="text-xl font-semibold text-text-primary mb-2">
              {headline}
            </h2>
            <p className="text-sm text-text-secondary">{description}</p>
          </div>

          <button
            type="button"
            onClick={isLast ? onDone : () => setStep((s) => s + 1)}
            className="mt-8 w-full rounded-md bg-accent text-white py-2 px-4 text-sm font-medium hover:opacity-95 transition-opacity"
          >
            {isLast ? "Get Started →" : "Next →"}
          </button>
        </div>
      </div>
    </div>
  );
}

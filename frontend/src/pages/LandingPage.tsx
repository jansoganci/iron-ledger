import { LogoMark } from "../components/Logo";

const SCREENSHOT_SRC = "";

export default function LandingPage() {
  return (
    <div className="bg-canvas text-text-primary font-sans antialiased min-h-screen">
      <header className="max-w-[720px] mx-auto px-6 pt-10 pb-6 flex items-center justify-between">
        <span className="flex items-center gap-2.5">
          <LogoMark size={20} className="shrink-0" />
          <span className="font-data text-xs tracking-widest uppercase text-text-secondary">
            TrueCost · Month-End Close · 2026
          </span>
        </span>
        <a
          href="/login"
          className="text-sm font-medium text-text-secondary hover:text-text-primary transition-colors [transition-duration:var(--duration-base)] focus:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded"
        >
          Sign in →
        </a>
      </header>

      <section className="max-w-[720px] mx-auto px-6 pt-16 pb-24">
        <p className="font-data text-xs text-text-secondary mb-10 tracking-widest uppercase">
          §1 · The Problem
        </p>

        <h1 className="font-serif font-semibold leading-[1.08] tracking-tight mb-8">
          <span className="block text-5xl md:text-6xl text-text-primary">
            A close report from
          </span>
          <span className="block text-5xl md:text-6xl italic text-accent">
            the files you already have.
          </span>
        </h1>

        <p className="text-lg leading-relaxed text-text-secondary max-w-[580px]">
          TrueCost is a month-end close tool for small finance teams. Upload
          Excel or CSV exports. It consolidates them, writes a plain-language
          report, and saves that report only after the numbers match the pandas
          results.
        </p>

        {SCREENSHOT_SRC ? (
          <img
            src={SCREENSHOT_SRC}
            alt="TrueCost close report"
            className="mt-12 w-full rounded-xl border border-border"
          />
        ) : null}
      </section>

      <section className="max-w-[720px] mx-auto px-6 py-20 border-t border-border">
        <p className="font-data text-xs text-text-secondary mb-8 tracking-widest uppercase">
          §2 · How it works
        </p>

        <h2 className="font-serif text-3xl md:text-4xl font-semibold leading-tight text-text-primary mb-10">
          How it works
        </h2>

        <ol className="space-y-6 text-base leading-relaxed text-text-primary list-decimal list-outside pl-6 marker:text-accent marker:font-data marker:text-sm marker:font-semibold">
          <li>Drop your Excel or CSV exports.</li>
          <li>TrueCost consolidates them and finds where they disagree.</li>
          <li>
            You get a plain-language report. Every number is verified against
            pandas before the report is saved.
          </li>
        </ol>

        <p className="text-base text-text-secondary mt-10 leading-relaxed">
          Uncertain account mappings pause so you can review them. If earlier
          months are already uploaded, the report includes variance against
          that history. With at least two complete months in a quarter,
          TrueCost can also write a quarterly narrative, including trends and
          anomalies that have shown up before.
        </p>
      </section>

      <section className="max-w-[720px] mx-auto px-6 py-20 border-t border-border">
        <p className="font-data text-xs text-text-secondary mb-8 tracking-widest uppercase">
          §3 · Trust
        </p>

        <h2 className="font-serif text-3xl md:text-4xl font-semibold leading-tight text-text-primary mb-10">
          How we know the{" "}
          <span className="italic text-accent">numbers are right.</span>
        </h2>

        <p className="text-lg leading-relaxed text-text-primary mb-6">
          Totals, variances, and anomaly thresholds are calculated in Python
          with pandas. The model writes the sentences around those numbers. It
          does not calculate them.
        </p>

        <p className="text-lg leading-relaxed text-text-primary">
          Before a report is saved, a numeric guardrail checks the figures in
          the prose against the pandas results. If they do not match, the
          report is not saved.
        </p>
      </section>

      <section className="max-w-[720px] mx-auto px-6 py-24 border-t border-border">
        <p className="font-data text-xs text-text-secondary mb-8 tracking-widest uppercase">
          §4 · Try It
        </p>

        <h2 className="font-serif text-3xl md:text-4xl font-semibold leading-tight text-text-primary mb-5">
          Try it on a{" "}
          <span className="italic text-accent">real month.</span>
        </h2>

        <div className="flex items-center gap-4 flex-wrap">
          <a
            href="mailto:john@truecost.lol?subject=TrueCost%20access"
            className="inline-block rounded-md bg-accent text-white px-8 py-3 text-base font-medium hover:bg-accent/90 hover:scale-[1.015] active:scale-[0.97] transition-all [transition-duration:var(--duration-base)] focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
          >
            Request access
          </a>
          <p className="text-sm text-text-secondary">
            Each company only sees its own data.
          </p>
        </div>
      </section>

      <section className="max-w-[720px] mx-auto px-6 py-20 border-t border-border">
        <p className="font-data text-xs text-text-secondary mb-8 tracking-widest uppercase">
          §5 · Commitments
        </p>

        <div className="font-data text-sm text-text-secondary mb-10 space-y-1 border border-border rounded-xl px-5 py-4 bg-surface">
          <p><span className="uppercase tracking-wider text-text-primary">To:</span>{" "}Finance teams evaluating TrueCost</p>
          <p><span className="uppercase tracking-wider text-text-primary">From:</span>{" "}The TrueCost team</p>
          <p><span className="uppercase tracking-wider text-text-primary">Re:</span>{" "}What this tool will not do</p>
        </div>

        <ol className="space-y-5 text-base leading-relaxed text-text-primary list-decimal list-outside pl-6 marker:text-accent marker:font-data marker:text-sm marker:font-semibold">
          <li>
            We do not do arithmetic. Every number in a saved report comes from
            pandas operating on your source file. The model writes sentences.
          </li>
          <li>
            This app does not train a model on your files. Personal columns
            are removed before a model sees a sample.
          </li>
          <li>
            We do not replace your judgment. The report is a first draft. You
            decide what to change.
          </li>
          <li>
            A saved report does not close the month. Closing the month is a
            separate step you confirm.
          </li>
          <li>
            You can read the report in the app and download the Excel close
            package.
          </li>
        </ol>

        <p className="text-base text-text-primary mt-10 leading-relaxed">
          Questions:{" "}
          <a
            href="mailto:john@truecost.lol"
            className="text-text-primary underline decoration-dotted underline-offset-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded"
          >
            john@truecost.lol
          </a>
        </p>
      </section>

      <footer className="max-w-[720px] mx-auto px-6 py-8 border-t border-border flex items-center justify-between">
        <p className="font-data text-xs text-text-secondary uppercase tracking-widest">
          TrueCost · 2026
        </p>
        <p className="text-xs text-text-secondary">
          Built at Anthropic Hackathon, April 2026
        </p>
      </footer>
    </div>
  );
}

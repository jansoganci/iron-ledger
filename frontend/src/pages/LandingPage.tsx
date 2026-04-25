export default function LandingPage() {
  return (
    <div className="bg-canvas text-text-primary font-serif antialiased min-h-screen">
      <header className="max-w-[680px] mx-auto px-6 pt-10 pb-6 flex items-center justify-between">
        <span className="font-sans font-semibold text-text-primary tracking-tight">
          IronLedger
        </span>
        <a
          href="/login"
          className="font-sans text-sm text-text-secondary hover:text-text-primary transition-colors"
        >
          Sign in
        </a>
      </header>

      {/* §1 — The Cold Open */}
      <section className="max-w-[680px] mx-auto px-6 pt-20 pb-24">
        <p className="font-mono text-xs text-text-secondary mb-8 tracking-widest">
          §1
        </p>

        <p className="text-lg leading-relaxed text-text-primary mb-10">
          You're still in the spreadsheet. Travel is up $38K against last month
          and you can't yet tell if it's the Denver offsite, a miscoded Amex
          batch, or something worse. The report goes to the CEO at 9 a.m. The
          last close took four days to reconcile; this one has to go out in
          twelve hours.
        </p>

        <h1 className="text-4xl md:text-5xl font-semibold leading-[1.15] tracking-tight text-text-primary">
          It's 11:47 PM. One number moved. You're the only one who's noticed.
        </h1>

        <p className="text-base text-text-secondary mt-6 max-w-[560px] leading-relaxed">
          IronLedger is a month-end close agent for US finance teams. This page
          explains how it works before it asks you to trust it.
        </p>
      </section>

      {/* §2 — The Single Anomaly Card */}
      <section className="max-w-[680px] mx-auto px-6 py-20">
        <p className="font-mono text-xs text-text-secondary mb-8 tracking-widest">
          §2
        </p>

        <p className="text-lg text-text-primary mb-8 leading-relaxed">
          Here's what IronLedger flagged in DRONE Inc.'s March close.
        </p>

        <article className="bg-surface border border-border rounded-lg p-6 shadow-sm">
          <span className="inline-block rounded-md bg-severity-high-bg text-severity-high-fg text-xs font-semibold uppercase tracking-wide px-2 py-0.5 font-sans">
            High
          </span>

          <h3 className="text-xl font-semibold mt-3 font-sans text-text-primary">
            Travel &amp; Entertainment
          </h3>

          <p className="font-mono text-2xl text-text-primary mt-2">
            +$38,420{" "}
            <span className="text-text-secondary text-base">(+61%)</span>
          </p>

          <p className="text-base text-text-primary mt-4 leading-relaxed">
            Travel spending nearly doubled against the 6-month baseline of
            $24K/month. The increase concentrates in the final week of March —
            consistent with an offsite, not a steady-state change.
          </p>

          <p className="text-xs text-text-secondary mt-6 flex items-center gap-1.5 font-sans">
            Verified against source · Guardrail passed
            <span className="text-accent font-semibold" aria-label="verified">
              ✓
            </span>
          </p>
        </article>

        <p className="text-base text-text-secondary mt-10 leading-relaxed">
          No screenshots of dashboards on this page. That's the actual shape of
          what IronLedger writes after it reads your file — one card per flagged
          account, one paragraph per anomaly, every number traceable back to a
          cell in the source spreadsheet.
        </p>
      </section>

      {/* §3 — How We Know the Numbers Are Right */}
      <section className="max-w-[680px] mx-auto px-6 py-20">
        <p className="font-mono text-xs text-text-secondary mb-8 tracking-widest">
          §3
        </p>

        <h2 className="text-3xl md:text-4xl font-semibold leading-tight text-text-primary mb-10">
          How we know the numbers are right.
        </h2>

        <p className="text-lg leading-relaxed text-text-primary mb-6">
          Every number in the report is calculated in Python. Not by the model.
          Totals, variances, anomaly thresholds — all pandas, all deterministic,
          all reproducible from your source file.
        </p>

        <p className="text-lg leading-relaxed text-text-primary mb-6">
          The model only writes the sentences around those numbers. Its job is
          to interpret, not to compute. Before any report is saved, a numeric
          guardrail compares every figure the model used against the pandas
          output. If they disagree by more than 2%, the report is rejected and
          rewritten.
        </p>

        <p className="text-lg leading-relaxed text-text-primary">
          That's it. No benchmarks. No accuracy percentage. Just a rule that is
          either satisfied, or the report does not leave the system.
        </p>

        <div className="border-l-2 border-border pl-4 mt-12 space-y-3 font-mono text-sm text-text-secondary">
          <p>
            Accepted · The report said "$4.8M revenue" — pandas had $4,730,000.
            Difference 1.46%, within tolerance.
            <span
              className="text-accent font-semibold ml-1"
              aria-label="verified"
            >
              ✓
            </span>
          </p>
          <p>
            Rejected · The report said "$5.1M revenue" — pandas had $4,730,000.
            Difference 7.8%, outside tolerance. Rewritten with the correct
            figure on second pass.
          </p>
        </div>
      </section>

      {/* §4 — Try It On A Real Month */}
      <section className="max-w-[680px] mx-auto px-6 py-24 text-center">
        <p className="font-mono text-xs text-text-secondary mb-8 tracking-widest">
          §4
        </p>

        <h2 className="text-3xl md:text-4xl font-semibold leading-tight text-text-primary mb-5">
          Try it on a real month.
        </h2>

        <p className="text-lg text-text-secondary max-w-[480px] mx-auto mb-10 leading-relaxed">
          Create an account and upload last month's trial balance. You'll see
          the first draft of the close report in under two minutes.
        </p>

        <a
          href="/register"
          className="inline-block rounded-md bg-accent text-white px-8 py-3 text-base font-medium font-sans hover:opacity-95 transition-opacity"
        >
          Get Started
        </a>

        <p className="text-sm text-text-secondary mt-6">
          Your files stay private. We never train on customer data.
        </p>
      </section>

      {/* §5 — The Memo */}
      <section className="max-w-[680px] mx-auto px-6 py-20 border-t border-border">
        <p className="font-mono text-xs text-text-secondary mb-8 tracking-widest">
          §5
        </p>

        <div className="font-mono text-sm text-text-secondary mb-10 space-y-1">
          <p>
            <span className="uppercase tracking-wider">TO:</span>{" "}
            Finance directors evaluating IronLedger
          </p>
          <p>
            <span className="uppercase tracking-wider">FROM:</span>{" "}
            The IronLedger team
          </p>
          <p>
            <span className="uppercase tracking-wider">RE:</span>{" "}
            What this tool will not do
          </p>
          <p>
            <span className="uppercase tracking-wider">DATE:</span> April 2026
          </p>
        </div>

        <ol className="space-y-6 text-lg leading-relaxed text-text-primary list-decimal list-outside pl-6 marker:text-text-secondary marker:font-mono marker:text-sm">
          <li>
            We do not do arithmetic. Every number in every report comes from
            pandas operating on your source file. The model writes sentences;
            it does not calculate totals.
          </li>
          <li>
            We do not train on your data. Your files are not used to improve
            any model, ours or a vendor's.
          </li>
          <li>
            We do not replace your judgment. IronLedger produces a first draft
            of the close narrative. The decision of what to send — and what to
            change — is yours.
          </li>
          <li>
            We do not claim to close your books. We claim to get you to a
            defensible first draft faster than rewriting last month's
            commentary by hand.
          </li>
        </ol>

        <p className="text-base text-text-primary mt-12 leading-relaxed">
          If any of the above stops being true, this page will be updated the
          same day.
        </p>

        <p className="text-base font-mono text-text-secondary mt-8">
          — Jan, Founder
        </p>
      </section>

      <footer className="max-w-[680px] mx-auto px-6 pb-10">
        <p className="text-xs text-text-secondary font-sans">
          © 2026 IronLedger
        </p>
      </footer>
    </div>
  );
}

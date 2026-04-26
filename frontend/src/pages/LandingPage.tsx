export default function LandingPage() {
  return (
    <div className="bg-canvas text-text-primary font-sans antialiased min-h-screen">
      <header className="max-w-[720px] mx-auto px-6 pt-10 pb-6 flex items-center justify-between">
        <span className="font-data text-xs tracking-widest uppercase text-text-secondary">
          IronLedger · Month-End Close · 2026
        </span>
        <a
          href="/login"
          className="text-sm font-medium text-text-secondary hover:text-text-primary transition-colors [transition-duration:var(--duration-base)] focus:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded"
        >
          Sign in →
        </a>
      </header>

      {/* §1 — Hero */}
      <section className="max-w-[720px] mx-auto px-6 pt-16 pb-24">
        <p className="font-data text-xs text-text-secondary mb-10 tracking-widest uppercase">
          §1 · The Problem
        </p>

        {/* Two-tone display headline */}
        <h1 className="font-serif font-semibold leading-[1.08] tracking-tight mb-8">
          <span className="block text-5xl md:text-6xl text-text-primary">
            "The financial chaos
          </span>
          <span className="block text-5xl md:text-6xl italic text-accent">
            ends here."
          </span>
        </h1>

        <p className="text-lg leading-relaxed text-text-secondary max-w-[580px] mb-10">
          Drop any Excel export from your accounting system — GL, payroll,
          supplier invoices. Get a verified, plain-language close report in
          under two minutes.
        </p>

        <p className="text-base leading-relaxed text-text-primary max-w-[560px]">
          You're still in the spreadsheet. Travel is up $38K against last month
          and you can't yet tell if it's the Denver offsite, a miscoded Amex
          batch, or something worse. The report goes to the CEO at 9 a.m.
          The last close took four days to reconcile; this one has to go out
          in twelve hours.
        </p>

        <p className="font-serif text-3xl md:text-4xl font-semibold leading-snug tracking-tight text-text-primary mt-10 max-w-[580px]">
          It's 11:47 PM. One number moved. You're the only one who's noticed.
        </p>

        <p className="text-base text-text-secondary mt-6 max-w-[520px] leading-relaxed">
          IronLedger is a month-end close agent for US finance teams. This page
          explains how it works before it asks you to trust it.
        </p>
      </section>

      {/* §2 — The Single Anomaly Card */}
      <section className="max-w-[720px] mx-auto px-6 py-20">
        <p className="font-data text-xs text-text-secondary mb-8 tracking-widest uppercase">
          §2 · Evidence
        </p>

        <p className="font-serif text-2xl font-semibold text-text-primary mb-8 leading-snug">
          Here's what IronLedger flagged in DRONE Inc.'s March close.
        </p>

        <article className="bg-surface border border-border rounded-xl p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <span className="inline-block rounded-md bg-severity-high-bg text-severity-high-fg text-xs font-semibold uppercase tracking-wide px-2 py-0.5">
              High · Travel &amp; Entertainment
            </span>
            <span className="font-data text-xs text-text-secondary">March 2026</span>
          </div>

          <p className="font-hero-num text-3xl text-text-primary">
            +$38,420{" "}
            <span className="font-data text-text-secondary text-lg">(+61%)</span>
          </p>

          <p className="text-base text-text-primary mt-4 leading-relaxed">
            Travel spending nearly doubled against the 6-month baseline of
            $24K/month. The increase concentrates in the final week of March —
            consistent with an offsite, not a steady-state change.
          </p>

          <p className="text-xs text-text-secondary mt-6 flex items-center gap-1.5">
            Verified against source · Guardrail passed
            <span className="text-teal-600 font-semibold" aria-label="verified">✓</span>
          </p>
        </article>

        <p className="text-base text-text-secondary mt-10 leading-relaxed">
          No screenshots of dashboards on this page. That's the actual shape of
          what IronLedger writes after it reads your file — one card per flagged
          account, one paragraph per anomaly, every number traceable back to a
          cell in the source spreadsheet.
        </p>

        {/* How it works — 4 steps */}
        <div className="mt-12 grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { step: "01", label: "Read", desc: "Parses your GL export. Detects headers, maps columns to GAAP categories." },
            { step: "02", label: "Map", desc: "Matches your chart of accounts to standard categories. Flags low-confidence mappings for your review." },
            { step: "03", label: "Compare", desc: "Calculates variance against your historical baseline. Python only — no AI arithmetic." },
            { step: "04", label: "Report", desc: "Claude writes plain-English narrative. Guardrail verifies every number. Report is sent or rejected." },
          ].map(({ step, label, desc }) => (
            <div key={step} className="space-y-2">
              <div className="flex items-baseline gap-2">
                <span className="font-data text-xs text-accent font-semibold">{step}</span>
                <span className="text-sm font-semibold text-text-primary">{label}</span>
              </div>
              <p className="text-xs text-text-secondary leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>

        {/* Quarterly reports callout */}
        <div className="mt-10 rounded-xl border border-border bg-surface px-5 py-4 flex items-start gap-3">
          <span className="font-data text-xs text-violet-500 font-semibold uppercase tracking-wide shrink-0 mt-0.5">
            New
          </span>
          <p className="text-sm text-text-secondary leading-relaxed">
            <span className="font-medium text-text-primary">Quarterly summaries.</span>{" "}
            After three monthly closes, IronLedger generates a quarter-over-quarter
            narrative with trend analysis and recurring anomaly patterns.
          </p>
        </div>
      </section>

      {/* §3 — How We Know the Numbers Are Right */}
      <section className="max-w-[720px] mx-auto px-6 py-20 border-t border-border">
        <p className="font-data text-xs text-text-secondary mb-8 tracking-widest uppercase">
          §3 · Trust
        </p>

        <h2 className="font-serif text-3xl md:text-4xl font-semibold leading-tight text-text-primary mb-10">
          How we know the{" "}
          <span className="italic text-accent">numbers are right.</span>
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

        <div className="border-l-2 border-accent/30 pl-5 mt-12 space-y-3 font-data text-sm text-text-secondary">
          <p className="flex items-start gap-2">
            <span className="text-emerald-600 font-semibold shrink-0 mt-0.5">✓</span>
            Accepted · The report said "$4.8M revenue" — pandas had $4,730,000.
            Difference 1.46%, within tolerance.
          </p>
          <p className="flex items-start gap-2">
            <span className="text-severity-high-fg font-semibold shrink-0 mt-0.5">✗</span>
            Rejected · The report said "$5.1M revenue" — pandas had $4,730,000.
            Difference 7.8%, outside tolerance. Rewritten on second pass.
          </p>
        </div>
      </section>

      {/* §4 — CTA */}
      <section className="max-w-[720px] mx-auto px-6 py-24 border-t border-border">
        <p className="font-data text-xs text-text-secondary mb-8 tracking-widest uppercase">
          §4 · Try It
        </p>

        <h2 className="font-serif text-3xl md:text-4xl font-semibold leading-tight text-text-primary mb-5">
          Try it on a{" "}
          <span className="italic text-accent">real month.</span>
        </h2>

        <p className="text-lg text-text-secondary max-w-[500px] mb-10 leading-relaxed">
          Create an account and upload any GL export from your accounting
          system. You'll see the first draft of the close report in under two
          minutes — ready to email directly from the app.
        </p>

        <div className="flex items-center gap-4 flex-wrap">
          <a
            href="/register"
            className="inline-block rounded-md bg-accent text-white px-8 py-3 text-base font-medium hover:bg-accent/90 hover:scale-[1.015] active:scale-[0.97] transition-all [transition-duration:var(--duration-base)] focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
          >
            Get Started →
          </a>
          <p className="text-sm text-text-secondary">
            Private by default. We never train on your data.
          </p>
        </div>
      </section>

      {/* §5 — The Memo */}
      <section className="max-w-[720px] mx-auto px-6 py-20 border-t border-border">
        <p className="font-data text-xs text-text-secondary mb-8 tracking-widest uppercase">
          §5 · Commitments
        </p>

        <div className="font-data text-sm text-text-secondary mb-10 space-y-1 border border-border rounded-xl px-5 py-4 bg-surface">
          <p><span className="uppercase tracking-wider text-text-primary">To:</span>{" "}Finance directors evaluating IronLedger</p>
          <p><span className="uppercase tracking-wider text-text-primary">From:</span>{" "}The IronLedger team</p>
          <p><span className="uppercase tracking-wider text-text-primary">Re:</span>{" "}What this tool will not do</p>
          <p><span className="uppercase tracking-wider text-text-primary">Date:</span> April 2026</p>
        </div>

        <ol className="space-y-5 text-base leading-relaxed text-text-primary list-decimal list-outside pl-6 marker:text-accent marker:font-data marker:text-sm marker:font-semibold">
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
          <li>
            We do not lock you in. The report is plain text you own — no
            proprietary format, no vendor dependency, no export gate.
          </li>
        </ol>

        <p className="text-base text-text-primary mt-10 leading-relaxed">
          If any of the above stops being true, this page will be updated the
          same day.
        </p>

        <p className="font-data text-sm text-text-secondary mt-6">
          — Jan, Founder
        </p>
      </section>

      <footer className="max-w-[720px] mx-auto px-6 py-8 border-t border-border flex items-center justify-between">
        <p className="font-data text-xs text-text-secondary uppercase tracking-widest">
          IronLedger · 2026
        </p>
        <p className="text-xs text-text-secondary">
          Built at Anthropic Hackathon, April 2026
        </p>
      </footer>
    </div>
  );
}

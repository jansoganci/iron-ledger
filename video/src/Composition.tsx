import {
  AbsoluteFill,
  Easing,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { TransitionSeries, springTiming } from "@remotion/transitions";
import { slide } from "@remotion/transitions/slide";

const sceneDurations = {
  intro: 120,
  ingest: 155,
  orchestrate: 165,
  python: 110,
  narrative: 105,
  guardrail: 170,
  report: 98,
  close: 125,
};

export const TOTAL_FRAMES =
  Object.values(sceneDurations).reduce((a, b) => a + b, 0) -
  (Object.keys(sceneDurations).length - 1) * 15;

const enter = (frame: number, from: number, duration = 24) =>
  interpolate(frame, [from, from + duration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

const exit = (frame: number, from: number, duration = 24) =>
  interpolate(frame, [from, from + duration], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.in(Easing.cubic),
  });

const px = (value: number) => `${value}px`;

export const MonthProofShowcase = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill className="stage">
      <Background />
      <TopBar />
      <TransitionSeries>
        <TransitionSeries.Sequence durationInFrames={sceneDurations.intro}>
          <IntroScene />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition
          presentation={slide({ direction: "from-right" })}
          timing={springTiming({ config: { damping: 24, stiffness: 140, mass: 0.8 } })}
        />
        <TransitionSeries.Sequence durationInFrames={sceneDurations.ingest}>
          <IngestScene />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition
          presentation={slide({ direction: "from-right" })}
          timing={springTiming({ config: { damping: 24, stiffness: 140, mass: 0.8 } })}
        />
        <TransitionSeries.Sequence durationInFrames={sceneDurations.orchestrate}>
          <OrchestrationScene />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition
          presentation={slide({ direction: "from-right" })}
          timing={springTiming({ config: { damping: 24, stiffness: 140, mass: 0.8 } })}
        />
        <TransitionSeries.Sequence durationInFrames={sceneDurations.python}>
          <PythonScene />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition
          presentation={slide({ direction: "from-right" })}
          timing={springTiming({ config: { damping: 24, stiffness: 140, mass: 0.8 } })}
        />
        <TransitionSeries.Sequence durationInFrames={sceneDurations.narrative}>
          <NarrativeScene />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition
          presentation={slide({ direction: "from-right" })}
          timing={springTiming({ config: { damping: 24, stiffness: 140, mass: 0.8 } })}
        />
        <TransitionSeries.Sequence durationInFrames={sceneDurations.guardrail}>
          <GuardrailScene />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition
          presentation={slide({ direction: "from-right" })}
          timing={springTiming({ config: { damping: 24, stiffness: 140, mass: 0.8 } })}
        />
        <TransitionSeries.Sequence durationInFrames={sceneDurations.report}>
          <ReportScene />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition
          presentation={slide({ direction: "from-right" })}
          timing={springTiming({ config: { damping: 24, stiffness: 140, mass: 0.8 } })}
        />
        <TransitionSeries.Sequence durationInFrames={sceneDurations.close}>
          <ClosingScene />
        </TransitionSeries.Sequence>
      </TransitionSeries>
      <ProgressRail frame={frame} />
    </AbsoluteFill>
  );
};

const Background = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const drift = interpolate(frame, [0, durationInFrames], [0, 80]);

  return (
    <AbsoluteFill
      style={{
        background:
          "radial-gradient(circle at 18% 12%, rgba(240,132,8,0.14), transparent 26%), radial-gradient(circle at 84% 24%, rgba(22,160,102,0.12), transparent 25%), linear-gradient(135deg, #FAFAF8 0%, #F4F3F0 48%, #EFEDE8 100%)",
      }}
    >
      <div
        className="grain"
        style={{
          transform: `translate3d(${px(-drift * 0.25)}, ${px(drift * 0.14)}, 0)`,
        }}
      />
      <div className="vignette" />
    </AbsoluteFill>
  );
};

const TopBar = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [8, 34, TOTAL_FRAMES - 50, TOTAL_FRAMES], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div className="topbar" style={{ opacity }}>
      <Wordmark />
      <div className="topbarMeta">AGENTIC FINANCE OPERATIONS</div>
    </div>
  );
};

const Wordmark = () => (
  <div className="wordmark">
    <div className="wordmarkMark">M</div>
    <span>MonthProof</span>
  </div>
);

const IntroScene = () => {
  const frame = useCurrentFrame();
  const local = frame;
  const titleIn = enter(local, 8, 34);
  const proofIn = enter(local, 48, 28);

  return (
    <AbsoluteFill className="scene intro">
      <div
        className="introStack"
        style={{
          opacity: titleIn,
          transform: `translateY(${px((1 - titleIn) * 34)})`,
        }}
      >
        <p className="kicker">Built for messy month-end reality</p>
        <h1>
          Finance agents
          <br />
          with receipts.
        </h1>
      </div>
      <div
        className="introProof"
        style={{
          opacity: proofIn,
          transform: `translateY(${px((1 - proofIn) * 20)})`,
        }}
      >
        <span>Python computes.</span>
        <span>Claude interprets.</span>
        <span>Guardrails verify.</span>
      </div>
    </AbsoluteFill>
  );
};

const IngestScene = () => {
  const frame = useCurrentFrame();
  const local = frame;

  return (
    <AbsoluteFill className="scene splitScene">
      <SceneLabel index="01" title="Messy spreadsheets enter the system" />
      <div className="spreadsheetStack">
        {["GL_export_march.xlsx", "payroll_variance.csv", "supplier_invoices.xlsx"].map(
          (name, index) => (
            <SpreadsheetCard key={name} name={name} index={index} local={local} />
          ),
        )}
      </div>
      <PipelinePanel local={local} />
    </AbsoluteFill>
  );
};

const SpreadsheetCard = ({
  name,
  index,
  local,
}: {
  name: string;
  index: number;
  local: number;
}) => {
  const appear = enter(local, 8 + index * 12, 24);
  const travel = interpolate(local, [60 + index * 7, 118 + index * 7], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.inOut(Easing.cubic),
  });

  return (
    <div
      className="sheetCard"
      style={{
        opacity: appear,
        transform: `translate3d(${px(travel * 425)}, ${px(index * 80 + (1 - appear) * 30)}, 0) rotate(${index * -2 + travel * 4}deg)`,
      }}
    >
      <div className="sheetHeader">
        <span>{name}</span>
        <b>{index === 1 ? "CSV" : "XLSX"}</b>
      </div>
      <div className="sheetGrid">
        {Array.from({ length: 24 }).map((_, cell) => (
          <i key={cell} className={cell % 7 === 0 ? "hotCell" : ""} />
        ))}
      </div>
    </div>
  );
};

const PipelinePanel = ({ local }: { local: number }) => {
  const reveal = enter(local, 42, 28);
  const pulse = interpolate(local % 44, [0, 22, 44], [0.25, 1, 0.25]);

  return (
    <div
      className="pipelinePanel"
      style={{
        opacity: reveal,
        transform: `translateX(${px((1 - reveal) * 30)})`,
      }}
    >
      <div className="panelHeader">
        <span>ingestion queue</span>
        <b>3 files</b>
      </div>
      {["Header detection", "Schema normalization", "Source provenance"].map(
        (item, index) => (
          <div className="pipelineRow" key={item}>
            <span>{`0${index + 1}`}</span>
            <strong>{item}</strong>
            <em style={{ opacity: index === 2 ? pulse : 1 }}>verified</em>
          </div>
        ),
      )}
    </div>
  );
};

const OrchestrationScene = () => {
  const frame = useCurrentFrame();
  const local = frame;
  const flow = interpolate(local, [18, 145], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill className="scene orchestrate">
      <SceneLabel index="02" title="Agents coordinate the workflow" />
      <div className="agentMap">
        <Connector x1={320} y1={245} x2={620} y2={245} progress={flow} />
        <Connector x1={620} y1={245} x2={920} y2={245} progress={flow - 0.18} />
        <Connector x1={920} y1={245} x2={1220} y2={245} progress={flow - 0.34} />
        <Connector x1={920} y1={245} x2={920} y2={455} progress={flow - 0.48} />
        <AgentNode label="Parser" detail="extracts facts" x={220} y={165} active={local > 24} />
        <AgentNode label="Mapper" detail="normalizes accounts" x={520} y={165} active={local > 52} />
        <AgentNode label="Analyzer" detail="runs variance logic" x={820} y={165} active={local > 82} />
        <AgentNode label="Writer" detail="drafts narrative" x={1120} y={165} active={local > 108} />
        <AgentNode label="Guardrail" detail="blocks bad numbers" x={820} y={375} active={local > 125} />
      </div>
    </AbsoluteFill>
  );
};

const Connector = ({
  x1,
  y1,
  x2,
  y2,
  progress,
}: {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  progress: number;
}) => {
  const clamped = Math.max(0, Math.min(1, progress));
  const length = Math.hypot(x2 - x1, y2 - y1);
  const angle = Math.atan2(y2 - y1, x2 - x1);

  return (
    <div
      className="connector"
      style={{
        left: x1,
        top: y1,
        width: length,
        transform: `rotate(${angle}rad)`,
      }}
    >
      <i style={{ width: `${clamped * 100}%` }} />
    </div>
  );
};

const AgentNode = ({
  label,
  detail,
  x,
  y,
  active,
}: {
  label: string;
  detail: string;
  x: number;
  y: number;
  active: boolean;
}) => {
  const frame = useCurrentFrame();
  const scale = active
    ? spring({
        frame: frame % 38,
        fps: 30,
        config: { damping: 18, stiffness: 90 },
      })
    : 0.96;

  return (
    <div
      className={active ? "agentNode active" : "agentNode"}
      style={{ left: x, top: y, transform: `scale(${scale})` }}
    >
      <span>{label}</span>
      <small>{detail}</small>
    </div>
  );
};

const PythonScene = () => {
  const frame = useCurrentFrame();
  const local = frame;
  const rows = ["revenue", "cogs", "payroll", "travel", "software", "rent"];

  return (
    <AbsoluteFill className="scene pythonScene">
      <SceneLabel index="03" title="Calculations stay deterministic" />
      <div className="codeWindow">
        <div className="windowDots">
          <i />
          <i />
          <i />
        </div>
        <pre>
          <code>
            {`df = normalize(source_files)
baseline = history.trailing_months(6)
variance = compare(df, baseline)
anomalies = variance.where(abs(delta_pct) > threshold)`}
          </code>
        </pre>
      </div>
      <div className="ledgerTable">
        <div className="tableHead">
          <span>account</span>
          <span>actual</span>
          <span>delta</span>
          <span>status</span>
        </div>
        {rows.map((row, index) => (
          <LedgerRow key={row} label={row} index={index} local={local} />
        ))}
      </div>
      <div className="pythonCallout">
        <strong>Python does the math.</strong>
        <span>No model arithmetic enters the report.</span>
      </div>
    </AbsoluteFill>
  );
};

const LedgerRow = ({
  label,
  index,
  local,
}: {
  label: string;
  index: number;
  local: number;
}) => {
  const reveal = enter(local, 28 + index * 10, 18);
  const values = ["$4.73M", "$1.21M", "$842K", "$101K", "$64K", "$48K"];
  const deltas = ["+8.2%", "-1.4%", "+2.0%", "+61.0%", "+11.7%", "0.0%"];
  const hot = label === "travel";

  return (
    <div
      className={hot ? "ledgerRow hot" : "ledgerRow"}
      style={{
        opacity: reveal,
        transform: `translateY(${px((1 - reveal) * 14)})`,
      }}
    >
      <span>{label}</span>
      <span>{values[index]}</span>
      <span>{deltas[index]}</span>
      <span>{hot ? "flagged" : "normal"}</span>
    </div>
  );
};

const typewriter = (text: string, frame: number, startFrame: number, charsPerFrame: number = 2): string => {
  const charCount = Math.floor(Math.max(0, (frame - startFrame) * charsPerFrame));
  return text.substring(0, Math.min(charCount, text.length));
};

const NarrativeScene = () => {
  const frame = useCurrentFrame();
  const local = frame;
  const anomalyReveal = enter(local, 0, 18);
  const text = "Travel spending increased sharply in the final week of March, matching the timing pattern of an offsite rather than a recurring run-rate change.";

  return (
    <AbsoluteFill className="scene narrativeScene">
      <SceneLabel index="04" title="Claude turns results into operator language" />
      <div
        className="anomalyCard"
        style={{
          opacity: anomalyReveal,
          transform: `translateX(${px((1 - anomalyReveal) * -40)})`,
        }}
      >
        <div className="cardTop">
          <span>High variance</span>
          <b>Travel & Entertainment</b>
        </div>
        <div className="metricLine">
          <strong>+$38,420</strong>
          <span>+61% vs baseline</span>
        </div>
        <div className="sparkline">
          {[48, 50, 52, 49, 51, 48, 50, 53, 47, 52, 50, 49, 55, 62, 78, 101, 118, 130].map((value, index) => (
            <i
              key={index}
              style={{
                height: `${value * 0.85 + 20}px`,
                background: index < 14
                  ? "linear-gradient(180deg, #f08408, #feda9a)"
                  : "linear-gradient(180deg, #b91c1c, #f08408)",
              }}
            />
          ))}
        </div>
      </div>
      <div className="narrativeCard">
        <span>draft interpretation</span>
        <p>
          {typewriter(text, local, 12, 2.5)}
          {local >= 12 + Math.ceil(text.length / 2.5) && <span className="cursor">|</span>}
        </p>
      </div>
    </AbsoluteFill>
  );
};

const GuardrailScene = () => {
  const frame = useCurrentFrame();
  const local = frame;
  const passIn = enter(local, 145, 20);
  const counter = Math.min(5, Math.max(0, Math.floor((local - 80) / 14) + 1));

  const numbers = [
    { p: "$4,730,000", a: "$4.73M" },
    { p: "$101,000", a: "$101K" },
    { p: "+61.0%", a: "61%" },
    { p: "$38,420", a: "$38,420" },
    { p: "$48,000", a: "$48K" },
  ];

  const phase1 = local < 40;
  const phase2 = local >= 40 && local < 80;
  const phase3 = local >= 80;

  const failFlashOpacity = phase1
    ? enter(local, 0, 12) * exit(local, 30, 10)
    : 0;

  const phase1Opacity = phase1 ? 1 : 0;
  const phase2Opacity = phase2 ? enter(local - 40, 4, 14) * exit(local - 40, 28, 12) : 0;
  const phase3Opacity = phase3 ? enter(local - 80, 0, 18) : 0;

  return (
    <AbsoluteFill className="scene guardrailScene">
      <SceneLabel index="05" title="The Golden Rule: every number is verified before it ships" />

      {phase1 && (
        <div className="verifyList" style={{ opacity: phase1Opacity }}>
          <div className="verifyListInner">
            <div className="verifyingRow">
              <span className="pandasVal">$4,730,000</span>
              <span className="arrow">→</span>
              <span className="aiVal mismatch">$4.80M</span>
              <span className="check" style={{ color: "#b91c1c" }}>✗</span>
            </div>
            <div className="failFlash" style={{ opacity: failFlashOpacity }}>
              Mismatch: $4,800,000 not found in pandas output
            </div>
          </div>
        </div>
      )}

      {phase2 && (
        <div className="retryText" style={{ opacity: phase2Opacity }}>
          Retrying with reinforced prompt…
        </div>
      )}

      {phase3 && (
        <>
          <div className="verifyList" style={{ opacity: phase3Opacity }}>
            <div className="verifyListInner">
              {numbers.map((n, i) => {
                const revealed = i < counter;
                return (
                  <div
                    key={i}
                    className="verifyingRow"
                    style={{
                      opacity: revealed ? 1 : 0.2,
                      transform: revealed ? "translateX(0)" : "translateX(-10px)",
                      transition: "opacity 0.3s, transform 0.3s",
                    }}
                  >
                    <span className="pandasVal">{n.p}</span>
                    <span className="arrow">→</span>
                    <span className="aiVal">{n.a}</span>
                    <span className="check">{revealed ? "✓" : ""}</span>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="counterBadge" style={{ opacity: phase3Opacity }}>
            {counter} / 5 numbers verified ✓
          </div>

          <div
            className="passedBanner"
            style={{
              opacity: passIn,
              transform: `scale(${0.92 + passIn * 0.08})`,
            }}
          >
            <strong>Guardrail passed</strong>
            <span>Every reported number independently verified against source data.</span>
          </div>
        </>
      )}
    </AbsoluteFill>
  );
};

const ReportScene = () => {
  const frame = useCurrentFrame();
  const local = frame;

  return (
    <AbsoluteFill className="scene reportScene">
      <SceneLabel index="06" title="A verified report leaves the pipeline" />
      <div className="reportFrame">
        <div className="reportHeader">
          <Wordmark />
          <span>March close report</span>
        </div>
        <div className="reportHero">
          <strong>Ready for review</strong>
          <span>5 anomalies · 31 reconciliations · 0 unverified claims</span>
        </div>
        <div className="reportCards">
          {["Revenue bridge", "Travel spike", "Supplier cleanup"].map((item, index) => (
            <div
              key={item}
              className="miniReport"
              style={{
                opacity: enter(local, 34 + index * 13, 18),
                transform: `translateY(${px((1 - enter(local, 34 + index * 13, 18)) * 16)})`,
              }}
            >
              <b>{item}</b>
              <span>{index === 1 ? "requires review" : "verified"}</span>
            </div>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};

const ClosingScene = () => {
  const frame = useCurrentFrame();
  const local = frame;
  const inA = enter(local, 0, 32);
  const inB = enter(local, 38, 26);

  return (
    <AbsoluteFill className="scene closingScene">
      <div
        className="closingWordmark"
        style={{
          opacity: inA,
          transform: `translateY(${px((1 - inA) * 22)})`,
        }}
      >
        <Wordmark />
      </div>
      <h2
        style={{
          opacity: inB,
          transform: `translateY(${px((1 - inB) * 24)})`,
        }}
      >
        AI agents for real financial operations.
      </h2>
    </AbsoluteFill>
  );
};

const SceneLabel = ({ index, title }: { index: string; title: string }) => {
  const frame = useCurrentFrame();
  const local = frame % 200;
  const reveal = enter(local, 0, 18);

  return (
    <div
      className="sceneLabel"
      style={{
        opacity: reveal,
        transform: `translateY(${px((1 - reveal) * 12)})`,
      }}
    >
      <span>{index}</span>
      <b>{title}</b>
    </div>
  );
};

const ProgressRail = ({ frame }: { frame: number }) => {
  const { durationInFrames } = useVideoConfig();
  const progress = interpolate(frame, [0, durationInFrames], [0, 100]);

  return (
    <div className="progressRail">
      <i style={{ width: `${progress}%` }} />
    </div>
  );
};

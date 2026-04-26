// Month Proof Dashboard — Shared Components + Both Variations
// Exported to window for use in main HTML file

const { useState, useEffect, useRef } = React;

/* ─── DATA ─── */
const KPIS = [
  { key:'revenue',  label:'Revenue',           prefix:'$', value:'$564,300', raw:'564300', trend:'+4.5% MoM',   pos:true,  sub:null,                   accent:'amber'   },
  { key:'margin',   label:'Gross Margin',       prefix:'~', value:'79.5%',   raw:null,     trend:'+0.4pp',       pos:true,  sub:null,                   accent:'emerald' },
  { key:'income',   label:'Net Income',         prefix:'$', value:'$82,100', raw:'82100',  trend:'+86.6% MoM',   pos:true,  sub:'14.5% net margin',     accent:'emerald' },
  { key:'opex',     label:'Operating Expenses', prefix:'$', value:'$366,700',raw:'366700', trend:null,           pos:null,  sub:'65.0% of revenue',     accent:'neutral' },
  { key:'issues',   label:'Critical Issues',    prefix:'!', value:'3',       raw:'3',      trend:null,           pos:false, sub:'3 high/medium anomalies',accent:'red'    },
  { key:'health',   label:'Financial Health',   prefix:'~', value:'Profitable',raw:null,   trend:null,           pos:true,  sub:'14.5% net margin',     accent:'emerald' },
];

const REPORTS = [
  { period:'Mar 2026', anomalies:3, generated:'Apr 26, 2026', hasIssues:true  },
  { period:'Feb 2026', anomalies:3, generated:'Apr 26, 2026', hasIssues:true  },
  { period:'Jan 2026', anomalies:0, generated:'Apr 26, 2026', hasIssues:false },
  { period:'Dec 2025', anomalies:1, generated:'Apr 26, 2026', hasIssues:true  },
  { period:'Nov 2025', anomalies:0, generated:'Apr 26, 2026', hasIssues:false },
  { period:'Oct 2025', anomalies:0, generated:'Apr 26, 2026', hasIssues:false },
  { period:'Sep 2025', anomalies:0, generated:'Mar 26, 2026', hasIssues:false },
  { period:'Aug 2025', anomalies:0, generated:'Feb 26, 2026', hasIssues:false },
];

const REPORT_REV = {
  'Mar 2026':'$564,300','Feb 2026':'$539,100','Jan 2026':'$512,800',
  'Dec 2025':'$498,200','Nov 2025':'$487,000','Oct 2025':'$471,500',
  'Sep 2025':'$462,300','Aug 2025':'$451,700',
};

const SPARKLINES = {
  'Mar 2026':[513,539,564], 'Feb 2026':[498,513,539],
  'Jan 2026':[487,498,513], 'Dec 2025':[471,487,498],
  'Nov 2025':[462,471,487], 'Oct 2025':[452,462,471],
  'Sep 2025':[443,452,462], 'Aug 2025':[434,443,452],
};

const AGENT_FINDINGS = [
  { sev:'high',   text:'Duplicate vendor payment — T&E', amount:'$8,200',  code:'AP-4421' },
  { sev:'medium', text:'Missing GL reference × 4 items', amount:'$3,450',  code:'GL-UNKN' },
  { sev:'medium', text:'Approval delay: 2 items >48h',   amount:null,      code:'PO-8832' },
];

/* ─── ICONS ─── */
const Ic = ({d,size=16,stroke='currentColor',sw=1.5,fill='none',vb='0 0 16 16'}) => (
  <svg width={size} height={size} viewBox={vb} fill={fill} stroke={stroke} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
    <path d={d}/>
  </svg>
);
const IcDashboard = ({size=16,color='currentColor'}) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth="1.4" strokeLinecap="round">
    <rect x="1.5" y="1.5" width="5.5" height="5.5" rx="1.2"/><rect x="9" y="1.5" width="5.5" height="5.5" rx="1.2"/>
    <rect x="1.5" y="9" width="5.5" height="5.5" rx="1.2"/><rect x="9" y="9" width="5.5" height="5.5" rx="1.2"/>
  </svg>
);
const IcUpload = ({size=16,color='currentColor'}) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2.5 11v2a.5.5 0 00.5.5h10a.5.5 0 00.5-.5v-2M8 2.5v8M5 5.5l3-3 3 3"/>
  </svg>
);
const IcData = ({size=16,color='currentColor'}) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth="1.4" strokeLinecap="round">
    <path d="M2 4h12M2 8h12M2 12h8"/>
  </svg>
);
const IcReports = ({size=16,color='currentColor'}) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth="1.4" strokeLinecap="round">
    <path d="M3 1.5h7l3.5 3.5V14a.5.5 0 01-.5.5H3a.5.5 0 01-.5-.5V2a.5.5 0 01.5-.5z"/>
    <path d="M10 1.5V5H13.5M5 8.5h6M5 11h4"/>
  </svg>
);
const IcChevron = ({size=14}) => (
  <svg width={size} height={size} viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M5 3l4 4-4 4"/>
  </svg>
);
const IcArrow = ({size=14}) => (
  <svg width={size} height={size} viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2 7h10M8 3l4 4-4 4"/>
  </svg>
);
const IcTrendUp = ({size=12}) => (
  <svg width={size} height={size} viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <path d="M1 9l3.5-3.5 2.5 2.5L11 2M11 2H7.5M11 2v3.5"/>
  </svg>
);
const IcDollar = ({size=11}) => (
  <svg width={size} height={size} viewBox="0 0 11 11" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round">
    <path d="M5.5 1v9M3 3.5a2.5 1.5 0 015 0 2.5 1.5 0 01-5 0zM3 7.5a2.5 1.5 0 005 0"/>
  </svg>
);
const IcSpark = ({size=11}) => (
  <svg width={size} height={size} viewBox="0 0 11 11" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round">
    <path d="M1 7.5l2.5-3.5 2 2L8.5 2 10 4"/>
  </svg>
);
const IcAlert = ({size=11}) => (
  <svg width={size} height={size} viewBox="0 0 11 11" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round">
    <path d="M5.5 1L1 9.5h9L5.5 1z"/><path d="M5.5 4.5v2.5M5.5 8.5v.5"/>
  </svg>
);
const IcSignOut = ({size=14}) => (
  <svg width={size} height={size} viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9.5 4.5L12 7l-2.5 2.5M12 7H5.5M7 2H3a.5.5 0 00-.5.5v9A.5.5 0 003 12h4"/>
  </svg>
);

/* ─── MINI SPARKLINE ─── */
const MiniSparkline = ({data, color='#16A066', w=72, h=28, showFill=true}) => {
  const min = Math.min(...data);
  const max = Math.max(...data);
  const rng = (max - min) || 1;
  const pts = data.map((v, i) => ({
    x: parseFloat(((i / (data.length-1)) * w).toFixed(1)),
    y: parseFloat((h - ((v-min)/rng) * (h-8) - 4).toFixed(1)),
  }));
  const polyPts = pts.map(p => `${p.x},${p.y}`).join(' ');
  const lastPt = pts[pts.length-1];
  const areaPath = `M ${pts[0].x},${h} ${polyPts} L ${lastPt.x},${h} Z`;
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} fill="none">
      {showFill && <path d={areaPath} fill={color} opacity="0.1"/>}
      <polyline points={polyPts} stroke={color} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
      <circle cx={lastPt.x} cy={lastPt.y} r="2.5" fill={color}/>
    </svg>
  );
};

/* ─── AGENT PULSE DOT ─── */
const AgentPulse = ({size=8}) => (
  <span style={{position:'relative',display:'inline-flex',width:size,height:size,flexShrink:0}}>
    <span style={{position:'absolute',inset:0,borderRadius:'50%',background:'var(--violet-400)',opacity:.5,animation:'agentRing 1.8s ease-out infinite'}}/>
    <span style={{position:'relative',width:'100%',height:'100%',borderRadius:'50%',background:'var(--violet-500)'}}/>
  </span>
);

/* ─── SIDEBAR ─── */
const NAV_ITEMS = [
  { key:'dashboard', label:'Dashboard', Icon:IcDashboard },
  { key:'upload',    label:'Upload',    Icon:IcUpload    },
  { key:'data',      label:'Data',      Icon:IcData      },
  { key:'reports',   label:'Reports',   Icon:IcReports   },
];

const Sidebar = ({active='dashboard', onNav}) => (
  <aside className="sidebar">
    <div className="sidebar-brand">
      <div className="sidebar-logo">Month Proof</div>
      <div className="sidebar-context">Month-end close</div>
    </div>
    <nav className="sidebar-nav">
      {NAV_ITEMS.map(({key,label,Icon}) => {
        const isActive = active === key;
        return (
          <div key={key} className={`nav-item ${isActive?'active':''}`} onClick={()=>onNav?.(key)}>
            <Icon size={15} color={isActive ? 'var(--amber-700)' : 'var(--neutral-500)'}/>
            {label}
          </div>
        );
      })}
    </nav>
    <div className="sidebar-footer">
      <div className="sidebar-company">Sentinel Secure</div>
      <div className="sidebar-email">demo@dronedemo.com</div>
      <div className="sidebar-signout">
        <IcSignOut size={13}/> Sign out
      </div>
    </div>
  </aside>
);

/* ─── SHARED BADGE ─── */
const SevBadge = ({sev}) => {
  const map = {
    high:   {bg:'#FEF0F0',color:'#B91C1C',border:'#FECACA',label:'High'},
    medium: {bg:'var(--amber-50)',color:'var(--amber-700)',border:'var(--amber-200)',label:'Medium'},
    normal: {bg:'var(--neutral-100)',color:'var(--neutral-600)',border:'var(--neutral-200)',label:'Normal'},
  };
  const s = map[sev] || map.normal;
  return (
    <span style={{
      fontSize:10,fontWeight:600,letterSpacing:'0.04em',textTransform:'uppercase',
      padding:'2px 6px',borderRadius:4,border:`1px solid ${s.border}`,
      background:s.bg,color:s.color,
    }}>{s.label}</span>
  );
};

/* ══════════════════════════════════════════════
   VARIATION A — Safe Evolution
   Same structure, evolved tokens + agent strip
══════════════════════════════════════════════ */

const KPIAccentColor = {
  amber:'var(--amber-500)', emerald:'var(--emerald-500)',
  neutral:'var(--neutral-300)', red:'#DC2626',
};
const KPIValueColor = {
  amber:'var(--amber-700)', emerald:'var(--emerald-600)',
  neutral:'var(--text-primary)', red:'#B91C1C',
};

const KPICard = ({kpi}) => {
  const accentColor = KPIAccentColor[kpi.accent] || 'var(--neutral-300)';
  const valueColor = kpi.accent === 'red' ? '#B91C1C' : kpi.accent === 'amber' ? 'var(--amber-700)' : kpi.accent === 'emerald' ? 'var(--emerald-700)' : 'var(--text-primary)';
  const LabelIcon = kpi.prefix === '$' ? IcDollar : kpi.prefix === '~' ? IcSpark : IcAlert;
  return (
    <div className="kpi-card" style={{borderLeft:`3px solid ${accentColor}`}}>
      <div className="kpi-label">
        <LabelIcon size={11}/>{kpi.label}
      </div>
      <div className="kpi-value" style={{color:valueColor}}>{kpi.value}</div>
      {kpi.trend && (
        <div className="kpi-trend" style={{color: kpi.pos ? 'var(--emerald-600)' : '#B91C1C'}}>
          <IcTrendUp size={11}/> {kpi.trend}
        </div>
      )}
      {kpi.sub && <div className="kpi-sub">{kpi.sub}</div>}
    </div>
  );
};

const AgentStrip = () => {
  const [msgIdx, setMsgIdx] = useState(0);
  const msgs = [
    'Reviewing Mar 2026 — found 3 variance patterns',
    'Cross-referencing 847 rows against GL codes',
    'Duplicate vendor entry detected in Operating Expenses',
  ];
  useEffect(() => {
    const t = setInterval(() => setMsgIdx(i => (i+1) % msgs.length), 3200);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="agent-strip">
      <AgentPulse size={8}/>
      <span className="agent-strip-label">Agent · Running</span>
      <span className="agent-strip-divider"/>
      <span className="agent-strip-msg" key={msgIdx}>{msgs[msgIdx]}</span>
      <span style={{flex:1}}/>
      <span className="agent-strip-link">3 findings <IcChevron size={11}/></span>
    </div>
  );
};

const ReportRow = ({report, delay=0}) => {
  const [hovered, setHovered] = useState(false);
  return (
    <div
      className="report-row"
      style={{animationDelay:`${delay}ms`}}
      onMouseEnter={()=>setHovered(true)}
      onMouseLeave={()=>setHovered(false)}
    >
      <span className={`report-dot ${report.hasIssues?'has-issues':''}`}/>
      <div style={{flex:1}}>
        <div className="report-period">{report.period}</div>
        <div className="report-meta">
          {report.anomalies > 0
            ? <span className="report-anomaly-count">{report.anomalies} {report.anomalies===1?'anomaly':'anomalies'}</span>
            : <span style={{color:'var(--emerald-600)',fontWeight:500}}>No anomalies</span>
          }
          <span style={{color:'var(--text-tertiary)',margin:'0 6px'}}>·</span>
          <span style={{color:'var(--text-tertiary)'}}>Generated {report.generated}</span>
        </div>
      </div>
      {SPARKLINES[report.period] && (
        <div style={{opacity: hovered ? 1 : 0.5, transition:'opacity 140ms'}}>
          <MiniSparkline
            data={SPARKLINES[report.period]}
            color={report.hasIssues ? 'var(--amber-500)' : 'var(--emerald-500)'}
            w={56} h={22} showFill={false}
          />
        </div>
      )}
      <div className="report-rev" style={{opacity: hovered ? 1 : 0}}>{REPORT_REV[report.period]}</div>
      <IcChevron size={13}/>
    </div>
  );
};

const VariationA = ({activeNav, onNav}) => {
  const [period, setPeriod] = useState('Monthly');
  return (
    <div className="var-a-layout">
      <Sidebar active={activeNav} onNav={onNav}/>
      <main className="var-a-main">
        {/* Top bar */}
        <div className="var-a-topbar">
          <div>
            <h1 className="page-title">Dashboard</h1>
            <p className="page-subtitle">Sentinel Secure · Overview of your loaded data and recent reports.</p>
          </div>
          <button className="btn-primary-cta">
            <IcUpload size={14} color="white"/> Upload new period
          </button>
        </div>

        <div className="var-a-content">
          {/* KPI Grid */}
          <div className="kpi-grid">
            {KPIS.map(kpi => <KPICard key={kpi.key} kpi={kpi}/>)}
          </div>

          {/* Agent strip */}
          <AgentStrip/>

          {/* Q1 promo banner */}
          <div className="q1-banner">
            <div className="q1-banner-left">
              <IcSpark size={14} color="var(--emerald-600)"/>
              <span className="q1-banner-title">Q1 2026 is complete</span>
              <span className="q1-banner-sub">Generate a quarterly summary to see trends across the quarter</span>
            </div>
            <button className="btn-emerald-sm">Generate Quarterly Summary</button>
            <button className="q1-banner-x">×</button>
          </div>

          {/* Recent reports */}
          <div className="reports-section">
            <div className="reports-header">
              <span className="section-label">Recent reports</span>
              <div className="period-toggle">
                {['Monthly','Quarterly'].map(p => (
                  <button key={p} className={`period-pill ${period===p?'active':''}`} onClick={()=>setPeriod(p)}>{p}</button>
                ))}
              </div>
            </div>
            <div className="reports-list">
              {REPORTS.map((r, i) => <ReportRow key={r.period} report={r} delay={i*40}/>)}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

/* ══════════════════════════════════════════════
   VARIATION B — Bold: Editorial + Agent Panel
   Typographic metrics · Period cards · Right panel
══════════════════════════════════════════════ */

const HeadlineMetrics = () => {
  const metrics = [
    { label:'Revenue',      value:'$564,300', trend:'+4.5% MoM', pos:true  },
    { label:'Gross Margin', value:'79.5%',    trend:'+0.4pp',     pos:true  },
    { label:'Net Income',   value:'$82,100',  trend:'+86.6% MoM', pos:true  },
  ];
  return (
    <div className="headline-metrics">
      {metrics.map((m, i) => (
        <div key={m.label} className="headline-metric" style={{borderRight: i<2 ? '1px solid var(--border)' : 'none'}}>
          <div className="headline-label">{m.label}</div>
          <div className="headline-value">{m.value}</div>
          <div className="headline-trend" style={{color: m.pos ? 'var(--emerald-600)' : '#B91C1C'}}>
            <IcTrendUp size={11}/>{m.trend}
          </div>
        </div>
      ))}
      <div className="headline-metric headline-metric-right" style={{borderLeft:'1px solid var(--border)'}}>
        <div className="headline-label">Critical Issues</div>
        <div className="headline-value" style={{color:'#B91C1C',fontSize:38}}>3</div>
        <div style={{fontSize:11,color:'var(--text-tertiary)',marginTop:2}}>high/medium · Mar 2026</div>
      </div>
    </div>
  );
};

const PeriodCard = ({report, delay=0}) => {
  const [hov, setHov] = useState(false);
  const spark = SPARKLINES[report.period];
  const rev = REPORT_REV[report.period];
  return (
    <div
      className="period-card"
      style={{animationDelay:`${delay}ms`}}
      onMouseEnter={()=>setHov(true)}
      onMouseLeave={()=>setHov(false)}
    >
      <div className="period-card-header">
        <span className="period-card-label">{report.period}</span>
        {report.anomalies > 0
          ? <span className="period-anomaly-badge has-issues">{report.anomalies} {report.anomalies===1?'anomaly':'anomalies'}</span>
          : <span className="period-anomaly-badge clean">Clean</span>
        }
      </div>
      <div className="period-card-body">
        <div>
          <div className="period-rev">{rev || '—'}</div>
          <div className="period-rev-sub" style={{color:'var(--emerald-600)'}}>
            {report.period === 'Mar 2026' ? '+4.5% MoM' :
             report.period === 'Feb 2026' ? '+5.1% MoM' : '+3.1% MoM'}
          </div>
        </div>
        {spark && (
          <MiniSparkline
            data={spark}
            color={report.hasIssues ? 'var(--amber-500)' : 'var(--emerald-500)'}
            w={80} h={36}
          />
        )}
      </div>
      <div className="period-card-footer" style={{opacity: hov ? 1 : 0}}>
        View report <IcArrow size={12}/>
      </div>
    </div>
  );
};

const AgentPanel = () => {
  const [msgIdx, setMsgIdx] = useState(0);
  const tasks = ['Cross-referencing vendor entries…','Scanning GL codes for duplicates…','Validating approval workflows…'];
  useEffect(() => {
    const t = setInterval(() => setMsgIdx(i => (i+1) % tasks.length), 2800);
    return () => clearInterval(t);
  }, []);

  return (
    <aside className="agent-panel">
      <div className="agent-panel-header">
        <div className="agent-panel-title-row">
          <AgentPulse size={8}/>
          <span className="agent-panel-title">Agent</span>
          <span className="agent-running-chip">Running</span>
        </div>
        <div className="agent-panel-period">Mar 2026 · 847 rows</div>
      </div>

      {/* Current task */}
      <div className="agent-task-wrap">
        <div className="agent-task-label">Current task</div>
        <div className="agent-task-text" key={msgIdx}>{tasks[msgIdx]}</div>
        <div className="agent-progress-track">
          <div className="agent-progress-fill"/>
        </div>
      </div>

      {/* Findings */}
      <div className="agent-findings-wrap">
        <div className="agent-section-label">Findings so far</div>
        {AGENT_FINDINGS.map((f, i) => (
          <div className="agent-finding-row" key={i}>
            <span className={`finding-dot sev-${f.sev}`}/>
            <div style={{flex:1}}>
              <div className="finding-text">{f.text}</div>
              <div className="finding-code">{f.code}</div>
            </div>
            {f.amount && <div className="finding-amount">{f.amount}</div>}
          </div>
        ))}
      </div>

      {/* Q1 action */}
      <div className="agent-panel-action">
        <div className="q1-action-text">
          <IcSpark size={13} color="var(--emerald-600)"/>
          <div>
            <div style={{fontSize:12,fontWeight:600,color:'var(--text-primary)'}}>Q1 2026 complete</div>
            <div style={{fontSize:11,color:'var(--text-tertiary)'}}>Generate quarterly summary</div>
          </div>
        </div>
        <button className="btn-emerald-block">Generate Summary <IcArrow size={12}/></button>
      </div>

      {/* Data coverage */}
      <div className="agent-panel-footer">
        <div className="agent-footer-row"><span>Periods analyzed</span><span>18</span></div>
        <div className="agent-footer-row"><span>Total rows</span><span>14,832</span></div>
        <div className="agent-footer-row"><span>Last run</span><span>2m ago</span></div>
      </div>
    </aside>
  );
};

const VariationB = ({activeNav, onNav}) => {
  const [period, setPeriod] = useState('Monthly');
  return (
    <div className="var-b-layout">
      <Sidebar active={activeNav} onNav={onNav}/>
      <div className="var-b-center">
        {/* Top bar */}
        <div className="var-b-topbar">
          <div>
            <div className="var-b-eyebrow">Sentinel Secure</div>
            <h1 className="page-title" style={{fontSize:18,marginBottom:0}}>Dashboard</h1>
          </div>
          <div style={{display:'flex',gap:8,alignItems:'center'}}>
            <div className="period-toggle">
              {['Monthly','Quarterly'].map(p => (
                <button key={p} className={`period-pill ${period===p?'active':''}`} onClick={()=>setPeriod(p)}>{p}</button>
              ))}
            </div>
            <button className="btn-primary-cta"><IcUpload size={14} color="white"/> Upload new period</button>
          </div>
        </div>

        {/* Headline metrics */}
        <HeadlineMetrics/>

        {/* Period cards grid */}
        <div className="var-b-content">
          <div className="var-b-content-header">
            <span className="section-label">Period history</span>
            <span style={{fontSize:12,color:'var(--text-tertiary)'}}>18 total</span>
          </div>
          <div className="period-cards-grid">
            {REPORTS.map((r, i) => <PeriodCard key={r.period} report={r} delay={i*50}/>)}
          </div>
        </div>
      </div>

      <AgentPanel/>
    </div>
  );
};

/* ─── EXPORTS ─── */
Object.assign(window, {
  Sidebar, VariationA, VariationB,
  AgentPulse, MiniSparkline, SevBadge,
  KPIS, REPORTS, AGENT_FINDINGS, SPARKLINES,
});

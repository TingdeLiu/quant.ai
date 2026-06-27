// Tyndall Markets — AI equity-analysis dashboard (Claude-style)
// Shared chrome: data wiring, price chart, top bar, i18n helper.
const { Button, IconButton, Input, Badge, Card, Avatar, Tag } = window.ClaudeDesignSystem_9a1625;
const Ico = ({ n, s = 18 }) => <i data-lucide={n} style={{ width: s, height: s }}></i>;

// ---- language (driven by the server's config.language) -------------------
const LANG = (typeof window !== "undefined" && window.MARKETS_DATA && window.MARKETS_DATA.lang) || "en";
const ZH = LANG === "zh";
const T = (en, zh) => (ZH ? zh : en);

// ---- seeded data ---------------------------------------------------------
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function series(seed, n, drift) {
  const r = mulberry32(seed);
  const out = []; let v = 100;
  for (let i = 0; i < n; i++) { v += (r() - 0.5) * 6 + drift; out.push(v); }
  const min = Math.min(...out), max = Math.max(...out);
  return out.map((x) => (x - min) / (max - min || 1));
}

const _FB_TICKERS = {
  NVDA: {
    name: "NVIDIA Corporation", sector: "Semiconductors", price: 1284.32, chg: 2.41, seed: 7, drift: 0.55,
    stats: { "Market cap": "$3.16T", "P/E ratio": "68.4", "Volume": "41.2M", "52-wk range": "$394–$1,312", "Div yield": "0.02%", "Beta": "1.74" },
    rating: "Bullish", ratingLabel: "Bullish",
    recommendation: { stance: "Constructive · watch", tone: "success", line: "Trend and momentum are favorable — worth following in research; still mind position sizing and drawdown." },
    summary: "NVIDIA's data-center momentum remains the dominant story. The risk is concentration and a valuation that already prices in flawless execution.",
    bull: ["Data-center revenue up triple digits year over year", "Blackwell backlog extends visibility into 2027", "Software + networking deepen the platform lock-in"],
    bear: ["~40% of revenue from a few hyperscale buyers", "Custom silicon chips at the edges", "Multiple leaves little room for a demand air-pocket"],
  },
  AAPL: {
    name: "Apple Inc.", sector: "Consumer Electronics", price: 232.18, chg: -0.62, seed: 19, drift: 0.12,
    stats: { "Market cap": "$3.52T", "P/E ratio": "35.1", "Volume": "52.8M", "52-wk range": "$164–$237", "Div yield": "0.43%", "Beta": "1.21" },
    rating: "Neutral", ratingLabel: "Neutral",
    recommendation: { stance: "Neutral · hold", tone: "neutral", line: "The signal is neutral with no clear direction — wait for a stronger trend or a pullback to confirm." },
    summary: "Apple is a cash-compounding machine with a services flywheel. Near-term, iPhone units are flattish and the AI roadmap is still proving itself.",
    bull: ["Services at record gross margin and still growing", "Installed base over 2.2B active devices", "Buybacks shrink the share count every quarter"],
    bear: ["iPhone unit growth has stalled in key markets", "On-device AI features lag the frontier", "Regulatory pressure on App Store economics"],
  },
  TSLA: {
    name: "Tesla, Inc.", sector: "Automobiles", price: 408.77, chg: 4.18, seed: 31, drift: 0.34,
    stats: { "Market cap": "$1.31T", "P/E ratio": "112", "Volume": "98.4M", "52-wk range": "$138–$415", "Div yield": "—", "Beta": "2.31" },
    rating: "Volatile", ratingLabel: "Volatile",
    recommendation: { stance: "High volatility", tone: "warning", line: "Swings are large — a small size or watch-only posture fits, with strict risk control." },
    summary: "Tesla trades as an autonomy and energy option more than a carmaker. Auto margins are compressing while the bull case rests on robotaxi and storage scaling.",
    bull: ["Energy storage deployments inflecting sharply", "FSD and robotaxi optionality not in base numbers", "Cost-per-vehicle still trending down"],
    bear: ["Automotive gross margin under price-war pressure", "Robotaxi timeline has slipped before", "Valuation depends on non-auto bets landing"],
  },
};
const _FB_WATCH = [
  { sym: "NVDA", chg: 2.41 }, { sym: "AAPL", chg: -0.62 }, { sym: "TSLA", chg: 4.18 },
];
const _FB_PRICE = { NVDA: 1284.32, AAPL: 232.18, TSLA: 408.77 };
const _FB_TFS = ["1D", "1W", "1M", "6M", "1Y", "5Y"];

// Prefer real quant data injected by the quant.ai server (window.MARKETS_DATA);
// fall back to the seeded placeholders so this file still runs standalone in Claude Design.
const _MD = (typeof window !== "undefined" && window.MARKETS_DATA && window.MARKETS_DATA.TICKERS) ? window.MARKETS_DATA : null;
const TICKERS = _MD ? _MD.TICKERS : _FB_TICKERS;
const WATCH = _MD ? _MD.WATCH : _FB_WATCH;
const PRICE = _MD ? _MD.PRICE : _FB_PRICE;
const TFS = (_MD && _MD.TFS) ? _MD.TFS : _FB_TFS;
const ASOF = _MD ? _MD.as_of : null;

// ---- chart ---------------------------------------------------------------
function Chart({ seed, drift, up }) {
  const W = 720, H = 240, P = 8;
  const pts = React.useMemo(() => series(seed, 56, drift), [seed, drift]);
  const stroke = up ? "var(--status-success)" : "var(--status-danger)";
  const x = (i) => P + (i / (pts.length - 1)) * (W - P * 2);
  const y = (v) => H - P - v * (H - P * 2);
  const line = pts.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
  const area = `${line} L${x(pts.length - 1)} ${H} L${x(0)} ${H} Z`;
  const gid = "g" + seed;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: 240, display: "block" }} preserveAspectRatio="none">
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.16" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0" />
        </linearGradient>
      </defs>
      {[0.25, 0.5, 0.75].map((g) => (
        <line key={g} x1="0" x2={W} y1={H * g} y2={H * g} stroke="var(--border-subtle)" strokeWidth="1" />
      ))}
      <path d={area} fill={`url(#${gid})`} />
      <path d={line} fill="none" stroke={stroke} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

// ---- top bar -------------------------------------------------------------
function TopBar({ query, setQuery, onSearch }) {
  return (
    <header style={{ height: 60, flex: "none", display: "flex", alignItems: "center", gap: 14, padding: "0 22px", borderBottom: "1px solid var(--border-subtle)", background: "var(--surface-canvas)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
        <img src="../../assets/brand-mark.svg" style={{ width: 22 }} alt="" />
        <span style={{ fontFamily: "var(--font-serif)", fontSize: 18, fontWeight: 500, letterSpacing: "-0.01em" }}>Tyndall Markets</span>
      </div>
      <form onSubmit={(e) => { e.preventDefault(); onSearch(); }} style={{ width: 300, marginLeft: 8 }}>
        <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={T("Search a ticker — try AAPL, TSLA", "搜索代码 — 试试 AAPL、TSLA")} iconLeft={<Ico n="search" s={16} />} />
      </form>
      <Badge tone="success" dot>{T("Markets open", "开盘中")}</Badge>
      {ASOF && <span style={{ fontSize: 12, color: "var(--text-tertiary)" }}>{T("as of", "数据截止")} {ASOF}</span>}
      <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6 }}>
        <a href="/console" title={T("Console", "控制台")} style={{ display: "inline-flex", textDecoration: "none", color: "var(--text-secondary)" }}>
          <IconButton label={T("Console", "控制台")}><Ico n="sliders-horizontal" /></IconButton>
        </a>
        <IconButton label={T("Refresh", "刷新")} onClick={() => location.reload()}><Ico n="refresh-cw" /></IconButton>
      </div>
    </header>
  );
}

Object.assign(window, { Ico, Chart, TopBar, TICKERS, WATCH, PRICE, TFS, ASOF, T, ZH });

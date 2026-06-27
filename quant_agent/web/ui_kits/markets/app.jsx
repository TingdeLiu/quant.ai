// Tyndall Markets — dashboard view: market status, AI read + recommendation, live AI chat.
const M = window.ClaudeDesignSystem_9a1625;
const { Ico, Chart, TopBar, TICKERS, WATCH, PRICE, TFS, T, ZH } = window;
const BRIEF = (window.MARKETS_DATA && window.MARKETS_DATA.brief) || null;
const DISCLAIMER = (window.MARKETS_DATA && window.MARKETS_DATA.disclaimer) ||
  T("Research signals from price history. Not investment advice.", "基于历史价格的研究信号，非投资建议。");

const RATING_TONE = { Bullish: "success", Neutral: "neutral", Cautious: "danger", Volatile: "warning" };
const ratingTone = (t) => (t.recommendation && t.recommendation.tone) || RATING_TONE[t.rating] || "neutral";

function fmtPrice(p) { return "$" + Number(p).toLocaleString(undefined, { maximumFractionDigits: 2 }); }

// ---- small pieces --------------------------------------------------------
function Stat({ k, v }) {
  return (
    <div style={{ padding: "11px 14px", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", background: "var(--surface-raised)" }}>
      <div style={{ fontSize: 11.5, color: "var(--text-tertiary)", marginBottom: 4 }}>{k}</div>
      <div style={{ fontSize: 15, fontWeight: 600, color: "var(--text-primary)" }}>{v}</div>
    </div>
  );
}

function CaseList({ label, items, color, ic }) {
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11.5, fontWeight: 700, letterSpacing: "0.04em", textTransform: "uppercase", color, marginBottom: 9 }}>
        <Ico n={ic} s={15} /> {label}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {(items || []).map((x, i) => (
          <div key={i} style={{ display: "flex", gap: 8, fontSize: 13.5, lineHeight: 1.45, color: "var(--text-secondary)" }}>
            <span style={{ color, flex: "none", marginTop: 1 }}>•</span>{x}
          </div>
        ))}
      </div>
    </div>
  );
}

// ---- 建议: research recommendation card ----------------------------------
function RecommendationCard({ t }) {
  const rec = t.recommendation || {};
  const tone = ratingTone(t);
  return (
    <M.Card padding="none" style={{ overflow: "hidden" }}>
      <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--border-subtle)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
          <span style={{ fontSize: 11.5, fontWeight: 700, letterSpacing: "0.05em", textTransform: "uppercase", color: "var(--text-tertiary)" }}>
            {T("Recommendation", "研究建议")}
          </span>
          <M.Badge tone={tone}>{rec.stance || t.ratingLabel || t.rating}</M.Badge>
        </div>
        <p style={{ margin: 0, fontFamily: "var(--font-prose)", fontSize: 15, lineHeight: 1.55, color: "var(--text-primary)" }}>
          {rec.line || t.summary}
        </p>
      </div>
      <div style={{ padding: "16px 20px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
        <CaseList label={T("Bull case", "看多逻辑")} items={t.bull} color="var(--status-success)" ic="trending-up" />
        <CaseList label={T("Bear case", "看空逻辑")} items={t.bear} color="var(--status-danger)" ic="trending-down" />
      </div>
    </M.Card>
  );
}

// ---- AI chat (持续讨论, real backend) ------------------------------------
async function askServer(symbol, messages) {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol, messages }),
  });
  if (!res.ok) throw new Error("chat " + res.status);
  return res.json();
}

const STARTERS = ZH
  ? ["现在能买吗？", "主要风险是什么？", "和同业比如何？", "解释一下这个评级"]
  : ["Can I buy this now?", "What are the main risks?", "How does it compare to peers?", "Explain this rating"];

function Bubble({ m }) {
  if (m.role === "user") {
    return (
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <div style={{ background: "var(--surface-sunken)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-lg)", padding: "9px 13px", fontSize: 13.5, lineHeight: 1.5, maxWidth: 300 }}>{m.text}</div>
      </div>
    );
  }
  return (
    <div style={{ display: "flex", gap: 10 }}>
      <M.Avatar brand size="sm" />
      <div style={{ maxWidth: 300 }}>
        <p style={{ margin: 0, fontFamily: "var(--font-prose)", fontSize: 14, lineHeight: 1.6, color: "var(--text-primary)", whiteSpace: "pre-wrap" }}>{m.text}</p>
        {m.offline && (
          <div style={{ marginTop: 6, fontSize: 11, color: "var(--text-tertiary)" }}>
            {T("Offline mode · set ANTHROPIC_API_KEY for live Claude.", "离线模式 · 配置 ANTHROPIC_API_KEY 启用 Claude 实时讨论。")}
          </div>
        )}
      </div>
    </div>
  );
}

function AIChat({ sym, t }) {
  const [thread, setThread] = React.useState([]);
  const [draft, setDraft] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const scrollRef = React.useRef(null);

  React.useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    setTimeout(() => window.lucide && window.lucide.createIcons(), 20);
  }, [thread, busy]);

  const send = async (text) => {
    const q = (text || "").trim();
    if (!q || busy) return;
    const next = [...thread, { role: "user", text: q }];
    setThread(next); setDraft(""); setBusy(true);
    try {
      const reply = await askServer(sym, next);
      setThread((cur) => [...cur, { role: "assistant", text: reply.text, offline: reply.offline }]);
    } catch (e) {
      setThread((cur) => [...cur, { role: "assistant", text: T("Sorry — I couldn't reach the analyst service.", "抱歉，暂时无法连接分析服务。"), offline: true }]);
    } finally { setBusy(false); }
  };

  return (
    <M.Card padding="none" style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 108px)", overflow: "hidden" }}>
      {/* header */}
      <div style={{ display: "flex", alignItems: "center", gap: 11, padding: "14px 18px", borderBottom: "1px solid var(--border-subtle)", flex: "none" }}>
        <M.Avatar brand size="sm" />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 600 }}>{T("AI analyst", "AI 分析师")}</div>
          <div style={{ fontSize: 11.5, color: "var(--text-tertiary)" }}>Tyndall Lumen · {sym}</div>
        </div>
        <M.Badge tone={ratingTone(t)}>{t.ratingLabel || t.rating}</M.Badge>
      </div>

      {/* messages */}
      <div ref={scrollRef} style={{ flex: 1, overflowY: "auto", padding: "16px 18px", display: "flex", flexDirection: "column", gap: 14 }}>
        <div style={{ display: "flex", gap: 10 }}>
          <M.Avatar brand size="sm" />
          <p style={{ margin: 0, fontFamily: "var(--font-prose)", fontSize: 14, lineHeight: 1.6, color: "var(--text-primary)" }}>
            {T(`I've reviewed ${sym} — it screens as ${(t.ratingLabel || t.rating)}. Ask me about the read, the risks, or how I'd frame it.`,
               `我已看过 ${sym}，量化上呈现「${(t.ratingLabel || t.rating)}」。可以问我研判依据、风险，或该如何看待它。`)}
          </p>
        </div>
        {thread.length === 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginLeft: 38 }}>
            {STARTERS.map((s) => (
              <button key={s} onClick={() => send(s)} style={{ border: "1px solid var(--border-default)", background: "var(--surface-raised)", color: "var(--text-secondary)", borderRadius: "var(--radius-pill)", padding: "6px 12px", fontFamily: "var(--font-sans)", fontSize: 12.5, cursor: "pointer" }}>{s}</button>
            ))}
          </div>
        )}
        {thread.map((m, i) => <Bubble key={i} m={m} />)}
        {busy && (
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <M.Avatar brand size="sm" />
            <div style={{ fontSize: 13, color: "var(--text-tertiary)", fontStyle: "italic" }}>{T("Thinking…", "思考中…")}</div>
          </div>
        )}
      </div>

      {/* input */}
      <div style={{ padding: "12px 16px 14px", borderTop: "1px solid var(--border-subtle)", flex: "none" }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center", background: "var(--surface-sunken)", border: "1px solid var(--border-default)", borderRadius: "var(--radius-pill)", padding: "5px 6px 5px 14px" }}>
          <Ico n="sparkles" s={16} />
          <input value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") send(draft); }}
            placeholder={T(`Ask about ${sym} — valuation, risks, peers…`, `就 ${sym} 提问 — 估值、风险、同业…`)}
            style={{ flex: 1, border: "none", outline: "none", background: "transparent", fontFamily: "var(--font-sans)", fontSize: 14, color: "var(--text-primary)" }} />
          <M.IconButton label={T("Ask", "发送")} variant="primary" onClick={() => send(draft)}><Ico n="arrow-up" /></M.IconButton>
        </div>
        <div style={{ marginTop: 8, fontSize: 10.5, color: "var(--text-tertiary)", textAlign: "center" }}>{DISCLAIMER}</div>
      </div>
    </M.Card>
  );
}

// ---- 股市现状: watchlist rail --------------------------------------------
function Watchlist({ sym, setSym }) {
  return (
    <aside style={{ width: 256, flex: "none", height: "100%", boxSizing: "border-box", overflowY: "auto", background: "var(--surface-panel)", borderRight: "1px solid var(--border-subtle)", padding: "18px 14px" }}>
      <div style={{ fontSize: 11.5, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--text-tertiary)", margin: "2px 6px 12px" }}>
        {T("Watchlist · market pulse", "自选 · 市场脉搏")}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {WATCH.map((w) => {
          const wu = w.chg >= 0, active = w.sym === sym, known = !!TICKERS[w.sym];
          const nm = (TICKERS[w.sym] && TICKERS[w.sym].name) || "";
          return (
            <button key={w.sym} onClick={() => known && setSym(w.sym)} style={{ width: "100%", display: "flex", alignItems: "center", gap: 10, padding: "10px 12px", border: "1px solid", borderColor: active ? "var(--border-default)" : "transparent", borderRadius: "var(--radius-md)", cursor: known ? "pointer" : "default", background: active ? "var(--surface-raised)" : "transparent", boxShadow: active ? "var(--shadow-xs)" : "none", textAlign: "left" }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13.5, fontWeight: 600 }}>{w.sym}</div>
                <div style={{ fontSize: 11.5, color: "var(--text-tertiary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{nm || (PRICE[w.sym] != null ? fmtPrice(PRICE[w.sym]) : "")}</div>
              </div>
              <div style={{ textAlign: "right" }}>
                {PRICE[w.sym] != null && <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>{fmtPrice(PRICE[w.sym])}</div>}
                <div style={{ fontSize: 12.5, fontWeight: 600, color: wu ? "var(--status-success)" : "var(--status-danger)" }}>{wu ? "+" : ""}{w.chg}%</div>
              </div>
            </button>
          );
        })}
      </div>
      {BRIEF && (
        <div style={{ marginTop: 16 }}>
          <M.Card style={{ background: "var(--surface-inverse)", border: "none" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--kraft-25)", fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
              <Ico n="sparkles" s={15} /> {T("Daily brief", "每日简报")}
            </div>
            <p style={{ margin: 0, fontFamily: "var(--font-prose)", fontSize: 13, lineHeight: 1.55, color: "var(--kraft-300)" }}>{BRIEF}</p>
          </M.Card>
        </div>
      )}
    </aside>
  );
}

// ---- main dashboard ------------------------------------------------------
function Dashboard({ sym }) {
  const t = TICKERS[sym];
  const up = t.chg >= 0;
  const col = up ? "var(--status-success)" : "var(--status-danger)";
  const [tf, setTf] = React.useState("1M");

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: "24px 28px 40px", background: "var(--surface-canvas)" }}>
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) 384px", gap: 24, maxWidth: 1280, margin: "0 auto", alignItems: "start" }}>
        {/* 现状 + 分析 + 建议 */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 16 }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <h1 style={{ margin: 0, fontFamily: "var(--font-serif)", fontSize: 34, fontWeight: 500, letterSpacing: "-0.02em" }}>{sym}</h1>
                <M.Tag>{t.sector}</M.Tag>
              </div>
              <div style={{ fontSize: 14, color: "var(--text-secondary)", marginTop: 2 }}>{t.name}</div>
            </div>
            <div style={{ marginLeft: "auto", textAlign: "right" }}>
              <div style={{ fontSize: 30, fontWeight: 600, letterSpacing: "-0.01em" }}>{fmtPrice(t.price)}</div>
              <div style={{ fontSize: 14.5, fontWeight: 600, color: col, display: "flex", alignItems: "center", gap: 4, justifyContent: "flex-end" }}>
                <Ico n={up ? "arrow-up-right" : "arrow-down-right"} s={16} />{up ? "+" : ""}{t.chg}% {T("today", "今日")}
              </div>
            </div>
          </div>

          <M.Card padding="none" style={{ overflow: "hidden" }}>
            <div style={{ display: "flex", gap: 6, padding: "12px 16px", borderBottom: "1px solid var(--border-subtle)" }}>
              {TFS.map((x) => (
                <button key={x} onClick={() => setTf(x)} style={{ border: "none", cursor: "pointer", padding: "5px 12px", borderRadius: "var(--radius-pill)", fontFamily: "var(--font-sans)", fontSize: 12.5, fontWeight: 600, color: tf === x ? "var(--text-on-accent)" : "var(--text-secondary)", background: tf === x ? "var(--accent)" : "transparent" }}>{x}</button>
              ))}
            </div>
            <div style={{ padding: "10px 8px 4px" }}>
              <Chart seed={t.seed + tf.length * 11} drift={t.drift} up={up} />
            </div>
          </M.Card>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 10 }}>
            {Object.entries(t.stats).map(([k, v]) => <Stat key={k} k={k} v={v} />)}
          </div>

          <RecommendationCard t={t} />
        </div>

        {/* 持续讨论 */}
        <div style={{ position: "sticky", top: 0 }}>
          <AIChat key={sym} sym={sym} t={t} />
        </div>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", padding: 40, background: "var(--surface-canvas)" }}>
      <div style={{ maxWidth: 440, textAlign: "center" }}>
        <div style={{ fontFamily: "var(--font-serif)", fontSize: 26, fontWeight: 500, marginBottom: 10 }}>{T("No market data yet", "暂无行情数据")}</div>
        <p style={{ fontFamily: "var(--font-prose)", fontSize: 15, lineHeight: 1.6, color: "var(--text-secondary)" }}>
          {T("Run the quant pipeline (or check your data source) so the dashboard can load real prices and signals.",
             "请先运行量化流水线（或检查数据源），仪表盘即可加载真实价格与信号。")}
        </p>
      </div>
    </div>
  );
}

function App() {
  const _init = (window.MARKETS_DATA && window.MARKETS_DATA.defaultSym && TICKERS[window.MARKETS_DATA.defaultSym])
    ? window.MARKETS_DATA.defaultSym
    : Object.keys(TICKERS)[0];
  const [sym, setSym] = React.useState(_init);
  const [query, setQuery] = React.useState("");
  React.useEffect(() => { setTimeout(() => window.lucide && window.lucide.createIcons(), 30); });
  const search = () => { const q = query.trim().toUpperCase(); if (TICKERS[q]) { setSym(q); setQuery(""); } };

  if (!sym || !TICKERS[sym]) {
    return (
      <div style={{ display: "flex", height: "100%", background: "var(--surface-canvas)" }}>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
          <TopBar query={query} setQuery={setQuery} onSearch={search} />
          <EmptyState />
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", height: "100%", background: "var(--surface-canvas)" }}>
      <Watchlist sym={sym} setSym={setSym} />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <TopBar query={query} setQuery={setQuery} onSearch={search} />
        <Dashboard sym={sym} />
      </div>
    </div>
  );
}

Object.assign(window, { App });

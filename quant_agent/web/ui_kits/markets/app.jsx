// Tyndall Markets — dashboard view, AI analysis panel, orchestrator
const M = window.ClaudeDesignSystem_9a1625;
const { Ico, Chart, Sidebar, TopBar, TICKERS, WATCH, PRICE, TFS } = window;

function Stat({ k, v }) {
  return (
    <div style={{ padding: "12px 14px", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", background: "var(--surface-raised)" }}>
      <div style={{ fontSize: 11.5, color: "var(--text-tertiary)", marginBottom: 4 }}>{k}</div>
      <div style={{ fontSize: 15.5, fontWeight: 600, fontFamily: "var(--font-sans)", color: "var(--text-primary)" }}>{v}</div>
    </div>
  );
}

function AIAnalysis({ t, sym, thread, onAsk, draft, setDraft }) {
  const ratingTone = t.rating === "Bullish" ? "success" : t.rating === "Neutral" ? "neutral" : t.rating === "Volatile" ? "warning" : "accent";
  return (
    <M.Card padding="none" style={{ overflow: "hidden" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 11, padding: "16px 20px", borderBottom: "1px solid var(--border-subtle)" }}>
        <M.Avatar brand size="sm" />
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 14.5, fontWeight: 600 }}>AI analyst</div>
          <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>Tyndall Lumen · {sym} read</div>
        </div>
        <M.Badge tone={ratingTone}>{t.rating}</M.Badge>
      </div>

      <div style={{ padding: "18px 20px" }}>
        <p style={{ margin: 0, fontFamily: "var(--font-prose)", fontSize: 15.5, lineHeight: 1.62, color: "var(--text-primary)" }}>{t.summary}</p>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 18 }}>
          {[["Bull case", t.bull, "var(--status-success)", "trending-up"], ["Bear case", t.bear, "var(--status-danger)", "trending-down"]].map(([label, items, color, ic]) => (
            <div key={label}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 700, letterSpacing: "0.04em", textTransform: "uppercase", color, marginBottom: 9 }}>
                <Ico n={ic} s={15} /> {label}
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {items.map((x, i) => (
                  <div key={i} style={{ display: "flex", gap: 8, fontSize: 13.5, lineHeight: 1.45, color: "var(--text-secondary)" }}>
                    <span style={{ color, flex: "none", marginTop: 1 }}>•</span>{x}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {thread.length > 0 && (
          <div style={{ marginTop: 18, display: "flex", flexDirection: "column", gap: 14, borderTop: "1px solid var(--border-subtle)", paddingTop: 16 }}>
            {thread.map((m, i) => (
              <div key={i}>
                {m.role === "user" ? (
                  <div style={{ display: "flex", justifyContent: "flex-end" }}>
                    <div style={{ background: "var(--surface-sunken)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-lg)", padding: "9px 13px", fontSize: 13.5, maxWidth: 460 }}>{m.text}</div>
                  </div>
                ) : (
                  <div style={{ display: "flex", gap: 10 }}>
                    <M.Avatar brand size="sm" />
                    <p style={{ margin: 0, fontFamily: "var(--font-prose)", fontSize: 14.5, lineHeight: 1.6, color: "var(--text-primary)", maxWidth: 520 }}>{m.text}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div style={{ padding: "0 20px 18px" }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center", background: "var(--surface-sunken)", border: "1px solid var(--border-default)", borderRadius: "var(--radius-pill)", padding: "5px 6px 5px 16px" }}>
          <Ico n="sparkles" s={16} />
          <input value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") onAsk(); }}
            placeholder={`Ask about ${sym} — valuation, risks, peers…`}
            style={{ flex: 1, border: "none", outline: "none", background: "transparent", fontFamily: "var(--font-sans)", fontSize: 14, color: "var(--text-primary)" }} />
          <IconButton label="Ask" variant="primary" onClick={onAsk}><Ico n="arrow-up" /></IconButton>
        </div>
      </div>
    </M.Card>
  );
}

function Dashboard({ sym, setSym }) {
  const t = TICKERS[sym];
  const up = t.chg >= 0;
  const col = up ? "var(--status-success)" : "var(--status-danger)";
  const [tf, setTf] = React.useState("1M");
  const [thread, setThread] = React.useState([]);
  const [draft, setDraft] = React.useState("");

  React.useEffect(() => { setThread([]); }, [sym]);

  const ask = () => {
    const q = draft.trim(); if (!q) return;
    setThread((x) => [...x, { role: "user", text: q }]);
    setDraft("");
    setTimeout(() => setThread((x) => [...x, { role: "assistant", text: `On ${sym}: the short answer is it depends on your time horizon. Over the next year the setup is ${t.rating.toLowerCase()} — ${t.bull[0].toLowerCase()}, balanced against ${t.bear[0].toLowerCase()}. I'd size the position to that uncertainty rather than the headline.` }]), 500);
  };

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "24px 28px 40px", background: "var(--surface-canvas)" }}>
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) 300px", gap: 24, maxWidth: 1180, margin: "0 auto" }}>
        {/* main column */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 16 }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <h1 style={{ margin: 0, fontFamily: "var(--font-serif)", fontSize: 34, fontWeight: 500, letterSpacing: "-0.02em" }}>{sym}</h1>
                <M.Tag>{t.sector}</M.Tag>
              </div>
              <div style={{ fontSize: 14, color: "var(--text-secondary)", marginTop: 2 }}>{t.name}</div>
            </div>
            <div style={{ marginLeft: "auto", textAlign: "right" }}>
              <div style={{ fontSize: 30, fontWeight: 600, fontFamily: "var(--font-sans)", letterSpacing: "-0.01em" }}>${t.price.toLocaleString()}</div>
              <div style={{ fontSize: 14.5, fontWeight: 600, color: col, display: "flex", alignItems: "center", gap: 4, justifyContent: "flex-end" }}>
                <Ico n={up ? "arrow-up-right" : "arrow-down-right"} s={16} />{up ? "+" : ""}{t.chg}% today
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

          <AIAnalysis t={t} sym={sym} thread={thread} onAsk={ask} draft={draft} setDraft={setDraft} />
        </div>

        {/* watchlist column */}
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.05em", textTransform: "uppercase", color: "var(--text-tertiary)", margin: "4px 4px 10px" }}>Watchlist</div>
          <M.Card padding="none" style={{ overflow: "hidden" }}>
            {WATCH.map((w, i) => {
              const wu = w.chg >= 0, active = w.sym === sym;
              return (
                <button key={w.sym} onClick={() => TICKERS[w.sym] && setSym(w.sym)} style={{ width: "100%", display: "flex", alignItems: "center", gap: 10, padding: "12px 15px", border: "none", borderTop: i ? "1px solid var(--border-subtle)" : "none", cursor: TICKERS[w.sym] ? "pointer" : "default", background: active ? "var(--accent-subtle)" : "transparent", textAlign: "left" }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13.5, fontWeight: 600 }}>{w.sym}</div>
                    <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>${PRICE[w.sym].toLocaleString()}</div>
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: wu ? "var(--status-success)" : "var(--status-danger)" }}>{wu ? "+" : ""}{w.chg}%</div>
                </button>
              );
            })}
          </M.Card>
          <div style={{ marginTop: 14 }}>
            <M.Card style={{ background: "var(--surface-inverse)", border: "none" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--kraft-25)", fontSize: 13.5, fontWeight: 600, marginBottom: 8 }}>
                <Ico n="sparkles" s={16} /> Daily brief
              </div>
              <p style={{ margin: 0, fontFamily: "var(--font-prose)", fontSize: 13.5, lineHeight: 1.55, color: "var(--kraft-300)" }}>
                {(window.MARKETS_DATA && window.MARKETS_DATA.brief) || "Semis led the tape today on data-center demand. Rates drifted lower; megacaps mixed. Your watchlist is up 0.9% on average."}
              </p>
            </M.Card>
          </div>
        </div>
      </div>
    </div>
  );
}

function App() {
  const _initSym = (window.MARKETS_DATA && window.MARKETS_DATA.defaultSym && TICKERS[window.MARKETS_DATA.defaultSym])
    ? window.MARKETS_DATA.defaultSym
    : Object.keys(TICKERS)[0];
  const [sym, setSym] = React.useState(_initSym);
  const [query, setQuery] = React.useState("");
  React.useEffect(() => { setTimeout(() => window.lucide && window.lucide.createIcons(), 30); });
  const search = () => {
    const q = query.trim().toUpperCase();
    if (TICKERS[q]) { setSym(q); setQuery(""); }
  };
  return (
    <div style={{ display: "flex", height: "100%", background: "var(--surface-canvas)" }}>
      <Sidebar />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <TopBar query={query} setQuery={setQuery} onSearch={search} />
        <Dashboard sym={sym} setSym={setSym} />
      </div>
    </div>
  );
}

Object.assign(window, { App });

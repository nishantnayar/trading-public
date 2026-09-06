import { MetaRows, Note, Panel, PanelHeader } from "@/components/ui";
import { CONSTRAINTS, COST_META, HOLDINGS, REBALANCE } from "@/lib/illustrative";
import { C, MONO } from "@/lib/palette";

const TH: React.CSSProperties = { padding: "7px 10px", fontWeight: 400, color: C.t4 };

export default function PositionsPage() {
  const maxPnl = Math.max(...HOLDINGS.map((r) => Math.abs(r.pnl)));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {/* constraints */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,minmax(0,1fr))", border: `1px solid ${C.border}`, background: C.panel }}>
        {CONSTRAINTS.map((c, i) => {
          const near = c.used > 90;
          return (
            <div key={c.label} style={{ padding: 14, borderRight: i < 3 ? `1px solid ${C.border}` : undefined }}>
              <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
                <span style={{ fontFamily: MONO, fontSize: 10, letterSpacing: "0.1em", color: C.t3 }}>{c.label}</span>
                <span style={{ fontFamily: MONO, fontSize: 9, letterSpacing: "0.1em", color: near ? C.accent : C.pos }}>
                  {near ? "NEAR CAP" : "OK"}
                </span>
              </div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 8, fontFamily: MONO }}>
                <span style={{ fontSize: 24, fontWeight: 600, lineHeight: 1 }}>{c.value}</span>
                <span style={{ fontSize: 11, color: C.t4 }}>{c.limit}</span>
              </div>
              <div style={{ position: "relative", height: 4, marginTop: 10, background: C.track }}>
                <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${c.used}%`, background: near ? C.accent : C.pos, opacity: 0.8 }} />
                <div style={{ position: "absolute", right: 0, top: -2, bottom: -2, width: 1, background: C.cap }} />
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,2.6fr) minmax(250px,1fr)", gap: 14, alignItems: "start" }}>
        {/* holdings */}
        <Panel>
          <PanelHeader
            label="OPEN HOLDINGS"
            right={
              <>
                <span style={{ fontFamily: MONO, fontSize: 11, color: C.t4 }}>8 of 100 · gross $1.28M</span>
                <span style={{ marginLeft: "auto", fontFamily: MONO, fontSize: 10, color: C.t4 }}>SORT ↓ MKT VAL</span>
              </>
            }
          />
          <table style={{ fontFamily: MONO, fontSize: 12 }}>
            <thead>
              <tr style={{ fontSize: 10, letterSpacing: "0.1em", borderBottom: `1px solid ${C.border}` }}>
                <th style={{ ...TH, padding: "7px 8px 7px 14px", textAlign: "left" }}>S</th>
                <th style={{ ...TH, textAlign: "left" }}>TICKER</th>
                <th style={{ ...TH, textAlign: "right" }}>QTY</th>
                <th style={{ ...TH, textAlign: "right" }}>MKT VAL</th>
                <th style={{ ...TH, textAlign: "right" }}>WT</th>
                <th style={{ ...TH, textAlign: "right" }}>uPnL</th>
                <th style={{ ...TH, padding: "7px 14px 7px 10px", textAlign: "center" }}>Δ</th>
              </tr>
            </thead>
            <tbody>
              {HOLDINGS.map((r) => {
                const up = r.pnl >= 0;
                return (
                  <tr key={r.ticker} style={{ borderTop: `1px solid ${C.border2}`, height: 30 }}>
                    <td style={{ padding: "0 8px 0 14px" }}>
                      <span style={{ fontFamily: MONO, fontSize: 10, color: r.side === "L" ? C.pos : C.neg }}>{r.side}</span>
                    </td>
                    <td style={{ padding: "0 10px" }}>{r.ticker}</td>
                    <td style={{ padding: "0 10px", textAlign: "right", color: C.t3 }}>{r.qty}</td>
                    <td style={{ padding: "0 10px", textAlign: "right" }}>{r.mkt}</td>
                    <td style={{ padding: "0 10px", textAlign: "right", color: C.t3 }}>{r.wt}</td>
                    <td style={{ padding: "0 10px", textAlign: "right", fontWeight: 500, color: up ? C.pos : C.neg }}>{r.upnl}</td>
                    <td style={{ padding: "0 14px 0 10px", width: 90 }}>
                      <div style={{ position: "relative", height: 8, background: C.track }}>
                        <div style={{ position: "absolute", left: "50%", top: -2, bottom: -2, width: 1, background: C.cap }} />
                        <div
                          style={{
                            position: "absolute",
                            top: 0,
                            bottom: 0,
                            [up ? "left" : "right"]: "50%",
                            width: `${((Math.abs(r.pnl) / maxPnl) * 50).toFixed(1)}%`,
                            background: up ? C.pos : C.neg,
                            opacity: 0.7,
                          }}
                        />
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <Note>ILLUSTRATIVE — live holdings arrive with Phase 7 paper execution</Note>
        </Panel>

        {/* next rebalance */}
        <Panel>
          <PanelHeader
            label="NEXT REBALANCE"
            right={<span style={{ marginLeft: "auto", fontFamily: MONO, fontSize: 11, color: C.accent }}>MON 09:35</span>}
          />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3,minmax(0,1fr))" }}>
            {REBALANCE.map((r, i) => (
              <div key={r.label} style={{ padding: "14px 8px", textAlign: "center", borderRight: i < 2 ? `1px solid ${C.border}` : undefined }}>
                <div style={{ fontFamily: MONO, fontSize: 22, fontWeight: 600, lineHeight: 1, color: r.tone === "pos" ? C.pos : r.tone === "neg" ? C.neg : C.text }}>
                  {r.value}
                </div>
                <div style={{ marginTop: 4, fontFamily: MONO, fontSize: 10, letterSpacing: "0.08em", color: C.t4 }}>{r.label}</div>
              </div>
            ))}
          </div>
          <div style={{ borderTop: `1px solid ${C.border}` }}>
            <MetaRows rows={COST_META.map((c) => ({ ...c }))} />
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "10px 14px",
              borderTop: `1px solid ${C.border}`,
              background: C.warnBg,
              fontFamily: MONO,
              fontSize: 11,
              color: C.accent,
            }}
          >
            <span style={{ width: 6, height: 6, borderRadius: 99, background: C.accent }} />
            23 ORDERS STAGED · NOT SENT
          </div>
        </Panel>
      </div>
    </div>
  );
}

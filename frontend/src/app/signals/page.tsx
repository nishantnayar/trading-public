import { MetaRows, Note, Panel, PanelHeader } from "@/components/ui";
import { LADDER, QUINTILES, SIGNAL_META } from "@/lib/illustrative";
import { C, MONO } from "@/lib/palette";

const TH: React.CSSProperties = { padding: "7px 10px", fontWeight: 400, color: C.t4 };

export default function SignalsPage() {
  const maxQ = Math.max(...QUINTILES.map((q) => Math.abs(q.v)));

  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(0,2.6fr) minmax(240px,1fr)", gap: 14, alignItems: "start" }}>
      <Panel>
        <PanelHeader
          label="RANK LADDER"
          right={
            <>
              <span style={{ fontFamily: MONO, fontSize: 11, color: C.t4 }}>100 of 502 shown · Q5 long / Q1 short</span>
              <span style={{ marginLeft: "auto", fontFamily: MONO, fontSize: 10, color: C.t4 }}>SORT ↓ SCORE</span>
            </>
          }
        />
        <table style={{ fontFamily: MONO, fontSize: 12 }}>
          <thead>
            <tr style={{ fontSize: 10, letterSpacing: "0.1em", borderBottom: `1px solid ${C.border}` }}>
              <th style={{ ...TH, padding: "7px 10px 7px 14px", textAlign: "left" }}>RK</th>
              <th style={{ ...TH, textAlign: "left" }}>TICKER</th>
              <th style={{ ...TH, textAlign: "left" }}>SECTOR</th>
              <th style={{ ...TH, textAlign: "right" }}>SCORE</th>
              <th style={{ ...TH, textAlign: "center" }}>Z-SPREAD</th>
              <th style={{ ...TH, textAlign: "right" }}>PCTL</th>
              <th style={{ ...TH, textAlign: "right" }}>WT</th>
              <th style={{ ...TH, padding: "7px 14px 7px 10px", textAlign: "right" }}>SIDE</th>
            </tr>
          </thead>
          <tbody>
            {LADDER.map((r, i) => {
              if ("gap" in r && r.gap) {
                return (
                  <tr key={`gap${i}`} style={{ borderTop: `1px solid ${C.border2}`, background: C.panel2, color: C.t4, fontSize: 11 }}>
                    <td style={{ padding: "0 10px 0 14px", height: 30, color: C.t4 }}>···</td>
                    <td style={{ padding: "0 10px" }} colSpan={7}>
                      {r.label}
                    </td>
                  </tr>
                );
              }
              const row = r as Extract<(typeof LADDER)[number], { score: number }>;
              const pos = row.score > 0;
              const w = (Math.abs(row.score) / 2.5) * 50;
              const color = pos ? C.pos : C.neg;
              return (
                <tr key={row.rank} style={{ borderTop: `1px solid ${C.border2}`, height: 30 }}>
                  <td style={{ padding: "0 10px 0 14px", color: C.t4 }}>{row.rank}</td>
                  <td style={{ padding: "0 10px", color: C.text }}>{row.ticker}</td>
                  <td style={{ padding: "0 10px", fontSize: 11, color: C.t3 }}>{row.sector}</td>
                  <td style={{ padding: "0 10px", textAlign: "right", fontWeight: 500, color }}>
                    {(pos ? "+" : "") + row.score.toFixed(2)}
                  </td>
                  <td style={{ padding: "0 10px", width: 150 }}>
                    <div style={{ position: "relative", height: 8, background: C.track }}>
                      <div style={{ position: "absolute", left: "50%", top: -2, bottom: -2, width: 1, background: C.cap }} />
                      <div
                        style={{
                          position: "absolute",
                          top: 0,
                          bottom: 0,
                          [pos ? "left" : "right"]: "50%",
                          width: `${w.toFixed(1)}%`,
                          background: color,
                          opacity: 0.7,
                        }}
                      />
                    </div>
                  </td>
                  <td style={{ padding: "0 10px", textAlign: "right", color: C.t3 }}>{row.pctl}</td>
                  <td style={{ padding: "0 10px", textAlign: "right" }}>{row.wt}</td>
                  <td style={{ padding: "0 14px 0 10px", textAlign: "right" }}>
                    <span style={{ fontSize: 10, letterSpacing: "0.06em", color }}>{row.side}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <Note>ILLUSTRATIVE — LightGBM lambdarank scores land in Phase 4</Note>
      </Panel>

      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <Panel>
          <PanelHeader label="QUINTILE SPREAD" />
          <div style={{ display: "flex", flexDirection: "column", gap: 9, padding: 14 }}>
            {QUINTILES.map((q) => {
              const positive = q.v >= 0;
              return (
                <div key={q.label} style={{ display: "flex", alignItems: "center", gap: 10, fontFamily: MONO, fontSize: 11 }}>
                  <span style={{ width: 22, color: C.t3 }}>{q.label}</span>
                  <div style={{ flex: 1, height: 14, background: C.track }}>
                    <div
                      style={{
                        height: "100%",
                        width: `${((Math.abs(q.v) / maxQ) * 100).toFixed(0)}%`,
                        background: positive ? C.pos : C.neg,
                        opacity: 0.7,
                        marginLeft: positive ? 0 : "auto",
                      }}
                    />
                  </div>
                  <span style={{ width: 48, textAlign: "right", color: positive ? C.pos : C.neg }}>
                    {positive ? "+" : ""}
                    {q.v.toFixed(1)}%
                  </span>
                </div>
              );
            })}
          </div>
          <Note>MEAN FWD 5D EXCESS RETURN</Note>
        </Panel>
        <Panel>
          <PanelHeader label="SIGNAL SUMMARY" />
          <MetaRows rows={SIGNAL_META.map((m) => ({ ...m }))} />
        </Panel>
      </div>
    </div>
  );
}

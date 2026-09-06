"use client";

import { MetaRows, Note, Panel, PanelHeader } from "@/components/ui";
import type { Quintile, SignalRow, SignalsSnapshot } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { C, MONO } from "@/lib/palette";

const TH: React.CSSProperties = { padding: "7px 10px", fontWeight: 400, color: C.t4 };

export default function SignalsPage() {
  const snap = useApi<SignalsSnapshot>("/signals");
  const quintiles = useApi<Quintile[]>("/signals/quintiles");
  const data = snap.data;
  const empty = !data?.as_of;
  const rows = data?.rows ?? [];
  const maxQ = Math.max(0.01, ...(quintiles.data ?? []).map((q) => Math.abs(q.v)));
  const maxAbs = Math.max(0.01, ...rows.filter((r) => r.score != null).map((r) => Math.abs(r.score!)));

  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(0,2.6fr) minmax(240px,1fr)", gap: 14, alignItems: "start" }}>
      <Panel>
        <PanelHeader
          label="RANK LADDER"
          right={
            <span style={{ marginLeft: "auto", fontFamily: MONO, fontSize: 10, color: C.t4 }}>
              {data?.as_of ? `OOF · ${data.as_of}` : "NO SCORES PUBLISHED"}
            </span>
          }
        />
        {empty ? (
          <div style={{ padding: 24, fontFamily: MONO, fontSize: 12, color: C.t3 }}>
            Run: uv run python -m quantis.backtest.publish
          </div>
        ) : (
          <table style={{ fontFamily: MONO, fontSize: 12 }}>
            <thead>
              <tr style={{ fontSize: 10, letterSpacing: "0.1em", borderBottom: `1px solid ${C.border}` }}>
                <th style={{ ...TH, padding: "7px 10px 7px 14px", textAlign: "left" }}>RK</th>
                <th style={{ ...TH, textAlign: "left" }}>TICKER</th>
                <th style={{ ...TH, textAlign: "left" }}>SECTOR</th>
                <th style={{ ...TH, textAlign: "right" }}>SCORE</th>
                <th style={{ ...TH, textAlign: "center" }}>Z-SPREAD</th>
                <th style={{ ...TH, textAlign: "right" }}>PCTL</th>
                <th style={{ ...TH, padding: "7px 14px 7px 10px", textAlign: "right" }}>SIDE</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r: SignalRow, i) => {
                if (r.gap) {
                  return (
                    <tr key={`gap${i}`} style={{ borderTop: `1px solid ${C.border2}`, background: C.panel2, color: C.t4, fontSize: 11 }}>
                      <td style={{ padding: "0 10px 0 14px", height: 30 }}>···</td>
                      <td style={{ padding: "0 10px" }} colSpan={6}>{r.label}</td>
                    </tr>
                  );
                }
                const pos = (r.score ?? 0) > 0;
                const color = pos ? C.pos : C.neg;
                const w = (Math.abs(r.score ?? 0) / maxAbs) * 50;
                return (
                  <tr key={r.rank} style={{ borderTop: `1px solid ${C.border2}`, height: 30 }}>
                    <td style={{ padding: "0 10px 0 14px", color: C.t4 }}>{r.rank}</td>
                    <td style={{ padding: "0 10px", color: C.text }}>{r.symbol}</td>
                    <td style={{ padding: "0 10px", fontSize: 11, color: C.t3 }}>{r.sector}</td>
                    <td style={{ padding: "0 10px", textAlign: "right", fontWeight: 500, color }}>
                      {(pos ? "+" : "") + (r.score ?? 0).toFixed(3)}
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
                    <td style={{ padding: "0 10px", textAlign: "right", color: C.t3 }}>{r.pctl?.toFixed(1)}</td>
                    <td style={{ padding: "0 14px 0 10px", textAlign: "right" }}>
                      <span style={{ fontSize: 10, letterSpacing: "0.06em", color: r.side === "L" ? C.pos : r.side === "S" ? C.neg : C.t4 }}>
                        {r.side || "—"}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
        <Note>LIVE OOF SCORES · side is the published target book, not a fill</Note>
      </Panel>

      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <Panel>
          <PanelHeader label="QUINTILE LABEL" />
          <div style={{ display: "flex", flexDirection: "column", gap: 9, padding: 14 }}>
            {(quintiles.data ?? []).map((q) => {
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
                    {q.v.toFixed(2)}
                  </span>
                </div>
              );
            })}
          </div>
          <Note>MEAN OOF LABEL (z) ON AS-OF DATE · not a return</Note>
        </Panel>
        <Panel>
          <PanelHeader label="SIGNAL SUMMARY" />
          <MetaRows
            rows={[
              { label: "horizon", value: data?.meta.horizon ?? "—" },
              { label: "scored names", value: data?.meta.scored != null ? String(data.meta.scored) : "—" },
              { label: "long book", value: data?.meta.longs != null ? `${data.meta.longs}` : "—", tone: "pos" },
              { label: "short book", value: data?.meta.shorts != null ? `${data.meta.shorts}` : "—", tone: "neg" },
              { label: "construction", value: data?.meta.construction || "—" },
            ]}
          />
        </Panel>
      </div>
    </div>
  );
}

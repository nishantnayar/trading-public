"use client";

import { MetaRows, Note, Panel, PanelHeader } from "@/components/ui";
import type { PositionsSnapshot } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { C, MONO } from "@/lib/palette";

const TH: React.CSSProperties = { padding: "7px 10px", fontWeight: 400, color: C.t4 };

export default function PositionsPage() {
  const snap = useApi<PositionsSnapshot>("/positions");
  const data = snap.data;
  const empty = !data?.as_of;
  const holdings = data?.holdings ?? [];
  const maxW = Math.max(0.001, ...holdings.map((h) => Math.abs(h.weight)));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,minmax(0,1fr))", border: `1px solid ${C.border}`, background: C.panel }}>
        {(data?.constraints ?? []).map((c, i) => (
          <div key={c.label} style={{ padding: 14, borderRight: i < 3 ? `1px solid ${C.border}` : undefined }}>
            <div style={{ fontFamily: MONO, fontSize: 10, letterSpacing: "0.1em", color: C.t3 }}>{c.label}</div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 8, fontFamily: MONO }}>
              <span style={{ fontSize: 24, fontWeight: 600, lineHeight: 1 }}>{c.value}</span>
              <span style={{ fontSize: 11, color: C.t4 }}>{c.limit}</span>
            </div>
            <div style={{ position: "relative", height: 4, marginTop: 10, background: C.track }}>
              <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${Math.min(100, c.used)}%`, background: C.pos, opacity: 0.8 }} />
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,2.6fr) minmax(250px,1fr)", gap: 14, alignItems: "start" }}>
        <Panel>
          <PanelHeader
            label="TARGET HOLDINGS"
            right={
              <span style={{ marginLeft: "auto", fontFamily: MONO, fontSize: 11, color: C.t4 }}>
                {empty ? "NONE" : `${data?.n_holdings} names · ${data?.as_of}`}
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
                  <th style={{ ...TH, padding: "7px 8px 7px 14px", textAlign: "left" }}>S</th>
                  <th style={{ ...TH, textAlign: "left" }}>TICKER</th>
                  <th style={{ ...TH, textAlign: "left" }}>SECTOR</th>
                  <th style={{ ...TH, padding: "7px 14px 7px 10px", textAlign: "right" }}>WT</th>
                </tr>
              </thead>
              <tbody>
                {holdings.map((r) => (
                  <tr key={r.symbol} style={{ borderTop: `1px solid ${C.border2}`, height: 30 }}>
                    <td style={{ padding: "0 8px 0 14px" }}>
                      <span style={{ fontFamily: MONO, fontSize: 10, color: r.side === "L" ? C.pos : C.neg }}>{r.side}</span>
                    </td>
                    <td style={{ padding: "0 10px" }}>{r.symbol}</td>
                    <td style={{ padding: "0 10px", color: C.t3, fontSize: 11 }}>{r.sector}</td>
                    <td style={{ padding: "0 14px 0 10px", textAlign: "right", width: 140 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, justifyContent: "flex-end" }}>
                        <div style={{ width: 72, height: 8, background: C.track, position: "relative" }}>
                          <div
                            style={{
                              position: "absolute",
                              top: 0,
                              bottom: 0,
                              left: 0,
                              width: `${((Math.abs(r.weight) / maxW) * 100).toFixed(0)}%`,
                              background: r.side === "L" ? C.pos : C.neg,
                              opacity: 0.7,
                            }}
                          />
                        </div>
                        <span>{(r.weight * 100).toFixed(2)}%</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <Note>TARGET WEIGHTS from {data?.construction ?? "—"} · not broker fills (Phase 7)</Note>
        </Panel>

        <Panel>
          <PanelHeader label="LAST BOOK CHANGE" />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3,minmax(0,1fr))" }}>
            {[
              { label: "ENTRIES", value: String(data?.rebalance.buys ?? 0), tone: "pos" as const },
              { label: "EXITS", value: String(data?.rebalance.sells ?? 0), tone: "neg" as const },
              { label: "TURNOVER", value: data?.rebalance.turnover != null ? `${(data.rebalance.turnover * 100).toFixed(0)}%` : "—" },
            ].map((r, i) => (
              <div key={r.label} style={{ padding: "14px 8px", textAlign: "center", borderRight: i < 2 ? `1px solid ${C.border}` : undefined }}>
                <div style={{ fontFamily: MONO, fontSize: 22, fontWeight: 600, lineHeight: 1, color: r.tone === "pos" ? C.pos : r.tone === "neg" ? C.neg : C.text }}>
                  {r.value}
                </div>
                <div style={{ marginTop: 4, fontFamily: MONO, fontSize: 10, letterSpacing: "0.08em", color: C.t4 }}>{r.label}</div>
              </div>
            ))}
          </div>
          <div style={{ borderTop: `1px solid ${C.border}` }}>
            <MetaRows
              rows={[
                { label: "as of", value: data?.as_of ?? "—" },
                { label: "prior book", value: data?.rebalance.prior ?? "—" },
                { label: "construction", value: data?.construction ?? "—" },
              ]}
            />
          </div>
        </Panel>
      </div>
    </div>
  );
}

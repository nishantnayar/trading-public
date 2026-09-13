"use client";

import { MetaRows, Note, Panel, PanelHeader } from "@/components/ui";
import type { SignalRow } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { C, MONO } from "@/lib/palette";

const TH: React.CSSProperties = { padding: "7px 10px", fontWeight: 400, color: C.t4 };

function fmtPct(value: number | null): string {
  if (value == null) return "—";
  const sign = value >= 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(1)}%`;
}

export default function SignalsPage() {
  const snap = useApi<SignalRow[]>("/signals");
  const rows = snap.data ?? [];
  const empty = !snap.loading && rows.length === 0;
  const longs = rows.filter((r) => r.signal === "long").length;

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "minmax(0,2.6fr) minmax(240px,1fr)",
        gap: 14,
        alignItems: "start",
      }}
    >
      <Panel>
        <PanelHeader
          label="TREND SIGNAL"
          right={
            <span style={{ marginLeft: "auto", fontFamily: MONO, fontSize: 10, color: C.t4 }}>
              {rows[0]?.date ? `as of ${rows[0].date}` : "NO SIGNALS PUBLISHED"}
            </span>
          }
        />
        {empty ? (
          <div style={{ padding: 24, fontFamily: MONO, fontSize: 12, color: C.t3 }}>
            Run: uv run python -m quantis.signals --persist
          </div>
        ) : (
          <table style={{ fontFamily: MONO, fontSize: 12, width: "100%" }}>
            <thead>
              <tr
                style={{ fontSize: 10, letterSpacing: "0.1em", borderBottom: `1px solid ${C.border}` }}
              >
                <th style={{ ...TH, padding: "7px 10px 7px 14px", textAlign: "left" }}>TICKER</th>
                <th style={{ ...TH, textAlign: "right" }}>CLOSE</th>
                <th style={{ ...TH, textAlign: "right" }}>SMA FAST</th>
                <th style={{ ...TH, textAlign: "right" }}>SMA SLOW</th>
                <th style={{ ...TH, textAlign: "right" }}>MOM 12-1</th>
                <th style={{ ...TH, padding: "7px 14px 7px 10px", textAlign: "right" }}>SIGNAL</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const isLong = r.signal === "long";
                return (
                  <tr key={r.symbol} style={{ borderTop: `1px solid ${C.border2}`, height: 30 }}>
                    <td style={{ padding: "0 10px 0 14px", color: C.text }}>{r.symbol}</td>
                    <td style={{ padding: "0 10px", textAlign: "right", color: C.t2 }}>
                      {r.close.toFixed(2)}
                    </td>
                    <td style={{ padding: "0 10px", textAlign: "right", color: C.t3 }}>
                      {r.sma_fast?.toFixed(2) ?? "—"}
                    </td>
                    <td style={{ padding: "0 10px", textAlign: "right", color: C.t3 }}>
                      {r.sma_slow?.toFixed(2) ?? "—"}
                    </td>
                    <td
                      style={{
                        padding: "0 10px",
                        textAlign: "right",
                        color: (r.mom_12_1 ?? 0) >= 0 ? C.pos : C.neg,
                      }}
                    >
                      {fmtPct(r.mom_12_1)}
                    </td>
                    <td style={{ padding: "0 14px 0 10px", textAlign: "right" }}>
                      <span
                        style={{
                          fontSize: 10,
                          letterSpacing: "0.06em",
                          color: isLong ? C.pos : C.t4,
                        }}
                      >
                        {isLong ? "LONG" : "FLAT"}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
        <Note>RULE-BASED · SMA crossover + 12-1 momentum, debounced exit — not a model score</Note>
      </Panel>

      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <Panel>
          <PanelHeader label="SIGNAL SUMMARY" />
          <MetaRows
            rows={[
              { label: "watchlist", value: String(rows.length) },
              { label: "long", value: String(longs), tone: "pos" },
              { label: "flat", value: String(rows.length - longs) },
              { label: "rule", value: "sma crossover" },
            ]}
          />
        </Panel>
      </div>
    </div>
  );
}

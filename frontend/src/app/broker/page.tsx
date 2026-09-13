"use client";

import { Note, Panel, PanelHeader } from "@/components/ui";
import type { BrokerState } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { C, MONO } from "@/lib/palette";

const TH: React.CSSProperties = { padding: "7px 10px", fontWeight: 400, color: C.t4 };

/**
 * quantis.execution.simulated - a paper ledger only. No real order is ever
 * submitted anywhere in that module; every number on this screen is a
 * simulated fill against `quantis.signals.portfolio.target_weights`, marked
 * at the latest close. See docs/LIMITATIONS.md for what that simplification
 * skips (slippage dispersion, borrow, market impact, financing).
 */
export default function BrokerPage() {
  const broker = useApi<BrokerState | null>("/broker");
  const b = broker.data;
  const positions = [...(b?.positions ?? [])].sort((a, c) => c.market_value - a.market_value);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,minmax(0,1fr))", border: `1px solid ${C.border}`, background: C.panel }}>
        {[
          { label: "EQUITY", value: b ? `$${b.equity.toLocaleString(undefined, { maximumFractionDigits: 0 })}` : "—" },
          { label: "CASH", value: b ? `$${b.cash.toLocaleString(undefined, { maximumFractionDigits: 0 })}` : "—" },
          { label: "POSITIONS", value: b ? String(positions.length) : "—" },
          { label: "UPDATED", value: b?.updated_at ? b.updated_at.replace("T", " ").slice(0, 16) : "—" },
        ].map((k, i) => (
          <div key={k.label} style={{ padding: 14, borderRight: i < 3 ? `1px solid ${C.border}` : undefined }}>
            <div style={{ fontFamily: MONO, fontSize: 10, letterSpacing: "0.1em", color: C.t3 }}>{k.label}</div>
            <div style={{ marginTop: 8, fontFamily: MONO, fontSize: 22, fontWeight: 600, lineHeight: 1 }}>{k.value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,2.6fr) minmax(280px,1fr)", gap: 14, alignItems: "start" }}>
        <Panel>
          <PanelHeader label="SIMULATED POSITIONS" />
          {!b ? (
            <div style={{ padding: 24, fontFamily: MONO, fontSize: 12, color: C.t3 }}>
              Run: uv run python -c &quot;from quantis.execution.simulated import
              rebalance; rebalance()&quot;
            </div>
          ) : positions.length === 0 ? (
            <div style={{ padding: 24, fontFamily: MONO, fontSize: 12, color: C.t3 }}>
              No open positions.
            </div>
          ) : (
            <table style={{ fontFamily: MONO, fontSize: 12, width: "100%" }}>
              <thead>
                <tr style={{ fontSize: 10, letterSpacing: "0.1em", borderBottom: `1px solid ${C.border}` }}>
                  <th style={{ ...TH, padding: "7px 10px 7px 14px", textAlign: "left" }}>TICKER</th>
                  <th style={{ ...TH, textAlign: "right" }}>QTY</th>
                  <th style={{ ...TH, textAlign: "right" }}>PRICE</th>
                  <th style={{ ...TH, padding: "7px 14px 7px 10px", textAlign: "right" }}>MKT VALUE</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((p) => (
                  <tr key={p.symbol} style={{ borderTop: `1px solid ${C.border2}`, height: 30 }}>
                    <td style={{ padding: "0 10px 0 14px", color: C.text }}>{p.symbol}</td>
                    <td style={{ padding: "0 10px", textAlign: "right", color: C.t2 }}>{p.qty.toFixed(3)}</td>
                    <td style={{ padding: "0 10px", textAlign: "right", color: C.t3 }}>{p.price?.toFixed(2) ?? "—"}</td>
                    <td style={{ padding: "0 14px 0 10px", textAlign: "right", color: C.text }}>
                      ${p.market_value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <Note>SIMULATED · fills at the latest close · fractional shares · no real order ever submitted</Note>
        </Panel>

        <Panel>
          <PanelHeader label="RECENT FILLS" />
          {!b || b.recent_fills.length === 0 ? (
            <div style={{ padding: 24, fontFamily: MONO, fontSize: 12, color: C.t3 }}>
              No fills yet.
            </div>
          ) : (
            <div style={{ maxHeight: 420, overflowY: "auto" }}>
              <table style={{ fontFamily: MONO, fontSize: 11, width: "100%" }}>
                <tbody>
                  {b.recent_fills.map((f, i) => (
                    <tr key={`${f.symbol}-${i}`} style={{ borderTop: `1px solid ${C.border2}`, height: 26 }}>
                      <td style={{ padding: "0 8px 0 14px", color: f.side === "buy" ? C.pos : C.neg, width: 40 }}>
                        {f.side.toUpperCase()}
                      </td>
                      <td style={{ padding: "0 8px", color: C.text }}>{f.symbol}</td>
                      <td style={{ padding: "0 8px", textAlign: "right", color: C.t3 }}>{f.qty.toFixed(3)}</td>
                      <td style={{ padding: "0 14px 0 8px", textAlign: "right", color: C.t2 }}>
                        {f.price.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}

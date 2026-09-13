"use client";

import { Note, Panel, PanelHeader } from "@/components/ui";
import type { SignalRow } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { C, MONO } from "@/lib/palette";

const TH: React.CSSProperties = { padding: "7px 10px", fontWeight: 400, color: C.t4 };

/**
 * There is no portfolio-construction layer yet (no weights, no rebalance
 * history) - the trend rule only says long/flat per symbol. So "positions"
 * here is an equal-weighted illustrative book of the names currently
 * signaled long, derived straight from /signals rather than a separate
 * endpoint.
 */
export default function PositionsPage() {
  const snap = useApi<SignalRow[]>("/signals");
  const rows = snap.data ?? [];
  const empty = !snap.loading && rows.length === 0;
  const longs = rows.filter((r) => r.signal === "long");
  const weight = longs.length > 0 ? 1 / longs.length : 0;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(0,2.6fr) minmax(240px,1fr)", gap: 14, alignItems: "start" }}>
      <Panel>
        <PanelHeader
          label="ILLUSTRATIVE BOOK"
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
        ) : longs.length === 0 ? (
          <div style={{ padding: 24, fontFamily: MONO, fontSize: 12, color: C.t3 }}>
            No watchlist symbol is currently signaled long.
          </div>
        ) : (
          <table style={{ fontFamily: MONO, fontSize: 12, width: "100%" }}>
            <thead>
              <tr style={{ fontSize: 10, letterSpacing: "0.1em", borderBottom: `1px solid ${C.border}` }}>
                <th style={{ ...TH, padding: "7px 10px 7px 14px", textAlign: "left" }}>TICKER</th>
                <th style={{ ...TH, textAlign: "right" }}>CLOSE</th>
                <th style={{ ...TH, padding: "7px 14px 7px 10px", textAlign: "right" }}>WEIGHT</th>
              </tr>
            </thead>
            <tbody>
              {longs.map((r) => (
                <tr key={r.symbol} style={{ borderTop: `1px solid ${C.border2}`, height: 30 }}>
                  <td style={{ padding: "0 10px 0 14px", color: C.text }}>{r.symbol}</td>
                  <td style={{ padding: "0 10px", textAlign: "right", color: C.t2 }}>{r.close.toFixed(2)}</td>
                  <td style={{ padding: "0 14px 0 10px", textAlign: "right", color: C.pos }}>
                    {(weight * 100).toFixed(1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <Note>EQUAL-WEIGHTED · every currently-long watchlist name at 1/N · not a broker position</Note>
      </Panel>

      <Panel>
        <PanelHeader label="BOOK SUMMARY" />
        <div style={{ padding: "4px 0" }}>
          {[
            { label: "watchlist", value: String(rows.length) },
            { label: "long (in book)", value: String(longs.length), tone: "pos" as const },
            { label: "flat (excluded)", value: String(rows.length - longs.length) },
          ].map((r) => (
            <div
              key={r.label}
              style={{
                display: "flex",
                alignItems: "baseline",
                justifyContent: "space-between",
                gap: 12,
                padding: "7px 14px",
                fontFamily: MONO,
                fontSize: 12,
              }}
            >
              <span style={{ fontSize: 11, color: C.t3 }}>{r.label}</span>
              <span style={{ color: r.tone === "pos" ? C.pos : C.text }}>{r.value}</span>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

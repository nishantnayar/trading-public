"use client";

import { useState } from "react";

import { PriceChart } from "@/components/PriceChart";
import { MetaRows, Panel, PanelHeader } from "@/components/ui";
import { FEED_LABEL, type Bar, type Coverage, type SectorCount } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { C, MONO } from "@/lib/palette";

const RANGES: Record<string, number> = { "1M": 31, "6M": 186, "1Y": 366, "3Y": 1097 };

type UniverseRow = { symbol: string; name: string | null; sector: string | null };

function fmtVol(v: number): string {
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return String(v);
}

function isoDaysAgo(days: number): string {
  return new Date(Date.now() - days * 864e5).toISOString().slice(0, 10);
}

function spanText(cov: Coverage): string {
  if (!cov.start || !cov.end) return "—";
  const yrs = (new Date(cov.end).getTime() - new Date(cov.start).getTime()) / (365.25 * 864e5);
  return `${yrs.toFixed(1)}y`;
}

export default function OverviewPage() {
  const [range, setRange] = useState("3Y");
  const [symbol, setSymbol] = useState("AAPL");
  const [input, setInput] = useState("AAPL");
  const cov = useApi<Coverage>("/coverage");
  const sectors = useApi<SectorCount[]>("/sectors");
  const universe = useApi<UniverseRow[]>("/universe");
  const bars = useApi<Bar[]>(`/bars/${symbol}?start=${isoDaysAgo(RANGES[range])}`);

  const known = new Set((universe.data ?? []).map((r) => r.symbol));
  const commit = (raw: string) => {
    const s = raw.trim().toUpperCase();
    if (s) setSymbol(s);
  };

  const list = bars.data ?? [];
  const last = list.at(-1);
  const first = list[0];
  const prev = list.at(-2) ?? last;
  const changePeriod = last && first ? (last.close / first.close - 1) * 100 : 0;
  const change1d = last && prev ? (last.close / prev.close - 1) * 100 : 0;
  const points = list.map((b) => ({ date: b.date, close: b.close }));

  const total = (sectors.data ?? []).reduce((a, r) => a + r.count, 0) || 1;
  const maxSector = Math.max(1, ...(sectors.data ?? []).map((r) => r.count));

  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(0,2.4fr) minmax(260px,1fr)", gap: 14, alignItems: "start" }}>
      {/* PRICE */}
      <Panel>
        <div style={{ display: "flex", alignItems: "center", gap: 12, height: 36, padding: "0 14px", borderBottom: `1px solid ${C.border}` }}>
          <span style={{ fontFamily: MONO, fontSize: 10, letterSpacing: "0.12em", color: C.t3 }}>PRICE ·</span>
          <input
            list="universe-symbols"
            value={input}
            spellCheck={false}
            autoCapitalize="characters"
            onChange={(e) => {
              setInput(e.target.value);
              // commit immediately when the value is an exact universe pick
              if (known.has(e.target.value.trim().toUpperCase())) commit(e.target.value);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") commit(input);
            }}
            onBlur={() => commit(input)}
            style={{
              width: 88,
              background: C.track,
              border: `1px solid ${C.border}`,
              color: C.text,
              fontFamily: MONO,
              fontSize: 12,
              fontWeight: 600,
              letterSpacing: "0.04em",
              textTransform: "uppercase",
              padding: "4px 8px",
              outline: "none",
            }}
          />
          <datalist id="universe-symbols">
            {(universe.data ?? []).map((r) => (
              <option key={r.symbol} value={r.symbol}>
                {r.name ?? ""}
              </option>
            ))}
          </datalist>
          <span style={{ fontFamily: MONO, fontSize: 11, color: C.t4 }}>adjusted · IEX · {range}</span>
          <div style={{ display: "flex", marginLeft: "auto", border: `1px solid ${C.border}` }}>
            {Object.keys(RANGES).map((r) => (
              <button
                key={r}
                onClick={() => setRange(r)}
                style={{
                  padding: "4px 9px",
                  fontFamily: MONO,
                  fontSize: 10,
                  cursor: "pointer",
                  border: "none",
                  borderRight: `1px solid ${C.border}`,
                  background: r === range ? C.track : "transparent",
                  color: r === range ? C.accent : C.t4,
                }}
              >
                {r}
              </button>
            ))}
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "baseline", gap: 18, padding: "12px 14px 0", fontFamily: MONO, flexWrap: "wrap" }}>
          <span style={{ fontSize: 28, fontWeight: 600, letterSpacing: "-0.01em" }}>{last ? last.close.toFixed(2) : "—"}</span>
          <span style={{ fontSize: 13, color: changePeriod >= 0 ? C.pos : C.neg }}>
            {last ? `${changePeriod >= 0 ? "+" : ""}${changePeriod.toFixed(1)}%` : "—"} <span style={{ color: C.t4 }}>{range}</span>
          </span>
          <span style={{ fontSize: 13, color: change1d >= 0 ? C.pos : C.neg }}>
            {last ? `${change1d >= 0 ? "+" : ""}${change1d.toFixed(2)}%` : "—"} <span style={{ color: C.t4 }}>1D</span>
          </span>
          <span style={{ marginLeft: "auto", fontSize: 11, color: C.t4 }}>
            {last ? `O ${last.open.toFixed(2)} · H ${last.high.toFixed(2)} · L ${last.low.toFixed(2)} · V ${fmtVol(last.volume)}` : ""}
          </span>
        </div>

        {bars.error ? (
          <div style={{ padding: 24, fontFamily: MONO, fontSize: 12, color: C.neg }}>API error: {bars.error} — is the backend on :8000?</div>
        ) : (
          <PriceChart points={points} />
        )}
      </Panel>

      {/* RIGHT COLUMN */}
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <Panel>
          <PanelHeader label="DATA COVERAGE" />
          <MetaRows
            rows={
              cov.data
                ? [
                    { label: "daily bars", value: cov.data.rows.toLocaleString() },
                    { label: "symbols", value: String(cov.data.symbols) },
                    { label: "range", value: `${cov.data.start} → ${cov.data.end}` },
                    { label: "span", value: spanText(cov.data) },
                    { label: "feed", value: FEED_LABEL, tone: "accent" },
                  ]
                : [{ label: "loading", value: "…" }]
            }
          />
        </Panel>

        <Panel>
          <PanelHeader
            label="UNIVERSE BY SECTOR"
            right={<span style={{ marginLeft: "auto", fontFamily: MONO, fontSize: 10, color: C.t4 }}>{cov.data ? `${cov.data.symbols} NAMES` : ""}</span>}
          />
          <table style={{ fontFamily: MONO, fontSize: 11 }}>
            <tbody>
              {(sectors.data ?? []).map((row) => (
                <tr key={row.sector} style={{ borderTop: `1px solid ${C.border2}` }}>
                  <td style={{ padding: "6px 0 6px 14px", color: C.t2, whiteSpace: "nowrap" }}>{row.sector}</td>
                  <td style={{ padding: "6px 8px", width: "38%" }}>
                    <div style={{ height: 6, background: C.track }}>
                      <div style={{ height: "100%", background: C.accent, opacity: 0.85, width: `${((row.count / maxSector) * 100).toFixed(0)}%` }} />
                    </div>
                  </td>
                  <td style={{ padding: "6px 6px", textAlign: "right", color: C.text }}>{row.count}</td>
                  <td style={{ padding: "6px 14px 6px 0", textAlign: "right", color: C.t4 }}>{((row.count / total) * 100).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      </div>
    </div>
  );
}

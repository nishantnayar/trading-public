"use client";

import { Panel, PanelHeader } from "@/components/ui";
import type { ModelSnapshot } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { C, MONO, SANS } from "@/lib/palette";

function fmt(value: number | null | undefined, digits = 3): string {
  return value == null || Number.isNaN(value) ? "—" : value.toFixed(digits);
}

export default function ModelPage() {
  const snap = useApi<ModelSnapshot>("/model");
  const m = snap.data;
  const empty = !m?.as_of && !m?.oof_source;
  const shap = m?.shap ?? [];
  const maxGain = Math.max(0.001, ...shap.map((s) => s.gain));
  const kpis = [
    { label: "OOF RANK IC", value: fmt(m?.rank_ic, 3), sub: "purged CV" },
    { label: "ICIR", value: fmt(m?.icir, 2), sub: `${m?.n_dates ?? "—"} dates` },
    { label: "HIT RATE", value: m?.ic_hit_rate != null ? `${(m.ic_hit_rate * 100).toFixed(1)}%` : "—", sub: "share of dates IC>0" },
    { label: "SHARPE @ 10bps", value: fmt(m?.sharpe_10bps, 2), sub: "working book" },
    { label: "BREAK-EVEN", value: m?.break_even_bps != null ? `${m.break_even_bps.toFixed(1)} bps` : "—", sub: "per side" },
  ];
  const params = m?.params ?? {};
  const config: [string, string][] = [
    ["objective", String(params.objective ?? "regression")],
    ["label", "xs z-score fwd 5d"],
    ["num_leaves", String(params.num_leaves ?? "—")],
    ["learning_rate", String(params.learning_rate ?? "—")],
    ["construction", m?.construction ?? "—"],
    ["oof source", m?.oof_source ?? "—"],
    ["cv", "purged walk-forward · 5d embargo"],
    ["turnover", m?.turnover != null ? `${m.turnover.toFixed(1)}x / yr` : "—"],
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5,minmax(0,1fr))", border: `1px solid ${C.border}`, background: C.panel }}>
        {kpis.map((k, i) => (
          <div key={k.label} style={{ padding: 14, borderRight: i < 4 ? `1px solid ${C.border}` : undefined }}>
            <div style={{ fontFamily: MONO, fontSize: 10, letterSpacing: "0.1em", color: C.t3 }}>{k.label}</div>
            <div style={{ marginTop: 8, fontFamily: MONO, fontSize: 24, fontWeight: 600, lineHeight: 1 }}>{empty ? "—" : k.value}</div>
            <div style={{ marginTop: 6, fontFamily: MONO, fontSize: 10, color: C.t4 }}>{k.sub}</div>
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1.5fr) minmax(280px,1fr)", gap: 14, alignItems: "start" }}>
        <Panel>
          <PanelHeader
            label="FEATURE IMPORTANCE"
            right={<span style={{ fontFamily: MONO, fontSize: 11, color: C.t4 }}>gain share · last booster</span>}
          />
          <table style={{ fontFamily: MONO, fontSize: 11 }}>
            <tbody>
              {shap.map((row, i) => (
                <tr key={row.feature} style={{ borderTop: `1px solid ${C.border2}` }}>
                  <td style={{ padding: "0 8px 0 14px", height: 30, color: C.t4, textAlign: "right", width: 24 }}>{i + 1}</td>
                  <td style={{ padding: "0 10px", color: C.text, whiteSpace: "nowrap" }}>{row.feature}</td>
                  <td style={{ padding: "0 10px", fontSize: 10, color: C.t4, whiteSpace: "nowrap" }}>{row.family}</td>
                  <td style={{ padding: "0 10px" }}>
                    <div style={{ height: 8, background: C.track }}>
                      <div style={{ height: "100%", background: C.accent, opacity: 0.85, width: `${((row.gain / maxGain) * 100).toFixed(0)}%` }} />
                    </div>
                  </td>
                  <td style={{ padding: "0 14px 0 10px", textAlign: "right", color: C.t2, width: 56 }}>{row.gain.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>

        <Panel>
          <PanelHeader label="TRAINING CONFIG" />
          <table style={{ fontFamily: MONO, fontSize: 11 }}>
            <tbody>
              {config.map(([key, value]) => (
                <tr key={key} style={{ borderTop: `1px solid ${C.border2}` }}>
                  <td style={{ padding: "0 10px 0 14px", height: 28, color: C.t3 }}>{key}</td>
                  <td style={{ padding: "0 14px 0 10px", textAlign: "right", color: C.text }}>{value}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ padding: "10px 14px", borderTop: `1px solid ${C.border}`, fontFamily: SANS, fontSize: 11, lineHeight: 1.5, color: C.t4 }}>
            Purged walk-forward CV with a 5-day embargo. Rank IC 0.018 is gross of costs; Sharpe at 10 bps is the working
            book (buffer=1, hold 10), not the Phase 5 weekly default.
          </div>
        </Panel>
      </div>
    </div>
  );
}

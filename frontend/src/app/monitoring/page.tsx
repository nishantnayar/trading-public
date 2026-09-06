"use client";

import { MetaRows, Panel, PanelHeader } from "@/components/ui";
import { FEED_LABEL, type Coverage, type IngestRun } from "@/lib/api";
import { FLOWS } from "@/lib/illustrative";
import { useApi } from "@/lib/useApi";
import { C, MONO, SANS } from "@/lib/palette";

const TH: React.CSSProperties = { padding: "7px 10px", fontWeight: 400, color: C.t4 };

export default function MonitoringPage() {
  const cov = useApi<Coverage>("/coverage");
  const runs = useApi<IngestRun[]>("/ingest-runs");
  const hasRuns = (runs.data?.length ?? 0) > 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {/* scheduled flows */}
      <Panel>
        <PanelHeader
          label="SCHEDULED FLOWS"
          right={
            <>
              <span style={{ fontFamily: MONO, fontSize: 11, color: C.t4 }}>Prefect · isolated profile :4201</span>
              <span style={{ marginLeft: "auto", fontFamily: MONO, fontSize: 11, color: C.t4 }}>1 of 4 live</span>
            </>
          }
        />
        <table style={{ fontFamily: MONO, fontSize: 12 }}>
          <thead>
            <tr style={{ fontSize: 10, letterSpacing: "0.1em", borderBottom: `1px solid ${C.border}` }}>
              <th style={{ ...TH, padding: "7px 10px 7px 14px", textAlign: "left" }}>FLOW</th>
              <th style={{ ...TH, textAlign: "left" }}>STATE</th>
              <th style={{ ...TH, textAlign: "left" }}>SCHEDULE</th>
              <th style={{ ...TH, textAlign: "left" }}>LAST RUN</th>
              <th style={{ ...TH, textAlign: "right" }}>ROWS</th>
              <th style={{ ...TH, padding: "7px 14px 7px 10px", textAlign: "left" }}>PHASE</th>
            </tr>
          </thead>
          <tbody>
            {FLOWS.map((f) => (
              <tr key={f.label} style={{ borderTop: `1px solid ${C.border2}`, height: 34, fontFamily: MONO }}>
                <td style={{ padding: "0 10px 0 14px", color: C.text }}>{f.label}</td>
                <td style={{ padding: "0 10px" }}>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 7, fontSize: 11, color: f.ok ? C.pos : C.t3 }}>
                    <span style={{ width: 6, height: 6, borderRadius: 99, background: f.ok ? C.pos : C.accent }} />
                    {f.state}
                  </span>
                </td>
                <td style={{ padding: "0 10px", color: C.t3 }}>{f.schedule}</td>
                <td style={{ padding: "0 10px", color: C.t3 }}>{f.last}</td>
                <td style={{ padding: "0 10px", textAlign: "right", color: C.t2 }}>{f.rows}</td>
                <td style={{ padding: "0 14px 0 10px", color: C.t4 }}>{f.phase}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) minmax(0,1.6fr)", gap: 14, alignItems: "start" }}>
        {/* bar coverage (real) */}
        <Panel>
          <PanelHeader label="BAR COVERAGE" />
          <MetaRows
            rows={
              cov.data
                ? [
                    { label: "daily bars", value: cov.data.rows.toLocaleString() },
                    { label: "symbols", value: String(cov.data.symbols) },
                    { label: "start", value: cov.data.start ?? "—" },
                    { label: "end", value: cov.data.end ?? "—" },
                    { label: "feed", value: FEED_LABEL, tone: "accent" },
                  ]
                : [{ label: "loading", value: "…" }]
            }
          />
          <div style={{ padding: "10px 14px", borderTop: `1px solid ${C.border}`, fontFamily: SANS, fontSize: 11, lineHeight: 1.5, color: C.t4 }}>
            Free IEX feed reports IEX-only volume and history starts 2017-11; the starter universe is the current S&amp;P 500
            (survivorship bias).
          </div>
        </Panel>

        {/* ingest run audit (real) */}
        <Panel>
          <PanelHeader label="INGEST RUN AUDIT" right={<span style={{ marginLeft: "auto", fontFamily: MONO, fontSize: 11, color: C.t4 }}>table: ingest_runs</span>} />
          {hasRuns ? (
            <table style={{ fontFamily: MONO, fontSize: 12 }}>
              <thead>
                <tr style={{ fontSize: 10, letterSpacing: "0.1em", borderBottom: `1px solid ${C.border}` }}>
                  <th style={{ ...TH, padding: "7px 10px 7px 14px", textAlign: "left" }}>FLOW</th>
                  <th style={{ ...TH, textAlign: "left" }}>STARTED</th>
                  <th style={{ ...TH, textAlign: "right" }}>SYMBOLS</th>
                  <th style={{ ...TH, textAlign: "right" }}>ROWS</th>
                  <th style={{ ...TH, padding: "7px 14px 7px 10px", textAlign: "left" }}>STATUS</th>
                </tr>
              </thead>
              <tbody>
                {runs.data!.map((r, i) => (
                  <tr key={i} style={{ borderTop: `1px solid ${C.border2}`, height: 30 }}>
                    <td style={{ padding: "0 10px 0 14px", color: C.text }}>{r.flow}</td>
                    <td style={{ padding: "0 10px", color: C.t3 }}>{r.started_at?.replace("T", " ").slice(0, 16) ?? "—"}</td>
                    <td style={{ padding: "0 10px", textAlign: "right", color: C.t2 }}>{r.symbols_processed ?? "—"}</td>
                    <td style={{ padding: "0 10px", textAlign: "right", color: C.t2 }}>{r.rows_written?.toLocaleString() ?? "—"}</td>
                    <td style={{ padding: "0 14px 0 10px", color: r.status === "success" ? C.pos : C.accent }}>{r.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 10, padding: "32px 14px" }}>
              <div style={{ fontFamily: MONO, fontSize: 11, letterSpacing: "0.1em", color: C.accent }}>NO ROWS YET</div>
              <div style={{ fontFamily: SANS, fontSize: 12, lineHeight: 1.6, color: C.t3, maxWidth: "46ch" }}>
                The daily ingest flow does not write the audit table yet. Once it does, every run lands here with symbols
                processed, rows written and failure detail.
              </div>
              <div style={{ border: `1px solid ${C.cap}`, padding: "5px 10px", fontFamily: MONO, fontSize: 11, color: C.t2 }}>
                Blocked on Phase 8 · Prefect deployments
              </div>
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}

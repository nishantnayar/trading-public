"use client";

import { useRef, useState } from "react";

import type { BrokerEquitySnapshot } from "@/lib/api";
import { C, MONO } from "@/lib/palette";

const W = 700;
const H = 200;
const PAD = 8;

/** Amber area line chart of simulated broker equity over successive rebalances. */
export function NavChart({ history }: { history: BrokerEquitySnapshot[] }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [idx, setIdx] = useState<number | null>(null);

  if (history.length < 2) {
    return (
      <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center", color: C.t4, fontFamily: MONO, fontSize: 11 }}>
        not enough history yet — one point per rebalance
      </div>
    );
  }

  const equity = history.map((p) => p.equity);
  const lo = Math.min(...equity) * 0.98;
  const hi = Math.max(...equity) * 1.02;
  const x = (i: number) => (i / (history.length - 1)) * W;
  const y = (v: number) => PAD + (1 - (v - lo) / (hi - lo)) * (H - PAD * 2);
  const line = equity.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
  const yTicks = Array.from({ length: 4 }, (_, i) => Math.round(hi - (i * (hi - lo)) / 3).toLocaleString());

  const pick = (clientX: number) => {
    const el = svgRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const t = (clientX - rect.left) / Math.max(rect.width, 1);
    setIdx(Math.round(Math.min(1, Math.max(0, t)) * (history.length - 1)));
  };

  const hover = idx == null ? null : history[idx];
  const tipX = hover && idx != null ? Math.min(Math.max(x(idx) + 10, 8), W - 150) : 0;

  return (
    <div style={{ display: "flex", gap: 10, padding: "8px 14px 12px" }}>
      <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", width: 60, height: H, fontFamily: MONO, fontSize: 10, color: C.t4, textAlign: "right" }}>
        {yTicks.map((t, i) => (
          <div key={i}>{t}</div>
        ))}
      </div>
      <div style={{ flex: 1, minWidth: 0, position: "relative" }}>
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          onPointerMove={(e) => pick(e.clientX)}
          onPointerLeave={() => setIdx(null)}
          style={{ width: "100%", height: H, display: "block", borderLeft: `1px solid ${C.border}`, borderBottom: `1px solid ${C.border}`, cursor: "crosshair" }}
        >
          <path d={`${line} L${W} ${H} L0 ${H} Z`} fill={C.accent} fillOpacity={0.09} />
          <path d={line} fill="none" stroke={C.accent} strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
          {hover && idx != null && (
            <>
              <line x1={x(idx)} x2={x(idx)} y1={0} y2={H} stroke={C.accent2} strokeOpacity={0.45} strokeWidth={1} vectorEffect="non-scaling-stroke" />
              <circle cx={x(idx)} cy={y(hover.equity)} r={3.5} fill={C.accent} stroke={C.panel} strokeWidth={1} />
            </>
          )}
          <rect x={0} y={0} width={W} height={H} fill="transparent" />
        </svg>
        {hover && idx != null && (
          <div
            style={{
              position: "absolute",
              left: `${(tipX / W) * 100}%`,
              top: 4,
              pointerEvents: "none",
              background: C.panel,
              border: `1px solid ${C.border}`,
              padding: "6px 8px",
              fontFamily: MONO,
              fontSize: 10,
              color: C.text,
              lineHeight: 1.55,
              minWidth: 130,
            }}
          >
            <div style={{ color: C.t3, marginBottom: 2 }}>
              {hover.recorded_at ? hover.recorded_at.replace("T", " ").slice(0, 16) : "—"}
            </div>
            <div>${hover.equity.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
            <div style={{ color: C.t4 }}>{hover.n_positions} positions</div>
          </div>
        )}
      </div>
    </div>
  );
}

"use client";

import { useRef, useState } from "react";

import type { Bar } from "@/lib/api";
import { fmtVol } from "@/lib/format";
import { C, MONO } from "@/lib/palette";

const W = 700;
const H = 300;
const PAD = 8;

/** Amber area line chart with a crosshair and OHLC tooltip on hover. */
export function PriceChart({ bars, onHover }: { bars: Bar[]; onHover?: (bar: Bar | null) => void }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [idx, setIdx] = useState<number | null>(null);

  if (bars.length < 2) {
    return <div style={{ height: 300, display: "flex", alignItems: "center", justifyContent: "center", color: C.t4, fontFamily: MONO, fontSize: 11 }}>no data</div>;
  }

  const closes = bars.map((p) => p.close);
  const lo = Math.min(...closes) * 0.97;
  const hi = Math.max(...closes) * 1.03;
  const x = (i: number) => (i / (bars.length - 1)) * W;
  const y = (v: number) => PAD + (1 - (v - lo) / (hi - lo)) * (H - PAD * 2);
  const line = closes.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
  const yTicks = Array.from({ length: 5 }, (_, i) => Math.round(hi - (i * (hi - lo)) / 4).toString());
  const gridY = [1, 2, 3, 4].map((i) => Number(((H / 5) * i).toFixed(0)));
  const xTicks = [0, 1, 2, 3, 4, 5].map((i) => bars[Math.round((i / 5) * (bars.length - 1))].date.slice(0, 7));

  const pick = (clientX: number) => {
    const el = svgRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const t = (clientX - rect.left) / Math.max(rect.width, 1);
    const next = Math.round(Math.min(1, Math.max(0, t)) * (bars.length - 1));
    setIdx(next);
    onHover?.(bars[next]);
  };
  const clear = () => {
    setIdx(null);
    onHover?.(null);
  };

  const hover = idx == null ? null : bars[idx];
  const tipX = hover && idx != null ? Math.min(Math.max(x(idx) + 10, 8), W - 170) : 0;
  const tipY = hover && idx != null ? Math.max(y(hover.close) - 78, 8) : 0;

  return (
    <div style={{ display: "flex", gap: 10, padding: "8px 14px 12px" }}>
      <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", width: 44, height: 300, fontFamily: MONO, fontSize: 10, color: C.t4, textAlign: "right" }}>
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
          onPointerLeave={clear}
          style={{ width: "100%", height: 300, display: "block", borderLeft: `1px solid ${C.border}`, borderBottom: `1px solid ${C.border}`, cursor: "crosshair" }}
        >
          {gridY.map((g, i) => (
            <line key={i} x1={0} x2={W} y1={g} y2={g} stroke={C.border2} strokeWidth={1} />
          ))}
          <path d={`${line} L${W} ${H} L0 ${H} Z`} fill={C.accent} fillOpacity={0.09} />
          <path d={line} fill="none" stroke={C.accent} strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
          {hover && idx != null && (
            <>
              <line x1={x(idx)} x2={x(idx)} y1={0} y2={H} stroke={C.accent2} strokeOpacity={0.45} strokeWidth={1} vectorEffect="non-scaling-stroke" />
              <circle cx={x(idx)} cy={y(hover.close)} r={3.5} fill={C.accent} stroke={C.panel} strokeWidth={1} />
            </>
          )}
          <rect x={0} y={0} width={W} height={H} fill="transparent" />
        </svg>
        {hover && (
          <div
            style={{
              position: "absolute",
              left: `${(tipX / W) * 100}%`,
              top: tipY,
              pointerEvents: "none",
              background: C.panel,
              border: `1px solid ${C.border}`,
              padding: "6px 8px",
              fontFamily: MONO,
              fontSize: 10,
              color: C.text,
              lineHeight: 1.55,
              minWidth: 148,
            }}
          >
            <div style={{ color: C.t3, marginBottom: 2 }}>{hover.date.slice(0, 10)}</div>
            <div>O {hover.open.toFixed(2)} · H {hover.high.toFixed(2)}</div>
            <div>L {hover.low.toFixed(2)} · C {hover.close.toFixed(2)}</div>
            <div style={{ color: C.t4 }}>V {fmtVol(hover.volume)}</div>
          </div>
        )}
        <div style={{ display: "flex", justifyContent: "space-between", paddingTop: 6, fontFamily: MONO, fontSize: 10, color: C.t4 }}>
          {xTicks.map((t, i) => (
            <div key={i}>{t}</div>
          ))}
        </div>
      </div>
    </div>
  );
}

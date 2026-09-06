"use client";

import { C, MONO } from "@/lib/palette";

type Point = { date: string; close: number };

/** Amber area line chart drawn as a single SVG path, matching the redesign. */
export function PriceChart({ points }: { points: Point[] }) {
  const w = 700;
  const h = 300;
  const pad = 8;

  if (points.length < 2) {
    return <div style={{ height: 300, display: "flex", alignItems: "center", justifyContent: "center", color: C.t4, fontFamily: MONO, fontSize: 11 }}>no data</div>;
  }

  const closes = points.map((p) => p.close);
  const lo = Math.min(...closes) * 0.97;
  const hi = Math.max(...closes) * 1.03;
  const x = (i: number) => (i / (points.length - 1)) * w;
  const y = (v: number) => pad + (1 - (v - lo) / (hi - lo)) * (h - pad * 2);

  const line = closes.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
  const area = `${line} L${w} ${h} L0 ${h} Z`;

  const yTicks: string[] = [];
  for (let i = 0; i < 5; i++) yTicks.push(Math.round(hi - (i * (hi - lo)) / 4).toString());
  const gridY: number[] = [];
  for (let i = 1; i < 5; i++) gridY.push(Number(((h / 5) * i).toFixed(0)));

  // six evenly spaced date ticks (YYYY-MM)
  const xTicks: string[] = [];
  for (let i = 0; i < 6; i++) {
    const idx = Math.round((i / 5) * (points.length - 1));
    xTicks.push(points[idx].date.slice(0, 7));
  }

  return (
    <div style={{ display: "flex", gap: 10, padding: "8px 14px 12px" }}>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          width: 44,
          height: 300,
          fontFamily: MONO,
          fontSize: 10,
          color: C.t4,
          textAlign: "right",
        }}
      >
        {yTicks.map((t, i) => (
          <div key={i}>{t}</div>
        ))}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <svg
          viewBox="0 0 700 300"
          preserveAspectRatio="none"
          style={{ width: "100%", height: 300, display: "block", borderLeft: `1px solid ${C.border}`, borderBottom: `1px solid ${C.border}` }}
        >
          {gridY.map((g, i) => (
            <line key={i} x1={0} x2={700} y1={g} y2={g} stroke={C.border2} strokeWidth={1} />
          ))}
          <path d={area} fill={C.accent} fillOpacity={0.09} />
          <path d={line} fill="none" stroke={C.accent} strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
        </svg>
        <div style={{ display: "flex", justifyContent: "space-between", paddingTop: 6, fontFamily: MONO, fontSize: 10, color: C.t4 }}>
          {xTicks.map((t, i) => (
            <div key={i}>{t}</div>
          ))}
        </div>
      </div>
    </div>
  );
}

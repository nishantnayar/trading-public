import type { CSSProperties, ReactNode } from "react";

import { C, MONO } from "@/lib/palette";

export function Panel({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return <div style={{ border: `1px solid ${C.border}`, background: C.panel, ...style }}>{children}</div>;
}

export function PanelHeader({ label, right }: { label: string; right?: ReactNode }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        height: 36,
        padding: "0 14px",
        borderBottom: `1px solid ${C.border}`,
      }}
    >
      <span style={{ fontFamily: MONO, fontSize: 10, letterSpacing: "0.12em", color: C.t3 }}>{label}</span>
      {right}
    </div>
  );
}

export function Note({ children }: { children: ReactNode }) {
  return (
    <div style={{ padding: "9px 14px", borderTop: `1px solid ${C.border}`, fontFamily: MONO, fontSize: 10, color: C.t4 }}>
      {children}
    </div>
  );
}

export function MetaRows({ rows }: { rows: { label: string; value: string; tone?: string }[] }) {
  return (
    <div style={{ padding: "4px 0" }}>
      {rows.map((r) => (
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
          <span style={{ color: r.tone === "pos" ? C.pos : r.tone === "neg" ? C.neg : r.tone === "accent" ? C.accent : C.text }}>
            {r.value}
          </span>
        </div>
      ))}
    </div>
  );
}

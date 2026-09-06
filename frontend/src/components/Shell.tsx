"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { NAV, PROVENANCE, TAPE } from "@/lib/illustrative";
import { C, MONO } from "@/lib/palette";
import { nowClockCT } from "@/lib/format";

function Tape() {
  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        alignItems: "stretch",
        borderBottom: `1px solid ${C.border}`,
        background: C.panel2,
        fontFamily: MONO,
        fontSize: 11,
      }}
    >
      {TAPE.map((t) => (
        <div
          key={t.label}
          style={{
            display: "flex",
            alignItems: "baseline",
            gap: 8,
            height: 33,
            padding: "0 16px",
            borderRight: `1px solid ${C.border3}`,
            whiteSpace: "nowrap",
          }}
        >
          <span style={{ fontSize: 10, letterSpacing: "0.08em", color: C.t4 }}>{t.label}</span>
          <span
            style={{
              fontSize: 12,
              fontWeight: 500,
              color: t.tone === "pos" ? C.pos : t.tone === "neg" ? C.neg : C.text,
            }}
          >
            {t.value}
          </span>
        </div>
      ))}
    </div>
  );
}

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [clock, setClock] = useState("—:—:— CT");

  useEffect(() => {
    const tick = () => setClock(nowClockCT());
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: "100vh", background: C.bg, color: C.text }}>
      <header
        style={{
          display: "flex",
          alignItems: "stretch",
          height: 46,
          borderBottom: `1px solid ${C.border}`,
          background: C.panel,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "0 18px", borderRight: `1px solid ${C.border}` }}>
          <span style={{ display: "block", width: 14, height: 14, background: C.accent }} />
          <span style={{ fontFamily: MONO, fontSize: 13, fontWeight: 600, letterSpacing: "0.14em" }}>QUANTIS</span>
          <span style={{ fontFamily: MONO, fontSize: 10, letterSpacing: "0.12em", color: C.t4 }}>XS-EQ ML</span>
        </div>
        <nav style={{ display: "flex", alignItems: "stretch" }}>
          {NAV.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.key}
                href={item.href}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 7,
                  padding: "0 16px",
                  borderRight: `1px solid ${C.border}`,
                  fontSize: 13,
                  color: active ? "#ffffff" : C.t3,
                  background: active ? C.track : "transparent",
                  boxShadow: active ? `inset 0 -2px 0 ${C.accent}` : "none",
                }}
              >
                <span style={{ fontFamily: MONO, fontSize: 10, color: C.t4 }}>{item.hot}</span>
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 14,
            marginLeft: "auto",
            padding: "0 18px",
            fontFamily: MONO,
            fontSize: 11,
            color: C.t3,
          }}
        >
          <span style={{ display: "flex", alignItems: "center", gap: 7, border: `1px solid ${C.cap}`, padding: "4px 8px", color: C.t4 }}>
            ⌘K <span style={{ color: C.cap }}>|</span> jump
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: 6, color: C.accent }}>ALPACA · PAPER</span>
          <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 6, height: 6, borderRadius: 99, background: C.pos }} />
            {clock}
          </span>
        </div>
      </header>

      <Tape />

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "6px 18px",
          borderBottom: `1px solid ${C.border}`,
          background: C.warnBg,
          fontFamily: MONO,
          fontSize: 10,
          letterSpacing: "0.1em",
          color: C.accent,
        }}
      >
        <span style={{ width: 5, height: 5, borderRadius: 99, background: C.accent, flexShrink: 0 }} />
        <span style={{ textWrap: "pretty" }}>{PROVENANCE}</span>
      </div>

      <main style={{ flex: 1, minWidth: 0, padding: "16px 18px 28px" }}>{children}</main>
    </div>
  );
}

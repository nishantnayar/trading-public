"use client";

import { useMemo } from "react";

import { EquityCurve } from "@/components/MockCharts";
import { Kpi } from "@/components/Kpi";
import { Panel } from "@/components/Panel";
import { Chip, Topbar } from "@/components/Topbar";
import type { Coverage } from "@/lib/api";
import { contributors, exposure, sectorTilts } from "@/lib/demo";
import { fmtInt, nowClockCT } from "@/lib/format";
import { useApi } from "@/lib/useApi";

export default function OverviewPage() {
  const { data: cov, error } = useApi<Coverage>("/coverage");
  const clock = useMemo(() => nowClockCT(), []);
  const names = cov?.symbols ? fmtInt(cov.symbols) : "503";

  return (
    <>
      <Topbar title="Portfolio Overview" subtitle="Last rebalance 2026-09-01 · Next 2026-09-08 · Weekly">
        <Chip>S&P 500 universe · {names} names</Chip>
        <Chip live>LIVE {clock}</Chip>
      </Topbar>
      <div className="space-y-4 overflow-auto px-8 py-6">
        {error ? <p className="text-sm text-red">API offline — start the stack with scripts/start.ps1</p> : null}
        <div className="grid grid-cols-4 gap-4">
          <Kpi label="Net Liq. Value" value="$1,284,930" sub="+$4,210 today · +0.33%" subTone="green" />
          <Kpi label="Sharpe (1Y)" value="1.87" sub="Sortino 2.64" subTone="green" />
          <Kpi label="Max Drawdown" value="-8.4%" tone="red" sub="Recovered 41d" />
          <Kpi label="Rank IC (20d)" value="0.061" tone="teal" sub="t-stat 3.2" subTone="green" />
        </div>
        <div className="grid grid-cols-3 gap-4">
          <div className="col-span-2">
            <Panel
              title="Equity Curve"
              hint="net of costs"
              right={
                <div className="flex gap-4 text-xs text-muted">
                  <span className="flex items-center gap-1.5">
                    <span className="h-[3px] w-3.5 rounded-sm bg-teal" />
                    Strategy
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="h-[3px] w-3.5 rounded-sm bg-dim" />
                    SPY
                  </span>
                </div>
              }
            >
              <EquityCurve />
            </Panel>
          </div>
          <Panel title="Exposure">
            <div className="mt-1">
              <div className="mb-1.5 flex justify-between text-[13px]">
                <span className="text-muted">Gross</span>
                <span className="font-mono">148%</span>
              </div>
              <div className="h-2 overflow-hidden rounded bg-bg">
                <div className="h-full w-[74%] bg-teal" />
              </div>
            </div>
            <div className="mt-4">
              <div className="mb-1.5 flex justify-between text-[13px]">
                <span className="text-muted">Net</span>
                <span className="font-mono">+12%</span>
              </div>
              <div className="h-2 overflow-hidden rounded bg-bg">
                <div className="h-full w-[56%] bg-violet" />
              </div>
            </div>
            <div className="my-5 h-px bg-line" />
            <div className="space-y-3 text-[13px]">
              {exposure.map((row) => (
                <div key={row.label} className="flex justify-between">
                  <span className="text-muted">{row.label}</span>
                  <span className={`font-mono ${row.tone}`}>{row.value}</span>
                </div>
              ))}
            </div>
          </Panel>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Panel title="Net Sector Tilt">
            <div className="flex flex-col gap-[11px]">
              {sectorTilts.map((row) => (
                <div key={row.name} className="flex items-center gap-3">
                  <span className="w-[78px] text-xs text-muted">{row.name}</span>
                  <div className="flex flex-1 justify-center">
                    <div className={`flex w-1/2 ${row.pos ? "justify-start" : "justify-end"}`}>
                      <div
                        className={`h-3.5 rounded-sm ${row.pos ? "bg-green" : "bg-red"}`}
                        style={{ width: row.width }}
                      />
                    </div>
                  </div>
                  <span className={`w-[42px] text-right font-mono text-xs ${row.pos ? "text-green" : "text-red"}`}>
                    {row.value}
                  </span>
                </div>
              ))}
            </div>
          </Panel>
          <Panel title="Top Contributors · Today">
            <div className="flex flex-col">
              {contributors.map((row, i) => (
                <div
                  key={row.ticker}
                  className={`flex items-center justify-between py-2 ${i < contributors.length - 1 ? "border-b border-row" : ""}`}
                >
                  <div className="flex items-center gap-2.5">
                    <span
                      className={`rounded px-1.5 py-0.5 font-mono text-[10px] ${
                        row.side === "LONG" ? "bg-long-bg text-green" : "bg-short-bg text-red"
                      }`}
                    >
                      {row.side}
                    </span>
                    <span className="font-mono text-[13px]">{row.ticker}</span>
                  </div>
                  <span className={`font-mono text-[13px] ${row.up ? "text-green" : "text-red"}`}>{row.pnl}</span>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </>
  );
}

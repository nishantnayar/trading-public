import { ScoreHistogram } from "@/components/MockCharts";
import { Chip, Topbar } from "@/components/Topbar";
import { longs, shorts } from "@/lib/demo";

function Book({
  title,
  rows,
  tone,
}: {
  title: string;
  rows: typeof longs;
  tone: "green" | "red";
}) {
  const color = tone === "green" ? "text-green" : "text-red";
  const dot = tone === "green" ? "bg-green" : "bg-red";
  return (
    <div className="overflow-hidden rounded-xl border border-line bg-panel">
      <div className="flex items-center gap-2 px-[18px] pt-4 pb-1.5">
        <span className={`h-2 w-2 rounded-full ${dot}`} />
        <span className="text-sm font-semibold">{title}</span>
        <span className="ml-auto font-mono text-[11px] text-dim">Q{tone === "green" ? "5" : "1"} · 50 names</span>
      </div>
      <table className="w-full text-[13px]">
        <thead className="text-left text-[11px] uppercase tracking-[0.6px] text-dim">
          <tr>
            <th className="px-3.5 pb-2.5">#</th>
            <th className="px-3.5 pb-2.5">Ticker</th>
            <th className="px-3.5 pb-2.5 text-right">Score</th>
            <th className="px-3.5 pb-2.5 text-right">Pctl</th>
            <th className="px-3.5 pb-2.5 text-right">Wt</th>
          </tr>
        </thead>
        <tbody className="font-mono">
          {rows.map((row) => (
            <tr key={row.ticker} className="border-t border-row">
              <td className="px-3.5 py-[11px] text-dim">{row.rank}</td>
              <td className="px-3.5 py-[11px]">{row.ticker}</td>
              <td className={`px-3.5 py-[11px] text-right ${color}`}>{row.score}</td>
              <td className="px-3.5 py-[11px] text-right text-muted">{row.pctl}</td>
              <td className="px-3.5 py-[11px] text-right">{row.wt}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function SignalsPage() {
  return (
    <>
      <Topbar title="Model Signals" subtitle="Scored 2026-09-08 06:00 ET · LightGBM v14 · 503 names ranked">
        <Chip>Horizon: 5d fwd</Chip>
        <Chip live>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 5v14M5 12h14" />
          </svg>
          Export CSV
        </Chip>
      </Topbar>
      <div className="space-y-4 overflow-auto px-8 py-6">
        <div className="rounded-xl border border-line bg-panel px-5 py-[18px]">
          <div className="mb-3 flex items-center justify-between">
            <div className="text-sm font-semibold">Predicted excess-return distribution</div>
            <div className="font-mono text-xs text-dim">quintile cutoffs shown</div>
          </div>
          <ScoreHistogram />
          <div className="mt-1.5 flex justify-between">
            <span className="font-mono text-[11px] text-red">◄ SHORT (Q1)</span>
            <span className="font-mono text-[11px] text-dim">neutral</span>
            <span className="font-mono text-[11px] text-green">LONG (Q5) ►</span>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Book title="Top Longs" rows={longs} tone="green" />
          <Book title="Top Shorts" rows={shorts} tone="red" />
        </div>
        <p className="text-center font-mono text-[11px] text-dim">
          Signals are model output, not orders. Rebalance runs 2026-09-08 09:35 ET after risk &amp; constraint checks.
        </p>
      </div>
    </>
  );
}

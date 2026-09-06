import { Kpi } from "@/components/Kpi";
import { Panel } from "@/components/Panel";
import { Chip, Topbar } from "@/components/Topbar";
import { holdings } from "@/lib/demo";

export default function PositionsPage() {
  return (
    <>
      <Topbar title="Positions & Risk" subtitle="100 open · reconciled with Alpaca 15:43 ET">
        <Chip ok>All constraints satisfied</Chip>
      </Topbar>
      <div className="space-y-4 overflow-auto px-8 py-6">
        <div className="grid grid-cols-4 gap-3.5">
          <Kpi compact label="Portfolio vol" value="9.6%" suffix="/ 10% tgt" />
          <Kpi compact label="Beta to SPY" value="0.11" />
          <Kpi compact label="Max name wt" value="2.4%" suffix="/ 3% cap" />
          <Kpi compact label="Max sector" value="18%" suffix="/ 25% cap" />
        </div>
        <div className="grid grid-cols-[1.7fr_1fr] gap-4">
          <div className="overflow-hidden rounded-xl border border-line bg-panel">
            <div className="flex items-center justify-between px-[18px] pt-4 pb-1.5 text-[15px] font-semibold">
              Open Holdings
              <span className="font-mono text-[11px] font-normal text-dim">showing 8 of 100</span>
            </div>
            <table className="w-full text-[12.5px]">
              <thead className="text-left text-[11px] uppercase tracking-[0.6px] text-dim">
                <tr>
                  {["Side", "Ticker", "Qty", "Mkt val", "Wt", "uPnL"].map((h) => (
                    <th key={h} className={`px-3.5 pb-2.5 ${h === "Side" || h === "Ticker" ? "" : "text-right"}`}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="font-mono">
                {holdings.map((row) => (
                  <tr key={row.ticker} className="border-t border-row">
                    <td className="px-3.5 py-2.5">
                      <span
                        className={
                          row.side === "L"
                            ? "rounded bg-long-bg px-1.5 py-0.5 text-[10px] text-green"
                            : "rounded bg-short-bg px-1.5 py-0.5 text-[10px] text-red"
                        }
                      >
                        {row.side}
                      </span>
                    </td>
                    <td className="px-3.5 py-2.5">{row.ticker}</td>
                    <td className="px-3.5 py-2.5 text-right">{row.qty}</td>
                    <td className="px-3.5 py-2.5 text-right">{row.mkt}</td>
                    <td className="px-3.5 py-2.5 text-right">{row.wt}</td>
                    <td className={`px-3.5 py-2.5 text-right ${row.up ? "text-green" : "text-red"}`}>{row.upnl}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Panel title="Next Rebalance" hint="Mon 09:35">
            <div className="mt-1 grid grid-cols-3 gap-2.5">
              <div className="rounded-lg border border-line bg-bg py-3 text-center">
                <div className="font-mono text-xl font-semibold text-green">12</div>
                <div className="mt-[3px] text-[11px] text-muted">buys</div>
              </div>
              <div className="rounded-lg border border-line bg-bg py-3 text-center">
                <div className="font-mono text-xl font-semibold text-red">11</div>
                <div className="mt-[3px] text-[11px] text-muted">sells</div>
              </div>
              <div className="rounded-lg border border-line bg-bg py-3 text-center">
                <div className="font-mono text-xl font-semibold">23%</div>
                <div className="mt-[3px] text-[11px] text-muted">turnover</div>
              </div>
            </div>
            <div className="my-[18px] h-px bg-line" />
            <div className="mb-3 text-[13px] text-muted">Est. transaction cost</div>
            <div className="font-mono text-[22px] font-semibold">
              $310 <span className="text-xs text-dim">· 2.4 bps</span>
            </div>
            <div className="mt-4 space-y-[9px] font-mono text-xs">
              <div className="flex justify-between">
                <span className="text-muted">commission</span>
                <span>$0 (Alpaca)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">est. slippage</span>
                <span>1.9 bps</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">spread cost</span>
                <span>0.5 bps</span>
              </div>
            </div>
            <p className="mt-[18px] flex items-center gap-2.5 rounded-lg border border-[#1b3b38] bg-nav px-3.5 py-[11px] text-xs text-teal">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2dd4bf" strokeWidth="2">
                <path d="M12 2v6M12 22v-6" />
                <circle cx="12" cy="12" r="3" />
              </svg>
              Orders staged — paper, not yet sent
            </p>
          </Panel>
        </div>
      </div>
    </>
  );
}

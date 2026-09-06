import { IcDecay } from "@/components/MockCharts";
import { Chip, Topbar } from "@/components/Topbar";
import { drift, flowRuns, pipeline } from "@/lib/demo";

export default function MonitoringPage() {
  return (
    <>
      <Topbar title="Pipeline & Model Monitoring" subtitle="Prefect deployments · data quality · drift & decay">
        <Chip live>Uptime 99.4%</Chip>
      </Topbar>
      <div className="space-y-4 overflow-auto px-8 py-6">
        <div className="grid grid-cols-4 gap-3.5">
          {pipeline.map((item) => (
            <div key={item.label} className="flex items-center gap-3 rounded-[10px] border border-line bg-panel p-[15px]">
              <span className={`h-2.5 w-2.5 rounded-full ${item.ok ? "bg-green" : "bg-amber"}`} />
              <div>
                <div className="text-[13px] font-medium">{item.label}</div>
                <div className="font-mono text-[11px] text-muted">{item.sub}</div>
              </div>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="rounded-xl border border-line bg-panel p-5">
            <div className="flex items-center justify-between">
              <div className="text-[15px] font-semibold">Live IC vs Backtest</div>
              <span className="font-mono text-[11px] text-amber">▼ mild decay</span>
            </div>
            <IcDecay />
            <div className="mt-1.5 flex gap-[18px]">
              <span className="flex items-center gap-1.5 text-[11px] text-muted">
                <span className="h-[3px] w-3.5 rounded-sm bg-dim" />
                Backtest OOF
              </span>
              <span className="flex items-center gap-1.5 text-[11px] text-muted">
                <span className="h-[3px] w-3.5 rounded-sm bg-teal" />
                Live realized
              </span>
            </div>
          </div>
          <div className="rounded-xl border border-line bg-panel p-5">
            <div className="text-[15px] font-semibold">
              Feature Drift <span className="text-[13px] font-normal text-dim">PSI vs train</span>
            </div>
            <div className="mt-5 flex flex-col gap-[13px]">
              {drift.map((row) => (
                <div key={row.name} className="flex items-center gap-3">
                  <span className="w-[120px] font-mono text-xs">{row.name}</span>
                  <div className="h-2.5 flex-1 overflow-hidden rounded-[5px] bg-bg">
                    <div className={`h-full ${row.bar}`} style={{ width: row.width }} />
                  </div>
                  <span className={`w-10 text-right font-mono text-xs ${row.tone}`}>{row.psi}</span>
                </div>
              ))}
            </div>
            <p className="mt-4 border-t border-line pt-3 font-mono text-[11px] text-dim">
              PSI &gt; 0.25 flags retrain review · news_sentiment breached
            </p>
          </div>
        </div>
        <div className="overflow-hidden rounded-xl border border-line bg-panel">
          <div className="px-[18px] pt-4 pb-1.5 text-[15px] font-semibold">Recent Flow Runs</div>
          <table className="w-full text-[12.5px]">
            <thead className="text-left text-[11px] uppercase tracking-[0.6px] text-dim">
              <tr>
                {["Flow", "Trigger", "Started", "Duration", "Rows", "Status"].map((h) => (
                  <th key={h} className={`px-3.5 pb-2.5 ${h === "Status" ? "text-right" : ""}`}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="font-mono">
              {flowRuns.map((run) => (
                <tr key={run.flow} className="border-t border-row">
                  <td className="px-3.5 py-2.5">{run.flow}</td>
                  <td className="px-3.5 py-2.5 text-muted">{run.trigger}</td>
                  <td className="px-3.5 py-2.5 text-muted">{run.started}</td>
                  <td className="px-3.5 py-2.5">{run.duration}</td>
                  <td className="px-3.5 py-2.5">{run.rows}</td>
                  <td className="px-3.5 py-2.5 text-right">
                    <span className={run.status === "success" ? "text-green" : "text-amber"}>
                      ● {run.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

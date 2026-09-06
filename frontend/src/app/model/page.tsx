import { CvFolds, RankIcBars } from "@/components/MockCharts";
import { Kpi } from "@/components/Kpi";
import { Panel } from "@/components/Panel";
import { Chip, Topbar } from "@/components/Topbar";
import { shap, trainConfig } from "@/lib/demo";

export default function ModelPage() {
  return (
    <>
      <Topbar title="Model Diagnostics" subtitle="LightGBM · v14 · trained 2026-09-06 · purged 6-fold CV, 5d embargo">
        <Chip live>Compare vs v13</Chip>
      </Topbar>
      <div className="space-y-4 overflow-auto px-8 py-6">
        <div className="grid grid-cols-5 gap-3.5">
          <Kpi compact label="CV Rank IC" value="0.058" tone="teal" />
          <Kpi compact label="ICIR" value="0.94" />
          <Kpi compact label="Hit rate" value="54.2%" />
          <Kpi compact label="Q5–Q1 spread" value="11.3%" tone="green" />
          <Kpi compact label="Features" value="42" />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Panel title="Feature Importance" hint="mean |SHAP|">
            <div className="mt-1 space-y-3">
              {shap.map((row) => (
                <div key={row.name} className="flex items-center gap-3 text-xs">
                  <span className="w-[130px] font-mono text-[#c9d3dc]">{row.name}</span>
                  <div className="h-4 flex-1 overflow-hidden rounded bg-bg">
                    <div className={`h-full ${row.bar}`} style={{ width: row.width }} />
                  </div>
                  <span className="w-11 text-right font-mono text-muted">{row.value.toFixed(3)}</span>
                </div>
              ))}
            </div>
          </Panel>
          <Panel title="Out-of-fold Rank IC" hint="by month">
            <RankIcBars />
            <div className="mt-2 flex justify-around border-t border-line pt-3.5">
              <div className="text-center">
                <div className="font-mono text-base font-semibold text-green">10 / 13</div>
                <div className="text-[11px] text-muted">positive months</div>
              </div>
              <div className="text-center">
                <div className="font-mono text-base font-semibold">0.94</div>
                <div className="text-[11px] text-muted">ICIR (ann.)</div>
              </div>
              <div className="text-center">
                <div className="font-mono text-base font-semibold">−0.5%</div>
                <div className="text-[11px] text-muted">worst month</div>
              </div>
            </div>
          </Panel>
        </div>
        <div className="grid grid-cols-[1.4fr_1fr] gap-4">
          <Panel title="Purged Walk-Forward CV" hint="6 folds · 5d embargo">
            <CvFolds />
            <p className="mt-2 font-mono text-[11px] text-dim">
              Overlapping 5d labels purged around each split to prevent leakage (López de Prado).
            </p>
          </Panel>
          <Panel title="Training Config">
            <div className="space-y-2.5 font-mono text-xs">
              {trainConfig.map(([key, value]) => (
                <div key={key} className="flex justify-between">
                  <span className="text-muted">{key}</span>
                  <span className={value.includes("MLflow") ? "text-teal" : ""}>{value}</span>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </>
  );
}

import { Panel, PanelHeader } from "@/components/ui";
import { MODEL_KPIS, SHAP, TRAIN_CONFIG } from "@/lib/illustrative";
import { C, MONO, SANS } from "@/lib/palette";

export default function ModelPage() {
  const maxShap = Math.max(...SHAP.map((s) => s.value));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {/* KPI strip */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5,minmax(0,1fr))", border: `1px solid ${C.border}`, background: C.panel }}>
        {MODEL_KPIS.map((k, i) => (
          <div key={k.label} style={{ padding: 14, borderRight: i < 4 ? `1px solid ${C.border}` : undefined }}>
            <div style={{ fontFamily: MONO, fontSize: 10, letterSpacing: "0.1em", color: C.t3 }}>{k.label}</div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 8, fontFamily: MONO }}>
              <span style={{ fontSize: 24, fontWeight: 600, lineHeight: 1 }}>{k.value}</span>
              <span style={{ fontSize: 11, color: k.delta ? (k.up ? C.pos : C.neg) : C.t4 }}>{k.delta}</span>
            </div>
            <div style={{ marginTop: 6, fontFamily: MONO, fontSize: 10, color: C.t4 }}>{k.sub}</div>
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1.5fr) minmax(280px,1fr)", gap: 14, alignItems: "start" }}>
        {/* SHAP */}
        <Panel>
          <PanelHeader
            label="FEATURE IMPORTANCE"
            right={<span style={{ fontFamily: MONO, fontSize: 11, color: C.t4 }}>mean |SHAP| · top 8 of 42</span>}
          />
          <table style={{ fontFamily: MONO, fontSize: 11 }}>
            <tbody>
              {SHAP.map((row, i) => (
                <tr key={row.name} style={{ borderTop: `1px solid ${C.border2}` }}>
                  <td style={{ padding: "0 8px 0 14px", height: 30, color: C.t4, textAlign: "right", width: 24 }}>{i + 1}</td>
                  <td style={{ padding: "0 10px", color: C.text, whiteSpace: "nowrap" }}>{row.name}</td>
                  <td style={{ padding: "0 10px", fontSize: 10, color: C.t4, whiteSpace: "nowrap" }}>{row.family}</td>
                  <td style={{ padding: "0 10px" }}>
                    <div style={{ height: 8, background: C.track }}>
                      <div style={{ height: "100%", background: C.accent, opacity: 0.85, width: `${((row.value / maxShap) * 100).toFixed(0)}%` }} />
                    </div>
                  </td>
                  <td style={{ padding: "0 14px 0 10px", textAlign: "right", color: C.t2, width: 56 }}>{row.value.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>

        {/* training config */}
        <Panel>
          <PanelHeader label="TRAINING CONFIG" />
          <table style={{ fontFamily: MONO, fontSize: 11 }}>
            <tbody>
              {TRAIN_CONFIG.map(([key, value]) => (
                <tr key={key} style={{ borderTop: `1px solid ${C.border2}` }}>
                  <td style={{ padding: "0 10px 0 14px", height: 28, color: C.t3 }}>{key}</td>
                  <td style={{ padding: "0 14px 0 10px", textAlign: "right", color: value.includes("MLflow") ? C.accent : C.text }}>{value}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ padding: "10px 14px", borderTop: `1px solid ${C.border}`, fontFamily: SANS, fontSize: 11, lineHeight: 1.5, color: C.t4 }}>
            Purged 6-fold CV with a 5-day embargo (López de Prado) so overlapping forward-return labels cannot leak across folds.
            Placeholder until <span style={{ fontFamily: MONO, color: C.t3 }}>train.py</span> exists.
          </div>
        </Panel>
      </div>
    </div>
  );
}

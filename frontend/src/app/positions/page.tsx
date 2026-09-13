"use client";

import { Note, Panel, PanelHeader } from "@/components/ui";
import type { PortfolioSnapshot, SignalRow } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { C, MONO } from "@/lib/palette";

const TH: React.CSSProperties = { padding: "7px 10px", fontWeight: 400, color: C.t4 };

function fmtPct(value: number, digits = 1): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(digits)}%`;
}

/**
 * The holdings table is a simple illustrative equal-weight display (every
 * currently-long watchlist name at 1/N) - it does not apply the 15% sector
 * cap / water-filling reallocation that the actual backtested construction
 * (quantis.signals.portfolio, shown below) uses. Replicating that per-symbol
 * weight math client-side wasn't worth it for a read-only display; the
 * backtest panel is where the real construction's numbers live.
 */
export default function PositionsPage() {
  const signals = useApi<SignalRow[]>("/signals");
  const portfolio = useApi<PortfolioSnapshot | null>("/portfolio");
  const rows = signals.data ?? [];
  const empty = !signals.loading && rows.length === 0;
  const longs = rows.filter((r) => r.signal === "long");
  const weight = longs.length > 0 ? 1 / longs.length : 0;
  const p = portfolio.data;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,2.6fr) minmax(240px,1fr)", gap: 14, alignItems: "start" }}>
        <Panel>
          <PanelHeader
            label="ILLUSTRATIVE BOOK"
            right={
              <span style={{ marginLeft: "auto", fontFamily: MONO, fontSize: 10, color: C.t4 }}>
                {rows[0]?.date ? `as of ${rows[0].date}` : "NO SIGNALS PUBLISHED"}
              </span>
            }
          />
          {empty ? (
            <div style={{ padding: 24, fontFamily: MONO, fontSize: 12, color: C.t3 }}>
              Run: uv run python -m quantis.signals --persist
            </div>
          ) : longs.length === 0 ? (
            <div style={{ padding: 24, fontFamily: MONO, fontSize: 12, color: C.t3 }}>
              No watchlist symbol is currently signaled long.
            </div>
          ) : (
            <table style={{ fontFamily: MONO, fontSize: 12, width: "100%" }}>
              <thead>
                <tr style={{ fontSize: 10, letterSpacing: "0.1em", borderBottom: `1px solid ${C.border}` }}>
                  <th style={{ ...TH, padding: "7px 10px 7px 14px", textAlign: "left" }}>TICKER</th>
                  <th style={{ ...TH, textAlign: "right" }}>CLOSE</th>
                  <th style={{ ...TH, padding: "7px 14px 7px 10px", textAlign: "right" }}>WEIGHT</th>
                </tr>
              </thead>
              <tbody>
                {longs.map((r) => (
                  <tr key={r.symbol} style={{ borderTop: `1px solid ${C.border2}`, height: 30 }}>
                    <td style={{ padding: "0 10px 0 14px", color: C.text }}>{r.symbol}</td>
                    <td style={{ padding: "0 10px", textAlign: "right", color: C.t2 }}>{r.close.toFixed(2)}</td>
                    <td style={{ padding: "0 14px 0 10px", textAlign: "right", color: C.pos }}>
                      {(weight * 100).toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <Note>EQUAL-WEIGHTED DISPLAY · not sector-capped · not a broker position</Note>
        </Panel>

        <Panel>
          <PanelHeader label="BOOK SUMMARY" />
          <div style={{ padding: "4px 0" }}>
            {[
              { label: "watchlist", value: String(rows.length) },
              { label: "long (in book)", value: String(longs.length), tone: "pos" as const },
              { label: "flat (excluded)", value: String(rows.length - longs.length) },
            ].map((r) => (
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
                <span style={{ color: r.tone === "pos" ? C.pos : C.text }}>{r.value}</span>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <Panel>
        <PanelHeader
          label="BACKTESTED PERFORMANCE"
          right={
            <span style={{ marginLeft: "auto", fontFamily: MONO, fontSize: 10, color: C.t4 }}>
              {p ? `${p.period_start} → ${p.period_end}` : "NO SNAPSHOT PUBLISHED"}
            </span>
          }
        />
        {!p ? (
          <div style={{ padding: 24, fontFamily: MONO, fontSize: 12, color: C.t3 }}>
            Run: uv run python -c &quot;from quantis.signals.portfolio import
            persist_portfolio_summary; persist_portfolio_summary()&quot;
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(6,minmax(0,1fr))" }}>
            {[
              { label: "TOTAL RETURN", value: fmtPct(p.total_return), tone: p.total_return >= 0 ? "pos" : "neg" },
              { label: "CAGR", value: fmtPct(p.cagr), tone: p.cagr >= 0 ? "pos" : "neg" },
              { label: "SHARPE", value: p.sharpe.toFixed(2) },
              { label: "MAX DRAWDOWN", value: fmtPct(p.max_drawdown), tone: "neg" },
              { label: "AVG EXPOSURE", value: `${(p.avg_exposure * 100).toFixed(0)}%` },
              { label: "ANN. TURNOVER", value: `${p.annualized_turnover.toFixed(1)}x` },
            ].map((k, i) => (
              <div key={k.label} style={{ padding: 14, borderRight: i < 5 ? `1px solid ${C.border}` : undefined, borderTop: `1px solid ${C.border}` }}>
                <div style={{ fontFamily: MONO, fontSize: 10, letterSpacing: "0.1em", color: C.t3 }}>{k.label}</div>
                <div
                  style={{
                    marginTop: 8,
                    fontFamily: MONO,
                    fontSize: 22,
                    fontWeight: 600,
                    lineHeight: 1,
                    color: k.tone === "pos" ? C.pos : k.tone === "neg" ? C.neg : C.text,
                  }}
                >
                  {k.value}
                </div>
              </div>
            ))}
          </div>
        )}
        <Note>
          {p
            ? `EQUAL-WEIGHT · ${p.max_sector_weight != null ? `${(p.max_sector_weight * 100).toFixed(0)}% sector cap` : "no sector cap"}${p.reallocated ? ", reallocated" : ""}${p.max_name_weight != null ? ` · ${(p.max_name_weight * 100).toFixed(0)}% name cap` : ""}${p.vol_target != null ? ` · ${(p.vol_target * 100).toFixed(0)}% vol target (avg leverage ${p.avg_leverage.toFixed(2)}x)` : ""} · ${p.trading_days} trading days · 10 bps/side cost model`
            : "Full-period backtest of the default portfolio construction (quantis.signals.portfolio) — recomputed daily by the daily-portfolio Prefect flow."}
        </Note>
      </Panel>
    </div>
  );
}

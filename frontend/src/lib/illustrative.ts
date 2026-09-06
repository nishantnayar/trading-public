/** Illustrative figures ported verbatim from the approved redesign — NOT live output.
 *  Each screen that uses these renders an "ILLUSTRATIVE" note, matching the mockup.
 */

export type Tone = "pos" | "neg" | "accent";

export const TAPE: { label: string; value: string; tone?: Tone }[] = [
  { label: "NAV", value: "$1.284M" },
  { label: "DAY", value: "+0.42%", tone: "pos" },
  { label: "MTD", value: "+1.86%", tone: "pos" },
  { label: "YTD", value: "+9.14%", tone: "pos" },
  { label: "GROSS", value: "198%" },
  { label: "NET", value: "+2%" },
  { label: "VOL", value: "9.6%" },
  { label: "β SPY", value: "0.11" },
  { label: "TURN", value: "23%" },
];

export const LADDER = [
  { rank: 1, ticker: "NVDA", sector: "Info Tech", score: 2.41, pctl: "99.8", wt: "2.4%", side: "L" },
  { rank: 2, ticker: "LLY", sector: "Health Care", score: 2.18, pctl: "99.4", wt: "2.2%", side: "L" },
  { rank: 3, ticker: "AVGO", sector: "Info Tech", score: 2.02, pctl: "99.0", wt: "2.1%", side: "L" },
  { rank: 4, ticker: "COST", sector: "Cons Staples", score: 1.87, pctl: "98.6", wt: "1.9%", side: "L" },
  { rank: 5, ticker: "JPM", sector: "Financials", score: 1.71, pctl: "98.2", wt: "1.8%", side: "L" },
  { rank: 6, ticker: "WMT", sector: "Cons Staples", score: 1.6, pctl: "97.8", wt: "1.7%", side: "L" },
  { rank: 7, ticker: "ORCL", sector: "Info Tech", score: 1.52, pctl: "97.4", wt: "1.6%", side: "L" },
  { gap: true, label: "44 more long · Q5" },
  { rank: 496, ticker: "KO", sector: "Cons Staples", score: -1.44, pctl: "2.9", wt: "1.5%", side: "S" },
  { rank: 497, ticker: "VZ", sector: "Comm Svcs", score: -1.55, pctl: "2.4", wt: "1.6%", side: "S" },
  { rank: 498, ticker: "PFE", sector: "Health Care", score: -1.65, pctl: "2.0", wt: "1.7%", side: "S" },
  { rank: 499, ticker: "CVX", sector: "Energy", score: -1.78, pctl: "1.6", wt: "1.8%", side: "S" },
  { rank: 500, ticker: "T", sector: "Comm Svcs", score: -1.94, pctl: "1.1", wt: "2.0%", side: "S" },
  { rank: 501, ticker: "INTC", sector: "Info Tech", score: -2.1, pctl: "0.7", wt: "2.1%", side: "S" },
  { rank: 502, ticker: "XOM", sector: "Energy", score: -2.33, pctl: "0.4", wt: "2.3%", side: "S" },
] as const;

export const QUINTILES = [
  { label: "Q5", v: 6.1 },
  { label: "Q4", v: 2.4 },
  { label: "Q3", v: 0.3 },
  { label: "Q2", v: -2.0 },
  { label: "Q1", v: -5.2 },
] as const;

export const SIGNAL_META: { label: string; value: string; tone?: Tone }[] = [
  { label: "horizon", value: "5d forward" },
  { label: "scored names", value: "502" },
  { label: "long book", value: "50 · Q5", tone: "pos" },
  { label: "short book", value: "50 · Q1", tone: "neg" },
  { label: "as of", value: "2026-09-04 16:00 ET" },
];

export const CONSTRAINTS = [
  { label: "PORTFOLIO VOL", value: "9.6%", limit: "/ 10.0% target", used: 96 },
  { label: "BETA TO SPY", value: "0.11", limit: "/ ±0.15 band", used: 73 },
  { label: "MAX NAME WT", value: "2.4%", limit: "/ 3.0% cap", used: 80 },
  { label: "MAX SECTOR WT", value: "18%", limit: "/ 25% cap", used: 72 },
] as const;

export const HOLDINGS = [
  { side: "L", ticker: "NVDA", qty: "168", mkt: "$30,840", wt: "2.4%", upnl: "+$2,110", pnl: 2110 },
  { side: "L", ticker: "LLY", qty: "31", mkt: "$28,270", wt: "2.2%", upnl: "+$1,340", pnl: 1340 },
  { side: "L", ticker: "AVGO", qty: "92", mkt: "$26,980", wt: "2.1%", upnl: "-$410", pnl: -410 },
  { side: "L", ticker: "COST", qty: "27", mkt: "$24,410", wt: "1.9%", upnl: "+$680", pnl: 680 },
  { side: "S", ticker: "XOM", qty: "-268", mkt: "$29,540", wt: "2.3%", upnl: "+$1,020", pnl: 1020 },
  { side: "S", ticker: "INTC", qty: "-940", mkt: "$26,960", wt: "2.1%", upnl: "+$780", pnl: 780 },
  { side: "S", ticker: "T", qty: "-1,120", mkt: "$25,700", wt: "2.0%", upnl: "-$260", pnl: -260 },
  { side: "S", ticker: "CVX", qty: "-158", mkt: "$23,140", wt: "1.8%", upnl: "+$540", pnl: 540 },
] as const;

export const REBALANCE: { label: string; value: string; tone?: Tone }[] = [
  { label: "BUYS", value: "12", tone: "pos" },
  { label: "SELLS", value: "11", tone: "neg" },
  { label: "TURNOVER", value: "23%" },
];

export const COST_META: { label: string; value: string; tone?: Tone }[] = [
  { label: "est. commission", value: "$118" },
  { label: "est. slippage", value: "$192" },
  { label: "total cost", value: "$310 · 2.4 bps" },
];

export const MODEL_KPIS = [
  { label: "CV RANK IC", value: "0.058", delta: "+0.004", sub: "vs v13", up: true },
  { label: "ICIR", value: "0.94", delta: "+0.06", sub: "vs v13", up: true },
  { label: "HIT RATE", value: "54.2%", delta: "-0.3", sub: "vs v13", up: false },
  { label: "Q5–Q1 SPREAD", value: "11.3%", delta: "+0.8", sub: "net of cost", up: true },
  { label: "FEATURES", value: "42", delta: "", sub: "5 families" },
] as const;

export const SHAP = [
  { name: "mom_12_1", family: "momentum", value: 0.184 },
  { name: "earnings_yield", family: "value", value: 0.148 },
  { name: "vol_60d", family: "volatility", value: 0.122 },
  { name: "roe_ttm", family: "quality", value: 0.106 },
  { name: "rsi_14", family: "technical", value: 0.088 },
  { name: "accruals", family: "quality", value: 0.074 },
  { name: "size_ln_mcap", family: "size", value: 0.058 },
  { name: "news_sentiment", family: "alt", value: 0.048 },
] as const;

export const TRAIN_CONFIG: [string, string][] = [
  ["objective", "lambdarank"],
  ["label", "xs z-score fwd 5d"],
  ["n_estimators", "1200"],
  ["learning_rate", "0.021"],
  ["num_leaves", "63"],
  ["train window", "2015–2024"],
  ["cv", "purged 6-fold · 5d embargo"],
  ["retrain", "weekly · Prefect"],
  ["registry", "MLflow · Prod"],
];

export const FLOWS = [
  { label: "daily_ingest", state: "HEALTHY", ok: true, schedule: "17:10 CT · weekdays", last: "2026-09-04 17:12", rows: "3,918", phase: "live" },
  { label: "feature_build", state: "NOT SCHEDULED", ok: false, schedule: "—", last: "—", rows: "—", phase: "Phase 3" },
  { label: "weekly_retrain", state: "NOT SCHEDULED", ok: false, schedule: "—", last: "—", rows: "—", phase: "Phase 4" },
  { label: "rebalance", state: "NOT SCHEDULED", ok: false, schedule: "—", last: "—", rows: "—", phase: "Phase 8" },
] as const;

export const NAV = [
  { key: "overview", hot: "F1", label: "Overview", href: "/" },
  { key: "signals", hot: "F2", label: "Signals", href: "/signals" },
  { key: "positions", hot: "F3", label: "Positions", href: "/positions" },
  { key: "model", hot: "F4", label: "Model", href: "/model" },
  { key: "monitoring", hot: "F5", label: "Monitoring", href: "/monitoring" },
] as const;

export const PROVENANCE = "ILLUSTRATIVE FIGURES · PAPER ONLY · PHASE 2 OF 11";

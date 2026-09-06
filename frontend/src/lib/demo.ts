/** Illustrative figures matching the approved mockups — not live strategy output. */

export const longs = [
  { rank: 1, ticker: "NVDA", score: "+2.41", pctl: "99.8", wt: "2.4%" },
  { rank: 2, ticker: "LLY", score: "+2.18", pctl: "99.4", wt: "2.2%" },
  { rank: 3, ticker: "AVGO", score: "+2.02", pctl: "99.0", wt: "2.1%" },
  { rank: 4, ticker: "COST", score: "+1.87", pctl: "98.6", wt: "1.9%" },
  { rank: 5, ticker: "JPM", score: "+1.71", pctl: "98.2", wt: "1.8%" },
  { rank: 6, ticker: "WMT", score: "+1.60", pctl: "97.8", wt: "1.7%" },
  { rank: 7, ticker: "ORCL", score: "+1.52", pctl: "97.4", wt: "1.6%" },
];

export const shorts = [
  { rank: 1, ticker: "XOM", score: "-2.33", pctl: "0.4", wt: "2.3%" },
  { rank: 2, ticker: "INTC", score: "-2.10", pctl: "0.7", wt: "2.1%" },
  { rank: 3, ticker: "T", score: "-1.94", pctl: "1.1", wt: "2.0%" },
  { rank: 4, ticker: "CVX", score: "-1.78", pctl: "1.6", wt: "1.8%" },
  { rank: 5, ticker: "PFE", score: "-1.65", pctl: "2.0", wt: "1.7%" },
  { rank: 6, ticker: "VZ", score: "-1.55", pctl: "2.4", wt: "1.6%" },
  { rank: 7, ticker: "KO", score: "-1.44", pctl: "2.9", wt: "1.5%" },
];

export const holdings = [
  { side: "L", ticker: "NVDA", qty: "168", mkt: "$30,840", wt: "2.4%", upnl: "+$2,110", up: true },
  { side: "L", ticker: "LLY", qty: "31", mkt: "$28,270", wt: "2.2%", upnl: "+$1,340", up: true },
  { side: "L", ticker: "AVGO", qty: "92", mkt: "$26,980", wt: "2.1%", upnl: "-$410", up: false },
  { side: "L", ticker: "COST", qty: "27", mkt: "$24,410", wt: "1.9%", upnl: "+$680", up: true },
  { side: "S", ticker: "XOM", qty: "-268", mkt: "$29,540", wt: "2.3%", upnl: "+$1,020", up: true },
  { side: "S", ticker: "INTC", qty: "-940", mkt: "$26,960", wt: "2.1%", upnl: "+$780", up: true },
  { side: "S", ticker: "T", qty: "-1,120", mkt: "$25,700", wt: "2.0%", upnl: "-$260", up: false },
  { side: "S", ticker: "CVX", qty: "-158", mkt: "$23,140", wt: "1.8%", upnl: "+$540", up: true },
];

export const shap = [
  { name: "mom_12_1", value: 0.184, width: "92%", bar: "bg-teal" },
  { name: "earnings_yield", value: 0.148, width: "74%", bar: "bg-teal" },
  { name: "vol_60d", value: 0.122, width: "61%", bar: "bg-[#3bb5b0]" },
  { name: "roe_ttm", value: 0.106, width: "53%", bar: "bg-[#3bb5b0]" },
  { name: "rsi_14", value: 0.088, width: "44%", bar: "bg-[#4a97a8]" },
  { name: "accruals", value: 0.074, width: "37%", bar: "bg-[#4a97a8]" },
  { name: "size_ln_mcap", value: 0.058, width: "29%", bar: "bg-dim" },
  { name: "news_sentiment", value: 0.048, width: "24%", bar: "bg-dim" },
];

export const trainConfig = [
  ["objective", "lambdarank"],
  ["label", "xs z-score fwd 5d"],
  ["n_estimators", "1200"],
  ["learning_rate", "0.021"],
  ["num_leaves", "63"],
  ["train window", "2015–2024"],
  ["retrain", "weekly · Prefect"],
  ["registry", "MLflow · Prod"],
];

export const sectorTilts = [
  { name: "Tech", value: "+6.1", pos: true, width: "60%" },
  { name: "Health", value: "+3.4", pos: true, width: "34%" },
  { name: "Energy", value: "-2.8", pos: false, width: "28%" },
  { name: "Financials", value: "-4.1", pos: false, width: "41%" },
  { name: "Staples", value: "+1.5", pos: true, width: "16%" },
];

export const contributors = [
  { side: "LONG", ticker: "NVDA", pnl: "+$1,840", up: true },
  { side: "SHORT", ticker: "INTC", pnl: "+$970", up: true },
  { side: "LONG", ticker: "LLY", pnl: "+$620", up: true },
  { side: "LONG", ticker: "AVGO", pnl: "-$410", up: false },
  { side: "SHORT", ticker: "XOM", pnl: "-$530", up: false },
];

export const exposure = [
  { label: "Long book", value: "50 names · 80%", tone: "text-green" },
  { label: "Short book", value: "50 names · 68%", tone: "text-red" },
  { label: "Turnover (wk)", value: "23%", tone: "" },
  { label: "Vol target", value: "10% ann.", tone: "" },
];

export const drift = [
  { name: "mom_12_1", psi: "0.03", width: "14%", tone: "text-green", bar: "bg-green" },
  { name: "earnings_yield", psi: "0.06", width: "22%", tone: "text-green", bar: "bg-green" },
  { name: "vol_60d", psi: "0.14", width: "52%", tone: "text-amber", bar: "bg-amber" },
  { name: "roe_ttm", psi: "0.05", width: "18%", tone: "text-green", bar: "bg-green" },
  { name: "news_sentiment", psi: "0.27", width: "78%", tone: "text-red", bar: "bg-red" },
];

export const flowRuns = [
  { flow: "ingest_prices", trigger: "cron 06:00", started: "09-08 06:02", duration: "41s", rows: "503", status: "success" },
  { flow: "build_features", trigger: "upstream", started: "09-08 06:04", duration: "1m18s", rows: "21,126", status: "success" },
  { flow: "score_universe", trigger: "upstream", started: "09-08 06:06", duration: "12s", rows: "503", status: "success" },
  { flow: "retrain_model", trigger: "cron Mon", started: "09-08 09:15", duration: "—", rows: "—", status: "queued" },
  { flow: "rebalance_paper", trigger: "cron Mon", started: "09-01 09:35", duration: "8s", rows: "100", status: "success" },
];

export const pipeline = [
  { label: "Daily ingest", sub: "06:02 ET · 41s", ok: true },
  { label: "Feature build", sub: "06:04 ET · 1m18s", ok: true },
  { label: "Weekly retrain", sub: "queued · 09:15 ET", ok: false },
  { label: "Rebalance", sub: "last ok · Mon", ok: true },
];

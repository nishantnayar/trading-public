const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${BASE}${path}`, { cache: "no-store", signal });
  if (!response.ok) {
    throw new Error(`${response.status} ${path}`);
  }
  return response.json() as Promise<T>;
}

export type Coverage = {
  rows: number;
  symbols: number;
  start: string | null;
  end: string | null;
};

export type SectorCount = { sector: string; count: number };

export type Bar = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type IngestRun = {
  id: number;
  flow: string;
  started_at: string | null;
  finished_at: string | null;
  symbols_processed: number | null;
  rows_written: number | null;
  status: string;
  detail: string | null;
};

/** One watchlist symbol's current trend-rule signal (quantis.signals). */
export type SignalRow = {
  symbol: string;
  date: string;
  signal: "long" | "flat";
  close: number;
  sma_fast: number | null;
  sma_slow: number | null;
  mom_12_1: number | null;
  computed_at: string | null;
};

/** Latest full-period backtest of the portfolio construction (quantis.signals.portfolio). */
export type PortfolioSnapshot = {
  period_start: string | null;
  period_end: string | null;
  trading_days: number;
  total_return: number;
  cagr: number;
  ann_vol: number;
  sharpe: number;
  max_drawdown: number;
  avg_names_long: number;
  avg_exposure: number;
  annualized_turnover: number;
  max_sector_weight: number | null;
  reallocated: boolean;
  max_name_weight: number | null;
  vol_target: number | null;
  avg_leverage: number;
  computed_at: string | null;
};

export type BrokerPosition = {
  symbol: string;
  qty: number;
  price: number | null;
  market_value: number | null;
  /** No valid price was ever found for this symbol — excluded from equity, not traded. */
  stale: boolean;
};

export type BrokerFill = {
  symbol: string;
  side: "buy" | "sell";
  qty: number;
  price: number;
  submitted_at: string | null;
};

/** Current state of the simulated paper broker (quantis.execution.simulated). */
export type BrokerEquitySnapshot = {
  equity: number;
  cash: number;
  n_positions: number;
  recorded_at: string | null;
};

export type BrokerState = {
  broker: string;
  cash: number;
  equity: number;
  updated_at: string | null;
  /** Held symbols with no valid price this run — excluded from equity, left untouched. */
  unpriced_symbols: string[];
  positions: BrokerPosition[];
  recent_fills: BrokerFill[];
  /** One row per historical rebalance, oldest first — for charting NAV over time. */
  equity_history: BrokerEquitySnapshot[];
};

/** IEX free-tier fact, surfaced in the UI (not returned by /coverage). */
export const FEED_LABEL = "IEX · adjusted";

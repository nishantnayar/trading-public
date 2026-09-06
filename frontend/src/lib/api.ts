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

export type SignalRow = {
  rank?: number;
  symbol?: string;
  sector?: string;
  score?: number;
  pctl?: number;
  weight?: number;
  side?: string;
  gap?: boolean;
  label?: string;
};

export type SignalsSnapshot = {
  as_of: string | null;
  rows: SignalRow[];
  meta: {
    horizon?: string;
    scored?: number;
    longs?: number;
    shorts?: number;
    construction?: string;
  };
};

export type Quintile = { label: string; v: number };

export type PositionHolding = {
  symbol: string;
  sector: string;
  weight: number;
  side: string;
};

export type PositionsSnapshot = {
  as_of: string | null;
  construction?: string;
  holdings: PositionHolding[];
  n_holdings?: number;
  constraints: { label: string; value: string; limit: string; used: number }[];
  rebalance: { buys: number; sells: number; turnover: number; prior: string | null };
};

export type ModelSnapshot = {
  as_of: string | null;
  oof_source: string;
  construction: string;
  n_dates: number | null;
  n_symbols: number | null;
  rank_ic: number | null;
  icir: number | null;
  ic_hit_rate: number | null;
  q_spread: number | null;
  sharpe_10bps: number | null;
  turnover: number | null;
  break_even_bps: number | null;
  shap: { feature: string; gain: number; family: string }[];
  params: Record<string, string | number>;
};

/** IEX free-tier fact, surfaced in the UI (not returned by /coverage). */
export const FEED_LABEL = "IEX · adjusted";

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

/** IEX free-tier fact, surfaced in the UI (not returned by /coverage). */
export const FEED_LABEL = "IEX · adjusted";

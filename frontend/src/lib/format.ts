const CT = "America/Chicago";

export function nowClockCT(): string {
  const time = new Date().toLocaleTimeString("en-US", {
    timeZone: CT,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return `${time} CT`;
}

export function fmtInt(value: number | null | undefined): string {
  return (value ?? 0).toLocaleString("en-US");
}

export function fmtUsd(value: number): string {
  return value.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

export function fmtVol(v: number): string {
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return String(v);
}

export function cls(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

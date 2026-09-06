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

export function cls(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

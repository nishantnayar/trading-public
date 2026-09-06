type Tone = "default" | "teal" | "green" | "red";

type Props = {
  label: string;
  value: string;
  sub?: string;
  suffix?: string;
  tone?: Tone;
  subTone?: Tone | "muted";
  compact?: boolean;
};

const VALUE: Record<Tone, string> = {
  default: "text-text",
  teal: "text-teal",
  green: "text-green",
  red: "text-red",
};

const SUB: Record<Tone | "muted", string> = {
  default: "text-muted",
  teal: "text-teal",
  green: "text-green",
  red: "text-red",
  muted: "text-muted",
};

export function Kpi({
  label,
  value,
  sub,
  suffix,
  tone = "default",
  subTone = "muted",
  compact = false,
}: Props) {
  return (
    <div className={`rounded-xl border border-line bg-panel ${compact ? "px-4 py-3.5" : "px-4 py-4"}`}>
      <div className="text-[11px] uppercase tracking-[0.6px] text-muted">{label}</div>
      <div
        className={`mt-2 font-mono font-semibold leading-none ${compact ? "text-xl" : "text-[26px]"} ${VALUE[tone]}`}
      >
        {value}
        {suffix ? <span className="ml-1 text-xs font-normal text-dim">{suffix}</span> : null}
      </div>
      {sub ? <div className={`mt-1.5 font-mono text-[13px] ${SUB[subTone]}`}>{sub}</div> : null}
    </div>
  );
}

import type { ReactNode } from "react";

type Props = {
  title: string;
  subtitle: string;
  children?: ReactNode;
};

export function Topbar({ title, subtitle, children }: Props) {
  return (
    <header className="flex items-center justify-between border-b border-line px-8 py-5">
      <div>
        <h1 className="text-xl font-semibold">{title}</h1>
        <p className="mt-[3px] font-mono text-xs text-dim">{subtitle}</p>
      </div>
      <div className="flex items-center gap-3">{children}</div>
    </header>
  );
}

export function Chip({
  children,
  live = false,
  ok = false,
}: {
  children: ReactNode;
  live?: boolean;
  ok?: boolean;
}) {
  if (live) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-[#1b3b38] bg-nav px-3 py-2 font-mono text-xs text-teal">
        <span className="h-[7px] w-[7px] rounded-full bg-teal" />
        {children}
      </div>
    );
  }
  if (ok) {
    return (
      <div className="rounded-lg border border-[#16351f] bg-long-bg px-3 py-2 font-mono text-xs text-green">
        {children}
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-line px-3 py-2 font-mono text-xs text-muted">{children}</div>
  );
}

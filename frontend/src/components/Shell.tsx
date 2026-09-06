"use client";

import type { ReactNode, SVGProps } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cls } from "@/lib/format";

function Icon({ children, ...props }: SVGProps<SVGSVGElement> & { children: ReactNode }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      {children}
    </svg>
  );
}

const NAV = [
  {
    href: "/",
    label: "Overview",
    icon: (
      <Icon>
        <rect x="3" y="3" width="7" height="9" />
        <rect x="14" y="3" width="7" height="5" />
        <rect x="14" y="12" width="7" height="9" />
        <rect x="3" y="16" width="7" height="5" />
      </Icon>
    ),
  },
  {
    href: "/signals",
    label: "Signals",
    icon: (
      <Icon>
        <line x1="4" y1="6" x2="20" y2="6" />
        <line x1="4" y1="12" x2="14" y2="12" />
        <line x1="4" y1="18" x2="18" y2="18" />
      </Icon>
    ),
  },
  {
    href: "/positions",
    label: "Positions",
    icon: (
      <Icon>
        <path d="M3 3v18h18" />
        <rect x="7" y="10" width="3" height="8" />
        <rect x="12" y="6" width="3" height="12" />
        <rect x="17" y="13" width="3" height="5" />
      </Icon>
    ),
  },
  {
    href: "/model",
    label: "Model",
    icon: (
      <Icon>
        <circle cx="12" cy="12" r="3" />
        <path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1" />
      </Icon>
    ),
  },
  {
    href: "/monitoring",
    label: "Monitoring",
    icon: (
      <Icon>
        <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
      </Icon>
    ),
  },
];

const FOOTER: Record<string, { label: string; status: string }> = {
  "/": { label: "ALPACA · PAPER", status: "Pipeline healthy" },
  "/signals": { label: "ALPACA · PAPER", status: "Pipeline healthy" },
  "/positions": { label: "ALPACA · PAPER", status: "100 / 100 filled" },
  "/model": { label: "MLFLOW · run 8f21c", status: "Registered · Prod" },
  "/monitoring": { label: "PREFECT · orchestrator", status: "All flows nominal" },
};

export function Shell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const footer = FOOTER[path] ?? FOOTER["/"];

  return (
    <div className="flex min-h-screen bg-bg text-text">
      <aside className="flex w-[220px] shrink-0 flex-col border-r border-line bg-sidebar py-[22px]">
        <div className="mb-[26px] flex items-center gap-2.5 px-[22px]">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#2dd4bf" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 3v18h18" />
            <path d="M7 14l3-4 3 3 5-7" />
          </svg>
          <div>
            <div className="text-[15px] font-semibold tracking-[0.2px]">Quantis</div>
            <div className="font-mono text-[10px] tracking-widest text-dim">XS-EQUITY ML</div>
          </div>
        </div>
        <nav className="flex flex-col gap-0.5 px-3">
          {NAV.map((item) => {
            const active = path === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cls(
                  "flex items-center gap-3 rounded-lg px-3.5 py-2.5 text-sm",
                  active ? "bg-nav font-medium text-teal" : "text-muted hover:text-text",
                )}
              >
                {item.icon}
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto border-t border-line px-[22px] pt-4">
          <div className="font-mono text-[11px] text-dim">{footer.label}</div>
          <div className="mt-2 flex items-center gap-[7px] text-xs text-muted">
            <span className="h-2 w-2 rounded-full bg-green shadow-[0_0_8px_#22c55e]" />
            {footer.status}
          </div>
        </div>
      </aside>
      <main className="flex min-w-0 flex-1 flex-col">{children}</main>
    </div>
  );
}

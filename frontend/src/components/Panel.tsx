import type { ReactNode } from "react";

type Props = {
  title: string;
  hint?: string;
  right?: ReactNode;
  children: ReactNode;
};

export function Panel({ title, hint, right, children }: Props) {
  return (
    <div className="rounded-xl border border-line bg-panel p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="text-[15px] font-semibold">
          {title}
          {hint ? <span className="ml-2 text-[13px] font-normal text-dim">{hint}</span> : null}
        </div>
        {right}
      </div>
      {children}
    </div>
  );
}

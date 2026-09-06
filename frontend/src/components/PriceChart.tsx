"use client";

import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { Bar } from "@/lib/api";

export function PriceChart({ data }: { data: Bar[] }) {
  const series = data.map((row) => ({ date: row.date.slice(0, 7), close: row.close }));
  return (
    <ResponsiveContainer width="100%" height={280}>
      <AreaChart data={series} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <XAxis dataKey="date" tick={{ fill: "#5f6b78", fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis
          domain={["auto", "auto"]}
          tick={{ fill: "#5f6b78", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={56}
        />
        <Tooltip
          contentStyle={{ background: "#12181f", border: "1px solid #1e2831", borderRadius: 8 }}
          labelStyle={{ color: "#8b97a3" }}
        />
        <Area type="monotone" dataKey="close" stroke="#2dd4bf" fill="#2dd4bf" fillOpacity={0.18} strokeWidth={2} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

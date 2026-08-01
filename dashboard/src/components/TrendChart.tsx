import { useMemo } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { PlatformTrend } from "../api";

function formatDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function TrendChart({ trends }: { trends: PlatformTrend[] }) {
  const dailyOverall = useMemo(() => {
    const byDate = new Map<string, { builds: number; successes: number }>();
    for (const row of trends) {
      const bucket = byDate.get(row.date) ?? { builds: 0, successes: 0 };
      bucket.builds += row.build_count;
      bucket.successes += row.build_count * row.success_rate;
      byDate.set(row.date, bucket);
    }
    return Array.from(byDate.entries())
      .map(([date, { builds, successes }]) => ({
        date,
        success_rate: builds > 0 ? successes / builds : 0,
      }))
      .sort((a, b) => a.date.localeCompare(b.date));
  }, [trends]);

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>30-day build success trend</h2>
        <span className="subtitle">Overall success rate, weighted by build volume</span>
      </div>
      {dailyOverall.length === 0 ? (
        <div className="empty-state">Not enough history yet &mdash; check back after a few days of data.</div>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={dailyOverall}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tickFormatter={formatDate} minTickGap={40} tick={{ fontSize: 12 }} />
            <YAxis domain={[0, 1]} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} tick={{ fontSize: 12 }} />
            <Tooltip labelFormatter={formatDate} formatter={(v: number) => `${(v * 100).toFixed(1)}%`} />
            <Line type="monotone" dataKey="success_rate" stroke="#2563eb" strokeWidth={2} dot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { LiveBuildHealth } from "../api";

function colorFor(rate: number) {
  if (rate >= 0.95) return "#059669";
  if (rate >= 0.85) return "#d97706";
  return "#dc2626";
}

export default function PlatformBreakdownChart({ live }: { live: LiveBuildHealth[] }) {
  const byPlatform = useMemo(() => {
    const map = new Map<string, { builds: number; successes: number }>();
    for (const row of live) {
      const bucket = map.get(row.platform) ?? { builds: 0, successes: 0 };
      bucket.builds += row.build_count;
      bucket.successes += row.build_count * row.success_rate;
      map.set(row.platform, bucket);
    }
    return Array.from(map.entries())
      .map(([platform, { builds, successes }]) => ({
        platform,
        success_rate: builds > 0 ? successes / builds : 0,
      }))
      .sort((a, b) => a.success_rate - b.success_rate);
  }, [live]);

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>Success rate by platform</h2>
        <span className="subtitle">Aggregated across hardware tiers</span>
      </div>
      {byPlatform.length === 0 ? (
        <div className="empty-state">No data yet.</div>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={byPlatform} layout="vertical" margin={{ left: 8, right: 16 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis
              type="number"
              domain={[0, 1]}
              tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
              tick={{ fontSize: 12 }}
            />
            <YAxis type="category" dataKey="platform" width={70} tick={{ fontSize: 12 }} />
            <Tooltip formatter={(v: number) => `${(v * 100).toFixed(1)}%`} />
            <Bar dataKey="success_rate" radius={[0, 4, 4, 0]} barSize={18}>
              {byPlatform.map((entry) => (
                <Cell key={entry.platform} fill={colorFor(entry.success_rate)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
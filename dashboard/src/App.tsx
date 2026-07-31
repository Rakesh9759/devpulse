import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from "recharts";
import { getLiveBuildHealth, getTrends, LiveBuildHealth, PlatformTrend } from "./api";

export default function App() {
  const [live, setLive] = useState<LiveBuildHealth[]>([]);
  const [trends, setTrends] = useState<PlatformTrend[]>([]);

  useEffect(() => {
    const load = () => getLiveBuildHealth().then(setLive).catch(console.error);
    load();
    const interval = setInterval(load, 15000); // poll the hot path every 15s
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    getTrends(30).then(setTrends).catch(console.error);
  }, []);

  return (
    <div style={{ fontFamily: "sans-serif", padding: "2rem", maxWidth: 960, margin: "0 auto" }}>
      <h1>DevPulse</h1>
      <p>Fleet build and test health across platforms.</p>

      <h2>Live build health</h2>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left" }}>Platform</th>
            <th style={{ textAlign: "left" }}>Hardware</th>
            <th style={{ textAlign: "right" }}>Builds (1m)</th>
            <th style={{ textAlign: "right" }}>Success rate</th>
            <th style={{ textAlign: "right" }}>Avg duration (s)</th>
          </tr>
        </thead>
        <tbody>
          {live.map((row) => (
            <tr key={`${row.platform}-${row.hardware}`}>
              <td>{row.platform}</td>
              <td>{row.hardware}</td>
              <td style={{ textAlign: "right" }}>{row.build_count}</td>
              <td style={{ textAlign: "right" }}>{(row.success_rate * 100).toFixed(1)}%</td>
              <td style={{ textAlign: "right" }}>{row.avg_duration_seconds.toFixed(0)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>30-day build success trend</h2>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={trends}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" />
          <YAxis domain={[0, 1]} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
          <Tooltip formatter={(v: number) => `${(v * 100).toFixed(1)}%`} />
          <Line type="monotone" dataKey="success_rate" stroke="#378ADD" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

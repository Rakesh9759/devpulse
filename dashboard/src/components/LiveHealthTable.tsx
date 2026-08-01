import { LiveBuildHealth } from "../api";

function badgeClass(rate: number): "good" | "warn" | "bad" {
  if (rate >= 0.95) return "good";
  if (rate >= 0.85) return "warn";
  return "bad";
}

export default function LiveHealthTable({ live }: { live: LiveBuildHealth[] }) {
  const sorted = [...live].sort((a, b) => a.success_rate - b.success_rate);

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>Live build health</h2>
        <span className="subtitle">1-minute window &middot; refreshes every 15s</span>
      </div>
      {sorted.length === 0 ? (
        <div className="empty-state">No build activity in the last minute.</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Platform</th>
              <th>Hardware</th>
              <th className="num">Builds</th>
              <th className="num">Success rate</th>
              <th className="num">Avg duration</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => (
              <tr key={`${row.platform}-${row.hardware}`}>
                <td>{row.platform}</td>
                <td>{row.hardware}</td>
                <td className="num mono">{row.build_count}</td>
                <td className="num">
                  <span className={`badge ${badgeClass(row.success_rate)}`}>
                    {(row.success_rate * 100).toFixed(1)}%
                  </span>
                </td>
                <td className="num mono">{row.avg_duration_seconds.toFixed(0)}s</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
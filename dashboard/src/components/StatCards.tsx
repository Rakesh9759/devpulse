import { LiveBuildHealth } from "../api";

function rateClass(rate: number): "good" | "warn" | "bad" {
  if (rate >= 0.95) return "good";
  if (rate >= 0.85) return "warn";
  return "bad";
}

export default function StatCards({ live }: { live: LiveBuildHealth[] }) {
  const totalBuilds = live.reduce((sum, r) => sum + r.build_count, 0);
  const weightedSuccess =
    totalBuilds > 0
      ? live.reduce((sum, r) => sum + r.build_count * r.success_rate, 0) / totalBuilds
      : 0;
  const avgDuration =
    live.length > 0 ? live.reduce((sum, r) => sum + r.avg_duration_seconds, 0) / live.length : 0;
  const activeCombos = live.length;
  const platformCount = new Set(live.map((r) => r.platform)).size;

  return (
    <div className="stat-grid">
      <div className="stat-card">
        <div className="label">Builds (last minute)</div>
        <div className="value mono">{totalBuilds}</div>
      </div>
      <div className="stat-card">
        <div className="label">Overall success rate</div>
        <div className={`value mono ${rateClass(weightedSuccess)}`}>
          {(weightedSuccess * 100).toFixed(1)}%
        </div>
      </div>
      <div className="stat-card">
        <div className="label">Avg build duration</div>
        <div className="value mono">{avgDuration.toFixed(0)}s</div>
      </div>
      <div className="stat-card">
        <div className="label">Active platforms</div>
        <div className="value mono">
          {platformCount}
          <span className="tag">{activeCombos} combos</span>
        </div>
      </div>
    </div>
  );
}

import { FlakyTest } from "../api";

export default function FlakyTestsPanel({ tests }: { tests: FlakyTest[] }) {
  return (
    <div className="panel">
      <div className="panel-header">
        <h2>Flaky test leaderboard</h2>
        <span className="subtitle">Last 7 days &middot; highest flake rate first</span>
      </div>
      {tests.length === 0 ? (
        <div className="empty-state">No flaky tests detected in the last 7 days.</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Suite</th>
              <th>Platform</th>
              <th>Hardware</th>
              <th className="num">Flaky / Total</th>
              <th style={{ width: "30%" }}>Flake rate</th>
            </tr>
          </thead>
          <tbody>
            {tests.map((t, i) => (
              <tr key={`${t.suite}-${t.platform}-${t.hardware}-${i}`}>
                <td>{t.suite}</td>
                <td>{t.platform}</td>
                <td>{t.hardware}</td>
                <td className="num mono">
                  {t.flaky_runs_7d} / {t.total_runs_7d}
                </td>
                <td>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <div className="flake-bar-track">
                      <div
                        className="flake-bar-fill"
                        style={{ width: `${Math.min(t.flake_rate * 100, 100)}%` }}
                      />
                    </div>
                    <span className="mono" style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                      {(t.flake_rate * 100).toFixed(1)}%
                    </span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
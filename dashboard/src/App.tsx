import { useEffect, useState } from "react";
import {
  FlakyTest,
  LiveBuildHealth,
  PlatformTrend,
  getFlakyTests,
  getLiveBuildHealth,
  getTrends,
} from "./api";
import StatCards from "./components/StatCards";
import LiveHealthTable from "./components/LiveHealthTable";
import PlatformBreakdownChart from "./components/PlatformBreakdownChart";
import TrendChart from "./components/TrendChart";
import FlakyTestsPanel from "./components/FlakyTestsPanel";

export default function App() {
  const [live, setLive] = useState<LiveBuildHealth[]>([]);
  const [trends, setTrends] = useState<PlatformTrend[]>([]);
  const [flakyTests, setFlakyTests] = useState<FlakyTest[]>([]);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  useEffect(() => {
    const load = () =>
      getLiveBuildHealth()
        .then((data) => {
          setLive(data);
          setLastUpdated(new Date());
        })
        .catch(console.error);
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    getTrends(30).then(setTrends).catch(console.error);
    getFlakyTests(10).then(setFlakyTests).catch(console.error);
  }, []);

  return (
    <div className="app">
      <div className="app-header">
        <div>
          <h1>DevPulse</h1>
          <p>Fleet build and test health across platforms.</p>
        </div>
        <div className="live-indicator">
          <span className="live-dot" />
          {lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : "Connecting..."}
        </div>
      </div>

      <StatCards live={live} />

      <div className="grid-2">
        <LiveHealthTable live={live} />
        <PlatformBreakdownChart live={live} />
      </div>

      <TrendChart trends={trends} />

      <FlakyTestsPanel tests={flakyTests} />
    </div>
  );
}
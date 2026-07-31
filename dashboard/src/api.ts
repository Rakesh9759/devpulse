const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export interface LiveBuildHealth {
  platform: string;
  hardware: string;
  window_end: string;
  build_count: number;
  success_rate: number;
  avg_duration_seconds: number;
}

export interface PlatformTrend {
  date: string;
  platform: string;
  build_count: number;
  success_rate: number;
  p95_duration_seconds: number | null;
}

export async function getLiveBuildHealth(): Promise<LiveBuildHealth[]> {
  const res = await fetch(`${API_BASE}/live/build-health`);
  if (!res.ok) throw new Error("Failed to fetch live build health");
  return res.json();
}

export async function getTrends(days = 30): Promise<PlatformTrend[]> {
  const res = await fetch(`${API_BASE}/analytics/trends?days=${days}`);
  if (!res.ok) throw new Error("Failed to fetch trends");
  return res.json();
}

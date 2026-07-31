from pydantic import BaseModel


class LiveBuildHealth(BaseModel):
    platform: str
    hardware: str
    window_end: str
    build_count: int
    success_rate: float
    avg_duration_seconds: float


class PlatformTrend(BaseModel):
    date: str
    platform: str
    build_count: int
    success_rate: float
    p95_duration_seconds: float | None = None


class FlakyTest(BaseModel):
    suite: str
    platform: str
    hardware: str
    flaky_runs_7d: int
    total_runs_7d: int
    flake_rate: float
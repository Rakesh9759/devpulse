from fastapi import APIRouter, HTTPException

from app.db import get_redis
from app.models import LiveBuildHealth

router = APIRouter()


@router.get("/build-health", response_model=list[LiveBuildHealth])
def current_build_health():
    """
    Latest 1-minute windowed build health per platform/hardware combo,
    as written by the Spark streaming job's hot path.
    """
    r = get_redis()
    results = []
    for key in r.scan_iter("live:build_health:*"):
        _, _, platform, hardware = key.split(":")
        data = r.hgetall(key)
        if not data:
            continue
        results.append(
            LiveBuildHealth(
                platform=platform,
                hardware=hardware,
                window_end=data.get("window_end", ""),
                build_count=int(data.get("build_count", 0)),
                success_rate=float(data.get("success_rate", 0)),
                avg_duration_seconds=float(data.get("avg_duration_seconds", 0)),
            )
        )
    return results


@router.get("/build-health/{platform}/{hardware}", response_model=LiveBuildHealth)
def build_health_for(platform: str, hardware: str):
    r = get_redis()
    key = f"live:build_health:{platform}:{hardware}"
    data = r.hgetall(key)
    if not data:
        raise HTTPException(status_code=404, detail="No recent data for this platform/hardware")
    return LiveBuildHealth(
        platform=platform,
        hardware=hardware,
        window_end=data.get("window_end", ""),
        build_count=int(data.get("build_count", 0)),
        success_rate=float(data.get("success_rate", 0)),
        avg_duration_seconds=float(data.get("avg_duration_seconds", 0)),
    )

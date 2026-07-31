from fastapi import APIRouter
from sqlalchemy import text

from app.db import get_engine
from app.models import FlakyTest, PlatformTrend

router = APIRouter()


@router.get("/trends", response_model=list[PlatformTrend])
def platform_trends(days: int = 30):
    """
    Daily build volume/success rate per platform, from the dbt mart
    `fct_build_health` (built by the batch/dbt path, see dbt/models/marts).
    """
    query = text(
        """
        select
            build_date::text as date,
            platform,
            build_count,
            success_rate,
            p95_duration_seconds
        from fct_build_health
        where build_date >= current_date - :days
        order by build_date
        """
    )
    with get_engine().connect() as conn:
        rows = conn.execute(query, {"days": days}).mappings().all()
    return [PlatformTrend(**row) for row in rows]


@router.get("/flaky-tests", response_model=list[FlakyTest])
def flaky_test_leaderboard(limit: int = 20):
    """Top flaky test suites over the last 7 days, from fct_test_health."""
    query = text(
        """
        select
            suite,
            platform,
            hardware,
            flaky_runs_7d,
            total_runs_7d,
            flake_rate
        from fct_test_health
        order by flake_rate desc
        limit :limit
        """
    )
    with get_engine().connect() as conn:
        rows = conn.execute(query, {"limit": limit}).mappings().all()
    return [FlakyTest(**row) for row in rows]

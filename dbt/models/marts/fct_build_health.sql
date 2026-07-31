select
    build_date,
    platform,
    count(*) as build_count,
    avg(case when success then 1.0 else 0.0 end) as success_rate,
    percentile_cont(0.95) within group (order by duration_seconds) as p95_duration_seconds
from {{ ref('stg_build_events') }}
group by 1, 2

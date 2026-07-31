select
    suite,
    platform,
    hardware,
    sum(case when flaky then 1 else 0 end) as flaky_runs_7d,
    count(*) as total_runs_7d,
    sum(case when flaky then 1.0 else 0.0 end) / count(*) as flake_rate
from {{ ref('stg_test_events') }}
where test_date >= current_date - 7
group by 1, 2, 3

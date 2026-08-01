select
    event_id,
    build_event_id,
    cast(timestamp as timestamp) as test_ts,
    date(timestamp) as test_date,
    platform,
    hardware,
    suite,
    duration_seconds,
    passed,
    flaky,
    crash_on_test
from {{ source('raw', 'fleet_events') }}
where event_type = 'test_run'

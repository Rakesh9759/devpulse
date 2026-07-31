-- Cleans and types the raw build events landed by the Spark streaming job
-- (cold path) into the Iceberg lake, exposed to Snowflake via an external
-- table or periodic COPY INTO.

select
    event_id,
    cast(timestamp as timestamp_ntz) as build_ts,
    date(timestamp) as build_date,
    platform,
    hardware,
    branch,
    commit_sha,
    duration_seconds,
    queue_seconds,
    success,
    signing_ok
from {{ source('raw', 'fleet_events') }}
where event_type = 'build'

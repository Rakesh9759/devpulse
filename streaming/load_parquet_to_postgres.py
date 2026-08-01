"""
Local-dev bridge: loads parquet files written by the streaming job's cold
path into Postgres as `raw.fleet_events`, so `dbt run` has something to read
via the `raw.fleet_events` source without needing a real Iceberg catalog or
Snowflake account.

In a real deployment this step doesn't exist -- Snowflake reads the Iceberg
table directly (external table or COPY INTO), which is what the
`sync_iceberg_external_table` task in airflow/dags/fleet_batch_pipeline.py
stands in for. This script is local-dev-only plumbing.

Run after the streaming job has been writing for a bit:
    python load_parquet_to_postgres.py
"""
import os

import pandas as pd
from sqlalchemy import create_engine, text

COLD_SINK_PATH = os.environ.get("COLD_SINK_PATH", "/tmp/devpulse/raw_events")
POSTGRES_URL = os.environ.get(
    "WAREHOUSE_URL", "postgresql://devpulse:devpulse@localhost:5433/devpulse"
)


def main():
    engine = create_engine(POSTGRES_URL)

    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw"))
        conn.commit()

    df = pd.read_parquet(COLD_SINK_PATH)
    df.to_sql(
        "fleet_events",
        engine,
        schema="raw",
        if_exists="replace",  # simple full-refresh for local dev
        index=False,
    )
    print(f"Loaded {len(df)} rows into raw.fleet_events")


if __name__ == "__main__":
    main()

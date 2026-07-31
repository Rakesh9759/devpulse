"""
Batch pipeline DAG.

The streaming job already lands raw events into Iceberg continuously.
This DAG runs on a schedule to:
  1. Sync/refresh the warehouse's view of the Iceberg raw table
  2. Run dbt to rebuild the staging + mart models
  3. Run dbt tests to catch data quality regressions before the analytics
     API and dashboard read from the marts

Runs hourly by default -- adjust to match how fresh the historical trend
views need to be.
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "devpulse",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="fleet_batch_pipeline",
    default_args=default_args,
    description="Refresh warehouse marts from the Iceberg raw event lake",
    schedule_interval="@hourly",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["devpulse", "dbt", "batch"],
) as dag:

    # Local dev (Postgres, no real Iceberg catalog): bridges the streaming
    # job's parquet output into raw.fleet_events.
    #   sync_raw_table = BashOperator(
    #       task_id="load_parquet_to_postgres",
    #       bash_command="python /opt/devpulse/streaming/load_parquet_to_postgres.py",
    #   )
    # Production (Snowflake + real Iceberg catalog): refresh the external
    # table / run COPY INTO instead. Swap in SnowflakeOperator once the
    # `snowflake_default` connection is configured in Airflow.
    sync_raw_table = BashOperator(
        task_id="sync_iceberg_external_table",
        bash_command="python /opt/devpulse/streaming/load_parquet_to_postgres.py",
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        # --target prod uses Snowflake (dbt/profiles.yml); drop the flag
        # (or use --target dev) to run against local Postgres instead.
        bash_command="cd /opt/devpulse/dbt && dbt run --profiles-dir . --target prod",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command="cd /opt/devpulse/dbt && dbt test --profiles-dir . --target prod",
    )

    sync_raw_table >> dbt_run >> dbt_test

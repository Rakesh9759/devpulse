# DevPulse

A fleet build and test intelligence platform: simulates the kind of telemetry a
device build/test farm generates (macOS, iOS, iPadOS, watchOS, tvOS across
several hardware tiers) and turns it into a queryable analytics service with a
live dashboard.

The project mirrors the shape of a developer-productivity analytics system —
streaming ingestion, batch transformation, a backend API, and a stakeholder
facing UI — rather than a single script or notebook.

## Why this project

Answers questions like:
- Which platform/hardware combo has the worst build success rate right now?
- Which test suites are flakiest over the last 7 days?
- Is build queue time trending up for a given platform after a recent change?

These are the kind of questions a developer-productivity or workflow-analytics
team answers for an engineering organization at scale.

## Architecture

```
Fleet event producer (Python)
        |
        v
     Kafka  ---------------------------+
        |                              |
        v                              v
Spark Structured Streaming     (same job, two sinks)
        |                              |
        v                              v
  Redis (hot path,                Iceberg raw lake
  live dashboard reads)           (cold path, durable)
                                        |
                                        v
                              Airflow -> dbt -> Snowflake/Postgres
                              (staging + mart models)
                                        |
                                        v
                              FastAPI (/live/*, /analytics/*)
                                        |
                                        v
                          React + TypeScript dashboard
```

Everything downstream of the API is containerized and deployed to Kubernetes;
GitHub Actions handles test -> build -> push -> deploy on merge to `main`.

## Repo layout

```
producer/     synthetic fleet event generator -> Kafka
streaming/    Spark Structured Streaming job (hot + cold path fan-out)
api/          FastAPI service (live + analytics routes), Dockerfile
dbt/          staging + mart models transforming raw events into marts
airflow/      DAG orchestrating the batch dbt run
dashboard/    React + TypeScript frontend
k8s/          Kubernetes manifests (API deployment, HPA, Redis, services)
.github/      CI/CD pipeline
docker-compose.yml   local dev stack: Kafka, Redis, Postgres, API
```

## How each piece works

**Producer** (`producer/fleet_event_producer.py`) — generates build and test
events with realistic distributions (a couple of platform/hardware combos are
deliberately biased to be unhealthy so there's something to detect
downstream) and publishes them to per-platform Kafka topics.

**Streaming job** (`streaming/spark_streaming_job.py`) — a single Spark
Structured Streaming job reads from Kafka and fans out to two sinks:
- *hot path*: 1-minute windowed build health aggregates written to Redis,
  read by `/live/*` API routes for the live dashboard view
- *cold path*: raw events appended to an Iceberg table, the durable,
  replayable source of truth for batch processing

**Batch/dbt** (`dbt/`, `airflow/`) — Airflow runs hourly, triggering `dbt run`
+ `dbt test` against the Iceberg-backed raw table. Staging models clean and
type the raw events; mart models (`fct_build_health`, `fct_test_health`)
compute the daily trend and flaky-test aggregates the analytics routes query.

**API** (`api/`) — FastAPI service with two route groups matching the two
data paths: `/live/*` for fast Redis reads (sub-second freshness, small
payloads) and `/analytics/*` for heavier warehouse queries (historical
trends, flaky test leaderboard). `/healthz` backs the Kubernetes liveness and
readiness probes.

**Dashboard** (`dashboard/`) — React + TypeScript, polls `/live/build-health`
every 15s for the live table and fetches `/analytics/trends` once for the
30-day success rate chart.

**Deployment** — `api/Dockerfile` builds the API image; `k8s/` deploys it
alongside a Redis instance with a `HorizontalPodAutoscaler`. GitHub Actions
(`.github/workflows/ci-cd.yml`) lints, tests, builds and pushes the image to
GHCR, then updates the deployment's image on merge to `main`.

## Build stages

1. **Local plumbing** — `docker compose up` for Kafka/Redis/Postgres, run the
   producer, confirm events land on the Kafka topics.
2. **Streaming path** — get the Spark job consuming and writing to Redis;
   verify `/live/build-health` returns data (swap the Iceberg sink for local
   parquet first if you don't want to stand up a full Iceberg catalog yet).
3. **Batch path** — stand up Postgres locally as a Snowflake stand-in, get
   `dbt run` producing `fct_build_health` / `fct_test_health`, verify
   `/analytics/trends` and `/analytics/flaky-tests` return data.
4. **Dashboard** — `npm install && npm run dev` in `dashboard/`, point it at
   the local API, confirm the live table and trend chart render.
5. **Containerize** — build and run the API image locally via Docker.
6. **Kubernetes** — apply the manifests in `k8s/` to a local cluster
   (kind/minikube), confirm the deployment, service, and HPA come up healthy.
7. **CI/CD** — push to a GitHub repo, confirm the Actions workflow runs
   tests, builds the image, and (once `KUBE_CONFIG` is set) deploys.
8. **Swap in the real backends** — point `WAREHOUSE_URL` at Snowflake and
   configure a real Iceberg catalog for the streaming job's cold path.

## Local dev quickstart

```bash
docker compose up -d
python producer/fleet_event_producer.py --rate 5

# separate terminal: streaming job (defaults to parquet cold-path sink,
# no Iceberg catalog needed for local dev)
spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
  streaming/spark_streaming_job.py

# bridge the parquet cold-path output into Postgres so dbt has a source
python streaming/load_parquet_to_postgres.py

# run the batch transform
cd dbt && dbt run --profiles-dir . --target dev && dbt test --profiles-dir . --target dev

# API and dashboard
cd ../api && uvicorn app.main:app --reload
cd ../dashboard && npm install && npm run dev
```

## Config changes required before this runs end to end

These are the gaps between "scaffold" and "runs" -- most are now wired up
with local-dev-friendly defaults, a few still need real credentials.

**Already defaulted for local dev (no action needed to get running):**
- `dbt/profiles.yml` — `dev` target points at the local Postgres from
  `docker-compose.yml`; switch to `--target prod` once Snowflake creds exist
  as env vars (`SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`)
- Streaming job's cold-path sink defaults to `parquet` at
  `/tmp/devpulse/raw_events` (`COLD_SINK_FORMAT=iceberg` to switch once a
  real Iceberg catalog exists)
- `streaming/load_parquet_to_postgres.py` bridges that parquet output into
  `raw.fleet_events` in Postgres so dbt sources resolve locally — this
  script is local-dev-only plumbing; a real deployment has Snowflake read
  the Iceberg table directly instead
- API CORS now reads `CORS_ALLOW_ORIGINS` (defaults to the Vite dev server
  at `http://localhost:5173`) instead of allowing all origins

**Still need real values before deploying:**
- `WAREHOUSE_URL` — Snowflake connection string, set as a k8s secret:
  ```bash
  kubectl create secret generic devpulse-warehouse \
    --from-literal=url="snowflake://user:pass@account/DEVPULSE/analytics?warehouse=WH_XS"
  ```
- `k8s/api-deployment.yaml` — replace `ghcr.io/OWNER/devpulse-api` with your
  actual GitHub username/org (must match what CI pushes)
- GitHub Actions — add a `KUBE_CONFIG` repo secret (base64-encoded
  kubeconfig) for the `deploy` job to work
- Iceberg catalog config for `spark-submit`, once you're past local dev:
  ```
  --conf spark.sql.catalog.devpulse=org.apache.iceberg.spark.SparkCatalog \
  --conf spark.sql.catalog.devpulse.type=hadoop \
  --conf spark.sql.catalog.devpulse.warehouse=s3a://your-bucket/devpulse
  ```
  plus `COLD_SINK_FORMAT=iceberg` and `ICEBERG_TABLE=devpulse.raw_events`
- Airflow's `sync_iceberg_external_table` task currently runs the local
  Postgres loader; swap in a `SnowflakeOperator` + real `REFRESH`/`COPY INTO`
  once Snowflake is live

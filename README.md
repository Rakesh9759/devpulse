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

## How to run this (Windows + WSL2, verified steps)

This is the exact sequence that gets a fully working local pipeline — every
step here was hit and fixed during actual setup, not theoretical.

### One-time setup

**1. Install Docker Desktop** — enable WSL2 integration (default). Launch it
and let it finish initializing before continuing.

**2. Install WSL2 + Ubuntu** (Spark runs inside WSL — native Windows Spark
needs Hadoop native libs and is fragile; WSL sidesteps that entirely):
```powershell
wsl --install
```
Restart if prompted, then finish Ubuntu's first-run setup (username/password,
local to WSL only).

**3. Inside WSL (Ubuntu): install Java, build tools, and a Python venv**
```bash
sudo apt update
sudo apt install -y openjdk-17-jdk python3-pip python3-venv python3-full \
  build-essential libpq-dev
python3 -m venv ~/devpulse-venv
source ~/devpulse-venv/bin/activate
```
Ubuntu blocks system-wide `pip install` by default (PEP 668) — always use
this venv for anything Spark/streaming-related. Reactivate it
(`source ~/devpulse-venv/bin/activate`) every time you open a new WSL
terminal for this project.

**4. Install Node.js** (Windows side, for the dashboard) — download the LTS
installer from nodejs.org rather than Chocolatey (fewer permission issues),
or if using Chocolatey, run PowerShell **as Administrator**.

### Every time you want to run the full stack

You'll end up with **5 terminals** running simultaneously. Open them in this
order:

**Terminal 1 (Windows) — infra:**
```powershell
cd devpulse
docker compose up -d zookeeper kafka redis postgres
docker compose ps   # confirm all 4 show "running", postgres shows 5433->5432/tcp
```

**Terminal 2 (Windows) — producer:**
```powershell
cd devpulse/producer
python -m pip install -r requirements.txt
python fleet_event_producer.py --rate 5
```
Leave running — it prints nothing while it works.

**Terminal 3 (WSL) — Spark streaming job:**
```bash
source ~/devpulse-venv/bin/activate
cd /mnt/c/path/to/devpulse/streaming
pip install -r requirements.txt
spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
  spark_streaming_job.py
```
Leave running. First launch downloads the Kafka connector jar (~1 min), then
prints periodic micro-batch progress as JSON — that's normal, not an error.

**Terminal 4 (Windows) — API:**
```powershell
cd devpulse/api
python -m pip install fastapi uvicorn[standard] redis sqlalchemy psycopg2-binary pydantic
$env:REDIS_HOST="localhost"
$env:WAREHOUSE_URL="postgresql://devpulse:devpulse@localhost:5433/devpulse"
python -m uvicorn app.main:app --reload
```
(Skip `snowflake-sqlalchemy` locally — it needs MSVC build tools to compile
`cffi` from source and isn't needed until you're pointing at real Snowflake.)

**Terminal 5 (Windows) — dashboard:**
```powershell
cd devpulse/dashboard
npm install
npm run dev
```
Open **http://localhost:5173**. The live table should populate within ~15s.

### Populate the batch/analytics side (trend chart, flaky-test leaderboard)

The live table works as soon as Terminal 3 is running. The **trend chart**
and **flaky test leaderboard** read from Postgres via dbt, which needs one
manual bridge step since local dev has no real Iceberg catalog:

**Terminal 3 or a new WSL terminal (venv active), after Spark has run a
few minutes:**
```bash
python load_parquet_to_postgres.py
```
Prints `Loaded N rows into raw.fleet_events`.

```bash
pip install dbt-postgres
cd ../dbt
dbt run --profiles-dir . --target dev
dbt test --profiles-dir . --target dev
```
Refresh the dashboard — the trend chart and flaky test leaderboard should
now show data. Re-run this loader + dbt pair periodically to refresh the
batch views with newer events.

### Verifying each layer independently (useful when debugging)

```bash
# Kafka has events flowing
docker exec -it devpulse-kafka-1 kafka-console-consumer \
  --bootstrap-server localhost:9092 --topic fleet.events.macos \
  --from-beginning --max-messages 3

# Redis has hot-path data
docker exec -it devpulse-redis-1 redis-cli KEYS "live:*"
docker exec -it devpulse-redis-1 redis-cli HGETALL "live:build_health:macOS:M2"
```
```powershell
# API is serving both route groups
curl http://localhost:8000/live/build-health
curl http://localhost:8000/analytics/trends
curl http://localhost:8000/analytics/flaky-tests
```

### Common gotchas from actual setup (in case you hit them again)

| Symptom | Fix |
|---|---|
| `pip`/`node`/`doctl` "not recognized" right after install | Close and reopen the terminal — PATH doesn't refresh in the current session |
| `ModuleNotFoundError: kafka.vendor.six.moves` | `kafka-python` is unmaintained; use `kafka-python-ng` instead (already in `producer/requirements.txt`) |
| pandas/pyarrow/psycopg2/sqlalchemy fail to build from source | Python 3.14 is very new; use the version floors already in `requirements.txt` (`>=`) rather than exact pins |
| Postgres `port already allocated` | Something else (often a native Postgres install) is already on 5432 — this repo's `docker-compose.yml` already remaps to `5433` |
| `type "timestamp_ntz" does not exist` in dbt | That's Snowflake-only syntax; staging models use plain `timestamp` so they work on both |
| Trend chart shows one label repeated with a fake "wiggle" | Don't chart the mart's per-platform rows directly — aggregate to one point per date first (see `TrendChart.tsx`) |
| k8s pod `ImagePullBackOff` / `401 Unauthorized` | GHCR packages are private by default; either make the package public or use an `imagePullSecret` (see `k8s/api-deployment.yaml`) |

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

## Screenshots

![DevPulse dashboard](docs/screenshots/01-dashboard.png)
*Live build health table, platform breakdown chart, 30-day trend, and flaky
test leaderboard — all reading real data from the running pipeline.*

![Architecture diagram](docs/screenshots/02-architecture.png)
*Producer → Kafka → Spark Structured Streaming (hot path to Redis, cold path
to the lake) → dbt/Postgres → FastAPI → React dashboard.*

![Spark Structured Streaming micro-batch progress](docs/screenshots/03-spark-streaming.png)
*A single micro-batch (batch 47): 213 events processed, ~178 rows/sec,
watermark tracking, and per-partition state store metrics — the streaming
job actually running, not mocked.*

![Kubernetes pods and rolling deployment](docs/screenshots/04-kubernetes-pods.png)
*`kubectl get pods` / `get deployment` mid-rollout: old replicas terminating
as new ones come up healthy, `2/2` ready on the API deployment.*

![GitHub Actions pipeline, all green](docs/screenshots/05-github-actions.png)
*`test` → `build-and-push` → `deploy` succeeding end to end in 2m 21s.*

To reproduce or update these screenshots yourself, see the "How to run
this" section above for getting the pipeline running, then capture each
view as described in the captions.

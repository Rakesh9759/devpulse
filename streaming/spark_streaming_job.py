"""
Spark Structured Streaming job.

Consumes fleet build/test events from Kafka and fans out two ways:
  1. Hot path  -> windowed aggregates written to Redis for the live dashboard
  2. Cold path -> raw events appended to an Iceberg table for batch/dbt use

Run (local):
    spark-submit \
        --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,\
org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.0 \
        spark_streaming_job.py

NOTE: this assumes a Kafka cluster reachable at KAFKA_BOOTSTRAP and an
Iceberg catalog configured via spark-defaults.conf (or --conf flags). For a
first pass without a real Iceberg catalog, swap the `writeStream` sink at the
bottom for `.format("parquet")` writing to a local/S3 path — the windowed
aggregation logic is identical either way.
"""
import os

import redis
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    avg, col, count, expr, from_json, sum as _sum, window
)
from pyspark.sql.types import (
    BooleanType, DoubleType, StringType, StructField, StructType, TimestampType
)

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")

# Cold-path sink format: "parquet" works out of the box for local dev with no
# extra catalog setup. Set COLD_SINK_FORMAT=iceberg once a real Iceberg
# catalog is configured (see README "Config changes" section) -- the rest of
# this job doesn't need to change.
COLD_SINK_FORMAT = os.environ.get("COLD_SINK_FORMAT", "parquet")
COLD_SINK_PATH = os.environ.get("COLD_SINK_PATH", "/tmp/devpulse/raw_events")
ICEBERG_TABLE = os.environ.get("ICEBERG_TABLE", "devpulse.raw_events")

EVENT_SCHEMA = StructType([
    StructField("event_type", StringType()),
    StructField("event_id", StringType()),
    StructField("build_event_id", StringType()),
    StructField("timestamp", TimestampType()),
    StructField("platform", StringType()),
    StructField("hardware", StringType()),
    StructField("branch", StringType()),
    StructField("commit_sha", StringType()),
    StructField("suite", StringType()),
    StructField("duration_seconds", DoubleType()),
    StructField("queue_seconds", DoubleType()),
    StructField("success", BooleanType()),
    StructField("passed", BooleanType()),
    StructField("flaky", BooleanType()),
    StructField("signing_ok", BooleanType()),
    StructField("crash_on_test", BooleanType()),
])


def write_batch_to_redis(batch_df, batch_id):
    """foreachBatch sink: push windowed aggregates into Redis as JSON."""
    r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
    rows = batch_df.collect()
    for row in rows:
        key = f"live:build_health:{row['platform']}:{row['hardware']}"
        payload = {
            "window_end": str(row["window"]["end"]),
            "build_count": row["build_count"],
            "success_rate": row["success_rate"],
            "avg_duration_seconds": row["avg_duration_seconds"],
        }
        r.hset(key, mapping=payload)
        r.expire(key, 3600)  # rolling TTL keeps the hot store bounded


def main():
    spark = (
        SparkSession.builder.appName("devpulse-streaming")
        .config("spark.sql.shuffle.partitions", "8")
        .getOrCreate()
    )

    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
        .option("subscribePattern", "fleet.events.*")
        .option("startingOffsets", "latest")
        .load()
    )

    events = raw.select(
        from_json(col("value").cast("string"), EVENT_SCHEMA).alias("e")
    ).select("e.*").withWatermark("timestamp", "10 minutes")

    # ---- Cold path: append raw events to the lake ----
    cold_writer = events.writeStream.outputMode("append").option(
        "checkpointLocation", "/tmp/devpulse/checkpoints/raw"
    ).trigger(processingTime="30 seconds")

    if COLD_SINK_FORMAT == "iceberg":
        cold_writer.format("iceberg").option("path", ICEBERG_TABLE).start()
    else:
        cold_writer.format("parquet").option("path", COLD_SINK_PATH).start()

    # ---- Hot path: 1-minute windowed build health -> Redis ----
    build_health = (
        events.where(col("event_type") == "build")
        .groupBy(window(col("timestamp"), "1 minute"), col("platform"), col("hardware"))
        .agg(
            count("*").alias("build_count"),
            _sum(expr("CASE WHEN success THEN 1 ELSE 0 END")).alias("success_count"),
            avg("duration_seconds").alias("avg_duration_seconds"),
        )
        .withColumn("success_rate", col("success_count") / col("build_count"))
    )

    (
        build_health.writeStream.outputMode("update")
        .foreachBatch(write_batch_to_redis)
        .option("checkpointLocation", "/tmp/devpulse/checkpoints/redis")
        .trigger(processingTime="15 seconds")
        .start()
    )

    spark.streams.awaitAnyTermination()


if __name__ == "__main__":
    main()

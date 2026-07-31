"""
Fleet event producer.

Simulates build/test telemetry across a fake device fleet (macOS, iOS, iPadOS,
watchOS, tvOS x M1/M2/M3/Intel hardware) and publishes events to Kafka.

This stands in for the real signal source in a Core-OS-style system: instead
of pulling from a build farm's real API, we generate statistically realistic
events so the rest of the pipeline (Kafka -> Spark -> Iceberg/Redis -> API ->
dashboard) can be built and demoed end to end.

Run:
    python fleet_event_producer.py --rate 5   # ~5 events/sec
"""
import argparse
import json
import random
import time
import uuid
from datetime import datetime, timezone

from kafka import KafkaProducer

PLATFORMS = ["macOS", "iOS", "iPadOS", "watchOS", "tvOS"]
HARDWARE = {
    "macOS": ["M1", "M2", "M3", "Intel"],
    "iOS": ["A16", "A17", "A18"],
    "iPadOS": ["M1", "M2"],
    "watchOS": ["S9", "S10"],
    "tvOS": ["A15"],
}
BRANCHES = ["main", "release/25.1", "release/25.2", "feature/net-stack", "feature/ui-refresh"]

# Bias a couple of platform/OS combos to be "unhealthy" so the analytics
# layer has something interesting to surface (flaky tests, low build health).
UNHEALTHY_BIAS = {("iPadOS", "M1"): 0.35, ("watchOS", "S9"): 0.28}


def make_build_event() -> dict:
    platform = random.choice(PLATFORMS)
    hw = random.choice(HARDWARE[platform])
    fail_rate = UNHEALTHY_BIAS.get((platform, hw), 0.06)
    success = random.random() > fail_rate

    return {
        "event_type": "build",
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "platform": platform,
        "hardware": hw,
        "branch": random.choice(BRANCHES),
        "commit_sha": uuid.uuid4().hex[:10],
        "duration_seconds": round(random.gauss(420, 90), 1),
        "queue_seconds": round(random.gauss(45, 20), 1),
        "success": success,
        "signing_ok": success and random.random() > 0.02,
    }


def make_test_event(build_event: dict) -> dict:
    platform, hw = build_event["platform"], build_event["hardware"]
    fail_rate = UNHEALTHY_BIAS.get((platform, hw), 0.05)
    flaky = random.random() < fail_rate * 0.6
    passed = random.random() > fail_rate

    return {
        "event_type": "test_run",
        "event_id": str(uuid.uuid4()),
        "build_event_id": build_event["event_id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "platform": platform,
        "hardware": hw,
        "suite": random.choice(["UnitTests", "UITests", "IntegrationTests"]),
        "duration_seconds": round(random.gauss(180, 60), 1),
        "passed": passed,
        "flaky": flaky,
        "crash_on_test": (not passed) and random.random() < 0.15,
    }


def topic_for(platform: str) -> str:
    return f"fleet.events.{platform.lower()}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap-servers", default="localhost:9092")
    parser.add_argument("--rate", type=float, default=3.0, help="events/sec")
    args = parser.parse_args()

    producer = KafkaProducer(
        bootstrap_servers=args.bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8") if k else None,
    )

    print(f"Producing to Kafka at {args.rate} events/sec. Ctrl+C to stop.")
    try:
        while True:
            build = make_build_event()
            producer.send(topic_for(build["platform"]), key=build["platform"], value=build)

            # A build usually triggers 1-3 test suite runs
            for _ in range(random.randint(1, 3)):
                test = make_test_event(build)
                producer.send(topic_for(test["platform"]), key=test["platform"], value=test)

            time.sleep(1 / args.rate)
    except KeyboardInterrupt:
        print("Stopping producer.")
    finally:
        producer.flush()
        producer.close()


if __name__ == "__main__":
    main()

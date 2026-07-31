import os

import redis
from sqlalchemy import create_engine

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))

# WAREHOUSE_URL should point at Snowflake in a real deployment, e.g.
# "snowflake://user:pass@account/devpulse/analytics?warehouse=WH_XS"
# Defaults to a local Postgres so the API runs without Snowflake credentials.
WAREHOUSE_URL = os.environ.get("WAREHOUSE_URL", "postgresql://devpulse:devpulse@localhost:5432/devpulse")

_redis_client = None
_engine = None


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    return _redis_client


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(WAREHOUSE_URL, pool_pre_ping=True)
    return _engine

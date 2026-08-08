import os

from dotenv import load_dotenv
from redis import Redis
from rq import Queue

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

redis_conn = Redis.from_url(REDIS_URL)

# 900s: a full ingest runs ~114s, and RQ's 180s default would kill a slow one.
ingest_queue = Queue("ingest", connection=redis_conn, default_timeout=900)

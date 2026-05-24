import json

import structlog

from app.core.redis_sync import get_redis_sync

log = structlog.get_logger()

CHANNEL_PREFIX = "kama:job_events:"
SEQ_PREFIX = "kama:job_seq:"


def channel_for_job(job_id: str) -> str:
    return f"{CHANNEL_PREFIX}{job_id}"


def next_sequence(job_id: str) -> int:
    r = get_redis_sync()
    return int(r.incr(f"{SEQ_PREFIX}{job_id}"))


def publish_job_event(job_id: str, payload: dict) -> None:
    r = get_redis_sync()
    data = json.dumps(payload, default=str)
    r.publish(channel_for_job(job_id), data)

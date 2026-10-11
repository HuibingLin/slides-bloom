"""Anonymous usage counters and the private owner dashboard."""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone

import redis
from fastapi import HTTPException, Request

FIELDS = ("visits", "uploads", "completed", "failed", "downloads")
PREFIX = "slides-bloom:stats"
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")


def _day() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _increment(connection: redis.Redis, field: str) -> None:
    pipe = connection.pipeline(transaction=True)
    pipe.hincrby(f"{PREFIX}:day:{_day()}", field, 1)
    pipe.hincrby(f"{PREFIX}:total", field, 1)
    pipe.execute()


def record_metric(field: str) -> None:
    """Metrics must not interrupt uploads or downloads when Redis is unavailable."""
    if field not in FIELDS:
        raise ValueError("Unknown metric")
    connection = redis.Redis.from_url(REDIS_URL, socket_connect_timeout=1, socket_timeout=2)
    try:
        _increment(connection, field)
    except redis.RedisError:
        pass
    finally:
        connection.close()


def record_job_outcome(connection: redis.Redis, job_id: str, state: str) -> None:
    """Count a terminal job once, even if Celery redelivers it."""
    field = {"done": "completed", "failed": "failed"}.get(state)
    if not field:
        return
    try:
        if connection.set(f"{PREFIX}:counted:{job_id}", "1", nx=True, ex=48 * 3600):
            _increment(connection, field)
    except redis.RedisError:
        pass


def require_admin(request: Request) -> None:
    token = os.environ.get("ADMIN_TOKEN", "").strip()
    if len(token) < 32:
        raise HTTPException(status_code=503, detail="Private statistics are not configured")
    scheme, _, candidate = request.headers.get("authorization", "").partition(" ")
    valid = scheme.lower() == "bearer" and secrets.compare_digest(
        candidate.encode("utf-8"), token.encode("utf-8"))
    if not valid:
        raise HTTPException(status_code=401, detail="Admin key required",
                            headers={"WWW-Authenticate": "Bearer"})


def snapshot(days: int = 30) -> dict:
    days = max(1, min(days, 90))
    today = datetime.now(timezone.utc).date()
    dates = [(today - timedelta(days=offset)).isoformat() for offset in range(days)]
    connection = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=1, socket_timeout=3)
    try:
        pipe = connection.pipeline(transaction=False)
        pipe.hgetall(f"{PREFIX}:total")
        for day in dates:
            pipe.hgetall(f"{PREFIX}:day:{day}")
        total_raw, *daily_raw = pipe.execute()
    finally:
        connection.close()
    return {
        "timezone": "UTC",
        "days": [
            {"date": day, **{field: int(values.get(field, 0)) for field in FIELDS}}
            for day, values in zip(dates, daily_raw)
        ],
        "total": {field: int(total_raw.get(field, 0)) for field in FIELDS},
    }

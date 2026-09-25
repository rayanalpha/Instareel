"""Tiny Redis-backed pub/sub for realtime dashboard updates + progress tracking."""
import json
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

_channel = "igfunnel:events"


def _client() -> aioredis.Redis:
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def publish(event: str, payload: dict[str, Any]) -> None:
    try:
        client = _client()
        try:
            await client.publish(_channel, json.dumps({"event": event, **payload}))
        finally:
            await client.aclose()
    except Exception:
        pass  # realtime is best-effort; never break the request path


async def set_progress(video_id: int, percentage: float, stage: str) -> None:
    # Same contract as the sync variant: persist for /status polling, never
    # publish per-tick events (see sync_helpers.set_progress_sync).
    try:
        client = _client()
        try:
            await client.set(f"igfunnel:progress:{video_id}", json.dumps({"percentage": percentage, "stage": stage}), ex=3600)
        finally:
            await client.aclose()
    except Exception:
        pass


async def get_progress(video_id: int) -> dict[str, Any] | None:
    try:
        client = _client()
        try:
            raw = await client.get(f"igfunnel:progress:{video_id}")
        finally:
            await client.aclose()
        return json.loads(raw) if raw else None
    except Exception:
        return None

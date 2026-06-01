"""Deep health checks + degradation model for KIA.

`/health` is a cheap liveness probe. This module powers `/health/deep`, which probes
every backing dependency (Redis, Weaviate, FalkorDB, Ollama) in parallel and rolls
them up into one of three degradation levels so the UI and ops can see *what* is
degraded and *whether KIA can still answer*:

    healthy  — everything up.
    degraded — a non-critical dependency is down (history/cache/RAG/graph reduced),
               but KIA can still generate answers.
    critical — KIA cannot generate at all (local LLM down AND no cloud key set).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import redis.asyncio as redis

from brain_core.config import settings
from brain_core.fallback import breaker_states

# Which dependencies, if down, only *degrade* KIA vs. take it *critical*.
# The LLM (ollama) is special-cased in _rollup because a cloud key can cover for it.
_DEGRADING = {"redis", "weaviate", "falkordb"}


async def _timed(coro: Any) -> dict[str, Any]:
    """Run a probe coroutine, returning {status, latency_ms, [error]}."""
    start = time.monotonic()
    try:
        await coro
        return {"status": "up", "latency_ms": round((time.monotonic() - start) * 1000, 1)}
    except Exception as e:
        return {
            "status": "down",
            "latency_ms": round((time.monotonic() - start) * 1000, 1),
            "error": f"{type(e).__name__}: {e}",
        }


async def _check_redis(url: str) -> None:
    client: Any = redis.from_url(url, decode_responses=True)
    try:
        await asyncio.wait_for(client.ping(), timeout=3.0)
    finally:
        try:
            await client.aclose()
        except Exception:
            pass


async def _check_http(url: str) -> None:
    async with httpx.AsyncClient(timeout=3.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()


async def deep_health() -> dict[str, Any]:
    """Probe all dependencies concurrently and roll up a degradation level.

    Native deployment (vector_backend=chroma, storage_backend=sqlite) uses embedded
    stores, so we don't probe Weaviate/Redis/FalkorDB servers — they don't exist and
    would falsely report 'down'. Embedded stores are reported up (in-process).
    """
    ollama_tags = settings.ollama_base_url.rstrip("/") + "/api/tags"
    native_vector = (settings.vector_backend or "weaviate").lower() == "chroma"
    native_storage = (settings.storage_backend or "redis").lower() != "redis"

    names = ["ollama"]
    coros = [_timed(_check_http(ollama_tags))]
    if not native_vector:
        ready_url = settings.weaviate_url.rstrip("/") + "/v1/.well-known/ready"
        names.append("weaviate")
        coros.append(_timed(_check_http(ready_url)))
    if not native_storage:
        names.extend(["redis", "falkordb"])
        coros.append(_timed(_check_redis(settings.redis_url)))
        coros.append(_timed(_check_redis(settings.falkordb_url)))

    results = await asyncio.gather(*coros)
    components = dict(zip(names, results, strict=True))
    if native_vector:
        components["vector"] = {"status": "up", "backend": "chroma (embedded)"}
    if native_storage:
        components["storage"] = {"status": "up", "backend": "sqlite (embedded)"}
    level, reasons = _rollup(components)
    return {
        "status": level,
        "reasons": reasons,
        "components": components,
        "breakers": breaker_states(),
        "llm_cloud_fallback": bool(
            settings.anthropic_api_key or settings.openai_api_key or settings.mistral_api_key
        ),
        "timestamp": time.time(),
    }


def _rollup(components: dict[str, dict[str, Any]]) -> tuple[str, list[str]]:
    """Collapse per-component status into a single level + human reasons."""
    reasons: list[str] = []
    level = "healthy"

    has_cloud = bool(
        settings.anthropic_api_key or settings.openai_api_key or settings.mistral_api_key
    )
    ollama_down = components.get("ollama", {}).get("status") == "down"
    if ollama_down and not has_cloud:
        level = "critical"
        reasons.append("Local LLM (Ollama) is down and no cloud fallback key is configured.")
    elif ollama_down:
        level = "degraded"
        reasons.append("Local LLM (Ollama) is down; using cloud fallback.")

    degraded_map = {
        "redis": "Conversation history and caching are unavailable.",
        "weaviate": "Knowledge retrieval (RAG) is unavailable; answers won't cite indexed docs.",
        "falkordb": "Knowledge-graph (GraphRAG) features are unavailable.",
    }
    for dep in _DEGRADING:
        if components.get(dep, {}).get("status") == "down":
            reasons.append(degraded_map[dep])
            if level == "healthy":
                level = "degraded"

    if not reasons:
        reasons.append("All systems operational.")
    return level, reasons

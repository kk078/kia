"""Load test for the KIA API: throughput, latency percentiles, rate-limit behavior.

Dependency-light (httpx + stdlib). Run with the agents venv python:

    python scripts/load_test.py --base-url http://localhost:8010 --seconds 15 --concurrency 20

Two phases:
1. Throughput: hammer /health (auth/rate-limit exempt) with N concurrent
   workers for S seconds; report RPS and latency percentiles.
2. Rate limiter: burst /api/v1/status until 429; verify the limiter trips at
   the configured RATE_LIMIT_PER_MINUTE and sends Retry-After.
"""

import argparse
import asyncio
import statistics
import time

import httpx


async def _throughput_worker(
    client: httpx.AsyncClient, url: str, deadline: float, latencies: list[float], errors: list[str]
) -> None:
    while time.monotonic() < deadline:
        start = time.monotonic()
        try:
            r = await client.get(url)
            if r.status_code != 200:
                errors.append(f"HTTP {r.status_code}")
            latencies.append((time.monotonic() - start) * 1000)
        except Exception as e:  # noqa: BLE001 - record and continue
            errors.append(type(e).__name__)


def _pct(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    idx = min(len(sorted_values) - 1, int(len(sorted_values) * p))
    return sorted_values[idx]


async def run_throughput(base_url: str, seconds: int, concurrency: int) -> dict[str, float | int]:
    latencies: list[float] = []
    errors: list[str] = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        deadline = time.monotonic() + seconds
        await asyncio.gather(
            *(
                _throughput_worker(client, f"{base_url}/health", deadline, latencies, errors)
                for _ in range(concurrency)
            )
        )
    latencies.sort()
    total = len(latencies)
    return {
        "requests": total,
        "errors": len(errors),
        "rps": round(total / seconds, 1),
        "p50_ms": round(_pct(latencies, 0.50), 1),
        "p95_ms": round(_pct(latencies, 0.95), 1),
        "p99_ms": round(_pct(latencies, 0.99), 1),
        "max_ms": round(latencies[-1], 1) if latencies else 0.0,
        "mean_ms": round(statistics.fmean(latencies), 1) if latencies else 0.0,
    }


async def run_rate_limit_probe(base_url: str, burst: int) -> dict[str, int | str | None]:
    ok = 0
    limited = 0
    first_429_at: int | None = None
    retry_after: str | None = None
    async with httpx.AsyncClient(timeout=10.0) as client:
        for i in range(burst):
            r = await client.get(f"{base_url}/api/v1/status")
            if r.status_code == 200:
                ok += 1
            elif r.status_code == 429:
                limited += 1
                if first_429_at is None:
                    first_429_at = i + 1
                    retry_after = r.headers.get("Retry-After")
    return {"ok": ok, "limited": limited, "first_429_at": first_429_at, "retry_after": retry_after}


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8010")
    parser.add_argument("--seconds", type=int, default=15)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--burst", type=int, default=150)
    parser.add_argument("--skip-rate-limit", action="store_true")
    args = parser.parse_args()

    print(f"# Load test against {args.base_url}")
    print(f"\n## Throughput: /health, {args.concurrency} workers x {args.seconds}s")
    result = await run_throughput(args.base_url, args.seconds, args.concurrency)
    for k, v in result.items():
        print(f"  {k}: {v}")

    if not args.skip_rate_limit:
        print(f"\n## Rate limiter: /api/v1/status burst of {args.burst}")
        probe = await run_rate_limit_probe(args.base_url, args.burst)
        for k, v in probe.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    asyncio.run(main())

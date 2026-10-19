"""Measure API latency and error rate under a bounded async concurrency budget."""
from __future__ import annotations

import argparse
import asyncio
import json
import platform
import sys
import time
from dataclasses import dataclass
from statistics import quantiles

import httpx


@dataclass(frozen=True)
class Sample:
    status_code: int
    elapsed_ms: float


async def _request(client: httpx.AsyncClient, url: str, semaphore: asyncio.Semaphore) -> Sample:
    async with semaphore:
        started = time.perf_counter()
        try:
            response = await client.get(url)
            status_code = response.status_code
        except httpx.HTTPError:
            status_code = 0
        return Sample(status_code=status_code, elapsed_ms=(time.perf_counter() - started) * 1000)


def _summarize(
    samples: list[Sample],
    *,
    url: str,
    concurrency: int,
    timeout: float,
    duration_seconds: float | None = None,
) -> dict:
    if not samples:
        raise ValueError("benchmark did not collect any requests")
    latencies = sorted(sample.elapsed_ms for sample in samples)
    successful = sum(200 <= sample.status_code < 400 for sample in samples)
    p95 = quantiles(latencies, n=20, method="inclusive")[18] if len(latencies) > 1 else latencies[0]
    result = {
        "target": url,
        "machine": platform.platform(),
        "python": sys.version.split()[0],
        "requests": len(samples),
        "concurrency": concurrency,
        "timeout_seconds": timeout,
        "successful": successful,
        "failed": len(samples) - successful,
        "error_rate": round((len(samples) - successful) / len(samples), 4),
        "latency_ms": {
            "p50": round(latencies[len(latencies) // 2], 2),
            "p95": round(p95, 2),
            "max": round(max(latencies), 2),
        },
        "duration_seconds": None if duration_seconds is None else round(duration_seconds, 2),
    }
    return result


async def run(base_url: str, path: str, requests: int, concurrency: int, timeout: float) -> dict:
    url = base_url.rstrip("/") + "/" + path.lstrip("/")
    semaphore = asyncio.Semaphore(concurrency)
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        samples = await asyncio.gather(*(_request(client, url, semaphore) for _ in range(requests)))
    return _summarize(samples, url=url, concurrency=concurrency, timeout=timeout)


async def run_for_duration(
    base_url: str,
    path: str,
    duration_seconds: float,
    concurrency: int,
    timeout: float,
) -> dict:
    """Run bounded workers until the requested duration expires."""
    url = base_url.rstrip("/") + "/" + path.lstrip("/")
    semaphore = asyncio.Semaphore(concurrency)
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    started = time.perf_counter()
    deadline = started + duration_seconds

    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        async def worker() -> list[Sample]:
            worker_samples: list[Sample] = []
            while time.perf_counter() < deadline:
                worker_samples.append(await _request(client, url, semaphore))
            return worker_samples

        worker_samples = await asyncio.gather(*(worker() for _ in range(concurrency)))

    samples = [sample for group in worker_samples for sample in group]
    elapsed = time.perf_counter() - started
    return _summarize(
        samples,
        url=url,
        concurrency=concurrency,
        timeout=timeout,
        duration_seconds=elapsed,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure bounded API latency and error rate")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--path", default="/api/dashboard?product_id=1&store_id=1")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument(
        "--duration-seconds",
        type=float,
        default=0,
        help="持续压测时长；大于 0 时忽略 --requests，直到时长结束",
    )
    args = parser.parse_args()
    if args.requests <= 0 or args.concurrency <= 0 or args.timeout <= 0 or args.duration_seconds < 0:
        parser.error("requests、concurrency 和 timeout 必须大于 0，duration-seconds 不能小于 0")
    if args.duration_seconds > 0:
        result = asyncio.run(
            run_for_duration(args.base_url, args.path, args.duration_seconds, args.concurrency, args.timeout)
        )
    else:
        result = asyncio.run(run(args.base_url, args.path, args.requests, args.concurrency, args.timeout))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

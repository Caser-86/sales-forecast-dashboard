# Docker and Performance Evidence

This record covers the local Docker Desktop run on 2026-09-15 after the security and deployment fixes. Docker Engine reported Linux server version `29.7.2`.

## Image and Compose verification

```text
docker compose build --no-cache backend -> success
backend image digest -> sha256:a14f2711e32d6cf2250f24fbef9381240d1da76b35cb63293ccf150e04b451bb
backend container -> healthy
frontend container -> healthy
```

The rebuilt backend image file list contains application code and `requirements.txt`, but no `.env`, database backup, runtime data, inventory snapshot, saved model, logs, tests, or pytest cache. `python -m pip check` inside the image returned `No broken requirements found.`

The Compose healthcheck uses `127.0.0.1` for nginx. A previous `localhost` probe resolved to IPv6 `::1` and incorrectly marked the otherwise reachable frontend unhealthy; the fixed probe remained `healthy`.

PowerShell endpoint verification against the running Compose stack returned HTTP 200 for `/`, `/health`, `/live`, `/api/products`, `/api/dashboard`, `/api/inventory`, `/api/kpi`, `/api/forecast`, `/api/sales`, `/api/stores`, `/api/metadata`, and frontend port `3000`. An unknown sales combination returned HTTP 404.

For outage injection, stopping `sales-backend` produced a refused backend health connection and frontend `/api/products` returned `502`; starting the backend again returned to `healthy` and `/health=200`.

## Dependency scan

The container-local `pip-audit 2.7.3` scan reported no known vulnerabilities after upgrading FastAPI, Starlette, LightGBM, pip, setuptools, and `torch==2.14.0+cpu`. The requirements audit uses the OSV service and both PyPI and the PyTorch CPU index, so the CPU wheel is resolved from its actual source rather than treated as an un-auditable PyPI-only package.

## Constrained performance

The backend container was constrained with Docker cgroups to `4` CPUs and `8 GiB` memory (`NanoCPUs=4000000000`, `Memory=8589934592`, `MemorySwap=8589934592`).

```text
Warm /api/model-info, 100 requests, concurrency 10:
  successful=100, failed=0, error_rate=0.0, p95=58.61ms

Cold /api/dashboard?product_id=1 after backend restart:
  successful=1, failed=0, p95=235.92ms

Five-minute dashboard run, concurrency 10, rate limit disabled for capacity measurement:
  duration=300s, requests=1500, failed=0, error_rate=0.0
  p95=247.88ms, max=1007.54ms
  memory=327.6-364.8MB, first=340.5MB, last=331.0MB
```

The production default was restored after the capacity run: `RATE_LIMIT_ENABLED=true`, `RATE_LIMIT_REQUESTS=100`, and `RATE_LIMIT_WINDOW_SECONDS=60`. A separate default-limit run produced HTTP 429 responses as designed; those responses are not counted as service-capacity failures.

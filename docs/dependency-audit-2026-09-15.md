# Dependency Audit Evidence

The backend image was rebuilt from the pinned requirements on 2026-09-15. The installed versions were:

```text
fastapi 0.141.1
starlette 1.6.0
lightgbm 4.6.0
pip 26.2.1
setuptools 84.0.0
torch 2.5.1+cpu
```

`pip-audit 2.7.3 --local --format json` reported `No known vulnerabilities found` for all auditable installed packages. The only skipped item was:

```text
torch Dependency not found on PyPI and could not be audited: torch (2.5.1+cpu)
```

Running the requirements audit with both PyPI and the PyTorch CPU index produced the same explicit skip, so this is retained as an open exception rather than silently suppressed. The remaining package findings from the first scan were resolved by the version upgrades above.

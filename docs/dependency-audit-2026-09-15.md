# Dependency Audit Evidence

The backend image was rebuilt from the pinned requirements on 2026-09-15. The installed versions were:

```text
fastapi 0.141.1
starlette 1.6.0
lightgbm 4.6.0
pip 26.2.1
setuptools 84.0.0
torch 2.14.0+cpu
```

`pip-audit 2.7.3` with the OSV service reported no known vulnerabilities for the audited installed packages. The precise CPU wheel was also audited from the PyTorch CPU index with:

```text
pip-audit -r backend/requirements.txt --vulnerability-service osv \
  --index-url https://pypi.org/simple \
  --extra-index-url https://download.pytorch.org/whl/cpu --strict
No known vulnerabilities found
```

The previous `torch==2.5.1+cpu` pin was replaced after OSV identified PyTorch advisories with fixes at newer versions. The container and CI audit now resolve the CPU wheel through the explicit PyTorch index instead of treating its PyPI absence as a silent skip.

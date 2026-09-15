"""Deployment context contract tests."""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_backend_docker_context_excludes_runtime_and_secret_files():
    rules = (PROJECT_ROOT / "backend" / ".dockerignore").read_text(encoding="utf-8").splitlines()

    assert ".env" in rules
    assert "logs/" in rules
    assert "data/raw/" in rules
    assert "data/processed/" in rules
    assert "ml/saved_models/" in rules
    assert "tests/" in rules


def test_frontend_docker_context_excludes_development_files():
    rules = (PROJECT_ROOT / "frontend" / ".dockerignore").read_text(encoding="utf-8").splitlines()

    assert ".env" in rules
    assert "node_modules/" in rules
    assert ".git/" in rules
    assert "*.md" in rules


def test_frontend_image_installs_same_origin_proxy():
    dockerfile = (PROJECT_ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")
    nginx = (PROJECT_ROOT / "frontend" / "nginx.conf").read_text(encoding="utf-8")

    assert "COPY nginx.conf /etc/nginx/conf.d/default.conf" in dockerfile
    assert "proxy_pass http://backend:8000;" in nginx
    assert "location /api/" in nginx


def test_compose_persists_plan_database_and_frontend_waits_for_backend():
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "DATABASE_URL=${DATABASE_URL:-sqlite:////app/data/dashboard.db}" in compose
    assert "condition: service_healthy" in compose
    assert "healthcheck:" in compose

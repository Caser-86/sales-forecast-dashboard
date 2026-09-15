"""Deployment context contract tests."""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_backend_docker_context_excludes_runtime_and_secret_files():
    rules = (PROJECT_ROOT / "backend" / ".dockerignore").read_text(encoding="utf-8").splitlines()

    assert ".env" in rules
    assert "data/" in rules
    assert "logs/" in rules
    assert "data/raw/" in rules
    assert "data/processed/" in rules
    assert "ml/saved_models/" in rules
    assert "*.db.bak" in rules
    assert ".pytest_cache/" in rules
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
    assert '"http://127.0.0.1/"' in compose


def test_compose_uses_a_persistent_named_volume_for_container_logs():
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "- backend_logs:/app/logs" in compose
    assert "backend_logs:" in compose
    assert "- ./backend/logs:/app/logs" not in compose


def test_deploy_script_uses_current_compose_and_fails_closed():
    script = (PROJECT_ROOT / "scripts" / "deploy.sh").read_text(encoding="utf-8")

    assert script.startswith("#!/bin/bash")
    assert "docker compose build" in script
    assert "docker-compose" not in script
    assert 'BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"' in script
    assert 'FRONTEND_URL="${FRONTEND_URL:-http://127.0.0.1:3000}"' in script
    assert '"${BACKEND_URL}/health"' in script
    assert '"${PROJECT_DIR}/scripts/verify_deployment.sh" "$BACKEND_URL"' in script
    assert "exit 1" in script

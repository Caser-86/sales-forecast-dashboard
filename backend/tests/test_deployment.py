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

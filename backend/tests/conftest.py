"""pytest 共享 fixtures。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# 注入 backend 到 sys.path，使测试可直接 import app
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "ml"))

# 测试环境：禁用认证，使用 DEBUG 日志
os.environ.setdefault("ENV", "test")
os.environ.setdefault("API_TOKEN", "")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    """FastAPI 测试客户端（session 级，所有测试共享）。"""
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_product_id():
    return 1


@pytest.fixture
def sample_store_id():
    return 1


@pytest.fixture
def invalid_product_id():
    return 99999


@pytest.fixture
def invalid_store_id():
    return 99999

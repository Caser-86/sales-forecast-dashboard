"""安全与中间件测试。"""
from __future__ import annotations

import pytest
from app.core.config import settings


class TestCors:
    def test_cors_allowed_origin(self, client):
        """白名单内的源应返回 CORS 头。"""
        r = client.get("/api/products", headers={"Origin": "http://localhost:3000"})
        assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"

        loopback = client.get("/api/products", headers={"Origin": "http://127.0.0.1:5500"})
        assert loopback.headers.get("access-control-allow-origin") == "http://127.0.0.1:5500"

    def test_cors_disallowed_origin(self, client):
        """白名单外的源不应返回 CORS 头。"""
        r = client.get("/api/products", headers={"Origin": "http://evil.com"})
        assert r.headers.get("access-control-allow-origin") is None


class TestRequestLogMiddleware:
    def test_request_id_header_returned(self, client):
        """响应包含 X-Request-ID 头。"""
        r = client.get("/api/products")
        assert "x-request-id" in r.headers

    def test_response_time_header_returned(self, client):
        """响应包含 X-Response-Time-ms 头。"""
        r = client.get("/api/products")
        assert "x-response-time-ms" in r.headers


class TestErrorHandling:
    def test_404_returns_unified_format(self, client, invalid_product_id, sample_store_id):
        """404 错误返回统一格式。"""
        r = client.get("/api/sales", params={
            "product_id": invalid_product_id,
            "store_id": sample_store_id,
            "days": 30,
        })
        assert r.status_code == 404
        body = r.json()
        assert "error" in body
        assert body["error"]["code"] == "NOT_FOUND"
        assert "message" in body["error"]

    def test_422_validation_error(self, client):
        """参数校验失败返回 422。"""
        r = client.get("/api/forecast")
        assert r.status_code == 422

    def test_unknown_path_returns_404(self, client):
        """未知路径返回 404。"""
        r = client.get("/api/nonexistent")
        assert r.status_code == 404


class TestDocsAccess:
    def test_docs_available_in_dev(self, client):
        """开发环境 /docs 可访问。"""
        r = client.get("/docs")
        assert r.status_code == 200


class TestApiProtection:
    def test_configured_token_protects_business_routes(self, client, monkeypatch):
        """配置 Token 后，业务路由必须拒绝缺失凭据并接受正确凭据。"""
        monkeypatch.setattr(settings, "API_TOKEN", "task-003-token")

        assert client.get("/api/products").status_code == 401
        assert client.get(
            "/api/products",
            headers={settings.API_TOKEN_HEADER: "task-003-token"},
        ).status_code == 200

    def test_configured_rate_limit_returns_429(self, client, monkeypatch):
        """超过配置的请求窗口后，业务路由返回 429。"""
        monkeypatch.setattr(settings, "API_TOKEN", "")
        monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
        monkeypatch.setattr(settings, "RATE_LIMIT_REQUESTS", 0)

        assert client.get("/api/products").status_code == 429

    def test_production_requires_api_token(self, monkeypatch):
        """生产环境未配置 API Token 时拒绝启动。"""
        from app import main

        monkeypatch.setattr(settings, "ENV", "production")
        monkeypatch.setattr(settings, "API_TOKEN", "")
        assert hasattr(main, "validate_runtime_security")
        with pytest.raises(RuntimeError, match="API_TOKEN"):
            main.validate_runtime_security()

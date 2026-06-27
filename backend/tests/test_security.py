"""安全与中间件测试。"""
from __future__ import annotations


class TestCors:
    def test_cors_allowed_origin(self, client):
        """白名单内的源应返回 CORS 头。"""
        r = client.get("/api/products", headers={"Origin": "http://localhost:3000"})
        assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"

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

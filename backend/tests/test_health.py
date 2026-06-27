"""健康检查与根路径测试。"""
from __future__ import annotations


class TestHealth:
    def test_root_returns_ok(self, client):
        """根路径返回服务状态。"""
        r = client.get("/")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["service"] == "sales-forecast-dashboard"

    def test_api_root_lists_endpoints(self, client):
        """/api 返回所有端点列表。"""
        r = client.get("/api")
        assert r.status_code == 200
        endpoints = r.json()["endpoints"]
        assert "/health" in endpoints
        assert "/api/products" in endpoints
        assert "/api/dashboard" in endpoints

    def test_health_returns_detailed_status(self, client):
        """/health 返回深度健康检查。"""
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] in ("healthy", "degraded")
        assert "checks" in body
        assert "sales_data" in body["checks"]
        assert "lstm_model" in body["checks"]
        assert "lightgbm_model" in body["checks"]

    def test_health_checks_all_ok(self, client):
        """健康检查所有依赖项状态应为 ok。"""
        r = client.get("/health")
        body = r.json()
        for name, check in body["checks"].items():
            assert check["status"] == "ok", f"{name} 状态异常: {check}"

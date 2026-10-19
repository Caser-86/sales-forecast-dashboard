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

    def test_health_distinguishes_demo_auth_from_api_token_auth(self, client, monkeypatch):
        """Readiness exposes session auth separately from the legacy API token flag."""
        from app.core.config import settings

        monkeypatch.setattr(settings, "API_TOKEN", "")
        monkeypatch.setattr(settings, "DEMO_AUTH_ENABLED", True)

        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["auth_enabled"] is False
        assert response.json()["demo_auth_enabled"] is True

    def test_health_checks_all_ok(self, client):
        """健康检查所有依赖项状态应为 ok。"""
        r = client.get("/health")
        body = r.json()
        for name, check in body["checks"].items():
            assert check["status"] == "ok", f"{name} 状态异常: {check}"

    def test_health_returns_503_when_required_assets_are_missing(self, client, monkeypatch):
        """就绪检查发现依赖缺失时必须阻止流量进入。"""
        from app.core import health

        monkeypatch.setattr(health, "_file_status", lambda _path: "missing")

        response = client.get("/health")

        assert response.status_code == 503
        assert response.json()["status"] == "degraded"

    def test_liveness_endpoint_stays_available_without_model_assets(self, client, monkeypatch):
        """存活检查只确认进程，不依赖数据和模型文件。"""
        from app.core import health

        monkeypatch.setattr(health, "_file_status", lambda _path: "missing")

        response = client.get("/live")

        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    def test_health_returns_503_when_model_runtime_cannot_load(self, client, monkeypatch):
        """模型文件存在但运行时加载失败时不能宣称 ready。"""
        from app.core import health

        monkeypatch.setattr(health, "_file_status", lambda _path: "ok")
        monkeypatch.setattr(health, "_report_status", lambda _path: "ok")
        monkeypatch.setattr(health, "_model_runtime_status", lambda: "unreadable")

        response = client.get("/health")

        assert response.status_code == 503
        assert response.json()["checks"]["model_runtime"]["status"] == "unreadable"

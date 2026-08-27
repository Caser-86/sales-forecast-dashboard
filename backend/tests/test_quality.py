"""模型报告与数据质量接口测试。"""
from __future__ import annotations


class TestQualityEndpoints:
    def test_model_info_exposes_metrics_and_split(self, client):
        r = client.get("/api/model-info")

        assert r.status_code == 200
        body = r.json()
        assert body["status"] in ("ready", "unavailable")
        assert "metrics" in body
        assert "ensemble" in body["metrics"]
        assert "split" in body

    def test_data_quality_exposes_integrity_checks(self, client):
        r = client.get("/api/data-quality")

        assert r.status_code == 200
        body = r.json()
        assert body["status"] in ("healthy", "warning", "error")
        assert body["rows"] > 0
        assert body["product_count"] == 20
        assert body["store_count"] == 5
        assert "missing_values" in body
        assert "date_gap_count" in body
        assert "issues" in body


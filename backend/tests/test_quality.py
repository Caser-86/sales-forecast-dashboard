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
        assert "backtest" in body
        if body["backtest"]:
            backtest = body["backtest"]
            assert backtest["protocol"]["horizon_days"] == 30
            assert backtest["protocol"]["origin_count"] > 0
            assert backtest["lstm"]["samples"] > 0
            assert len(backtest["lstm"]["per_horizon"]) == 30
            assert backtest["lstm"]["segments"]

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

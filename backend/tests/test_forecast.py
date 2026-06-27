"""预测接口测试。"""
from __future__ import annotations


class TestForecast:
    def test_get_forecast(self, client, sample_product_id, sample_store_id):
        """获取 30 天预测结果。"""
        r = client.get("/api/forecast", params={
            "product_id": sample_product_id,
            "store_id": sample_store_id,
        })
        assert r.status_code == 200
        body = r.json()
        assert body["product_id"] == sample_product_id
        assert body["store_id"] == sample_store_id
        assert len(body["forecast"]) == 30

    def test_forecast_fields(self, client, sample_product_id, sample_store_id):
        """预测记录字段完整。"""
        r = client.get("/api/forecast", params={
            "product_id": sample_product_id,
            "store_id": sample_store_id,
        })
        f = r.json()["forecast"][0]
        assert "date" in f
        assert "predicted_sales" in f
        assert "confidence_low" in f
        assert "confidence_high" in f

    def test_forecast_confidence_range(self, client, sample_product_id, sample_store_id):
        """置信区间下界 <= 预测值 <= 上界。"""
        r = client.get("/api/forecast", params={
            "product_id": sample_product_id,
            "store_id": sample_store_id,
        })
        for f in r.json()["forecast"]:
            assert f["confidence_low"] <= f["predicted_sales"] <= f["confidence_high"]

    def test_forecast_abc_class_valid(self, client, sample_product_id, sample_store_id):
        """ABC 分级取值合法。"""
        r = client.get("/api/forecast", params={
            "product_id": sample_product_id,
            "store_id": sample_store_id,
        })
        abc = r.json()["abc_class"]
        assert abc in ("A", "B", "C")

    def test_forecast_total_predicted_positive(self, client, sample_product_id, sample_store_id):
        """预测总量为正数。"""
        r = client.get("/api/forecast", params={
            "product_id": sample_product_id,
            "store_id": sample_store_id,
        })
        assert r.json()["total_predicted"] > 0

    def test_forecast_suggested_ge_total(self, client, sample_product_id, sample_store_id):
        """建议采购量 >= 预测总量（含安全库存）。"""
        r = client.get("/api/forecast", params={
            "product_id": sample_product_id,
            "store_id": sample_store_id,
        })
        body = r.json()
        assert body["suggested_purchase"] >= body["total_predicted"]

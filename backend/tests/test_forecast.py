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
        assert f["range_type"] == "scenario"

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

    def test_forecast_rejects_negative_ids(self, client):
        """预测 ID 必须在请求校验阶段拒绝负数。"""
        response = client.get("/api/forecast", params={"product_id": -1, "store_id": 1})

        assert response.status_code == 422

    def test_forecast_returns_404_for_unknown_product(self, client):
        """不存在的商品应返回明确的 404，而不是模型内部错误。"""
        response = client.get("/api/forecast", params={"product_id": 99999, "store_id": 1})

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    def test_forecast_returns_503_when_history_is_insufficient(self, client, monkeypatch):
        from app.api import forecast

        monkeypatch.setattr(
            forecast.data_service,
            "get_products",
            lambda: [{"product_id": 1, "product_name": "P1"}],
        )
        monkeypatch.setattr(
            forecast.data_service,
            "get_stores",
            lambda: [{"store_id": 1, "store_name": "S1"}],
        )
        monkeypatch.setattr(
            forecast.forecast_service,
            "get_forecast",
            lambda _product_id, _store_id: (_ for _ in ()).throw(ValueError("历史数据不足")),
        )

        response = client.get("/api/forecast", params={"product_id": 1, "store_id": 1})

        assert response.status_code == 503
        assert response.json()["error"]["code"] == "FORECAST_UNAVAILABLE"

"""历史销量接口测试。"""
from __future__ import annotations


class TestSales:
    def test_get_sales_history(self, client, sample_product_id, sample_store_id):
        """获取商品 1 在门店 1 的历史销量。"""
        r = client.get("/api/sales", params={
            "product_id": sample_product_id,
            "store_id": sample_store_id,
            "days": 30,
        })
        assert r.status_code == 200
        body = r.json()
        assert "points" in body
        assert len(body["points"]) > 0
        assert len(body["points"]) <= 30

    def test_sales_history_fields(self, client, sample_product_id, sample_store_id):
        """历史记录字段完整。"""
        r = client.get("/api/sales", params={
            "product_id": sample_product_id,
            "store_id": sample_store_id,
            "days": 7,
        })
        rec = r.json()["points"][0]
        assert "date" in rec
        assert "sales" in rec
        assert "price" in rec
        assert "is_promotion" in rec
        assert "is_holiday" in rec
        assert "is_weekend" in rec

    def test_sales_invalid_product_returns_404(self, client, invalid_product_id, sample_store_id):
        """不存在的商品返回 404 与统一错误格式。"""
        r = client.get("/api/sales", params={
            "product_id": invalid_product_id,
            "store_id": sample_store_id,
            "days": 30,
        })
        assert r.status_code == 404
        body = r.json()
        assert "error" in body
        assert body["error"]["code"] == "NOT_FOUND"
        assert "不存在" in body["error"]["message"]

    def test_sales_invalid_store_returns_404(self, client, sample_product_id, invalid_store_id):
        """不存在的门店返回 404。"""
        r = client.get("/api/sales", params={
            "product_id": sample_product_id,
            "store_id": invalid_store_id,
            "days": 30,
        })
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "NOT_FOUND"

    def test_sales_missing_param_returns_422(self, client):
        """缺少必填参数返回 422 校验错误。"""
        r = client.get("/api/sales", params={"product_id": 1})
        assert r.status_code == 422

    def test_sales_days_boundary(self, client, sample_product_id, sample_store_id):
        """days=1 边界值。"""
        r = client.get("/api/sales", params={
            "product_id": sample_product_id,
            "store_id": sample_store_id,
            "days": 1,
        })
        assert r.status_code == 200
        assert len(r.json()["points"]) <= 1

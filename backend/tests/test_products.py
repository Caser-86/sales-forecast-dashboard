"""商品列表接口测试。"""
from __future__ import annotations


class TestProducts:
    def test_get_products_returns_list(self, client):
        """商品列表接口返回 20 个商品。"""
        r = client.get("/api/products")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 20
        assert len(body["products"]) == 20

    def test_product_fields(self, client):
        """商品对象包含必要字段。"""
        r = client.get("/api/products")
        p = r.json()["products"][0]
        assert "product_id" in p
        assert "product_name" in p
        assert "category" in p
        assert "base_price" in p

    def test_product_ids_are_unique_and_sorted(self, client):
        """商品 ID 唯一且升序。"""
        r = client.get("/api/products")
        ids = [p["product_id"] for p in r.json()["products"]]
        assert ids == sorted(ids)
        assert len(set(ids)) == len(ids)

    def test_categories_cover_5_types(self, client):
        """商品覆盖 5 个品类。"""
        r = client.get("/api/products")
        cats = {p["category"] for p in r.json()["products"]}
        assert len(cats) == 5

    def test_products_support_search_and_pagination(self, client, monkeypatch):
        from app.api import products

        monkeypatch.setattr(products.data_service, "get_products", lambda: [
            {"product_id": 1, "product_name": "苹果", "category": "食品", "base_price": 1.0},
            {"product_id": 2, "product_name": "香蕉", "category": "食品", "base_price": 2.0},
            {"product_id": 3, "product_name": "洗衣液", "category": "日化", "base_price": 3.0},
        ])

        response = client.get("/api/products?search=食&page=2&page_size=1")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert len(body["products"]) == 1
        assert body["products"][0]["product_id"] == 2

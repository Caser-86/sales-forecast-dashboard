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

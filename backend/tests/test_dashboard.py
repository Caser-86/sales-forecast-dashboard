"""大屏聚合接口测试。"""
from __future__ import annotations


class TestDashboard:
    def test_dashboard_returns_kpi(self, client):
        """大屏接口返回 KPI。"""
        r = client.get("/api/dashboard")
        assert r.status_code == 200
        body = r.json()
        assert "kpi" in body
        kpi = body["kpi"]
        assert "total_sales" in kpi
        assert "total_predicted" in kpi
        assert "growth_rate" in kpi
        assert "accuracy" in kpi
        # abc_distribution 在根级
        assert "abc_distribution" in body

    def test_dashboard_kpi_accuracy_near_90(self, client):
        """模型准确率应接近 90%（MAPE 9.91%）。"""
        r = client.get("/api/dashboard")
        accuracy = r.json()["kpi"]["accuracy"]
        assert 80 <= accuracy <= 100, f"准确率异常: {accuracy}"

    def test_dashboard_abc_distribution_sums_to_20(self, client):
        """ABC 分布总数 = 商品数 = 20。"""
        r = client.get("/api/dashboard")
        body = r.json()
        total = sum(body["abc_distribution"].values())
        assert total == body["kpi"]["sku_count"] == 20

    def test_dashboard_category_sales(self, client):
        """品类销量数据。"""
        r = client.get("/api/dashboard")
        body = r.json()
        assert "category_sales" in body
        assert len(body["category_sales"]) == 5

    def test_dashboard_top_products(self, client):
        """Top 10 商品。"""
        r = client.get("/api/dashboard")
        body = r.json()
        assert "top_products" in body
        assert len(body["top_products"]) == 10


class TestInventory:
    def test_inventory_returns_cells(self, client):
        """库存接口返回 100 个单元格 (20×5)。"""
        r = client.get("/api/inventory")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 100
        assert len(body["cells"]) == 100

    def test_inventory_cell_fields(self, client):
        """单元格字段完整。"""
        r = client.get("/api/inventory")
        cell = r.json()["cells"][0]
        assert "product_id" in cell
        assert "store_id" in cell
        assert "predicted_sales" in cell
        assert "suggested_purchase" in cell
        assert "abc_class" in cell
        assert "risk_level" in cell

    def test_inventory_risk_summary(self, client):
        """风险分布总和 = 100。"""
        r = client.get("/api/inventory")
        body = r.json()
        risk = body["risk_summary"]
        assert risk["high"] + risk["medium"] + risk["low"] == 100

    def test_inventory_risk_level_valid(self, client):
        """风险等级取值合法。"""
        r = client.get("/api/inventory")
        for cell in r.json()["cells"]:
            assert cell["risk_level"] in ("high", "medium", "low")


class TestKpi:
    def test_kpi_endpoint(self, client):
        """/api/kpi 返回 KPI。"""
        r = client.get("/api/kpi")
        assert r.status_code == 200
        body = r.json()
        assert "total_sales" in body
        assert "total_predicted" in body

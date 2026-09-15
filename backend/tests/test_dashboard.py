"""大屏聚合接口测试。"""
from __future__ import annotations


class TestDashboard:
    def test_dashboard_top_product_forecast_is_all_store_sum(self, monkeypatch):
        """Top 商品预测和采购建议应汇总所有门店。"""
        from app.api import dashboard

        products = [{
            "product_id": 1,
            "product_name": "P1",
            "category": "服装",
            "base_price": 10.0,
        }]
        stores = [
            {"store_id": 1, "store_name": "S1"},
            {"store_id": 2, "store_name": "S2"},
        ]
        forecasts = [
            {
                "product_id": 1,
                "product_name": "P1",
                "category": "服装",
                "store_id": 1,
                "store_name": "S1",
                "total_predicted": 10,
                "suggested_purchase": 11,
                "abc_class": "A",
                "forecast": [],
            },
            {
                "product_id": 1,
                "product_name": "P1",
                "category": "服装",
                "store_id": 2,
                "store_name": "S2",
                "total_predicted": 20,
                "suggested_purchase": 22,
                "abc_class": "B",
                "forecast": [],
            },
        ]
        monkeypatch.setattr(dashboard.data_service, "get_products", lambda: products)
        monkeypatch.setattr(dashboard.data_service, "get_stores", lambda: stores)
        monkeypatch.setattr(dashboard.data_service, "get_total_sales_last_n", lambda days: 30)
        aggregate_windows = []
        monkeypatch.setattr(
            dashboard.data_service,
            "get_recent_product_demand",
            lambda days: {1: 30},
            raising=False,
        )
        monkeypatch.setattr(
            dashboard.data_service,
            "load_report",
            lambda: {"ensemble": {"mape": 10}},
        )
        monkeypatch.setattr(
            dashboard.data_service,
            "get_top_products",
            lambda n, product_id=None, store_id=None, days=30: aggregate_windows.append(days) or [{
                "product_id": 1,
                "product_name": "P1",
                "category": "服装",
                "sales": 100,
            }],
        )
        monkeypatch.setattr(
            dashboard.data_service,
            "get_category_sales",
            lambda product_id=None, store_id=None, days=30: aggregate_windows.append(days) or [{
                "category": "服装", "sales": 100, "ratio": 1.0,
            }],
        )
        monkeypatch.setattr(
            dashboard.forecast_service,
            "get_forecast_all",
            lambda p, s: forecasts,
        )

        result = dashboard.get_dashboard()

        assert result["top_products"][0]["predicted"] == 30
        assert result["top_products"][0]["suggested_purchase"] == 33
        assert aggregate_windows == [30, 30]

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
        assert "mape" in kpi
        assert kpi["window"]["unit"] == "units"
        assert kpi["window"]["historical_days"] == 30
        assert kpi["window"]["forecast_days"] == 30
        # abc_distribution 在根级
        assert "abc_distribution" in body

    def test_dashboard_kpi_accuracy_near_90(self, client):
        """模型准确率应保持在可接受范围内。"""
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

    def test_dashboard_scope_filters_product_and_store(self, client):
        """筛选后的 KPI 与 Top 商品应只使用指定商品和门店。"""
        r = client.get("/api/dashboard", params={"product_id": 1, "store_id": 1})

        assert r.status_code == 200
        body = r.json()
        assert body["kpi"]["sku_count"] == 1
        assert len(body["top_products"]) == 1
        assert body["top_products"][0]["product_id"] == 1

    def test_dashboard_reports_partial_forecast_coverage(self, client, monkeypatch):
        """部分预测失败时返回覆盖率，而不是静默丢弃失败项。"""
        from app.services import forecast_service

        monkeypatch.setattr(
            forecast_service,
            "get_forecast_all",
            lambda _products, _stores: [
                {
                    "product_id": 1,
                    "product_name": "P1",
                    "category": "服装",
                    "store_id": 1,
                    "store_name": "S1",
                    "total_predicted": 10,
                    "suggested_purchase": 11,
                    "abc_class": "A",
                    "forecast": [],
                },
                {"product_id": 1, "store_id": 2, "error": "model unavailable"},
            ],
        )

        response = client.get("/api/dashboard", params={"product_id": 1})

        assert response.status_code == 200
        assert response.json()["coverage"] == {
            "status": "partial",
            "requested": 2,
            "succeeded": 1,
            "failed": 1,
        }

    def test_dashboard_returns_503_when_all_forecasts_fail(self, client, monkeypatch):
        """所有预测失败时不能返回总量为零的正常大屏。"""
        from app.services import forecast_service

        monkeypatch.setattr(
            forecast_service,
            "get_forecast_all",
            lambda _products, _stores: [{"product_id": 1, "store_id": 1, "error": "model unavailable"}],
        )

        response = client.get("/api/dashboard", params={"product_id": 1, "store_id": 1})

        assert response.status_code == 503
        assert response.json()["error"]["code"] == "FORECAST_UNAVAILABLE"

    def test_dashboard_scope_uses_global_abc_population(self, monkeypatch):
        """筛选商品后，ABC等级仍来自固定的全量商品总体。"""
        from app.api import dashboard

        demand_calls = []
        monkeypatch.setattr(dashboard.data_service, "get_total_sales_last_n", lambda *args: 10)
        monkeypatch.setattr(
            dashboard.data_service,
            "get_recent_product_demand",
            lambda *args: demand_calls.append(args) or {1: 95, 2: 5},
        )
        monkeypatch.setattr(
            dashboard.data_service,
            "load_report",
            lambda: {"ensemble": {"mape": 10}},
        )
        monkeypatch.setattr(
            dashboard.data_service,
            "get_metric_window",
            lambda *_args: {
                "unit": "units",
                "historical_start": "2025-01-01",
                "historical_end": "2025-01-30",
                "historical_days": 30,
                "forecast_start": "2025-01-31",
                "forecast_end": "2025-03-01",
                "forecast_days": 30,
            },
        )

        result = dashboard._compute_kpi(
            all_f=[{"total_predicted": 12}],
            products=[{"product_id": 1}],
            stores=[{"store_id": 1}],
            product_id=1,
            store_id=1,
        )

        assert result["abc_distribution"] == {"A": 1, "B": 0, "C": 0}
        assert demand_calls == [(30,)]


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

    def test_inventory_scope_filters_product_and_store(self, client):
        r = client.get("/api/inventory", params={"product_id": 1, "store_id": 1})

        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["cells"][0]["product_id"] == 1
        assert body["cells"][0]["store_id"] == 1


class TestKpi:
    def test_kpi_endpoint(self, client):
        """/api/kpi 返回 KPI。"""
        r = client.get("/api/kpi")
        assert r.status_code == 200
        body = r.json()
        assert "total_sales" in body
        assert "total_predicted" in body

"""Pydantic 响应模型"""
from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel


class Product(BaseModel):
    product_id: int
    product_name: str
    category: str
    base_price: float


class ProductList(BaseModel):
    total: int
    products: List[Product]


class SalesPoint(BaseModel):
    date: str
    sales: int
    price: float
    is_promotion: int
    is_holiday: int
    is_weekend: int


class SalesHistory(BaseModel):
    product_id: int
    store_id: int
    points: List[SalesPoint]


class ForecastPoint(BaseModel):
    date: str
    predicted_sales: int
    confidence_low: int
    confidence_high: int


class ForecastResult(BaseModel):
    product_id: int
    store_id: int
    forecast: List[ForecastPoint]
    total_predicted: int
    suggested_purchase: int
    abc_class: str


class Kpi(BaseModel):
    total_sales: int
    total_predicted: int
    growth_rate: float
    accuracy: float
    sku_count: int
    alert_count: int


class TopProduct(BaseModel):
    product_id: int
    product_name: str
    category: str
    sales: int
    predicted: int
    suggested_purchase: int
    abc_class: str


class CategorySales(BaseModel):
    category: str
    sales: int
    ratio: float


class DashboardData(BaseModel):
    kpi: Kpi
    abc_distribution: Dict[str, int]
    top_products: List[TopProduct]
    category_sales: List[CategorySales]
    last_updated: str


class InventoryCell(BaseModel):
    product_id: int
    product_name: str
    store_id: int
    store_name: str
    predicted_sales: int
    suggested_purchase: int
    abc_class: str
    risk_level: str  # high / medium / low


class InventoryResult(BaseModel):
    total: int
    cells: List[InventoryCell]
    risk_summary: Dict[str, int]


class KpiResult(BaseModel):
    total_sales: int
    total_predicted: int
    growth_rate: float
    accuracy: float
    sku_count: int
    alert_count: int
    abc_distribution: Dict[str, int]

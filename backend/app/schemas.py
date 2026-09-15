"""Pydantic 响应模型"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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


class MetricWindow(BaseModel):
    unit: str
    historical_start: str
    historical_end: str
    historical_days: int
    forecast_start: str
    forecast_end: str
    forecast_days: int


class ForecastCoverage(BaseModel):
    status: str
    requested: int
    succeeded: int
    failed: int


class Kpi(BaseModel):
    total_sales: int
    total_predicted: int
    growth_rate: float
    accuracy: float
    mape: float
    window: MetricWindow
    coverage: ForecastCoverage
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
    coverage: ForecastCoverage
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
    coverage: ForecastCoverage


class KpiResult(BaseModel):
    total_sales: int
    total_predicted: int
    growth_rate: float
    accuracy: float
    mape: float
    window: MetricWindow
    coverage: ForecastCoverage
    sku_count: int
    alert_count: int
    abc_distribution: Dict[str, int]


class ModelInfoResult(BaseModel):
    status: str
    trained_at_utc: Optional[str] = None
    data_start: Optional[str] = None
    data_end: Optional[str] = None
    horizon_days: int
    feature_count: Optional[int] = None
    ensemble_weights: Dict[str, float] = Field(default_factory=dict)
    split: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Dict[str, float]] = Field(default_factory=dict)


class DataQualityResult(BaseModel):
    status: str
    checked_at: str
    source: str
    rows: int
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    product_count: int
    store_count: int
    missing_values: Dict[str, int] = Field(default_factory=dict)
    duplicate_rows: int
    date_gap_count: int
    negative_sales_count: int
    issues: List[str] = Field(default_factory=list)

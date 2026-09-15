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


class Store(BaseModel):
    store_id: int
    store_name: str


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
    range_type: str = "scenario"


class ForecastResult(BaseModel):
    product_id: int
    store_id: int
    forecast: List[ForecastPoint]
    total_predicted: int
    suggested_purchase: int
    abc_class: str
    range_type: str = "scenario"


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
    inventory_version: Optional[str] = None
    inventory_as_of_date: Optional[str] = None
    window_demand: Optional[float] = None
    net_available: Optional[float] = None
    target_stock: Optional[float] = None
    raw_replenishment: Optional[float] = None
    on_hand: Optional[float] = None
    confirmed_inbound: Optional[float] = None
    reserved: Optional[float] = None
    lead_time_days: Optional[int] = None
    review_period_days: Optional[int] = None
    safety_stock: Optional[float] = None
    pack_size: Optional[int] = None
    minimum_order_quantity: Optional[int] = None


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


class MetadataResult(BaseModel):
    data_version: str
    model_version: str
    inventory_version: str
    as_of_date: Optional[str] = None
    inventory_as_of_date: Optional[str] = None
    inventory_age_days: Optional[int] = None
    inventory_max_age_days: int
    inventory_status: str
    data_status: str
    model_status: str


class PlanCoverage(BaseModel):
    status: str
    requested: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)


class PlanItem(BaseModel):
    product_id: int = Field(ge=1)
    store_id: int = Field(ge=1)
    product_name: str
    store_name: str
    predicted_sales: int = Field(ge=0)
    suggested_purchase: int = Field(ge=0)
    risk_level: str
    on_hand: float = Field(ge=0)
    confirmed_inbound: float = Field(ge=0)
    reserved: float = Field(ge=0)
    lead_time_days: int = Field(ge=0)
    review_period_days: int = Field(ge=0)
    safety_stock: float = Field(ge=0)
    pack_size: int = Field(gt=0)
    minimum_order_quantity: int = Field(ge=0)
    adjustment_quantity: int = Field(default=0)
    adjustment_reason: str = ""


class PlanDraftCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    as_of_date: str
    inventory_as_of_date: str
    data_version: str = Field(min_length=1, max_length=100)
    model_version: str = Field(min_length=1, max_length=100)
    inventory_version: str = Field(min_length=1, max_length=100)
    policy_version: str = Field(min_length=1, max_length=100)
    coverage: PlanCoverage
    items: List[PlanItem] = Field(min_length=1)
    adjustments: List[Dict[str, Any]] = Field(default_factory=list)


class PlanSaveResult(BaseModel):
    plan_id: str
    created: bool
    created_at: str


class PlanSummary(BaseModel):
    plan_id: str
    name: str
    created_at: str
    item_count: int
    data_version: str
    model_version: str
    inventory_version: str
    policy_version: str


class PlanDetail(PlanSummary):
    snapshot: PlanDraftCreate

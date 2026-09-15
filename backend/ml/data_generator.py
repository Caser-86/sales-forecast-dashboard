"""模拟销售数据生成器

基于真实业务逻辑生成 6 个月历史销量数据。
- 商品：20 个 SKU，分 5 个品类（食品、日化、电子、服装、家居）
- 门店：5 家门店
- 时间：2025-01-01 至 2025-06-30（181 天）
"""
from __future__ import annotations

import os
from datetime import date, timedelta

import numpy as np
import pandas as pd

# 固定随机种子，保证可复现
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)

# 项目根目录（backend/ 的上一级）
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
RAW_DIR = os.path.join(BACKEND_DIR, "data", "raw")
OUTPUT_PATH = os.path.join(RAW_DIR, "sales_data.csv")
INVENTORY_OUTPUT_PATH = os.path.join(RAW_DIR, "inventory_snapshot.csv")

REQUIRED_INVENTORY_COLUMNS = (
    "as_of_date",
    "product_id",
    "store_id",
    "on_hand",
    "confirmed_inbound",
    "reserved",
    "lead_time_days",
    "review_period_days",
    "safety_stock",
    "pack_size",
    "minimum_order_quantity",
)

START_DATE = date(2025, 1, 1)
END_DATE = date(2025, 6, 30)
DAYS = (END_DATE - START_DATE).days + 1  # 181 天

# 品类定义：每个品类 4 个 SKU
CATEGORIES = {
    "食品": {"sku_count": 4, "price_range": (8.0, 35.0), "base_range": (60, 200)},
    "日化": {"sku_count": 4, "price_range": (15.0, 60.0), "base_range": (30, 120)},
    "电子": {"sku_count": 4, "price_range": (199.0, 1999.0), "base_range": (10, 60)},
    "服装": {"sku_count": 4, "price_range": (79.0, 399.0), "base_range": (20, 90)},
    "家居": {"sku_count": 4, "price_range": (29.0, 299.0), "base_range": (15, 80)},
}

# 门店：5 家
STORES = [
    {"store_id": 1, "store_name": "北京旗舰店", "weight": 1.15},
    {"store_id": 2, "store_name": "上海中心店", "weight": 1.20},
    {"store_id": 3, "store_name": "广州天河店", "weight": 1.05},
    {"store_id": 4, "store_name": "成都春熙店", "weight": 0.90},
    {"store_id": 5, "store_name": "武汉江汉店", "weight": 0.85},
]

# 2025 年法定节假日（节假日效应）
HOLIDAYS = {
    date(2025, 1, 1), date(2025, 1, 28), date(2025, 1, 29), date(2025, 1, 30),
    date(2025, 1, 31), date(2025, 2, 1), date(2025, 2, 2), date(2025, 2, 3),
    date(2025, 4, 4), date(2025, 4, 5), date(2025, 4, 6),
    date(2025, 5, 1), date(2025, 5, 2), date(2025, 5, 3),
    date(2025, 6, 1), date(2025, 6, 14), date(2025, 6, 15),
}


def _build_product_catalog() -> list[dict]:
    """构建 20 个 SKU 的商品目录。"""
    products = []
    pid = 1
    for cat_name, spec in CATEGORIES.items():
        for _i in range(spec["sku_count"]):
            price_lo, price_hi = spec["price_range"]
            base_lo, base_hi = spec["base_range"]
            # 每个 SKU 的固定属性
            base_price = round(np.random.uniform(price_lo, price_hi), 2)
            base_sales = int(np.random.uniform(base_lo, base_hi))
            # 趋势因子：-1 下降，0 平稳，1 上升
            trend = np.random.choice([-1, 0, 1], p=[0.3, 0.4, 0.3])
            products.append({
                "product_id": pid,
                "product_name": f"{cat_name}-{pid:02d}号商品",
                "category": cat_name,
                "base_price": base_price,
                "base_sales": base_sales,
                "trend": trend,
            })
            pid += 1
    return products


def _is_weekend(d: date) -> bool:
    return d.weekday() >= 5


def _generate_sku_sales(product: dict, store: dict, dates: list[date]) -> list[dict]:
    """为单个 SKU × 门店 生成 181 天销量数据。"""
    rows = []
    base = product["base_sales"] * store["weight"]
    base_price = product["base_price"]
    trend = product["trend"]
    total_days = len(dates)

    for i, d in enumerate(dates):
        # 当日价格：在基准价附近波动 ±5%
        price = round(base_price * (1 + np.random.uniform(-0.05, 0.05)), 2)

        # 是否促销：约 15% 的天数促销
        is_promotion = int(np.random.random() < 0.15)
        # 是否节假日
        is_holiday = int(d in HOLIDAYS)
        # 是否周末
        is_weekend = int(_is_weekend(d))

        # 基础销量 + 趋势
        trend_factor = 1.0
        if trend != 0:
            # 线性趋势：总变化 ±20%
            trend_factor = 1.0 + trend * 0.20 * (i / total_days)

        sales = base * trend_factor

        # 周末效应 +20-40%
        if is_weekend:
            sales *= np.random.uniform(1.20, 1.40)

        # 促销效应 +50-100%
        if is_promotion:
            sales *= np.random.uniform(1.50, 2.00)

        # 节假日效应 +80-150%
        if is_holiday:
            sales *= np.random.uniform(1.80, 2.50)

        # 价格弹性：价格相对基准上涨 10% → 销量下降 5-8%
        price_change = (price - base_price) / base_price
        sales *= (1 - 0.6 * price_change)  # 弹性系数 0.6

        # 竞品价格：基准价的 0.9-1.1 倍
        competitor_price = round(base_price * np.random.uniform(0.90, 1.10), 2)
        # 竞品降价 10% → 本商品销量下降 3-5%
        comp_ratio = competitor_price / base_price
        if comp_ratio < 1.0:
            sales *= (1 - 0.4 * (1.0 - comp_ratio))

        # 随机噪声 ±10%
        sales *= np.random.uniform(0.90, 1.10)

        sales = max(1, int(round(sales)))

        rows.append({
            "date": d.isoformat(),
            "product_id": product["product_id"],
            "product_name": product["product_name"],
            "category": product["category"],
            "store_id": store["store_id"],
            "store_name": store["store_name"],
            "sales": sales,
            "price": price,
            "is_promotion": is_promotion,
            "is_holiday": is_holiday,
            "is_weekend": is_weekend,
            "competitor_price": competitor_price,
        })
    return rows


def generate_sales_data(output_path: str = OUTPUT_PATH) -> str:
    """生成完整销售数据集并写入 CSV。返回输出路径。"""
    products = _build_product_catalog()
    dates = [START_DATE + timedelta(days=i) for i in range(DAYS)]

    all_rows: list[dict] = []
    for product in products:
        for store in STORES:
            all_rows.extend(_generate_sku_sales(product, store, dates))

    df = pd.DataFrame(all_rows)
    # 排序：按 门店 → 商品 → 日期
    df = df.sort_values(["store_id", "product_id", "date"]).reset_index(drop=True)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"[data_generator] 生成 {len(df)} 行数据 → {output_path}")
    print(f"[data_generator] 商品数: {df['product_id'].nunique()}, "
          f"门店数: {df['store_id'].nunique()}, "
          f"日期范围: {df['date'].min()} ~ {df['date'].max()}")
    return output_path


def generate_inventory_snapshot(
    sales_path: str = OUTPUT_PATH,
    output_path: str = INVENTORY_OUTPUT_PATH,
) -> str:
    """Generate a deterministic demo inventory snapshot from recent sales."""
    sales = pd.read_csv(sales_path, parse_dates=["date"])
    if sales.empty:
        raise ValueError("销售数据为空，无法生成库存快照")

    latest_date = sales["date"].max()
    recent = sales[sales["date"] >= latest_date - pd.Timedelta(days=29)]
    average_sales = recent.groupby(["product_id", "store_id"], as_index=False)["sales"].mean()
    rows = []
    for row in average_sales.itertuples(index=False):
        daily_demand = float(row.sales)
        rows.append({
            "as_of_date": latest_date.date().isoformat(),
            "product_id": int(row.product_id),
            "store_id": int(row.store_id),
            "on_hand": max(0.0, round(daily_demand * 5, 2)),
            "confirmed_inbound": 0.0,
            "reserved": 0.0,
            "lead_time_days": 3,
            "review_period_days": 4,
            "safety_stock": max(0.0, round(daily_demand * 2, 2)),
            "pack_size": 12,
            "minimum_order_quantity": 24,
        })

    inventory = pd.DataFrame(rows, columns=REQUIRED_INVENTORY_COLUMNS)
    inventory = inventory.sort_values(["product_id", "store_id"]).reset_index(drop=True)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    inventory.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"[data_generator] 生成 {len(inventory)} 行库存快照 → {output_path}")
    return output_path


if __name__ == "__main__":
    generate_sales_data()

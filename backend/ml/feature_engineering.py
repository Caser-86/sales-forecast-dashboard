"""特征工程

从原始销售数据中提取时间序列特征与统计特征，供 LightGBM 与 LSTM 使用。
"""
from __future__ import annotations

import os

import pandas as pd
from sklearn.preprocessing import LabelEncoder

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_PATH = os.path.join(BACKEND_DIR, "data", "raw", "sales_data.csv")
PROCESSED_DIR = os.path.join(BACKEND_DIR, "data", "processed")
OUTPUT_PATH = os.path.join(PROCESSED_DIR, "features.csv")

# 用于 LightGBM 的特征列
FEATURE_COLS = [
    "product_id", "store_id", "category_enc",
    "price", "competitor_price", "price_diff",
    "is_weekend", "is_holiday", "is_promotion",
    "sales_lag_1", "sales_lag_7", "sales_lag_14",
    "sales_rolling_7", "sales_rolling_30",
    "day_of_week", "month", "day_of_month",
]
TARGET_COL = "sales"
# LSTM 输入特征（连续数值型）
LSTM_FEATURE_COLS = [
    "sales", "price", "competitor_price", "price_diff",
    "is_weekend", "is_holiday", "is_promotion",
    "sales_lag_1", "sales_lag_7", "sales_lag_14",
    "sales_rolling_7", "sales_rolling_30",
]


def build_features(raw_path: str = RAW_PATH, output_path: str = OUTPUT_PATH) -> str:
    """读取原始数据 → 特征工程 → 写入 features.csv。返回输出路径。"""
    df = pd.read_csv(raw_path)
    df["date"] = pd.to_datetime(df["date"])

    # 排序保证 lag/rolling 正确
    df = df.sort_values(["store_id", "product_id", "date"]).reset_index(drop=True)

    # 类别编码
    le = LabelEncoder()
    df["category_enc"] = le.fit_transform(df["category"])

    # 时间特征
    df["day_of_week"] = df["date"].dt.dayofweek
    df["month"] = df["date"].dt.month
    df["day_of_month"] = df["date"].dt.day

    # 价格变化率
    df["price_diff"] = df.groupby(["store_id", "product_id"])["price"].pct_change().fillna(0.0)

    # lag 特征（按 门店×商品 分组，transform 自动对齐索引）
    grp = df.groupby(["store_id", "product_id"])["sales"]
    for lag in (1, 7, 14):
        df[f"sales_lag_{lag}"] = grp.shift(lag)
    # rolling 特征（shift(1) 防止泄露当前值）
    df["sales_rolling_7"] = grp.transform(lambda x: x.shift(1).rolling(7, min_periods=1).mean())
    df["sales_rolling_30"] = grp.transform(lambda x: x.shift(1).rolling(30, min_periods=1).mean())

    # 丢弃因 shift 产生的 NaN（仅前 14 天会缺失）
    df = df.dropna(subset=["sales_lag_14"]).reset_index(drop=True)

    # 数值类型规整
    for c in ["is_weekend", "is_holiday", "is_promotion", "category_enc",
              "day_of_week", "month", "day_of_month", "product_id", "store_id"]:
        df[c] = df[c].astype("int32")
    for c in ["sales_lag_1", "sales_lag_7", "sales_lag_14"]:
        df[c] = df[c].astype("float32")
    for c in ["sales_rolling_7", "sales_rolling_30", "price_diff"]:
        df[c] = df[c].astype("float32")
    df["sales"] = df["sales"].astype("float32")
    df["price"] = df["price"].astype("float32")
    df["competitor_price"] = df["competitor_price"].astype("float32")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"[feature_engineering] 生成 {len(df)} 行特征 → {output_path}")
    print(f"[feature_engineering] 特征列: {FEATURE_COLS}")
    return output_path


def load_features(processed_path: str = OUTPUT_PATH) -> pd.DataFrame:
    """供训练/预测时复用。"""
    df = pd.read_csv(processed_path)
    df["date"] = pd.to_datetime(df["date"])
    return df


if __name__ == "__main__":
    build_features()

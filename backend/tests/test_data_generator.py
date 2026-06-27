"""ML 数据生成器单元测试。"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd

# 注入 backend/ml 路径
BACKEND_DIR = Path(__file__).resolve().parent.parent
ML_DIR = BACKEND_DIR / "ml"
sys.path.insert(0, str(ML_DIR))

import data_generator as gen  # noqa: E402


class TestProductCatalog:
    def test_catalog_has_20_products(self):
        """商品目录应包含 20 个 SKU。"""
        products = gen._build_product_catalog()
        assert len(products) == 20

    def test_product_ids_unique(self):
        """商品 ID 唯一。"""
        products = gen._build_product_catalog()
        ids = [p["product_id"] for p in products]
        assert len(set(ids)) == 20

    def test_product_categories_cover_5(self):
        """商品覆盖 5 个品类。"""
        products = gen._build_product_catalog()
        cats = {p["category"] for p in products}
        assert len(cats) == 5

    def test_product_fields(self):
        """商品对象字段完整。"""
        products = gen._build_product_catalog()
        p = products[0]
        for k in ("product_id", "product_name", "category", "base_price", "base_sales", "trend"):
            assert k in p

    def test_product_trend_valid(self):
        """趋势因子取值合法。"""
        products = gen._build_product_catalog()
        for p in products:
            assert p["trend"] in (-1, 0, 1)

    def test_product_price_positive(self):
        """商品基础价格 > 0。"""
        products = gen._build_product_catalog()
        for p in products:
            assert p["base_price"] > 0


class TestWeekendHelper:
    def test_monday_is_not_weekend(self):
        assert gen._is_weekend(date(2025, 6, 23)) is False

    def test_saturday_is_weekend(self):
        assert gen._is_weekend(date(2025, 6, 28)) is True

    def test_sunday_is_weekend(self):
        assert gen._is_weekend(date(2025, 6, 29)) is True


class TestGenerateSalesData:
    def test_generate_writes_csv(self, tmp_path):
        """生成数据应写入 CSV 文件。"""
        out = tmp_path / "test_sales.csv"
        result_path = gen.generate_sales_data(output_path=str(out))
        assert os.path.exists(result_path)

    def test_generated_csv_shape(self, tmp_path):
        """生成 CSV 行数 = 20 商品 × 5 门店 × 181 天 = 18100。"""
        out = tmp_path / "test_sales.csv"
        gen.generate_sales_data(output_path=str(out))
        df = pd.read_csv(out)
        assert len(df) == 18100

    def test_generated_csv_columns(self, tmp_path):
        """CSV 包含必要字段。"""
        out = tmp_path / "test_sales.csv"
        gen.generate_sales_data(output_path=str(out))
        df = pd.read_csv(out)
        for col in ("product_id", "store_id", "date", "sales", "price", "is_weekend", "is_promotion", "is_holiday"):
            assert col in df.columns

    def test_generated_sales_non_negative(self, tmp_path):
        """生成的销量为非负整数。"""
        out = tmp_path / "test_sales.csv"
        gen.generate_sales_data(output_path=str(out))
        df = pd.read_csv(out)
        assert (df["sales"] >= 0).all()

    def test_generated_data_reproducible(self, tmp_path):
        """固定随机种子下数据可复现。"""
        out1 = tmp_path / "s1.csv"
        out2 = tmp_path / "s2.csv"
        # 重置种子后重新生成
        import numpy as np
        np.random.seed(gen.RANDOM_SEED)
        gen.generate_sales_data(output_path=str(out1))
        np.random.seed(gen.RANDOM_SEED)
        gen.generate_sales_data(output_path=str(out2))
        df1 = pd.read_csv(out1)
        df2 = pd.read_csv(out2)
        pd.testing.assert_frame_equal(df1, df2)

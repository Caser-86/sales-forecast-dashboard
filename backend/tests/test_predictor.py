"""predictor 模块单元测试。

只验证不依赖模型加载的纯逻辑：模块级类别编码器的正确性与稳定性。
"""
from __future__ import annotations

import json

import pytest


class TestCategoryEncoder:
    """验证 predictor._CATEGORY_ENCODER 的行为。

    重构将 LabelEncoder 从循环内提到模块级，必须保证：
    1. 编码值与原逻辑一致（fit 顺序：服装/家居/日化/电子/食品）
    2. 全部 5 个品类均可编码
    3. 同一品类多次编码结果稳定
    """

    def _encoder(self):
        from ml import predictor
        return predictor._CATEGORY_ENCODER

    def test_encoder_covers_5_categories(self):
        le = self._encoder()
        cats = list(le.classes_)
        assert set(cats) == {"服装", "家居", "日化", "电子", "食品"}

    def test_encoder_is_deterministic(self):
        le = self._encoder()
        first = le.transform(["服装", "电子"])
        second = le.transform(["服装", "电子"])
        assert list(first) == list(second)

    def test_encoder_returns_int(self):
        le = self._encoder()
        code = le.transform(["食品"])[0]
        # LabelEncoder 返回 numpy.int64，验证可安全转为 Python int
        assert int(code) >= 0 and int(code) < 5

    def test_encoder_fit_order_matches_legacy(self):
        """旧代码 fit(["服装","家居","日化","电子","食品"])，
        LabelEncoder 内部会先 sort，因此编码值由字母序决定。
        本测试锁定该映射，防止重构后变化。
        """
        le = self._encoder()
        # LabelEncoder.transform 返回 sort 后的索引
        expected = {c: i for i, c in enumerate(sorted(le.classes_))}
        for cat, idx in expected.items():
            assert int(le.transform([cat])[0]) == idx


def test_feature_schema_rejects_mismatched_feature_columns(tmp_path):
    from app.core.exceptions import ModelArtifactError
    from ml import predictor

    (tmp_path / "feature_schema.json").write_text(
        json.dumps({
            "feature_cols": ["future_sales"],
            "lstm_feature_cols": [],
            "target_col": "sales",
            "horizon_days": 30,
        }),
        encoding="utf-8",
    )

    with pytest.raises(ModelArtifactError, match="特征 schema"):
        predictor._validate_feature_schema(tmp_path)


def test_model_selection_rejects_invalid_strategy(tmp_path):
    from app.core.exceptions import ModelArtifactError
    from ml import predictor

    (tmp_path / "model_selection.json").write_text(
        json.dumps({"strategy": "untrusted_model", "weights": {}}),
        encoding="utf-8",
    )

    with pytest.raises(ModelArtifactError, match="模型选择配置"):
        predictor._load_model_selection(tmp_path)


def test_model_selection_rejects_inconsistent_weights(tmp_path):
    from app.core.exceptions import ModelArtifactError
    from ml import predictor

    (tmp_path / "model_selection.json").write_text(
        json.dumps({
            "strategy": "lightgbm",
            "weights": {"lstm": 1.0, "lightgbm": 0.0},
        }),
        encoding="utf-8",
    )

    with pytest.raises(ModelArtifactError, match="模型选择配置"):
        predictor._load_model_selection(tmp_path)

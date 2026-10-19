"""ABC 分类领域函数测试。"""
from __future__ import annotations

from common.abc import classify_abc


def test_classify_abc_uses_cumulative_thresholds():
    result = classify_abc({"a": 70, "b": 20, "c": 10})

    assert result == {"a": "A", "b": "B", "c": "C"}


def test_classify_abc_handles_zero_and_negative_values():
    assert classify_abc({"a": 0, "b": -1}) == {"a": "C", "b": "C"}


def test_classify_abc_matches_by_key_when_values_are_equal():
    result = classify_abc({"first": 10, "second": 10, "third": 10})

    assert result["first"] == "A"
    assert result["second"] == "A"
    assert result["third"] == "C"


def test_classify_abc_keeps_the_highest_demand_item_in_class_a():
    assert classify_abc({"only": 100}) == {"only": "A"}

    result = classify_abc({"dominant": 95, "tail": 5})

    assert result["dominant"] == "A"
    assert result["tail"] == "C"

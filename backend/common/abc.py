"""ABC 需求分级领域规则。"""
from __future__ import annotations

from collections.abc import Hashable, Mapping
from typing import TypeVar

Key = TypeVar("Key", bound=Hashable)


def classify_abc(
    values: Mapping[Key, float],
    *,
    class_a_threshold: float = 0.70,
    class_b_threshold: float = 0.90,
) -> dict[Key, str]:
    """按累计需求占比将对象分为 A、B、C 三类。

    负数需求按零处理；总需求为零时所有对象返回 C。相同数值按键的
    字符串表示稳定排序，保证结果不依赖字典或并行任务的完成顺序。
    """
    if not values:
        return {}
    if not 0 < class_a_threshold < class_b_threshold <= 1:
        raise ValueError("ABC 阈值必须满足 0 < A < B <= 1")

    normalized = {key: max(float(value), 0.0) for key, value in values.items()}
    grand_total = sum(normalized.values())
    if grand_total <= 0:
        return {key: "C" for key in normalized}

    ranked = sorted(normalized.items(), key=lambda item: (-item[1], str(item[0])))
    result: dict[Key, str] = {}
    cumulative = 0.0
    for index, (key, value) in enumerate(ranked):
        cumulative += value
        ratio = cumulative / grand_total
        # Always keep the highest-demand item visible as A, even if it crosses
        # the first cumulative threshold by itself.
        if index == 0:
            result[key] = "A"
        elif ratio <= class_a_threshold:
            result[key] = "A"
        elif ratio <= class_b_threshold:
            result[key] = "B"
        else:
            result[key] = "C"
    return result

"""Transparent, deterministic replenishment policy rules."""
from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any


def _number(name: str, value: Any, *, allow_zero: bool = True) -> float:
    if value is None:
        raise ValueError(f"缺少库存输入: {name}")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} 必须是有限数值") from exc
    if not math.isfinite(number) or (number < 0 if allow_zero else number <= 0):
        condition = "大于等于 0" if allow_zero else "大于 0"
        raise ValueError(f"{name} 必须{condition}")
    return number


def calculate_replenishment(
    *,
    demand_forecast: Sequence[float],
    on_hand: float,
    confirmed_inbound: float,
    reserved: float,
    lead_time_days: int,
    review_period_days: int,
    safety_stock: float,
    pack_size: int,
    minimum_order_quantity: int,
) -> dict[str, int | float | str]:
    """Calculate a human-review replenishment suggestion from explicit inputs."""
    if not demand_forecast:
        raise ValueError("demand_forecast 不能为空")
    forecast = [_number("demand_forecast", value) for value in demand_forecast]
    for name, value in {
        "on_hand": on_hand,
        "confirmed_inbound": confirmed_inbound,
        "reserved": reserved,
        "safety_stock": safety_stock,
    }.items():
        _number(name, value)
    if not isinstance(lead_time_days, int) or lead_time_days < 0:
        raise ValueError("lead_time_days 必须是非负整数")
    if not isinstance(review_period_days, int) or review_period_days < 0:
        raise ValueError("review_period_days 必须是非负整数")
    window_days = lead_time_days + review_period_days
    if window_days <= 0:
        raise ValueError("lead_time_days + review_period_days 必须大于 0")
    if window_days > len(forecast):
        raise ValueError("lead time and review window exceeds forecast horizon")
    if not isinstance(pack_size, int) or pack_size <= 0:
        raise ValueError("pack_size 必须大于 0")
    if not isinstance(minimum_order_quantity, int) or minimum_order_quantity < 0:
        raise ValueError("minimum_order_quantity 必须大于等于 0")

    window_demand = sum(forecast[:window_days])
    net_available = float(on_hand + confirmed_inbound - reserved)
    target_stock = window_demand + float(safety_stock)
    raw_replenishment = max(0.0, target_stock - net_available)
    if raw_replenishment <= 0:
        suggested_quantity = 0
    else:
        minimum_target = max(raw_replenishment, float(minimum_order_quantity))
        suggested_quantity = math.ceil(minimum_target / pack_size) * pack_size

    shortfall_ratio = raw_replenishment / target_stock if target_stock > 0 else 0.0
    risk_level = "low" if raw_replenishment <= 0 else ("high" if shortfall_ratio >= 0.5 else "medium")
    return {
        "window_days": window_days,
        "window_demand": float(window_demand),
        "net_available": net_available,
        "target_stock": float(target_stock),
        "raw_replenishment": float(raw_replenishment),
        "suggested_quantity": int(suggested_quantity),
        "risk_level": risk_level,
    }

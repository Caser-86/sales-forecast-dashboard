"""Server-side replenishment what-if calculations."""
from __future__ import annotations

from typing import Any

from common.replenishment import calculate_replenishment

from app.core.exceptions import InventoryUnavailableError, NotFoundError
from app.services import data_service, forecast_service, inventory_service
from app.services.inventory_dataset_service import get_active_inventory_id


def preview_replenishment(
    *,
    product_id: int,
    store_id: int,
    lead_time_days: int | None = None,
    review_period_days: int | None = None,
    safety_stock: float | None = None,
    pack_size: int | None = None,
    minimum_order_quantity: int | None = None,
) -> dict[str, Any]:
    products = {item["product_id"]: item for item in data_service.get_products()}
    stores = {item["store_id"]: item for item in data_service.get_stores()}
    if product_id not in products:
        raise NotFoundError(f"product_id={product_id} 不存在")
    if store_id not in stores:
        raise NotFoundError(f"store_id={store_id} 不存在")

    snapshot = inventory_service.load_active_inventory_snapshot()
    if snapshot is None or snapshot.empty:
        raise InventoryUnavailableError("缺少有效库存快照，请先导入库存数据")
    inventory_service._validate_snapshot_freshness(snapshot)
    matched = snapshot[(snapshot["product_id"] == product_id) & (snapshot["store_id"] == store_id)]
    if matched.empty:
        raise InventoryUnavailableError(
            f"库存快照缺少商品/门店记录：product_id={product_id}, store_id={store_id}"
        )
    inventory = matched.iloc[0]
    forecast = forecast_service.get_forecast(product_id, store_id)
    demand = [point["predicted_sales"] for point in forecast["forecast"]]
    policy = calculate_replenishment(
        demand_forecast=demand,
        on_hand=float(inventory.on_hand),
        confirmed_inbound=float(inventory.confirmed_inbound),
        reserved=float(inventory.reserved),
        lead_time_days=int(inventory.lead_time_days if lead_time_days is None else lead_time_days),
        review_period_days=int(inventory.review_period_days if review_period_days is None else review_period_days),
        safety_stock=float(inventory.safety_stock if safety_stock is None else safety_stock),
        pack_size=int(inventory.pack_size if pack_size is None else pack_size),
        minimum_order_quantity=int(
            inventory.minimum_order_quantity
            if minimum_order_quantity is None
            else minimum_order_quantity
        ),
    )
    return {
        "product_id": product_id,
        "store_id": store_id,
        "product_name": products[product_id]["product_name"],
        "store_name": stores[store_id]["store_name"],
        "inventory_version": get_active_inventory_id(),
        "inventory_as_of_date": str(inventory.as_of_date.date()),
        "forecast_days": len(demand),
        "on_hand": float(inventory.on_hand),
        "confirmed_inbound": float(inventory.confirmed_inbound),
        "reserved": float(inventory.reserved),
        "lead_time_days": int(inventory.lead_time_days if lead_time_days is None else lead_time_days),
        "review_period_days": int(inventory.review_period_days if review_period_days is None else review_period_days),
        "safety_stock": float(inventory.safety_stock if safety_stock is None else safety_stock),
        "pack_size": int(inventory.pack_size if pack_size is None else pack_size),
        "minimum_order_quantity": int(
            inventory.minimum_order_quantity
            if minimum_order_quantity is None
            else minimum_order_quantity
        ),
        **policy,
    }

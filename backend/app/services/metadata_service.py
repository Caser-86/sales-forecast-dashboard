"""Runtime versions and freshness metadata without triggering forecast inference."""
from __future__ import annotations

from datetime import date
from typing import Any

from ml.artifacts import get_active_model_id

from app.core.config import settings
from app.services import data_service
from app.services.dataset_service import get_active_dataset_id
from app.services.inventory_dataset_service import get_active_inventory_id, load_active_inventory_snapshot


def _inventory_metadata(reference_date: date | None) -> dict[str, Any]:
    inventory_id = get_active_inventory_id()
    if inventory_id == "legacy":
        return {
            "inventory_version": inventory_id,
            "inventory_as_of_date": None,
            "inventory_age_days": None,
            "inventory_status": "unavailable",
        }

    frame = load_active_inventory_snapshot()
    if frame is None or frame.empty:
        return {
            "inventory_version": inventory_id,
            "inventory_as_of_date": None,
            "inventory_age_days": None,
            "inventory_status": "unavailable",
        }
    inventory_date = frame["as_of_date"].max().date()
    age_days = (reference_date - inventory_date).days if reference_date else None
    status = "fresh" if age_days is not None and 0 <= age_days <= settings.INVENTORY_MAX_AGE_DAYS else "stale"
    return {
        "inventory_version": inventory_id,
        "inventory_as_of_date": inventory_date.isoformat(),
        "inventory_age_days": age_days,
        "inventory_status": status,
    }


def get_metadata() -> dict[str, Any]:
    quality = data_service.get_data_quality()
    reference_date = date.fromisoformat(quality["date_end"]) if quality.get("date_end") else None
    result = {
        "data_version": get_active_dataset_id(),
        "model_version": get_active_model_id(),
        "as_of_date": quality.get("date_end"),
        "data_status": quality.get("status", "unknown"),
        "model_status": data_service.get_model_info().get("status", "unknown"),
        "inventory_max_age_days": settings.INVENTORY_MAX_AGE_DAYS,
    }
    result.update(_inventory_metadata(reference_date))
    return result

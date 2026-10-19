"""商品列表接口"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.schemas import ProductList
from app.services import data_service

router = APIRouter()


@router.get("/products", response_model=ProductList, summary="商品列表")
def list_products(
    search: Annotated[str | None, Query(max_length=100)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=1000)] = 1000,
):
    """Return a bounded, searchable product catalog without changing source data."""
    products = data_service.get_products()
    normalized = search.strip().lower() if search else ""
    if normalized:
        products = [
            item for item in products
            if normalized in str(item["product_id"]).lower()
            or normalized in str(item["product_name"]).lower()
            or normalized in str(item["category"]).lower()
        ]
    total = len(products)
    start = (page - 1) * page_size
    return {"total": total, "products": products[start:start + page_size]}

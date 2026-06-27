"""商品列表接口"""
from __future__ import annotations

from fastapi import APIRouter

from app.services import data_service
from app.schemas import ProductList

router = APIRouter()


@router.get("/products", response_model=ProductList, summary="商品列表")
def list_products():
    """返回所有商品及品类。"""
    products = data_service.get_products()
    return {"total": len(products), "products": products}

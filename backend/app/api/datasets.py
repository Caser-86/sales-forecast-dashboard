"""Dataset upload preflight, version catalog, and runtime snapshot APIs."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.schemas import (
    DatasetCatalog,
    DatasetPreviewResult,
    DatasetVersionResult,
    RuntimeSnapshotPublishRequest,
    RuntimeSnapshotResponse,
)
from app.services import dataset_service, inventory_dataset_service, runtime_snapshot_service

router = APIRouter()

_SALES_TEMPLATE = (
    "date,product_id,store_id,product_name,store_name,category,sales,price\n"
    "2026-01-01,1,1,示例商品,示例门店,示例品类,10,12.5\n"
)
_INVENTORY_TEMPLATE = (
    "as_of_date,product_id,store_id,on_hand,confirmed_inbound,reserved,"
    "lead_time_days,review_period_days,safety_stock,pack_size,minimum_order_quantity\n"
    "2026-01-01,1,1,40,10,5,2,2,10,12,24\n"
)


def _kind(kind: str) -> str:
    normalized = kind.lower()
    if normalized not in {"sales", "inventory"}:
        raise ValidationError("数据类型必须是 sales 或 inventory")
    return normalized


def _source_name(request: Request, kind: str) -> str:
    value = request.headers.get("X-Filename", f"{kind}.csv")
    return Path(value).name[:120] or f"{kind}.csv"


async def _read_payload(request: Request) -> bytes:
    raw = await request.body()
    if len(raw) > settings.DATASET_MAX_UPLOAD_BYTES:
        raise ValidationError(
            f"上传文件超过 {settings.DATASET_MAX_UPLOAD_BYTES // 1024 // 1024} MB 限制"
        )
    return raw


def _preview(kind: str, raw: bytes) -> dict:
    if len(raw) == 0:
        return {
            "valid": False,
            "row_count": 0,
            "errors": [{"row": 1, "column": "", "message": "上传内容为空"}],
            "error_count": 1,
            "truncated": False,
        }
    result = (
        dataset_service.preview_sales_bytes(raw)
        if kind == "sales"
        else inventory_dataset_service.preview_inventory_bytes(raw)
    )
    if result["row_count"] > settings.DATASET_MAX_ROWS:
        result["valid"] = False
        result["errors"].append({
            "row": 1,
            "column": "",
            "message": f"行数超过 {settings.DATASET_MAX_ROWS} 行限制",
        })
        result["error_count"] = len(result["errors"])
    return result


@router.get("/datasets", response_model=DatasetCatalog, summary="数据与运行版本清单")
def list_datasets():
    return runtime_snapshot_service.list_dataset_catalog()


@router.get("/datasets/templates/{kind}", summary="下载 CSV 模板")
def download_template(kind: str):
    normalized = _kind(kind)
    content = _SALES_TEMPLATE if normalized == "sales" else _INVENTORY_TEMPLATE
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{normalized}-template.csv"'},
    )


@router.post("/datasets/runtime", response_model=RuntimeSnapshotResponse, status_code=201, summary="发布运行快照候选")
def publish_runtime_snapshot(payload: RuntimeSnapshotPublishRequest):
    return runtime_snapshot_service.publish_runtime_snapshot(**payload.model_dump(), activate=False)


@router.post(
    "/datasets/runtime/{snapshot_id}/activate",
    response_model=RuntimeSnapshotResponse,
    summary="激活运行快照",
)
def activate_runtime_snapshot(snapshot_id: str):
    return runtime_snapshot_service.activate_runtime_snapshot(snapshot_id)


@router.post(
    "/datasets/runtime/{snapshot_id}/rollback",
    response_model=RuntimeSnapshotResponse,
    summary="回滚到运行快照",
)
def rollback_runtime_snapshot(snapshot_id: str):
    return runtime_snapshot_service.rollback_runtime_snapshot(snapshot_id)


@router.get(
    "/datasets/runtime/{snapshot_id}",
    response_model=RuntimeSnapshotResponse,
    summary="查看运行快照详情",
)
def get_runtime_snapshot(snapshot_id: str):
    return runtime_snapshot_service.get_runtime_snapshot_detail(snapshot_id)


@router.post("/datasets/{kind}/preview", response_model=DatasetPreviewResult, summary="预检 CSV")
async def preview_dataset(kind: str, request: Request):
    normalized = _kind(kind)
    raw = await _read_payload(request)
    result = _preview(normalized, raw)
    return {"kind": normalized, "source_name": _source_name(request, normalized), **result}


@router.post("/datasets/{kind}", response_model=DatasetVersionResult, status_code=201, summary="保存候选版本")
async def upload_dataset(
    kind: str,
    request: Request,
):
    normalized = _kind(kind)
    raw = await _read_payload(request)
    preview = _preview(normalized, raw)
    if not preview["valid"]:
        raise ValidationError(
            "文件预检未通过",
            detail=json.dumps(preview["errors"], ensure_ascii=False),
        )
    source_name = _source_name(request, normalized)
    with tempfile.TemporaryDirectory(dir=settings.JOBS_DIR, prefix="dataset-upload-") as directory:
        source = Path(directory) / source_name
        source.write_bytes(raw)
        result = (
            dataset_service.import_sales_dataset(source, activate=False)
            if normalized == "sales"
            else inventory_dataset_service.import_inventory_snapshot(source, activate=False)
        )
    return result["manifest"]

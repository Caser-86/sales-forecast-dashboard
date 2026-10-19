"""模型报告与输入数据质量接口。"""
from __future__ import annotations

from fastapi import APIRouter

from app.schemas import DataQualityResult, MetadataResult, ModelInfoResult
from app.services import data_service, metadata_service

router = APIRouter()


@router.get("/model-info", response_model=ModelInfoResult, summary="模型信息与评估指标")
def get_model_info():
    return data_service.get_model_info()


@router.get("/data-quality", response_model=DataQualityResult, summary="数据质量检查")
def get_data_quality():
    return data_service.get_data_quality()


@router.get("/metadata", response_model=MetadataResult, summary="版本与数据新鲜度")
def get_metadata():
    return metadata_service.get_metadata()

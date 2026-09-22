"""Local-only deterministic demo operations."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.exceptions import ValidationError
from app.schemas import DemoArtifactRequest, DemoScenarioRequest, DemoScenarioResponse
from app.services import demo_service
from app.services.auth_service import DemoUser, require_roles

router = APIRouter()
_AdminDependency = Depends(require_roles("admin"))


@router.get("/demo/scenarios", response_model=DemoScenarioResponse, summary="查看演示场景")
def list_scenarios(_user: DemoUser = _AdminDependency):
    return demo_service.list_scenarios()


@router.post("/demo/scenarios/{name}", response_model=DemoScenarioResponse, summary="切换演示场景")
def switch_scenario(name: str, payload: DemoScenarioRequest, _user: DemoUser = _AdminDependency):
    return demo_service.switch_scenario(name, confirm=payload.confirm)


@router.post("/demo/backups", summary="创建演示备份")
def create_backup(payload: DemoArtifactRequest, _user: DemoUser = _AdminDependency):
    return demo_service.create_backup(artifact_name=payload.artifact_name)


@router.get("/demo/artifacts", summary="查看演示备份和诊断包")
def list_artifacts(_user: DemoUser = _AdminDependency):
    return demo_service.list_artifacts()


@router.post("/demo/backups/restore", summary="恢复演示备份")
def restore_backup(payload: DemoArtifactRequest, _user: DemoUser = _AdminDependency):
    if not payload.artifact_name:
        raise ValidationError("恢复备份必须提供 artifact_name")
    return demo_service.restore_backup(payload.artifact_name)


@router.post("/demo/diagnostics", summary="生成脱敏诊断包")
def create_diagnostic(payload: DemoArtifactRequest, _user: DemoUser = _AdminDependency):
    return demo_service.create_diagnostic_package(artifact_name=payload.artifact_name)

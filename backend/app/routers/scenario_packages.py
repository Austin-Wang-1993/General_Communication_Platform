"""场景包路由（API 文档 §2.1 ~ §2.4）。

只做 HTTP 接收/翻译：参数校验交给 Pydantic、业务规则交给 Service、
异常翻译交给全局 handler（app/errors.py）。
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Response, status

from app.dependencies import get_intake_service, get_scenario_package_service
from app.models.intake import CommitIntakeRequest, CommitIntakeResponse
from app.models.package import (
    CreatePackageRequest,
    CreatePackageResponse,
    PackageListResponse,
    PackageSummary,
)
from app.services.intake_service import IntakeService
from app.services.scenario_package_service import ScenarioPackageService

router = APIRouter(prefix="/scenario-packages", tags=["scenario-packages"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=CreatePackageResponse,
    summary="创建空场景包（P2「创建新场景」）",
)
async def create_scenario_package(
    body: Optional[CreatePackageRequest] = None,
    svc: ScenarioPackageService = Depends(get_scenario_package_service),
) -> CreatePackageResponse:
    """API 文档 §2.1。

    请求体可为 `null` / `{}` / 含 `scenario_title_hint`。
    返回新创建的 `scenario_id`、`lifecycle_phase=draft` 等。
    """
    hint = body.scenario_title_hint if body else ""
    package = await svc.create_empty(scenario_title_hint=hint)
    return CreatePackageResponse(
        scenario_id=package.scenario_id,
        lifecycle_phase=package.lifecycle_phase,
        scenario_title=package.scenario_title,
        created_at=package.created_at,
        updated_at=package.updated_at,
    )


@router.get(
    "",
    response_model=PackageListResponse,
    summary="场景包列表（P2 列表）",
)
async def list_scenario_packages(
    svc: ScenarioPackageService = Depends(get_scenario_package_service),
) -> PackageListResponse:
    """API 文档 §2.2。按 `updated_at` 降序。"""
    items = await svc.list_all()
    return PackageListResponse(packages=items)


@router.post(
    "/{scenario_id}/commit-intake",
    response_model=CommitIntakeResponse,
    summary="提交五字段并扩写（P2.1「下一步」）",
)
async def commit_intake(
    scenario_id: str,
    body: CommitIntakeRequest,
    svc: IntakeService = Depends(get_intake_service),
) -> CommitIntakeResponse:
    """API 文档 §2.5：校验 → 可选 G3 → LLM 扩写 → 落盘 intake.json / analysis.json。"""
    return await svc.commit_intake(scenario_id, body)


@router.get(
    "/{scenario_id}",
    response_model=PackageSummary,
    summary="场景包完整摘要（P2a / P2.5 / P3 进入前查询）",
)
async def get_scenario_package(
    scenario_id: str,
    svc: ScenarioPackageService = Depends(get_scenario_package_service),
) -> PackageSummary:
    """API 文档 §2.3。包不存在则抛 ScenarioNotFoundError → 404。"""
    return await svc.get_summary(scenario_id)


@router.delete(
    "/{scenario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="物理删除场景包（P2b 确认删除）",
)
async def delete_scenario_package(
    scenario_id: str,
    svc: ScenarioPackageService = Depends(get_scenario_package_service),
) -> Response:
    """API 文档 §2.4。允许任意 lifecycle_phase 下删除（PRD §5.4）。"""
    await svc.delete(scenario_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

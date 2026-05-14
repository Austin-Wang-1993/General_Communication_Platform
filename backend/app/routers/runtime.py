"""运行期 API（API 文档 §4.1 / §4.2）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_runtime_service
from app.models.runtime_api import EnterSectionResponse, RuntimeResponse
from app.services.runtime_service import RuntimeService

router = APIRouter(prefix="/scenario-packages", tags=["runtime"])


@router.get(
    "/{scenario_id}/runtime",
    response_model=RuntimeResponse,
    summary="运行态一次性拉取（P3）",
)
async def get_runtime(
    scenario_id: str,
    svc: RuntimeService = Depends(get_runtime_service),
) -> RuntimeResponse:
    """API §4.1：当前指针、本节叙事/任务、回合列表、框架摘要。"""
    return await svc.get_runtime(scenario_id)


@router.post(
    "/{scenario_id}/sections/{chapter_id}/{section_id}/enter",
    response_model=EnterSectionResponse,
    summary="进节（含自动开场 §6.6.5）",
)
async def enter_section(
    scenario_id: str,
    chapter_id: int,
    section_id: int,
    svc: RuntimeService = Depends(get_runtime_service),
) -> EnterSectionResponse:
    """API §4.2：更新指针；若本节尚无回合则同步生成首条 NPC 开场。"""
    return await svc.enter_section(scenario_id, chapter_id, section_id)

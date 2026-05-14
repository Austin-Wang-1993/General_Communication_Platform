"""运行期 API（API 文档 §4.1 ~ §4.4）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_runtime_service
from app.models.runtime_api import (
    AutoOpenerRetryResponse,
    EnterSectionResponse,
    PostUserTurnRequest,
    PostUserTurnResponse,
    RuntimeResponse,
    SectionTurnsListResponse,
)
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


@router.get(
    "/{scenario_id}/sections/{chapter_id}/{section_id}/turns",
    response_model=SectionTurnsListResponse,
    summary="拉取指定小节全部回合（§4.4）",
)
async def get_section_turns(
    scenario_id: str,
    chapter_id: int,
    section_id: int,
    limit: int | None = Query(None, description="不传则全量；传则仅返回最近 N 条"),
    svc: RuntimeService = Depends(get_runtime_service),
) -> SectionTurnsListResponse:
    return await svc.get_section_turns(scenario_id, chapter_id, section_id, limit=limit)


@router.post(
    "/{scenario_id}/sections/{chapter_id}/{section_id}/turns",
    response_model=PostUserTurnResponse,
    summary="用户发送一条英文并触发 NPC 续聊（§4.5）",
)
async def post_user_turn(
    scenario_id: str,
    chapter_id: int,
    section_id: int,
    body: PostUserTurnRequest,
    svc: RuntimeService = Depends(get_runtime_service),
) -> PostUserTurnResponse:
    return await svc.post_user_turn(
        scenario_id,
        chapter_id,
        section_id,
        content=body.content,
        recipient_id=body.recipient_id,
    )


@router.post(
    "/{scenario_id}/sections/{chapter_id}/{section_id}/auto-opener",
    response_model=AutoOpenerRetryResponse,
    summary="显式重试本节自动开场（§4.3）",
)
async def post_auto_opener_retry(
    scenario_id: str,
    chapter_id: int,
    section_id: int,
    svc: RuntimeService = Depends(get_runtime_service),
) -> AutoOpenerRetryResponse:
    return await svc.retry_section_auto_opener(scenario_id, chapter_id, section_id)


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

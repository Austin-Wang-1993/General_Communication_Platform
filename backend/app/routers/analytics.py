"""R2 本节复盘 API（API 文档 §6.1 / §6.2）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.dependencies import get_section_analytics_service
from app.models.analytics_api import SectionAnalyticsLatestResponse, SectionAnalyticsPostResponse
from app.services.section_analytics_service import SectionAnalyticsService

router = APIRouter(prefix="/scenario-packages", tags=["analytics"])


@router.post(
    "/{scenario_id}/sections/{chapter_id}/{section_id}/analytics",
    response_model=SectionAnalyticsPostResponse,
    summary="生成本节复盘（R2 / §6.8）",
)
async def post_section_analytics(
    scenario_id: str,
    chapter_id: int,
    section_id: int,
    svc: SectionAnalyticsService = Depends(get_section_analytics_service),
) -> SectionAnalyticsPostResponse:
    return await svc.post_section_analytics(scenario_id, chapter_id, section_id)


@router.get(
    "/{scenario_id}/sections/{chapter_id}/{section_id}/analytics",
    response_model=None,
    summary="拉取本节最新成功复盘（无则 204）",
    responses={204: {"description": "尚无成功复盘记录"}},
)
async def get_section_analytics_latest(
    scenario_id: str,
    chapter_id: int,
    section_id: int,
    svc: SectionAnalyticsService = Depends(get_section_analytics_service),
) -> SectionAnalyticsLatestResponse | Response:
    out = await svc.get_section_analytics_latest(scenario_id, chapter_id, section_id)
    if out is None:
        return Response(status_code=204)
    return out

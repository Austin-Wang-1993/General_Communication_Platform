"""R1 回答提示 API（API 文档 §5.1 / §5.2）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.dependencies import get_hints_service
from app.models.hint_api import HintResponse, PostHintRequest
from app.services.hints_service import HintsService

router = APIRouter(prefix="/scenario-packages", tags=["hints"])


@router.post(
    "/{scenario_id}/sections/{chapter_id}/{section_id}/hints",
    response_model=HintResponse,
    summary="生成回答提示（R1 / §6.7）",
)
async def post_hint(
    scenario_id: str,
    chapter_id: int,
    section_id: int,
    body: PostHintRequest,
    svc: HintsService = Depends(get_hints_service),
) -> HintResponse:
    return await svc.post_hint(scenario_id, chapter_id, section_id, body)


@router.get(
    "/{scenario_id}/sections/{chapter_id}/{section_id}/hints/latest",
    response_model=None,
    summary="拉取本节最新回答提示（无则 204）",
    responses={204: {"description": "本节尚未生成过回答提示"}},
)
async def get_hint_latest(
    scenario_id: str,
    chapter_id: int,
    section_id: int,
    svc: HintsService = Depends(get_hints_service),
) -> HintResponse | Response:
    out = await svc.get_hint_latest(scenario_id, chapter_id, section_id)
    if out is None:
        return Response(status_code=204)
    return out

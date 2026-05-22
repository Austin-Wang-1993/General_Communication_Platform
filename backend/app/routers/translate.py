"""句级英译中辅助 API（中台 §6.9 / 技术方案 §8.x）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_translation_service
from app.models.translation_api import EnToZhRequest, EnToZhResponse
from app.services.translation_service import TranslationService

router = APIRouter(prefix="/translation", tags=["translation"])


@router.post(
    "/en-to-zh",
    response_model=EnToZhResponse,
    summary="英译中（Demo，不持久化）",
)
async def post_en_to_zh(
    body: EnToZhRequest,
    svc: TranslationService = Depends(get_translation_service),
) -> EnToZhResponse:
    out = await svc.translate_en_to_zh(body.text)
    return EnToZhResponse(translated_text=out)

"""调试 API：只读落盘 JSON（API 文档 §7.2）。"""

from __future__ import annotations

import json
import re

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.errors import InvalidRequestBodyError, RawFileNotFoundError, ScenarioNotFoundError

router = APIRouter(prefix="/debug", tags=["debug"])

# 仅允许场景包目录下白名单相对路径（禁止 .. 与绝对路径）
_ALLOWED_REL = re.compile(
    r"^(framework\.json|roster\.json|intake\.json|analysis\.json|"
    r"sections/ch\d+_sec\d+/(narrative|mission)\.json)$"
)


@router.get(
    "/raw-file",
    summary="读取场景包内白名单 JSON（§7.2）",
)
async def get_raw_file(
    scenario_id: str = Query(..., min_length=36, max_length=36),
    relpath: str = Query(..., min_length=1, max_length=256),
) -> JSONResponse:
    """返回 `data/scenarios/{id}/{relpath}` 的 JSON 对象（已解析为 dict/list）。"""
    rp = relpath.strip().replace("\\", "/")
    if rp.startswith("/") or ".." in rp.split("/"):
        raise InvalidRequestBodyError(details={"relpath": "路径非法"})
    if not _ALLOWED_REL.fullmatch(rp):
        raise InvalidRequestBodyError(details={"relpath": "不在白名单内", "allowed_pattern": _ALLOWED_REL.pattern})

    settings = get_settings()
    base = (settings.data_dir_path / "scenarios" / scenario_id).resolve()
    if not base.is_dir():
        raise ScenarioNotFoundError(details={"scenario_id": scenario_id})

    target = (base / rp).resolve()
    try:
        target.relative_to(base)
    except ValueError as e:
        raise InvalidRequestBodyError(details={"relpath": "路径穿越被拒绝"}) from e

    if not target.is_file():
        raise RawFileNotFoundError(details={"scenario_id": scenario_id, "relpath": rp})

    raw_text = target.read_text(encoding="utf-8")
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise RawFileNotFoundError(
            message="文件不是合法 JSON",
            details={"scenario_id": scenario_id, "relpath": rp, "reason": str(e)},
        ) from e

    if not isinstance(data, (dict, list)):
        raise RawFileNotFoundError(
            message="JSON 根须为 object 或 array",
            details={"scenario_id": scenario_id, "relpath": rp},
        )

    return JSONResponse(content=data)

"""健康检查路由。

对应 API 文档 §1.1 `GET /api/v1/health`：
返回服务可用性、数据目录可写性、DeepSeek 是否配置。
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app import __version__
from app.config import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    ok: bool = Field(..., description="总体是否健康")
    service: str = Field(..., description='固定 "gcp-backend"')
    version: str = Field(..., description="后端版本号")
    server_time: str = Field(..., description="服务器时间 RFC3339 UTC")
    data_dir_writable: bool = Field(..., description="GCP_DATA_DIR 是否可写")
    deepseek_configured: bool = Field(
        ..., description="DEEPSEEK_API_KEY 环境变量是否非空（不验证有效性）"
    )


def _is_dir_writable(path) -> bool:
    """探测目录是否可写：尝试创建并删除一个临时文件。"""
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except Exception:
        return False


@router.get("/health", response_model=HealthResponse, summary="健康检查")
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        ok=True,
        service=settings.service_name,
        version=__version__,
        server_time=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        data_dir_writable=_is_dir_writable(settings.data_dir_path),
        deepseek_configured=bool(settings.deepseek_api_key),
    )

"""统一异常类与 HTTP 翻译（与 API 文档 §0.7 错误响应统一格式对齐）。

设计目标：
- Service 层抛业务异常 → Router 层翻译为对应 HTTP 状态码。
- 响应体始终为 `{error_code, message, details?}`。
- M0 仅定义基础类与全局 handler；具体子类在 M1+ 业务实现时按需新增。
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class GcpError(Exception):
    """所有业务异常的基类。

    `error_code` 必须是 API 文档 §0.8 错误码总表里的字符串。
    """

    http_status: int = 500
    error_code: str = "internal_error"
    message: str = "系统异常，请稍后重试"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
        http_status: int | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message or self.message)
        if message is not None:
            self.message = message
        if details is not None:
            self.details = details
        else:
            self.details = None
        if http_status is not None:
            self.http_status = http_status
        if error_code is not None:
            self.error_code = error_code

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "error_code": self.error_code,
            "message": self.message,
        }
        if self.details is not None:
            payload["details"] = self.details
        return payload


# === 通用基础异常（后续 M1+ 会扩展子类） ===


class InvalidRequestBodyError(GcpError):
    http_status = 400
    error_code = "invalid_request_body"
    message = "请求格式错误"


class ScenarioNotFoundError(GcpError):
    http_status = 404
    error_code = "scenario_not_found"
    message = "场景包不存在或已被删除"


class LifecyclePhaseError(GcpError):
    http_status = 409
    error_code = "lifecycle_phase_invalid"
    message = "当前生命周期阶段不允许该操作"


class RepositoryIoError(GcpError):
    http_status = 500
    error_code = "repository_io_error"
    message = "数据文件读写失败"


# === FastAPI 全局异常 handler ===


async def gcp_error_handler(_request: Request, exc: GcpError) -> JSONResponse:
    return JSONResponse(status_code=exc.http_status, content=exc.to_payload())


async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """兜底 handler：未分类异常归类为 internal_error。"""
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "internal_error",
            "message": "系统异常，请稍后重试",
            "details": {"exception_type": type(exc).__name__},
        },
    )

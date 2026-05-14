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


class FrameworkAlreadyExistsError(GcpError):
    http_status = 409
    error_code = "framework_already_exists"
    message = "包内已有剧情框架，如需修改五字段并重新创作，请设置 force_reset_creation 为 true"


class IntakeFieldTooShortError(GcpError):
    http_status = 422
    error_code = "intake_field_too_short"
    message = "五字段长度不足"


class IntakeFieldTooLongError(GcpError):
    http_status = 422
    error_code = "intake_field_too_long"
    message = "五字段长度超出上限"


class DisplayNameInvalidError(GcpError):
    http_status = 422
    error_code = "display_name_invalid"
    message = "显示名包含非法字符或修剪后为空"


class IntakeUnrelatedTopicError(GcpError):
    http_status = 422
    error_code = "intake_unrelated_topic"
    message = "场景描述与目标在主题上缺乏关联，请调整后再试"


class LlmTimeoutError(GcpError):
    http_status = 504
    error_code = "llm_timeout"
    message = "语言模型响应超时，请稍后重试"


class JobNotFoundError(GcpError):
    http_status = 404
    error_code = "job_not_found"
    message = "Job 不存在或不属于该场景包"


class ActiveJobConflictError(GcpError):
    http_status = 409
    error_code = "active_job_conflict"
    message = "该场景包已有进行中的创作任务，请等待结束或取消后再试"


class SectionsAlreadyExistError(GcpError):
    http_status = 409
    error_code = "sections_already_exist"
    message = "包内已有小节产物或已进入创作完成态；需设置 force_regenerate=true 以清空并重生成"


class JobAlreadyTerminalError(GcpError):
    http_status = 409
    error_code = "job_already_terminal"
    message = "该 Job 已结束，无法取消"


class ChapterNotFoundError(GcpError):
    http_status = 404
    error_code = "chapter_not_found"
    message = "指定的 chapter_id 不存在于本包剧情框架"


class SectionNotFoundError(GcpError):
    http_status = 404
    error_code = "section_not_found"
    message = "指定的 section_id 在该章中不存在或本节资产缺失"


class TurnNotFoundError(GcpError):
    http_status = 404
    error_code = "turn_not_found"
    message = "回合不存在或不是当前待回复的 NPC 回合"


class AutoOpenerFailedError(GcpError):
    http_status = 500
    error_code = "auto_opener_failed"
    message = "本节自动开场失败"


class RuntimeNotAwaitingUserError(GcpError):
    http_status = 409
    error_code = "runtime_not_awaiting_user"
    message = "当前不在等待用户发言，无法发送或触发相关操作"


class RecipientIdInvalidError(GcpError):
    http_status = 422
    error_code = "recipient_id_invalid"
    message = "接收方 NPC 无效：须为本节 appearing_npc_ids 之一且不能为 user"


class ContentEmptyOrTooLongError(GcpError):
    http_status = 422
    error_code = "content_empty_or_too_long"
    message = "发言内容为空或超出长度限制"


class SectionAlreadyHasTurnsError(GcpError):
    http_status = 409
    error_code = "section_already_has_turns"
    message = "本节已有对话回合，无法再次自动开场"


class SectionNoTurnsYetError(GcpError):
    http_status = 409
    error_code = "section_no_turns_yet"
    message = "本节尚无对话回合，无法生成本节复盘"


class LlmAuthenticationError(GcpError):
    """DeepSeek 返回 401/403：多为 API Key 错误、过期或环境变量含多余空白。"""

    http_status = 502
    error_code = "llm_authentication_failed"
    message = "DeepSeek 拒绝了当前 API Key，请检查服务器上的 DEEPSEEK_API_KEY 是否正确"


class LlmFailureError(GcpError):
    http_status = 500
    error_code = "llm_failure"
    message = "语言模型调用失败"


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

"""跨层枚举定义（对齐 PRD §5.4 / §6.6.1 / §6.7.1 / §6.8.1）。

约定：值的字符串与 PRD / JSON 完全一致，不做大小写或格式转换。
"""

from __future__ import annotations

from enum import Enum


class LifecyclePhase(str, Enum):
    """场景包生命周期 6 状态（PRD §5.4 v0.5.2）。

    `runtime_complete` 与 `archived` 已废止（v0.5.0），**不得**新增。
    """

    DRAFT = "draft"
    INTAKE_COMMITTED = "intake_committed"
    CREATION_RUNNING = "creation_running"
    CREATION_FAILED = "creation_failed"
    CREATION_SUCCEEDED = "creation_succeeded"
    RUNTIME_ACTIVE = "runtime_active"


# 以下枚举将在后续 milestone 启用，先占位定义保持单一真源
# class TurnWriter(str, Enum):   # PRD §6.6.1 — M5 启用
#     MODEL_NPC = "model_npc"
#     HUMAN_USER = "human_user"

# class HintStatus(str, Enum):   # PRD §6.7.1 — M5.5 启用
#     READY = "ready"
#     STALE = "stale"
#     FAILED = "failed"

# class SectionAnalyticsStatus(str, Enum):   # PRD §6.8.1 — M5.5 启用
#     READY = "ready"
#     FAILED = "failed"

"""标识符生成工具（对齐 PRD §5.2）。"""

from __future__ import annotations

import uuid


def new_scenario_id() -> str:
    """生成 36 字符小写十六进制 UUID v4（PRD §5.2 `scenario_id` 规则）。"""
    return str(uuid.uuid4())


def new_turn_id() -> str:
    """生成 turn UUID v4（PRD §5.2 `turn_id` 规则）；M5 阶段开始使用。"""
    return str(uuid.uuid4())

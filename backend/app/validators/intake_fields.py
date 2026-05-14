"""五字段格式与主题粗校验（PRD §6.1.1 / §6.1.3）。"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

_CONTROL = re.compile(r"[\u0000-\u001f\u007f]")


def trim_and_check_display_name(name: str) -> str:
    """修剪空白；非法控制字符或修剪后空 → 抛 DisplayNameInvalidError。"""
    from app.errors import DisplayNameInvalidError

    s = name.strip()
    if not s:
        raise DisplayNameInvalidError()
    if _CONTROL.search(s):
        raise DisplayNameInvalidError(message="显示名包含 ASCII 控制字符")
    if len(s) > 120:
        raise DisplayNameInvalidError(message="显示名超过 120 个字符")
    return s


def trim_scenario_title(title: str) -> str:
    from app.errors import DisplayNameInvalidError

    s = title.strip()
    if not s:
        raise DisplayNameInvalidError(
            message="场景名称不能为空",
            error_code="display_name_invalid",
        )
    if _CONTROL.search(s):
        raise DisplayNameInvalidError(message="场景名称包含非法字符")
    if len(s) > 120:
        from app.errors import IntakeFieldTooLongError

        raise IntakeFieldTooLongError(details={"field": "scenario_title"})
    return s


def validate_scene_brief(scene_brief: str) -> str:
    from app.errors import IntakeFieldTooLongError, IntakeFieldTooShortError

    s = scene_brief.strip()
    n = len(s)
    if n < 40:
        raise IntakeFieldTooShortError(
            message="「你梦想的场景」至少需要 40 个字符（修剪后）",
            details={"field": "scene_brief", "min": 40, "actual": n},
        )
    if n > 20000:
        raise IntakeFieldTooLongError(details={"field": "scene_brief"})
    if _CONTROL.search(s):
        from app.errors import DisplayNameInvalidError

        raise DisplayNameInvalidError(
            message="场景描述包含非法控制字符",
            details={"field": "scene_brief"},
        )
    return s


def validate_user_goal_brief(goal: str) -> str:
    from app.errors import IntakeFieldTooLongError, IntakeFieldTooShortError

    s = goal.strip()
    n = len(s)
    if n < 10:
        raise IntakeFieldTooShortError(
            message="「你的目标」至少需要 10 个字符（修剪后）",
            details={"field": "user_goal_brief", "min": 10, "actual": n},
        )
    if n > 20000:
        raise IntakeFieldTooLongError(details={"field": "user_goal_brief"})
    if _CONTROL.search(s):
        from app.errors import DisplayNameInvalidError

        raise DisplayNameInvalidError(
            message="目标描述包含非法控制字符",
            details={"field": "user_goal_brief"},
        )
    return s


def validate_vocabulary_list(raw: str) -> str:
    from app.errors import IntakeFieldTooLongError

    s = (raw or "").strip()
    if len(s) > 5000:
        raise IntakeFieldTooLongError(details={"field": "vocabulary_list"})
    return s


def topics_loosely_related(scene: str, goal: str) -> bool:
    """PRD §6.1.3：完全无关则拒绝。使用归一化文本的序列相似度 + 词片交集的保守启发式。"""
    def norm(t: str) -> str:
        t = unicodedata.normalize("NFKC", t).lower()
        return "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in t)

    a, b = norm(scene), norm(goal)
    if not a or not b:
        return False
    ratio = SequenceMatcher(None, a[:8000], b[:8000]).ratio()
    if ratio >= 0.12:
        return True
    words_a = {w for w in a.split() if len(w) >= 3}
    words_b = {w for w in b.split() if len(w) >= 3}
    if not words_a or not words_b:
        return ratio >= 0.05
    inter = words_a & words_b
    return len(inter) >= 2 or ratio >= 0.06

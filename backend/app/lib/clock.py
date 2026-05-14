"""时间工具：统一以 RFC 3339 / ISO 8601（UTC，Z 后缀，秒精度）输出。

对齐 PRD §5.3 `timestamp` 类型规则。
"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now_rfc3339() -> str:
    """返回当前 UTC 时刻字符串，形如 `2026-05-14T08:30:45Z`。

    精度到秒；不含毫秒/微秒；严格使用 `Z` 而非 `+00:00`。
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

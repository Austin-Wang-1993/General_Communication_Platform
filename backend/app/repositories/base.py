"""数据仓库通用工具：JSON 原子读写、按场景包加 asyncio.Lock。

设计对齐 `02-代码架构与目录约定.md` §2.3：
- 暴露的方法只关心数据存取，不知道业务规则。
- 写入用 `tmp + os.replace` 实现近似原子（POSIX 下 rename 原子）。
- 锁按 `scenario_id` 隔离，避免同包并发撕裂；不同包并行无阻塞。
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import threading
from pathlib import Path
from typing import Any

from app.errors import RepositoryIoError


# 全局锁注册表（key = scenario_id；用普通 threading.Lock 保护，
# 因为锁本身的 get/创建不需要 async 上下文）
_LOCKS: dict[str, asyncio.Lock] = {}
_LOCKS_MUTEX = threading.Lock()


def get_scenario_lock(scenario_id: str) -> asyncio.Lock:
    """获取或新建该 scenario_id 的进程内 asyncio 锁。

    所有写路径（save / append / delete）都应在调用前 `async with` 此锁。
    """
    with _LOCKS_MUTEX:
        lock = _LOCKS.get(scenario_id)
        if lock is None:
            lock = asyncio.Lock()
            _LOCKS[scenario_id] = lock
        return lock


def release_scenario_lock(scenario_id: str) -> None:
    """场景包删除后清掉锁条目，避免长期单用户运行下的内存增长。"""
    with _LOCKS_MUTEX:
        _LOCKS.pop(scenario_id, None)


async def read_json(path: Path) -> Any | None:
    """读 JSON 文件；不存在返回 None。

    使用 `asyncio.to_thread` 让阻塞 I/O 不占用事件循环（M1 单用户场景影响很小，
    但保留接口形态便于后续接入异步 I/O 库或更换持久层）。
    """

    def _read() -> Any | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:  # pragma: no cover - 罕见 IO 错误
            raise RepositoryIoError(
                message=f"读取 JSON 失败：{path.name}",
                details={"path": str(path), "error": str(e)},
            ) from e

    return await asyncio.to_thread(_read)


async def write_json_atomic(path: Path, data: Any) -> None:
    """原子写：先写入 `<path>.tmp` 再 `os.replace` 覆盖目标。

    在 POSIX 上 `os.replace` 是原子操作；读者要么看到旧文件要么看到完整新文件，
    不会看到半截内容。
    """

    def _write() -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(tmp, path)
        except Exception as e:
            raise RepositoryIoError(
                message=f"写入 JSON 失败：{path.name}",
                details={"path": str(path), "error": str(e)},
            ) from e

    await asyncio.to_thread(_write)


async def remove_dir_tree(path: Path) -> bool:
    """递归删除目录树；不存在返回 False，否则 True。"""

    def _rm() -> bool:
        if not path.exists():
            return False
        try:
            shutil.rmtree(path)
            return True
        except Exception as e:
            raise RepositoryIoError(
                message=f"删除目录失败：{path.name}",
                details={"path": str(path), "error": str(e)},
            ) from e

    return await asyncio.to_thread(_rm)

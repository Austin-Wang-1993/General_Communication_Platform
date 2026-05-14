"""FastAPI 应用入口。

按 `docs/engineering/02-代码架构与目录约定.md` §2.7 后端目录全图组织。
M0~M5：health、场景包 CRUD、commit-intake、framework/world Job、轮询与取消、运行期 runtime + 进节 enter + turns；R1：`.../hints`；R2：`.../analytics`。
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.config import get_settings
from app.errors import GcpError, gcp_error_handler, unhandled_exception_handler
from app.routers import analytics, creation_jobs, health, hints, runtime, scenario_packages

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """启动 / 关闭钩子。M0 仅做初始化日志与数据目录确保。"""
    settings = get_settings()
    logging.basicConfig(
        level=settings.gcp_log_level.upper(),
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    settings.data_dir_path.mkdir(parents=True, exist_ok=True)
    (settings.data_dir_path / "scenarios").mkdir(parents=True, exist_ok=True)
    logger.info(
        "GCP backend %s starting; data_dir=%s, deepseek_configured=%s",
        __version__,
        settings.data_dir_path,
        bool(settings.deepseek_api_key),
    )
    yield
    logger.info("GCP backend stopping")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="GCP Backend",
        description="通用英语对话练习 · 后端 API（M0~M5 + R1 hints + R2 analytics）",
        version=__version__,
        lifespan=lifespan,
    )

    # CORS（与技术方案 §11.3 一致）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 全局异常处理（API 文档 §0.7 错误响应统一格式）
    app.add_exception_handler(GcpError, gcp_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # 路由挂载
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(scenario_packages.router, prefix="/api/v1")
    app.include_router(creation_jobs.router, prefix="/api/v1")
    app.include_router(runtime.router, prefix="/api/v1")
    app.include_router(hints.router, prefix="/api/v1")
    app.include_router(analytics.router, prefix="/api/v1")

    # 调试页静态资源（同进程下访问 /debug-ui/，Nginx 通过 /debug/ 别名也可指向 backend/app/debug_ui/）
    debug_ui_dir = Path(__file__).parent / "debug_ui"
    if debug_ui_dir.exists():
        app.mount(
            "/debug-ui",
            StaticFiles(directory=str(debug_ui_dir), html=True),
            name="debug-ui",
        )

    return app


app = create_app()

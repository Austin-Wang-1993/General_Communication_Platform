"""创作期 Job 路由（API 文档 §3.1 / §3.3 之 framework 部分）。"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, status
from fastapi.responses import JSONResponse

from app.dependencies import get_framework_job_service
from app.models.creation_jobs import JobPollResponse
from app.services.framework_job_service import FrameworkJobService

router = APIRouter(prefix="/scenario-packages", tags=["creation-jobs"])


@router.post(
    "/{scenario_id}/jobs/framework",
    summary="启动剧情框架 + 角色清单 Job（P2.2）",
)
async def post_framework_job(
    scenario_id: str,
    background_tasks: BackgroundTasks,
    svc: FrameworkJobService = Depends(get_framework_job_service),
) -> JSONResponse:
    """立即 202；后台顺序生成 framework.json → roster.json（业务流程 §2.2）。"""
    out = await svc.start_framework_job(scenario_id)
    background_tasks.add_task(svc.run_framework_pipeline, scenario_id, out.job_id)
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content=out.model_dump(mode="json"),
    )


@router.get(
    "/{scenario_id}/jobs/{job_id}",
    response_model=JobPollResponse,
    summary="轮询 Job 状态（P2.2 / P2.4）",
)
async def get_job_status(
    scenario_id: str,
    job_id: str,
    svc: FrameworkJobService = Depends(get_framework_job_service),
) -> JobPollResponse:
    """API 文档 §3.3。"""
    return await svc.get_job(scenario_id, job_id)

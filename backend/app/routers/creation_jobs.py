"""创作期 Job 路由（API 文档 §3.1 / §3.2 / §3.3 / §3.4）。"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, status
from fastapi.responses import JSONResponse

from app.dependencies import (
    get_framework_job_service,
    get_job_control_service,
    get_job_query_service,
    get_world_job_service,
)
from app.models.creation_jobs import (
    CancelJobResponse,
    JobPollResponse,
    StartWorldJobRequest,
    StartWorldJobResponse,
)
from app.services.framework_job_service import FrameworkJobService
from app.services.job_control_service import JobControlService
from app.services.job_query_service import JobQueryService
from app.services.world_job_service import WorldJobService

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


@router.post(
    "/{scenario_id}/jobs/world",
    summary="启动全书小节扩写 Job（P2.4）",
)
async def post_world_job(
    scenario_id: str,
    background_tasks: BackgroundTasks,
    body: StartWorldJobRequest = StartWorldJobRequest(),
    svc: WorldJobService = Depends(get_world_job_service),
) -> JSONResponse:
    """立即 202；后台按 framework 顺序写 sections/ch*_sec*/（§6.4 + §6.5）。"""
    out = await svc.start_world_job(scenario_id, body)
    background_tasks.add_task(svc.run_world_pipeline, scenario_id, out.job_id)
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content=out.model_dump(mode="json"),
    )


@router.post(
    "/{scenario_id}/jobs/{job_id}/cancel",
    response_model=CancelJobResponse,
    summary="取消进行中的 Job（P2.2 / P2.4）",
)
async def post_cancel_job(
    scenario_id: str,
    job_id: str,
    ctrl: JobControlService = Depends(get_job_control_service),
) -> CancelJobResponse:
    """world job 会清空 sections/（API §3.4）。"""
    return await ctrl.cancel_job(scenario_id, job_id)


@router.get(
    "/{scenario_id}/jobs/{job_id}",
    response_model=JobPollResponse,
    summary="轮询 Job 状态（P2.2 / P2.4）",
)
async def get_job_status(
    scenario_id: str,
    job_id: str,
    q: JobQueryService = Depends(get_job_query_service),
) -> JobPollResponse:
    """API 文档 §3.3。"""
    return await q.get_job(scenario_id, job_id)

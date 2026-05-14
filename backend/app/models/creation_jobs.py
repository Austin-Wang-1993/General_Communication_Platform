"""创作期 Job 模型（API 文档 §3）。"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class JobType(str, Enum):
    FRAMEWORK = "framework"
    WORLD = "world"


class JobRecord(BaseModel):
    """落盘于 `jobs/{job_id}.json`，字段与 GET §3.3 对齐。"""

    model_config = ConfigDict(extra="forbid")

    job_id: str
    type: JobType
    scenario_id: str
    status: JobStatus
    current_step_label: str = ""
    progress_hint: Optional[str] = None
    created_at: str
    updated_at: str
    finished_at: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class StartFrameworkJobResponse(BaseModel):
    """POST .../jobs/framework 202 响应（API 文档 §3.1）。"""

    model_config = ConfigDict(extra="forbid")

    job_id: str
    type: JobType = JobType.FRAMEWORK
    scenario_id: str
    status: JobStatus
    current_step_label: str
    created_at: str


class JobPollResponse(BaseModel):
    """GET .../jobs/{job_id} 200 响应（API 文档 §3.3）。"""

    model_config = ConfigDict(extra="forbid")

    job_id: str
    type: JobType
    scenario_id: str
    status: JobStatus
    current_step_label: str
    progress_hint: Optional[str] = None
    created_at: str
    updated_at: str
    finished_at: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None

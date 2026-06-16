from __future__ import annotations

from celery.result import AsyncResult
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from evercurrent.jobs.celery_app import celery_app

router = APIRouter(prefix="/jobs", tags=["jobs"])

_PENDING_STATES = {"PENDING", "RECEIVED", "STARTED", "RETRY"}


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    job_id: str
    status: str
    result: dict[str, object] | None = None
    enqueue_time: str | None = None
    start_time: str | None = None
    finish_time: str | None = None


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_status(job_id: str) -> JobStatusResponse:
    async_result: AsyncResult[object] = AsyncResult(job_id, app=celery_app)
    state = async_result.state
    result: dict[str, object] | None = None
    if state == "SUCCESS":
        value = async_result.result
        if isinstance(value, dict):
            result = value
    return JobStatusResponse(
        job_id=job_id,
        status="complete" if state == "SUCCESS" else state.lower(),
        result=result,
    )

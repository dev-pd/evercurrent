"""Job status — thin probe over the Arq job registry."""

from __future__ import annotations

import contextlib

from arq.jobs import Job
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from evercurrent.api.deps import ArqPool

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    job_id: str
    status: str
    result: dict[str, object] | None = None
    enqueue_time: str | None = None
    start_time: str | None = None
    finish_time: str | None = None


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_status(job_id: str, arq: ArqPool) -> JobStatusResponse:
    """Return the queue + worker state for an Arq job id.

    Statuses: `deferred`, `queued`, `in_progress`, `complete`, `not_found`.
    Frontend polls this so the UI shows a spinner until the worker
    actually finishes — useful for the per-user regenerate flow.
    """
    job = Job(job_id, arq)
    raw_status = await job.status()
    status_str = raw_status.value if hasattr(raw_status, "value") else str(raw_status)
    info = await job.info()
    result: dict[str, object] | None = None
    if status_str == "complete":
        with contextlib.suppress(Exception):
            value = await job.result(timeout=0)
            if isinstance(value, dict):
                result = value
    enqueue_time = getattr(info, "enqueue_time", None)
    start_time = getattr(info, "start_time", None)
    finish_time = getattr(info, "finish_time", None)
    return JobStatusResponse(
        job_id=job_id,
        status=status_str,
        result=result,
        enqueue_time=enqueue_time.isoformat() if enqueue_time else None,
        start_time=start_time.isoformat() if start_time else None,
        finish_time=finish_time.isoformat() if finish_time else None,
    )

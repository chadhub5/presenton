"""In-process jobs for PPTX→template slide layout generation.

Long-running LLM calls can exceed reverse-proxy idle/read timeouts (often 60s).
The browser starts a job (fast POST) and polls status (short GETs) until completion.

Note: state lives in this process only (single uvicorn worker in the shipped stack).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field


class SlideLayoutJobStartResponse(BaseModel):
    job_id: str


class SlideLayoutJobStatusResponse(BaseModel):
    status: str = Field(..., description="pending | complete | failed")
    react_component: Optional[str] = None
    error: Optional[str] = None


@dataclass
class _JobRecord:
    status: str = "pending"
    react_component: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


_jobs: dict[str, _JobRecord] = {}
_lock = asyncio.Lock()
_MAX_JOBS = 256
LOGGER = logging.getLogger(__name__)


def _http_exception_message(exc: HTTPException) -> str:
    detail = exc.detail
    if isinstance(detail, str):
        return detail
    return str(detail)


async def _prune_if_needed() -> None:
    async with _lock:
        if len(_jobs) <= _MAX_JOBS:
            return
        terminal = [
            (jid, rec.created_at)
            for jid, rec in _jobs.items()
            if rec.status in ("complete", "failed")
        ]
        terminal.sort(key=lambda x: x[1])
        for jid, _ in terminal[: max(1, len(_jobs) - _MAX_JOBS + 32)]:
            _jobs.pop(jid, None)


async def start_slide_layout_job(
    work: Callable[[], Awaitable[str]],
    debug_label: str = "",
) -> str:
    await _prune_if_needed()
    job_id = str(uuid.uuid4())
    async with _lock:
        _jobs[job_id] = _JobRecord()

    async def _runner() -> None:
        LOGGER.info("[slide-layout-job] started job_id=%s label=%s", job_id, debug_label)
        try:
            react = await work()
            async with _lock:
                rec = _jobs.get(job_id)
                if rec:
                    rec.status = "complete"
                    rec.react_component = react
                    LOGGER.info(
                        "[slide-layout-job] completed job_id=%s label=%s chars=%d",
                        job_id,
                        debug_label,
                        len(react or ""),
                    )
        except HTTPException as exc:
            async with _lock:
                rec = _jobs.get(job_id)
                if rec:
                    rec.status = "failed"
                    rec.error = _http_exception_message(exc)[:4000]
                    LOGGER.error(
                        "[slide-layout-job] failed job_id=%s label=%s status=%d error=%s",
                        job_id,
                        debug_label,
                        exc.status_code,
                        rec.error,
                    )
        except asyncio.CancelledError:
            LOGGER.warning(
                "[slide-layout-job] cancelled job_id=%s label=%s",
                job_id,
                debug_label,
            )
            raise
        except Exception as exc:
            async with _lock:
                rec = _jobs.get(job_id)
                if rec:
                    rec.status = "failed"
                    msg = str(exc).strip() or exc.__class__.__name__
                    rec.error = msg[:4000]
                    LOGGER.error(
                        "[slide-layout-job] failed job_id=%s label=%s error=%s",
                        job_id,
                        debug_label,
                        rec.error,
                    )

    asyncio.create_task(_runner())
    return job_id


async def get_slide_layout_job(job_id: str) -> Optional[_JobRecord]:
    async with _lock:
        rec = _jobs.get(job_id)
        if rec is None:
            return None
        return _JobRecord(
            status=rec.status,
            react_component=rec.react_component,
            error=rec.error,
            created_at=rec.created_at,
        )

# 文件作用：runs 列表/详情/手动触发 API
# 版本：v0.1.0

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.db import get_db
from app.models.entities import Run

router = APIRouter(prefix="/api/runs", tags=["runs"])


class RunSummary(BaseModel):
    id: int
    trigger_type: str
    report_type: str
    model: str | None
    status: str
    period_start: datetime | None
    period_end: datetime | None
    total_tokens: int | None
    latency_ms: int | None
    started_at: datetime
    finished_at: datetime | None
    error_message: str | None = None


class RunDetail(RunSummary):
    prompt_id: int | None
    sql_dump: str | None
    data_dump: str | None
    prompt_rendered: str | None
    response_text: str | None
    response_html: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    cost_estimate: float | None


class ManualRunRequest(BaseModel):
    report_type: str
    model: str | None = None
    prompt_id: int | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None


@router.get("", response_model=list[RunSummary])
def list_runs(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.query(Run).order_by(desc(Run.id)).limit(limit).all()
    return [RunSummary.model_validate(r, from_attributes=True) for r in rows]


@router.get("/{run_id}", response_model=RunDetail)
def get_run(run_id: int, db: Session = Depends(get_db)):
    r = db.get(Run, run_id)
    if not r:
        raise HTTPException(404, "run not found")
    return RunDetail.model_validate(r, from_attributes=True)


@router.post("/manual", response_model=RunSummary)
def trigger_manual(req: ManualRunRequest, db: Session = Depends(get_db)):
    """触发一次手动 run（v0.1.0 仅落 pending 占位记录，后续 pipeline 实现真正执行）

    Doris 不返回 autoincrement id，无法 db.refresh()；改为 commit 后查最新一条
    """
    run = Run(
        trigger_type="manual",
        report_type=req.report_type,
        prompt_id=req.prompt_id,
        model=req.model,
        period_start=req.period_start,
        period_end=req.period_end,
        status="pending",
    )
    db.add(run)
    db.commit()
    latest = db.query(Run).order_by(desc(Run.id)).first()
    return RunSummary.model_validate(latest, from_attributes=True)

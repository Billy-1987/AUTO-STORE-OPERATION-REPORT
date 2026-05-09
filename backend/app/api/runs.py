# 文件作用：runs 列表/详情/手动触发 API
# 版本：v0.3.0 — /manual 创建 pending 后立刻通过 BackgroundTasks 派发到 runner；新增 /retry 重跑

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from app.models.db import get_db
from app.models.entities import Prompt, Run
from app.pipeline.runner import execute_run

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
    prompt_id: int | None = None
    prompt_name: str | None = None
    prompt_version: int | None = None


class RunDetail(RunSummary):
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


def _attach_prompt(db: Session, run: Run) -> dict:
    """把 Run ORM 对象转成带 prompt_name/version 的 dict"""
    data = {c.name: getattr(run, c.name) for c in Run.__table__.columns}
    if run.prompt_id:
        p = db.get(Prompt, run.prompt_id)
        if p:
            data["prompt_name"] = p.name
            data["prompt_version"] = p.version
    return data


@router.get("", response_model=list[RunSummary])
def list_runs(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.query(Run).order_by(desc(Run.id)).limit(limit).all()

    # 一次性把涉及到的 prompt 拉回，避免 N+1
    prompt_ids = {r.prompt_id for r in rows if r.prompt_id}
    prompts: dict[int, Prompt] = {}
    if prompt_ids:
        for p in db.query(Prompt).filter(Prompt.id.in_(prompt_ids)).all():
            prompts[p.id] = p

    out: list[RunSummary] = []
    for r in rows:
        d = {c.name: getattr(r, c.name) for c in Run.__table__.columns}
        if r.prompt_id and r.prompt_id in prompts:
            p = prompts[r.prompt_id]
            d["prompt_name"] = p.name
            d["prompt_version"] = p.version
        out.append(RunSummary.model_validate(d))
    return out


@router.get("/{run_id}", response_model=RunDetail)
def get_run(run_id: int, db: Session = Depends(get_db)):
    r = db.get(Run, run_id)
    if not r:
        raise HTTPException(404, "run not found")
    return RunDetail.model_validate(_attach_prompt(db, r))


@router.post("/manual", response_model=RunSummary)
def trigger_manual(
    req: ManualRunRequest,
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """触发一次手动 run。

    - 未传 prompt_id 时，锁定当前 report_type 的生产版本 prompt，运行历史可追溯
    - 落 pending 行后立刻派给 runner（FastAPI BackgroundTasks，本进程协程池）
    - Doris 不返回 autoincrement id，commit 后查最新一条
    """
    prompt_id = req.prompt_id
    if prompt_id is None:
        active = (
            db.query(Prompt)
            .filter(and_(Prompt.report_type == req.report_type, Prompt.is_active == 1))
            .order_by(desc(Prompt.version))
            .first()
        )
        if active:
            prompt_id = active.id

    run = Run(
        trigger_type="manual",
        report_type=req.report_type,
        prompt_id=prompt_id,
        model=req.model,
        period_start=req.period_start,
        period_end=req.period_end,
        status="pending",
    )
    db.add(run)
    db.commit()
    latest = db.query(Run).order_by(desc(Run.id)).first()

    bg.add_task(execute_run, latest.id)
    return RunSummary.model_validate(_attach_prompt(db, latest))


@router.post("/{run_id}/retry", response_model=RunSummary)
def retry_run(run_id: int, bg: BackgroundTasks, db: Session = Depends(get_db)):
    """重跑一条已存在的 run（pending 或 failed），running/success 不允许重跑。"""
    r = db.get(Run, run_id)
    if not r:
        raise HTTPException(404, "run not found")
    if r.status not in ("pending", "failed"):
        raise HTTPException(409, f"run 状态={r.status}，不允许重跑")
    # 重置错误信息但保留模型/时间窗口；runner 会把状态切到 running
    r.error_message = None
    r.status = "pending"
    r.finished_at = None
    db.commit()
    bg.add_task(execute_run, r.id)
    return RunSummary.model_validate(_attach_prompt(db, r))

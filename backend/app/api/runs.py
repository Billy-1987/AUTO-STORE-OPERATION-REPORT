# 文件作用：runs 列表/详情/手动触发 API
# 版本：v0.4.0 — 适配两阶段 runner：/manual 自动建 dataset+report_run；新增 scope 字段
# 版本：v0.3.0 — /manual 创建 pending 后立刻通过 BackgroundTasks 派发到 runner；新增 /retry 重跑

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from app.models.db import get_db
from app.models.entities import Dataset, Prompt, Run
from app.pipeline.runner import execute_dataset_run, execute_report_run

router = APIRouter(prefix="/api/runs", tags=["runs"])


class RunSummary(BaseModel):
    id: int
    trigger_type: str
    report_type: str
    dataset_id: int | None = None
    scope_type: str | None = None
    scope_id: str | None = None
    scope_label: str | None = None
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
    report_type: str                     # weekly/monthly/holiday
    scope_type: str = "national"         # national/super_region/region/shop
    scope_id: str | None = None          # 大区名 / region_id / shop_id
    scope_label: str | None = None
    model: str | None = None
    prompt_id: int | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    dataset_id: int | None = None        # 复用已有 dataset；不传则自动新建并跑


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


def _run_full_pipeline(dataset_id: int | None, run_id: int, need_dataset: bool):
    """后台串行：先跑 dataset（如需）再跑 report。"""
    if need_dataset and dataset_id is not None:
        execute_dataset_run(dataset_id)
    execute_report_run(run_id)


@router.post("/manual", response_model=RunSummary)
def trigger_manual(
    req: ManualRunRequest,
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """手动触发一次 run。
    - dataset_id 未传 → 自动建 + 跑 dataset_run，再跑 report_run
    - dataset_id 已传且 status=success → 直接复用，只跑 report_run
    """
    # 1. 解析 dataset
    ds = None
    need_dataset_run = False
    if req.dataset_id:
        ds = db.get(Dataset, req.dataset_id)
        if ds is None:
            raise HTTPException(404, f"dataset {req.dataset_id} 不存在")
    else:
        ds = Dataset(
            period_type=req.report_type,
            period_start=req.period_start or datetime.now(),
            period_end=req.period_end or datetime.now(),
            status="pending",
        )
        db.add(ds)
        db.commit()
        need_dataset_run = True

    # 2. 锁定 prompt（按 report_type + scope_type 找 active）
    prompt_id = req.prompt_id
    if prompt_id is None:
        active = (
            db.query(Prompt)
            .filter(and_(
                Prompt.report_type == req.report_type,
                Prompt.scope_type == req.scope_type,
                Prompt.is_active == 1,
            ))
            .order_by(desc(Prompt.version))
            .first()
        )
        if active:
            prompt_id = active.id

    # 3. 创建 report_run
    run = Run(
        trigger_type="manual",
        report_type=req.report_type,
        dataset_id=ds.id,
        scope_type=req.scope_type,
        scope_id=req.scope_id,
        scope_label=req.scope_label or ("全国" if req.scope_type == "national" else (req.scope_id or "")),
        prompt_id=prompt_id,
        model=req.model,
        period_start=ds.period_start,
        period_end=ds.period_end,
        status="pending",
    )
    db.add(run)
    db.commit()

    bg.add_task(_run_full_pipeline, ds.id, run.id, need_dataset_run)
    return RunSummary.model_validate(_attach_prompt(db, run))


@router.post("/{run_id}/retry", response_model=RunSummary)
def retry_run(run_id: int, bg: BackgroundTasks, db: Session = Depends(get_db)):
    """重跑一条已存在的 report_run（pending 或 failed）。"""
    r = db.get(Run, run_id)
    if not r:
        raise HTTPException(404, "run not found")
    if r.status not in ("pending", "failed"):
        raise HTTPException(409, f"run 状态={r.status}，不允许重跑")
    r.error_message = None
    r.status = "pending"
    r.finished_at = None
    db.commit()
    bg.add_task(execute_report_run, r.id)
    return RunSummary.model_validate(_attach_prompt(db, r))

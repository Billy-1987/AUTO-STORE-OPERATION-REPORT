# 文件作用：runs 列表/详情/手动触发 API
# 版本：v0.6.0 — RunSummary 加 prompt/completion_tokens + cost_estimate；新增 DELETE /{id}（连 Report + html）
# 版本：v0.5.0 — 新增 GET /{id}/dispatch：暴露第 6 步钉钉分发结果 + 命中的收件人
# 版本：v0.4.0 — 适配两阶段 runner：/manual 自动建 dataset+report_run；新增 scope 字段
# 版本：v0.3.0 — /manual 创建 pending 后立刻通过 BackgroundTasks 派发到 runner；新增 /retry 重跑

import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from app.models.db import get_db
from app.models.entities import Dataset, Prompt, Recipient, Report, Run
from app.pipeline.runner import _recipient_scope, execute_dataset_run, execute_report_run

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
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None
    cost_estimate: float | None = None
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


class DispatchRecipient(BaseModel):
    id: int
    name: str
    role: str
    dingtalk_userid: str | None
    dingtalk_mobile: str | None
    included: bool          # 派发时是否进了 userid_list（有 userid 才算）


class DispatchInfo(BaseModel):
    status: str             # pending / sent / failed / skipped / not_reached
    sent_at: datetime | None
    title: str | None
    summary: str | None
    public_url: str | None
    response: dict | None   # 钉钉 API 解析后的 JSON
    recipients: list[DispatchRecipient]


@router.get("/{run_id}/dispatch", response_model=DispatchInfo)
def get_run_dispatch(run_id: int, db: Session = Depends(get_db)):
    """第 6 步钉钉分发的展示接口：报告行 + 命中本 scope 的订阅者。"""
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "run not found")

    # Report 行（pipeline 走到第 7 步才会写）
    rep = (
        db.query(Report)
        .filter(Report.run_id == run_id)
        .order_by(desc(Report.id))
        .first()
    )

    # 命中本 scope 的订阅者快照（按当前 recipients 表算，非分发时刻）
    sub_col = {
        "weekly": Recipient.subscribe_weekly,
        "monthly": Recipient.subscribe_monthly,
        "holiday": Recipient.subscribe_holiday,
    }.get(run.report_type)
    q = db.query(Recipient).filter(Recipient.is_active == 1)
    if sub_col is not None:
        q = q.filter(sub_col == 1)

    matched: list[DispatchRecipient] = []
    for r in q.all():
        sc = _recipient_scope(r)
        if not sc:
            continue
        if sc[0] != run.scope_type or sc[1] != run.scope_id:
            continue
        matched.append(DispatchRecipient(
            id=r.id, name=r.name, role=r.role,
            dingtalk_userid=r.dingtalk_userid,
            dingtalk_mobile=r.dingtalk_mobile,
            included=bool(r.dingtalk_userid),
        ))

    parsed_response: dict | None = None
    if rep and rep.dingtalk_response:
        try:
            parsed_response = json.loads(rep.dingtalk_response)
        except Exception:
            parsed_response = {"raw": rep.dingtalk_response}

    return DispatchInfo(
        status=(rep.dingtalk_status if rep else "not_reached"),
        sent_at=(rep.sent_at if rep else None),
        title=(rep.title if rep else None),
        summary=(rep.summary if rep else None),
        public_url=(rep.public_url if rep else None),
        response=parsed_response,
        recipients=matched,
    )


REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "reports"


@router.delete("/{run_id}")
def delete_run(run_id: int, db: Session = Depends(get_db)):
    """删一条 run：级联删 Report 行 + 落盘 HTML。Dataset 不动（多 run 共享）。"""
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "run not found")
    if run.status == "running":
        raise HTTPException(409, "run 正在执行中，不允许删除")

    deleted_reports = db.query(Report).filter(Report.run_id == run_id).delete()
    db.delete(run)
    db.commit()

    html_file = REPORTS_DIR / f"{run_id}.html"
    html_removed = False
    if html_file.exists():
        html_file.unlink()
        html_removed = True

    return {"deleted_run": run_id, "deleted_reports": deleted_reports, "html_removed": html_removed}


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

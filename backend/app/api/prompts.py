# 文件作用：prompts 模板管理 API（每 (report_type, scope_type) 一份，原地编辑）
# 版本：v0.5.0 — 取消版本/激活/删除/新建；只剩 list/get/update。是否需要还原历史版本走 git。

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.db import get_db
from app.models.entities import Prompt

router = APIRouter(prefix="/api/prompts", tags=["prompts"])


class PromptOut(BaseModel):
    id: int
    name: str
    report_type: str
    scope_type: str | None = None
    version: int
    content: str | None
    description: str | None
    model: str | None
    is_active: int
    created_at: datetime
    updated_at: datetime


class PromptUpdate(BaseModel):
    content: str | None = None
    description: str | None = None
    model: str | None = None


@router.get("", response_model=list[PromptOut])
def list_prompts(report_type: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Prompt)
    if report_type:
        q = q.filter(Prompt.report_type == report_type)
    return [PromptOut.model_validate(p, from_attributes=True) for p in q.order_by(desc(Prompt.id)).all()]


@router.get("/{prompt_id}", response_model=PromptOut)
def get_prompt(prompt_id: int, db: Session = Depends(get_db)):
    p = db.get(Prompt, prompt_id)
    if not p:
        raise HTTPException(404, "prompt not found")
    return PromptOut.model_validate(p, from_attributes=True)


@router.put("/{prompt_id}", response_model=PromptOut)
def update_prompt(prompt_id: int, req: PromptUpdate, db: Session = Depends(get_db)):
    """原地更新 content / description / model。不允许改 name/report_type/scope_type/version。"""
    p = db.get(Prompt, prompt_id)
    if not p:
        raise HTTPException(404, "prompt not found")
    if req.content is not None:
        p.content = req.content
    if req.description is not None:
        p.description = req.description
    if req.model is not None:
        p.model = req.model or None
    p.updated_at = datetime.now()
    db.commit()
    p = db.get(Prompt, prompt_id)
    return PromptOut.model_validate(p, from_attributes=True)

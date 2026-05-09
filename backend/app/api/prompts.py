# 文件作用：prompts 版本管理 API
# 版本：v0.1.0

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, and_
from sqlalchemy.orm import Session

from app.models.db import get_db
from app.models.entities import Prompt

router = APIRouter(prefix="/api/prompts", tags=["prompts"])


class PromptOut(BaseModel):
    id: int
    name: str
    report_type: str
    version: int
    content: str | None
    description: str | None
    model: str | None
    is_active: int
    created_at: datetime
    updated_at: datetime


class PromptCreate(BaseModel):
    name: str
    report_type: str
    content: str
    description: str | None = None
    model: str | None = None
    set_active: bool = False


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


@router.post("", response_model=PromptOut)
def create_prompt(req: PromptCreate, db: Session = Depends(get_db)):
    """创建新版本（同 name 自动 +1）"""
    last = (
        db.query(Prompt)
        .filter(Prompt.name == req.name)
        .order_by(desc(Prompt.version))
        .first()
    )
    next_version = (last.version + 1) if last else 1

    if req.set_active:
        db.query(Prompt).filter(
            and_(Prompt.name == req.name, Prompt.is_active == 1)
        ).update({"is_active": 0})

    p = Prompt(
        name=req.name,
        report_type=req.report_type,
        version=next_version,
        content=req.content,
        description=req.description,
        model=req.model,
        is_active=1 if req.set_active else 0,
    )
    db.add(p)
    db.commit()
    # Doris 不返回 autoincrement，重新查
    p = db.query(Prompt).filter(Prompt.name == req.name, Prompt.version == next_version).first()
    return PromptOut.model_validate(p, from_attributes=True)


@router.post("/{prompt_id}/activate", response_model=PromptOut)
def activate_prompt(prompt_id: int, db: Session = Depends(get_db)):
    p = db.get(Prompt, prompt_id)
    if not p:
        raise HTTPException(404, "prompt not found")
    db.query(Prompt).filter(
        and_(Prompt.name == p.name, Prompt.is_active == 1)
    ).update({"is_active": 0})
    p.is_active = 1
    db.commit()
    p = db.get(Prompt, prompt_id)
    return PromptOut.model_validate(p, from_attributes=True)

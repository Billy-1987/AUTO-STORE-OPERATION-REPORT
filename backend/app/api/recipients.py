# 文件作用：recipients CRUD API
# 版本：v0.1.0

import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.db import get_db
from app.models.entities import Recipient

router = APIRouter(prefix="/api/recipients", tags=["recipients"])


class RecipientOut(BaseModel):
    id: int
    name: str
    role: str
    region_ids: list[int] = []
    shop_ids: list[int] = []
    dingtalk_userid: str | None
    dingtalk_mobile: str | None
    subscribe_weekly: int
    subscribe_monthly: int
    subscribe_holiday: int
    is_active: int


class RecipientUpsert(BaseModel):
    name: str
    role: str
    region_ids: list[int] = []
    shop_ids: list[int] = []
    dingtalk_userid: str | None = None
    dingtalk_mobile: str | None = None
    subscribe_weekly: int = 1
    subscribe_monthly: int = 1
    subscribe_holiday: int = 1
    is_active: int = 1


def _to_out(r: Recipient) -> RecipientOut:
    return RecipientOut(
        id=r.id,
        name=r.name,
        role=r.role,
        region_ids=json.loads(r.region_ids) if r.region_ids else [],
        shop_ids=json.loads(r.shop_ids) if r.shop_ids else [],
        dingtalk_userid=r.dingtalk_userid,
        dingtalk_mobile=r.dingtalk_mobile,
        subscribe_weekly=r.subscribe_weekly,
        subscribe_monthly=r.subscribe_monthly,
        subscribe_holiday=r.subscribe_holiday,
        is_active=r.is_active,
    )


@router.get("", response_model=list[RecipientOut])
def list_recipients(db: Session = Depends(get_db)):
    return [_to_out(r) for r in db.query(Recipient).order_by(Recipient.id).all()]


@router.post("", response_model=RecipientOut)
def create_recipient(req: RecipientUpsert, db: Session = Depends(get_db)):
    r = Recipient(
        name=req.name,
        role=req.role,
        region_ids=json.dumps(req.region_ids),
        shop_ids=json.dumps(req.shop_ids),
        dingtalk_userid=req.dingtalk_userid,
        dingtalk_mobile=req.dingtalk_mobile,
        subscribe_weekly=req.subscribe_weekly,
        subscribe_monthly=req.subscribe_monthly,
        subscribe_holiday=req.subscribe_holiday,
        is_active=req.is_active,
    )
    db.add(r)
    db.commit()
    # Doris 不返回 autoincrement，按最新一条返回
    from sqlalchemy import desc as _desc
    latest = db.query(Recipient).order_by(_desc(Recipient.id)).first()
    return _to_out(latest)


@router.delete("/{rid}")
def delete_recipient(rid: int, db: Session = Depends(get_db)):
    r = db.get(Recipient, rid)
    if not r:
        raise HTTPException(404)
    db.delete(r)
    db.commit()
    return {"deleted": rid}

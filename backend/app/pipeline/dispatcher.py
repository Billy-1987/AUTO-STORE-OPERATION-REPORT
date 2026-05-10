# 文件作用：报告落盘 + 钉钉工作通知（企业内部应用，OAuth 私发）
# 版本：v0.2.0 — 弃 webhook 群推，改走 corpconversation/asyncsend_v2 私发到"工作通知"小助手
#
# 钉钉接入流程（运维侧）：
#   1) 钉钉开放平台 → 应用开发 → 企业内部应用 → 创建应用
#   2) 凭证与基础信息：抄 AppKey / AppSecret / AgentId 到 .env
#   3) 权限管理：开 "消息通知"（Message.SendMessage）
#   4) 开发管理：服务器出口 IP 加白名单
#
# 收件人填手机号 → recipients API 自动调 _resolve_userid_by_mobile 解析存回 userid。
# pipeline stage 6 调 send_dingtalk(userid_list=...)，userid 为空则跳过。

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.entities import Recipient, Report

log = logging.getLogger(__name__)

REPORTS_ROOT = Path(__file__).resolve().parent.parent.parent / "reports"
REPORTS_ROOT.mkdir(parents=True, exist_ok=True)

DINGTALK_OAPI = "https://oapi.dingtalk.com"

# 模块级 access_token 缓存。钉钉返回 expires_in=7200，留 5 分钟余量
_token_cache: dict[str, Any] = {"token": "", "expires_at": 0.0}
_token_lock = threading.Lock()


# ---------- 报告落盘（不变） ----------

def write_html(run_id: int, html: str) -> Path:
    """写到 backend/reports/{run_id}.html，返回绝对路径"""
    p = REPORTS_ROOT / f"{run_id}.html"
    p.write_text(html, encoding="utf-8")
    return p


def public_url_of(run_id: int) -> str:
    s = get_settings()
    return f"{s.public_base_url.rstrip('/')}/reports/{run_id}"


def write_report_row(
    db: Session,
    *,
    run_id: int,
    report_type: str,
    period_start: datetime | None,
    period_end: datetime | None,
    title: str | None,
    summary: str | None,
    html_path: str,
    public_url: str,
    dingtalk_status: str = "pending",
    dingtalk_response: str | None = None,
) -> None:
    db.add(
        Report(
            run_id=run_id,
            report_type=report_type,
            period_start=period_start,
            period_end=period_end,
            scope="national",
            scope_id=None,
            title=title,
            summary=summary,
            html_path=html_path,
            public_url=public_url,
            dingtalk_status=dingtalk_status,
            dingtalk_response=dingtalk_response,
            sent_at=datetime.now() if dingtalk_status == "sent" else None,
        )
    )
    db.commit()


def pick_recipients(db: Session, report_type: str) -> list[Recipient]:
    """按订阅开关筛选启用的收件人"""
    q = db.query(Recipient).filter(Recipient.is_active == 1)
    col = {
        "weekly": Recipient.subscribe_weekly,
        "monthly": Recipient.subscribe_monthly,
        "holiday": Recipient.subscribe_holiday,
    }.get(report_type)
    if col is not None:
        q = q.filter(col == 1)
    return q.all()


# ---------- 钉钉 OAuth：access_token ----------

def _get_access_token(force_refresh: bool = False) -> str:
    """获取 access_token，进程内缓存 ~7200s（提前 5 分钟过期）。

    钉钉未配置时抛 RuntimeError，由上层捕获返回 skipped。
    """
    s = get_settings()
    if not (s.dingtalk_app_key and s.dingtalk_app_secret):
        raise RuntimeError("DINGTALK_APP_KEY / DINGTALK_APP_SECRET 未配置")

    now = time.time()
    with _token_lock:
        if not force_refresh and _token_cache["token"] and _token_cache["expires_at"] > now:
            return _token_cache["token"]

        with httpx.Client(timeout=10) as client:
            r = client.get(
                f"{DINGTALK_OAPI}/gettoken",
                params={"appkey": s.dingtalk_app_key, "appsecret": s.dingtalk_app_secret},
            )
            data = r.json()

        if data.get("errcode") != 0:
            raise RuntimeError(f"gettoken 失败: {data}")

        _token_cache["token"] = data["access_token"]
        _token_cache["expires_at"] = now + max(60, int(data.get("expires_in", 7200)) - 300)
        return _token_cache["token"]


# ---------- 钉钉 OAuth：手机号 → userid ----------

def _resolve_userid_by_mobile(mobile: str) -> str | None:
    """按手机号查 userid，失败返回 None（不抛异常，方便保存收件人时降级）。

    用 /topapi/v2/user/getbymobile（新版接口，支持手机号查 userid）。
    """
    if not mobile:
        return None
    try:
        token = _get_access_token()
    except RuntimeError as e:
        log.warning("解析 userid 跳过：%s", e)
        return None

    try:
        with httpx.Client(timeout=10) as client:
            r = client.post(
                f"{DINGTALK_OAPI}/topapi/v2/user/getbymobile",
                params={"access_token": token},
                json={"mobile": mobile},
            )
            data = r.json()
    except Exception as e:
        log.warning("getbymobile 网络错误 mobile=%s: %s", mobile, e)
        return None

    if data.get("errcode") != 0:
        log.warning("getbymobile 业务错误 mobile=%s: %s", mobile, data)
        return None

    return (data.get("result") or {}).get("userid")


# ---------- 钉钉工作通知：ActionCard 私发 ----------

def send_dingtalk(
    *,
    title: str,
    summary_markdown: str,
    detail_url: str,
    userid_list: list[str],
) -> dict[str, Any]:
    """企业内部应用 → 工作通知 → ActionCard。

    发送对象：userid_list 里的每个员工，单独收到一条"工作通知"消息。
    未配置或 userid_list 空 → {"status": "skipped"}。
    """
    s = get_settings()
    if not (s.dingtalk_app_key and s.dingtalk_app_secret and s.dingtalk_agent_id):
        return {"status": "skipped", "reason": "钉钉企业内部应用未配置"}
    if not userid_list:
        return {"status": "skipped", "reason": "无有效 userid"}

    try:
        token = _get_access_token()
    except RuntimeError as e:
        return {"status": "failed", "response": {"error": str(e)}}

    payload = {
        "agent_id": int(s.dingtalk_agent_id),
        "userid_list": ",".join(userid_list),
        "msg": {
            "msgtype": "action_card",
            "action_card": {
                "title": title,
                "markdown": summary_markdown,
                "single_title": "查看完整报告",
                "single_url": detail_url,
            },
        },
    }

    try:
        with httpx.Client(timeout=10) as client:
            r = client.post(
                f"{DINGTALK_OAPI}/topapi/message/corpconversation/asyncsend_v2",
                params={"access_token": token},
                json=payload,
            )
            body = r.text
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body}
    except Exception as e:
        return {"status": "failed", "response": {"error": str(e)}}

    ok = parsed.get("errcode") == 0
    # asyncsend_v2 成功返回 task_id，钉钉异步派发，调用方拿到的是"已受理"
    return {"status": "sent" if ok else "failed", "response": parsed}

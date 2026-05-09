# 文件作用：流水线执行器 — 两阶段
# 版本：v0.2.1 — dispatch 改用 OAuth 工作通知（userid_list 私发）
# 版本：v0.2.0 — 拆 dataset_run（SQL+shape）+ report_run（prompt+AI+dispatch）；fanout 按 recipients 展开
# 版本：v0.1.0 — 单 run 6 步线性
#
# 阶段 A：execute_dataset_run(dataset_id) — render_sql → fetch → shape → 落 datasets
# 阶段 B：execute_report_run(run_id)      — slice dataset → render_prompt → ai_call → dispatch → 落 runs+reports
# 编排：  fanout_dataset(dataset_id)      — 按 recipients 创建 N 个 report_run

from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime
from typing import Any

from jinja2 import Environment, StrictUndefined
from sqlalchemy import desc

from app.doris.connection import query_ro
from app.models.db import get_session_factory
from app.models.entities import Dataset, Prompt, Recipient, Run
from app.pipeline import ai_client, data_shaper, dispatcher, sql_loader
from app.pipeline.data_shaper import REGIONS, SUPER_REGIONS

log = logging.getLogger(__name__)


class StageError(Exception):
    def __init__(self, stage: int, msg: str):
        super().__init__(msg)
        self.stage = stage


def _save(db, obj, **fields) -> None:
    for k, v in fields.items():
        setattr(obj, k, v)
    db.commit()


# ───────────────────── 阶段 A：dataset_run ─────────────────────

def execute_dataset_run(dataset_id: int) -> None:
    """SQL 渲染 → 跑 6 个 SQL → data_shaper → 落 datasets"""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    ds: Dataset | None = None
    try:
        ds = db.get(Dataset, dataset_id)
        if ds is None:
            log.error("dataset %s 不存在", dataset_id)
            return
        if ds.status not in ("pending", "failed"):
            log.warning("dataset %s 状态=%s 不重跑", dataset_id, ds.status)
            return

        _save(db, ds, status="running", started_at=datetime.now(), error_message=None)

        # 1. render_sql
        try:
            sqls = sql_loader.load_sqls(
                ds.period_type,
                period_start=ds.period_start,
                period_end=ds.period_end,
            )
            sql_dump = "\n\n".join(f"-- {n}\n{s}" for n, s in sqls)
            _save(db, ds, sql_dump=sql_dump)
        except Exception as e:
            raise StageError(1, f"render_sql 失败: {e}") from e

        # 2. fetch
        try:
            rows_by_query: dict[str, list[dict[str, Any]]] = {}
            for name, sql in sqls:
                rows_by_query[name] = query_ro(sql)
            rows_summary = {n: len(rs) for n, rs in rows_by_query.items()}
        except Exception as e:
            raise StageError(2, f"fetch 失败: {e}") from e

        # 3. shape
        try:
            shaped = data_shaper.shape(
                rows_by_query,
                period_type=ds.period_type,
                period_start=ds.period_start,
                period_end=ds.period_end,
            )
            _save(
                db, ds,
                data_dump=json.dumps(shaped, ensure_ascii=False, default=str),
                rows_summary=json.dumps(rows_summary, ensure_ascii=False),
            )
        except Exception as e:
            raise StageError(3, f"shape 失败: {e}") from e

        _save(db, ds, status="success", finished_at=datetime.now())
        log.info("dataset %s 完成", dataset_id)

    except StageError as se:
        log.exception("dataset %s 在 stage %s 失败", dataset_id, se.stage)
        if ds is not None:
            _save(db, ds, status="failed", error_message=f"stage:{se.stage} {se}",
                  finished_at=datetime.now())
    except Exception as e:
        log.exception("dataset %s 未知错误", dataset_id)
        if ds is not None:
            _save(db, ds, status="failed",
                  error_message=f"unknown: {e}\n{traceback.format_exc()[:1500]}",
                  finished_at=datetime.now())
    finally:
        db.close()


# ───────────────────── 阶段 B：report_run ─────────────────────

def _wrap_html(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;
max-width:880px;margin:32px auto;padding:0 20px;color:#222;line-height:1.7}}
h1,h2,h3{{color:#0f172a}} table{{border-collapse:collapse;width:100%;margin:12px 0}}
th,td{{border:1px solid #e2e8f0;padding:6px 10px;text-align:left}}
th{{background:#f8fafc}} pre{{background:#f8fafc;padding:12px;overflow:auto}}
</style></head><body>
{body}
</body></html>"""


def _scope_key(scope_type: str, scope_id: str | None) -> str:
    if scope_type == "national":
        return "national"
    return f"{scope_type}:{scope_id}"


def execute_report_run(run_id: int) -> None:
    """切片 dataset → render_prompt → ai_call → dispatch"""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    run: Run | None = None
    try:
        run = db.get(Run, run_id)
        if run is None:
            log.error("run %s 不存在", run_id)
            return
        if run.status not in ("pending", "failed"):
            log.warning("run %s 状态=%s 不重跑", run_id, run.status)
            return

        _save(db, run, status="running", started_at=datetime.now(), error_message=None)

        ds = db.get(Dataset, run.dataset_id) if run.dataset_id else None
        if ds is None or ds.status != "success":
            raise StageError(4, f"dataset {run.dataset_id} 不可用 (status={ds.status if ds else 'None'})")

        # 4. select_slice
        try:
            shaped = json.loads(ds.data_dump)
            scope_key = _scope_key(run.scope_type, run.scope_id)
            slice_data = shaped["scopes"].get(scope_key)
            if slice_data is None:
                raise RuntimeError(f"scope_key={scope_key} 不在 dataset.scopes 中")
        except Exception as e:
            raise StageError(4, f"select_slice 失败: {e}") from e

        # 5. render_prompt
        try:
            prompt_row = (
                db.query(Prompt)
                .filter(
                    Prompt.report_type == run.report_type,
                    Prompt.scope_type == run.scope_type,
                    Prompt.is_active == 1,
                )
                .order_by(desc(Prompt.id))
                .first()
            )
            if run.prompt_id:
                forced = db.get(Prompt, run.prompt_id)
                if forced:
                    prompt_row = forced
            if not prompt_row:
                raise RuntimeError(
                    f"找不到 active prompt: report_type={run.report_type} scope_type={run.scope_type}"
                )
            env = Environment(undefined=StrictUndefined, autoescape=False)
            env.filters["tojson"] = lambda v, **kw: json.dumps(v, ensure_ascii=False, default=str)
            tpl = env.from_string(prompt_row.content or "")
            rendered = tpl.render(
                period_start=run.period_start,
                period_end=run.period_end,
                period_start_str=run.period_start.strftime("%Y-%m-%d") if run.period_start else "",
                period_end_str=run.period_end.strftime("%Y-%m-%d") if run.period_end else "",
                scope_type=run.scope_type,
                scope_id=run.scope_id,
                scope_label=run.scope_label,
                data=slice_data,
                meta=shaped.get("_meta", {}),
            )
            _save(db, run, prompt_id=prompt_row.id, prompt_rendered=rendered)
        except Exception as e:
            raise StageError(5, f"render_prompt 失败: {e}") from e

        # 6. ai_call
        try:
            result = ai_client.complete(
                rendered,
                model=run.model or (prompt_row.model if prompt_row else None),
            )
            html_body = result.text
            title = f"{run.scope_label or '全国'} {run.report_type} {run.period_start:%Y-%m-%d}~{run.period_end:%Y-%m-%d}"
            html = _wrap_html(title, html_body)
            _save(
                db, run,
                response_text=result.text, response_html=html,
                prompt_tokens=result.prompt_tokens, completion_tokens=result.completion_tokens,
                total_tokens=result.total_tokens, latency_ms=result.latency_ms, model=result.model,
            )
        except Exception as e:
            raise StageError(6, f"ai_call 失败: {e}") from e

        # 7. dispatch
        try:
            html_path = dispatcher.write_html(run.id, html)
            public_url = dispatcher.public_url_of(run.id)
            summary = " ".join(result.text.split())[:200]

            userid_list = _userids_for_scope(db, run)
            send_result = dispatcher.send_dingtalk(
                title=title, summary_markdown=summary, detail_url=public_url,
                userid_list=userid_list,
            )
            dispatcher.write_report_row(
                db, run_id=run.id, report_type=run.report_type,
                period_start=run.period_start, period_end=run.period_end,
                title=title, summary=summary, html_path=str(html_path),
                public_url=public_url, dingtalk_status=send_result["status"],
                dingtalk_response=json.dumps(send_result, ensure_ascii=False),
            )
        except Exception as e:
            raise StageError(7, f"dispatch 失败: {e}") from e

        _save(db, run, status="success", finished_at=datetime.now())
        log.info("run %s 完成", run_id)

    except StageError as se:
        log.exception("run %s 在 stage %s 失败", run_id, se.stage)
        if run is not None:
            _save(db, run, status="failed", error_message=f"stage:{se.stage} {se}",
                  finished_at=datetime.now())
    except Exception as e:
        log.exception("run %s 未知错误", run_id)
        if run is not None:
            _save(db, run, status="failed",
                  error_message=f"unknown: {e}\n{traceback.format_exc()[:1500]}",
                  finished_at=datetime.now())
    finally:
        db.close()


# ───────────────────── 编排：fanout ─────────────────────

def _recipient_scope(rec: Recipient) -> tuple[str, str | None, str] | None:
    """从 recipient 的 role + region_ids/shop_ids 推断 scope。"""
    role = (rec.role or "").lower()
    rids = json.loads(rec.region_ids or "[]") if rec.region_ids else []
    sids = json.loads(rec.shop_ids or "[]") if rec.shop_ids else []

    if role in ("national", "全国"):
        return ("national", None, "全国")
    if role in ("super_region", "大区") and rids:
        for sr_name, ids in SUPER_REGIONS.items():
            if set(rids) == set(ids):
                return ("super_region", sr_name, sr_name)
        return None
    if role in ("region", "区域") and rids:
        rid = rids[0]
        return ("region", str(rid), REGIONS.get(rid, str(rid)))
    if role in ("shop", "店长") and sids:
        return ("shop", str(sids[0]), rec.name or str(sids[0]))
    return None


def _userids_for_scope(db, run: Run) -> list[str]:
    """按 run.scope 收集订阅者的 dingtalk_userid（OAuth 工作通知必需）。

    未解析 userid 的收件人会被静默跳过 — 保存收件人时会自动按 mobile 解析。
    """
    col = {
        "weekly": Recipient.subscribe_weekly,
        "monthly": Recipient.subscribe_monthly,
        "holiday": Recipient.subscribe_holiday,
    }.get(run.report_type)
    q = db.query(Recipient).filter(Recipient.is_active == 1)
    if col is not None:
        q = q.filter(col == 1)
    out: list[str] = []
    for r in q.all():
        sc = _recipient_scope(r)
        if sc and sc[0] == run.scope_type and sc[1] == run.scope_id and r.dingtalk_userid:
            out.append(r.dingtalk_userid)
    return out


def fanout_dataset(dataset_id: int, *, trigger_type: str = "scheduled") -> list[int]:
    """按 recipients 展开 N 个 report_run。返回 run_id 列表。"""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        ds = db.get(Dataset, dataset_id)
        if ds is None or ds.status != "success":
            log.warning("dataset %s 不可用，无法 fanout", dataset_id)
            return []

        col = {
            "weekly": Recipient.subscribe_weekly,
            "monthly": Recipient.subscribe_monthly,
            "holiday": Recipient.subscribe_holiday,
        }.get(ds.period_type)
        q = db.query(Recipient).filter(Recipient.is_active == 1)
        if col is not None:
            q = q.filter(col == 1)

        # 同一 scope 多个收件人合并成一个 run（dispatch 时 userid_list 多选）
        scopes_seen: set[tuple[str, str | None]] = set()
        run_ids: list[int] = []
        for rec in q.all():
            sc = _recipient_scope(rec)
            if not sc:
                continue
            scope_type, scope_id, scope_label = sc
            if (scope_type, scope_id) in scopes_seen:
                continue
            scopes_seen.add((scope_type, scope_id))

            run = Run(
                trigger_type=trigger_type,
                report_type=ds.period_type,
                dataset_id=ds.id,
                scope_type=scope_type,
                scope_id=scope_id,
                scope_label=scope_label,
                period_start=ds.period_start,
                period_end=ds.period_end,
                status="pending",
            )
            db.add(run)
            db.flush()
            run_ids.append(run.id)
        db.commit()
        log.info("dataset %s fanout → %d 个 run: %s", dataset_id, len(run_ids), run_ids)
        return run_ids
    finally:
        db.close()

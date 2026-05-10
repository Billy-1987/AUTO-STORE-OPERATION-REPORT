# 文件作用：加载并渲染 sql/{report_type}/*.sql.j2 模板
# 版本：v0.2.0 — 派生 YoY 参数（yoy_start/yoy_end/yoy_months_count/period_end_next_day），让模板写半开区间
# 版本：v0.1.0 — 初始化

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound

SQL_ROOT = Path(__file__).resolve().parent.parent.parent / "sql"


def _env(report_type: str) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(SQL_ROOT / report_type)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )


def _shift_year(d: datetime, years: int = -1) -> datetime:
    # 闰年 2-29 退一年用 2-28，避免 ValueError
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(year=d.year + years, day=28)


def _months_between(start: datetime, end_inclusive: datetime) -> int:
    # [start, end_inclusive] 跨越的自然月数（含两端）
    return (end_inclusive.year - start.year) * 12 + (end_inclusive.month - start.month) + 1


def _build_ctx(period_start: datetime, period_end: datetime) -> dict[str, Any]:
    yoy_start = _shift_year(period_start, -1)
    yoy_end = _shift_year(period_end, -1)
    period_end_next = period_end + timedelta(days=1)
    yoy_end_next = yoy_end + timedelta(days=1)
    return {
        "period_start": period_start,
        "period_end": period_end,
        "period_start_str": period_start.strftime("%Y-%m-%d"),
        "period_end_str": period_end.strftime("%Y-%m-%d"),
        "period_end_next_day_str": period_end_next.strftime("%Y-%m-%d"),
        "yoy_start": yoy_start,
        "yoy_end": yoy_end,
        "yoy_start_str": yoy_start.strftime("%Y-%m-%d"),
        "yoy_end_str": yoy_end.strftime("%Y-%m-%d"),
        "yoy_end_next_day_str": yoy_end_next.strftime("%Y-%m-%d"),
        "yoy_months_count": _months_between(yoy_start, yoy_end),
    }


def load_sqls(
    report_type: str,
    *,
    period_start: datetime,
    period_end: datetime,
    extra: dict[str, Any] | None = None,
) -> list[tuple[str, str]]:
    """渲染 report_type 目录下所有 .sql.j2，返回 [(name, sql), ...]

    name = 文件名去掉 .sql.j2，按字母序，方便 shaper 按命名约定取数。
    """
    folder = SQL_ROOT / report_type
    if not folder.exists():
        raise FileNotFoundError(f"sql 目录不存在: {folder}")

    files = sorted(folder.glob("*.sql.j2"))
    if not files:
        raise FileNotFoundError(
            f"sql/{report_type}/ 下还没有 .sql.j2 模板。需要先把 bigoffs-db plugin 的 SQL 落到这里。"
        )

    env = _env(report_type)
    ctx: dict[str, Any] = _build_ctx(period_start, period_end)
    if extra:
        ctx.update(extra)

    out: list[tuple[str, str]] = []
    for f in files:
        try:
            tpl = env.get_template(f.name)
        except TemplateNotFound as e:
            raise FileNotFoundError(f"模板加载失败: {f}") from e
        out.append((f.name.removesuffix(".sql.j2"), tpl.render(**ctx)))
    return out

# 文件作用：把 6 个 SQL 结果聚合成 dataset，直接按 scope 切好。
# 版本：v0.3.0 — 重构：输出 scopes dict，每个 scope 都是一份完整可喂 prompt 的视图
# 版本：v0.2.0 — 完整 4 层 + 双口径 + 同比 + TOP5/TOP20 + 增长拆解
# 版本：v0.1.0 — 骨架占位
#
# 输出结构：
#   {
#     "_meta": {period_type, period_start, period_end, store_count_total, same_store_count_total},
#     "scopes": {
#        "national":             { 完整视图 },
#        "super_region:华北大区":  { 完整视图 },
#        "super_region:西南大区":  { 完整视图 },
#        "region:68":            { 完整视图 },        # 8 个区
#        ...
#        "shop:3079":            { 简化视图（店长版） },  # 每家本期有销售的门店
#     }
#   }
#
# 红线：
# 1. AI 只接聚合数据（这里输出 ≤几 KB 的切片）
# 3. 客流先门店再区域两层（SQL 已先按 shop_id sum，scope view 第二层 sum）
# 4. 同店 = 上年同期跨越的每个自然月都有销售（SQL 1）

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any, Iterable

# 区域映射（CLAUDE.md 红线常量）
REGIONS: dict[int, str] = {
    68: "华北区", 67: "北京区", 163: "华中区", 75: "华东区",
    66: "东北区", 69: "西南区", 165: "西北区", 164: "华南区",
}
SUPER_REGIONS: dict[str, list[int]] = {
    "华北大区": [68, 67, 163, 75, 66],
    "西南大区": [69, 165, 164],
}
REGION_OVERRIDE: dict[int, int] = {3079: 163, 3066: 67}
EXCLUDE_SHOPS: set[int] = {3018}

RAW_NUMERATOR_FIELDS = (
    "sales_yuan", "qty", "orders",
    "old_user_sales_yuan", "member_sales_yuan",
    "new_members", "traffic",
)


# ───────────────────────── helpers ─────────────────────────

def _f(v: Any) -> float:
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


def _i(v: Any) -> int:
    return 0 if v is None else int(v)


def _safe_div(a: float, b: float) -> float | None:
    return a / b if b else None


def _yoy(curr: float | None, prev: float | None) -> float | None:
    if curr is None or prev is None or prev == 0:
        return None
    return (curr - prev) / prev


def _resolve_region(shop_id: int, declared: int | None) -> int | None:
    return REGION_OVERRIDE.get(shop_id, declared)


def _super_of(region_id: int | None) -> str | None:
    if region_id is None:
        return None
    for sr, ids in SUPER_REGIONS.items():
        if region_id in ids:
            return sr
    return None


def _zero_raw() -> dict[str, float]:
    return {k: 0.0 for k in RAW_NUMERATOR_FIELDS}


def _add(a: dict[str, float], b: dict[str, float]) -> None:
    for k in RAW_NUMERATOR_FIELDS:
        a[k] = a.get(k, 0.0) + b.get(k, 0.0)


def _derive(raw: dict[str, float]) -> dict[str, float | None]:
    """每层重算除法指标，不跨层平均。"""
    sales = raw.get("sales_yuan", 0.0)
    orders = raw.get("orders", 0.0)
    qty = raw.get("qty", 0.0)
    traffic = raw.get("traffic", 0.0)
    old = raw.get("old_user_sales_yuan", 0.0)
    return {
        **raw,
        "atv": _safe_div(sales, orders),
        "upt": _safe_div(qty, orders),
        "old_user_ratio": _safe_div(old, sales),
        "conversion": _safe_div(orders, traffic),
    }


def _yoy_block(curr: dict, prev: dict) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for k in ("sales_yuan", "qty", "orders", "atv", "upt", "new_members", "traffic"):
        out[k] = _yoy(curr.get(k), prev.get(k))
    return out


# ───────────────────────── parse ─────────────────────────

def _parse(rows_by_query: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    shop_meta: dict[int, dict[str, Any]] = {}
    for r in rows_by_query.get("06_shop_meta", []):
        sid = _i(r["shop_id"])
        if sid in EXCLUDE_SHOPS:
            continue
        rid = _resolve_region(sid, r.get("region_id"))
        rid = _i(rid) if rid is not None else None
        shop_meta[sid] = {
            "shop_id": sid,
            "shop_name": r.get("shop_name") or "",
            "region_id": rid,
            "region_name": REGIONS.get(rid),
            "super_region": _super_of(rid),
            "opening_date": r.get("opening_time"),
        }

    same_store_set: set[int] = {
        _i(r["shop_id"]) for r in rows_by_query.get("01_same_store_shops", [])
        if _i(r["shop_id"]) not in EXCLUDE_SHOPS
    }

    metrics: dict[tuple[str, int], dict[str, float]] = defaultdict(_zero_raw)

    for r in rows_by_query.get("02_shop_metrics", []):
        sid = _i(r["shop_id"])
        if sid in EXCLUDE_SHOPS:
            continue
        m = metrics[(r["period_tag"], sid)]
        m["sales_yuan"] = _f(r["sales_yuan"])
        m["qty"] = _f(r["qty"])
        m["orders"] = _f(r["orders"])
        m["old_user_sales_yuan"] = _f(r["old_user_sales_yuan"])
        m["member_sales_yuan"] = _f(r["member_sales_yuan"])

    for r in rows_by_query.get("03_shop_traffic", []):
        sid = _i(r["shop_id"])
        if sid in EXCLUDE_SHOPS:
            continue
        metrics[(r["period_tag"], sid)]["traffic"] = _f(r["traffic"])

    for r in rows_by_query.get("04_shop_new_members", []):
        sid = _i(r["shop_id"])
        if sid in EXCLUDE_SHOPS:
            continue
        metrics[(r["period_tag"], sid)]["new_members"] = _f(r["new_members"])

    brand_metrics: list[dict[str, Any]] = []
    for r in rows_by_query.get("05_shop_brand_metrics", []):
        sid = _i(r["shop_id"])
        if sid in EXCLUDE_SHOPS:
            continue
        brand_metrics.append({
            "period_tag": r["period_tag"],
            "shop_id": sid,
            "brand_id": _i(r["brand_id"]),
            "brand_name": r.get("brand_name") or "",
            "sales_yuan": _f(r["sales_yuan"]),
            "qty": _f(r["qty"]),
            "orders": _f(r["orders"]),
        })

    return {
        "shop_meta": shop_meta,
        "same_store_set": same_store_set,
        "shop_metrics": metrics,
        "brand_metrics": brand_metrics,
    }


# ───────────────────────── 单 scope 视图 ─────────────────────────

def _agg(metrics: dict[tuple[str, int], dict[str, float]], shop_ids: set[int]) -> tuple[dict, dict]:
    raw_curr = _zero_raw()
    raw_prev = _zero_raw()
    for (tag, sid), m in metrics.items():
        if sid not in shop_ids:
            continue
        if tag == "curr":
            _add(raw_curr, m)
        elif tag == "yoy":
            _add(raw_prev, m)
    return _derive(raw_curr), _derive(raw_prev)


def _store_view(parsed: dict, sid: int) -> dict[str, Any] | None:
    metrics = parsed["shop_metrics"]
    meta = parsed["shop_meta"].get(sid)
    if not meta:
        return None
    curr_raw = metrics.get(("curr", sid), _zero_raw())
    prev_raw = metrics.get(("yoy", sid), _zero_raw())
    if not curr_raw.get("sales_yuan") and not curr_raw.get("orders"):
        return None
    curr = _derive(curr_raw)
    prev = _derive(prev_raw)
    return {
        **meta,
        "is_same_store": sid in parsed["same_store_set"],
        "is_new": sid not in parsed["same_store_set"],
        "metrics": curr,
        "metrics_yoy": _yoy_block(curr, prev),
    }


def _top_n_stores(parsed: dict, shop_ids: set[int], n: int) -> list[dict]:
    views = [v for v in (_store_view(parsed, s) for s in shop_ids) if v]
    views.sort(key=lambda x: -(x["metrics"].get("sales_yuan") or 0))
    return [{"rank": i + 1, **v} for i, v in enumerate(views[:n])]


def _new_stores_in(parsed: dict, shop_ids: set[int]) -> list[dict]:
    views = [v for v in (_store_view(parsed, s) for s in shop_ids) if v and v["is_new"]]
    views.sort(key=lambda x: -(x["metrics"].get("sales_yuan") or 0))
    return views


def _top20_brands_in(parsed: dict, shop_ids: set[int]) -> list[dict]:
    same_store = parsed["same_store_set"] & shop_ids
    rows = parsed["brand_metrics"]

    curr_total: dict[int, dict[str, Any]] = {}
    for r in rows:
        if r["period_tag"] != "curr" or r["shop_id"] not in shop_ids:
            continue
        bid = r["brand_id"]
        b = curr_total.setdefault(bid, {
            "brand_id": bid, "brand_name": r["brand_name"],
            "sales_yuan": 0.0, "qty": 0.0, "orders": 0.0, "shop_set": set(),
        })
        b["sales_yuan"] += r["sales_yuan"]
        b["qty"] += r["qty"]
        b["orders"] += r["orders"]
        b["shop_set"].add(r["shop_id"])

    same_curr: dict[int, float] = defaultdict(float)
    same_prev: dict[int, float] = defaultdict(float)
    for r in rows:
        if r["shop_id"] not in same_store:
            continue
        if r["period_tag"] == "curr":
            same_curr[r["brand_id"]] += r["sales_yuan"]
        elif r["period_tag"] == "yoy":
            same_prev[r["brand_id"]] += r["sales_yuan"]

    total_sales = sum(b["sales_yuan"] for b in curr_total.values()) or 1.0
    sorted_brands = sorted(curr_total.values(), key=lambda x: -x["sales_yuan"])[:20]

    out: list[dict] = []
    for i, b in enumerate(sorted_brands):
        bid = b["brand_id"]
        prev = same_prev.get(bid, 0.0)
        cur = same_curr.get(bid, 0.0)
        if prev >= 1_000_000:
            yoy_label = _yoy(cur, prev)
        elif prev > 0:
            yoy_label = "小基数"
        else:
            yoy_label = "新进"
        out.append({
            "rank": i + 1,
            "brand_id": bid,
            "brand_name": b["brand_name"],
            "sales_yuan": b["sales_yuan"],
            "share_pct": b["sales_yuan"] / total_sales,
            "qty": b["qty"],
            "orders": b["orders"],
            "atv": _safe_div(b["sales_yuan"], b["orders"]),
            "upt": _safe_div(b["qty"], b["orders"]),
            "shop_coverage": len(b["shop_set"]),
            "same_store_yoy": yoy_label,
        })
    return out


def _growth_in(parsed: dict, shop_ids: set[int]) -> dict[str, Any]:
    metrics = parsed["shop_metrics"]
    same_store = parsed["same_store_set"] & shop_ids

    total_curr = sum(metrics.get(("curr", s), {}).get("sales_yuan", 0.0) for s in shop_ids)
    total_prev = sum(metrics.get(("yoy", s), {}).get("sales_yuan", 0.0) for s in shop_ids)
    total_inc = total_curr - total_prev

    new_shops = shop_ids - same_store
    new_contrib = sum(metrics.get(("curr", s), {}).get("sales_yuan", 0.0) for s in new_shops)

    same_curr_sum = sum(metrics.get(("curr", s), {}).get("sales_yuan", 0.0) for s in same_store)
    same_prev_sum = sum(metrics.get(("yoy", s), {}).get("sales_yuan", 0.0) for s in same_store)
    same_inc = same_curr_sum - same_prev_sum

    return {
        "total_increment_yuan": total_inc,
        "new_store_contribution_yuan": new_contrib,
        "new_store_pct_of_total": _safe_div(new_contrib, total_inc),
        "same_store_increment_yuan": same_inc,
        "same_store_pct_of_total": _safe_div(same_inc, total_inc),
    }


def _scope_summary(parsed: dict, shop_ids: set[int]) -> dict[str, Any]:
    """只算计数 + 双口径汇总 + 同比，不含 TOP/品牌/增长。给 sub_breakdown 用。"""
    metrics = parsed["shop_metrics"]
    same_store = parsed["same_store_set"]
    active = {sid for (tag, sid) in metrics if tag == "curr" and sid in shop_ids}
    same_in = shop_ids & same_store

    overall_curr, overall_prev = _agg(metrics, shop_ids)
    same_curr, same_prev = _agg(metrics, same_in)

    return {
        "store_count": len(active),
        "same_store_count": len(same_in & active),
        "new_store_count": len(active - same_store),
        "overall": overall_curr,
        "overall_yoy": _yoy_block(overall_curr, overall_prev),
        "same_store": same_curr,
        "same_store_yoy": _yoy_block(same_curr, same_prev),
    }


def _full_scope_view(
    parsed: dict,
    *,
    scope_type: str,
    scope_id: str | None,
    scope_label: str,
    shop_ids: set[int],
    sub_breakdown: list[dict] | None,
) -> dict[str, Any]:
    """region/super_region/national 用：完整视图"""
    summary = _scope_summary(parsed, shop_ids)
    return {
        "scope_type": scope_type,
        "scope_id": scope_id,
        "scope_label": scope_label,
        **summary,
        "sub_breakdown": sub_breakdown or [],
        "top5_stores": _top_n_stores(parsed, shop_ids, 5),
        "new_stores": _new_stores_in(parsed, shop_ids),
        "top20_brands": _top20_brands_in(parsed, shop_ids),
        "growth_decomposition": _growth_in(parsed, shop_ids),
    }


def _shop_scope_view(parsed: dict, sid: int) -> dict[str, Any] | None:
    """门店级简化视图（店长版）：自己的指标 + 该门店 TOP10 品牌"""
    sv = _store_view(parsed, sid)
    if sv is None:
        return None
    # 该门店 TOP10 品牌（不含同店同比，店长视角）
    top_brands: list[dict] = []
    for r in parsed["brand_metrics"]:
        if r["shop_id"] != sid or r["period_tag"] != "curr":
            continue
        top_brands.append({
            "brand_id": r["brand_id"], "brand_name": r["brand_name"],
            "sales_yuan": r["sales_yuan"], "qty": r["qty"], "orders": r["orders"],
            "atv": _safe_div(r["sales_yuan"], r["orders"]),
            "upt": _safe_div(r["qty"], r["orders"]),
        })
    top_brands.sort(key=lambda x: -x["sales_yuan"])
    top10 = [{"rank": i + 1, **b} for i, b in enumerate(top_brands[:10])]
    return {
        "scope_type": "shop",
        "scope_id": str(sid),
        "scope_label": sv["shop_name"],
        "shop_meta": {k: sv[k] for k in ("shop_id", "shop_name", "region_id", "region_name", "super_region", "opening_date", "is_same_store", "is_new")},
        "metrics": sv["metrics"],
        "metrics_yoy": sv["metrics_yoy"],
        "top10_brands": top10,
    }


# ───────────────────────── entry ─────────────────────────

def shape(rows_by_query: dict[str, list[dict[str, Any]]], *, period_type: str | None = None,
          period_start: Any = None, period_end: Any = None) -> dict[str, Any]:
    parsed = _parse(rows_by_query)
    meta = parsed["shop_meta"]
    metrics = parsed["shop_metrics"]
    all_shops = set(meta.keys())
    active_shops = {sid for (tag, sid) in metrics if tag == "curr"}

    scopes: dict[str, Any] = {}

    # ── 区域级 sub_breakdown 模板（national 和 super_region 共用）──
    region_summaries: dict[int, dict] = {}
    for rid, rname in REGIONS.items():
        rshops = {sid for sid, m in meta.items() if m["region_id"] == rid}
        region_summaries[rid] = {
            "scope_type": "region", "id": rid, "name": rname,
            **_scope_summary(parsed, rshops),
        }

    # ── 全国 ──
    national_breakdown = sorted(
        region_summaries.values(),
        key=lambda x: -(x["overall"].get("sales_yuan") or 0),
    )
    scopes["national"] = _full_scope_view(
        parsed, scope_type="national", scope_id=None, scope_label="全国",
        shop_ids=all_shops, sub_breakdown=national_breakdown,
    )

    # ── 大区 ──
    for sr_name, region_ids in SUPER_REGIONS.items():
        sr_shops = {sid for sid, m in meta.items() if m["region_id"] in region_ids}
        sr_breakdown = sorted(
            (region_summaries[rid] for rid in region_ids if rid in region_summaries),
            key=lambda x: -(x["overall"].get("sales_yuan") or 0),
        )
        scopes[f"super_region:{sr_name}"] = _full_scope_view(
            parsed, scope_type="super_region", scope_id=sr_name, scope_label=sr_name,
            shop_ids=sr_shops, sub_breakdown=sr_breakdown,
        )

    # ── 区域 ──
    for rid, rname in REGIONS.items():
        rshops = {sid for sid, m in meta.items() if m["region_id"] == rid}
        if not (rshops & active_shops):  # 该区无活跃门店跳过
            continue
        # 区域版的 sub_breakdown = 该区门店级简表
        store_breakdown = []
        for s in sorted(rshops, key=lambda s: -(metrics.get(("curr", s), {}).get("sales_yuan", 0.0))):
            sv = _store_view(parsed, s)
            if sv:
                store_breakdown.append({
                    "scope_type": "shop", "id": sv["shop_id"], "name": sv["shop_name"],
                    "is_same_store": sv["is_same_store"], "is_new": sv["is_new"],
                    "metrics": sv["metrics"], "metrics_yoy": sv["metrics_yoy"],
                })
        scopes[f"region:{rid}"] = _full_scope_view(
            parsed, scope_type="region", scope_id=str(rid), scope_label=rname,
            shop_ids=rshops, sub_breakdown=store_breakdown,
        )

    # ── 门店 ──
    for sid in active_shops:
        v = _shop_scope_view(parsed, sid)
        if v:
            scopes[f"shop:{sid}"] = v

    return {
        "_meta": {
            "period_type": period_type,
            "period_start": str(period_start) if period_start else None,
            "period_end": str(period_end) if period_end else None,
            "store_count_total": len(active_shops),
            "same_store_count_total": len(parsed["same_store_set"] & active_shops),
        },
        "scopes": scopes,
    }

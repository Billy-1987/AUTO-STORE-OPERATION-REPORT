# 文件作用：把 6 个 SQL 结果聚合成 dataset，按 scope 切好；输出**中文字段名**给 AI 用
# 版本：v0.4.0 — 字段全中文，prompt 和数据完全用同一套术语，LLM 零猜测
# 版本：v0.3.0 — 重构按 scope 切片
# 版本：v0.2.0 — 完整 4 层 + 双口径 + 同比 + TOP5/TOP20 + 增长拆解
#
# 输出结构：
#   {
#     "_meta": {...},   # 内部用，AI 不会看
#     "scopes": {
#        "national":              { 中文键的完整视图 },
#        "super_region:华北大区":  { ... },
#        "region:68":             { ... },
#        "shop:3079":             { ... }
#     }
#   }
#
# 红线：
# 1. AI 只接聚合数据
# 3. 客流先门店再区域两层
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

# 内部聚合用英文字段（计算用），输出时再翻译成中文
_RAW_FIELDS = (
    "sales_yuan", "qty", "orders",
    "old_user_sales_yuan", "member_sales_yuan",
    "new_members", "traffic",
)

# 中文输出字段映射
_M_RAW = {
    "sales_yuan": "销售额",
    "qty": "销量",
    "orders": "订单量",
    "old_user_sales_yuan": "老客销售额",
    "member_sales_yuan": "会员销售额",
    "new_members": "新增会员",
    "traffic": "客流量",
}
_M_DERIVED = {
    "atv": "客单价",
    "upt": "连带率",
    "old_user_ratio": "老客销售占比",
    "conversion": "提袋率",
}
# 同比展示的字段（提袋率/老客销比不算同比）
_YOY_FIELDS = ("sales_yuan", "qty", "orders", "atv", "upt", "new_members", "traffic")


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
    return {k: 0.0 for k in _RAW_FIELDS}


def _add(a: dict[str, float], b: dict[str, float]) -> None:
    for k in _RAW_FIELDS:
        a[k] = a.get(k, 0.0) + b.get(k, 0.0)


def _derive_zh(raw: dict[str, float]) -> dict[str, Any]:
    """从英文 raw 算出中文键的指标块（含原料 + 派生）。"""
    sales = raw.get("sales_yuan", 0.0)
    orders = raw.get("orders", 0.0)
    qty = raw.get("qty", 0.0)
    traffic = raw.get("traffic", 0.0)
    old = raw.get("old_user_sales_yuan", 0.0)
    out: dict[str, Any] = {}
    for ek, zh in _M_RAW.items():
        out[zh] = raw.get(ek, 0.0)
    out["客单价"] = _safe_div(sales, orders)
    out["连带率"] = _safe_div(qty, orders)
    out["老客销售占比"] = _safe_div(old, sales)
    out["提袋率"] = _safe_div(orders, traffic)
    return out


def _yoy_block_zh(curr_raw: dict[str, float], prev_raw: dict[str, float]) -> dict[str, Any]:
    """同比块（中文键）。提袋率/老客销比不算同比。"""
    # 派生指标的同比要先派生再算
    curr_atv = _safe_div(curr_raw.get("sales_yuan", 0), curr_raw.get("orders", 0))
    prev_atv = _safe_div(prev_raw.get("sales_yuan", 0), prev_raw.get("orders", 0))
    curr_upt = _safe_div(curr_raw.get("qty", 0), curr_raw.get("orders", 0))
    prev_upt = _safe_div(prev_raw.get("qty", 0), prev_raw.get("orders", 0))
    return {
        "销售额": _yoy(curr_raw.get("sales_yuan"), prev_raw.get("sales_yuan")),
        "销量": _yoy(curr_raw.get("qty"), prev_raw.get("qty")),
        "订单量": _yoy(curr_raw.get("orders"), prev_raw.get("orders")),
        "客单价": _yoy(curr_atv, prev_atv),
        "连带率": _yoy(curr_upt, prev_upt),
        "新增会员": _yoy(curr_raw.get("new_members"), prev_raw.get("new_members")),
        "客流量": _yoy(curr_raw.get("traffic"), prev_raw.get("traffic")),
    }


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
            "门店ID": sid,
            "门店名": r.get("shop_name") or "",
            "区域ID": rid,
            "区域名": REGIONS.get(rid),
            "大区": _super_of(rid),
            "开业日期": str(r["opening_time"]) if r.get("opening_time") else None,
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

def _agg_raw(metrics: dict[tuple[str, int], dict[str, float]], shop_ids: set[int]) -> tuple[dict, dict]:
    raw_curr = _zero_raw()
    raw_prev = _zero_raw()
    for (tag, sid), m in metrics.items():
        if sid not in shop_ids:
            continue
        if tag == "curr":
            _add(raw_curr, m)
        elif tag == "yoy":
            _add(raw_prev, m)
    return raw_curr, raw_prev


def _store_view_zh(parsed: dict, sid: int) -> dict[str, Any] | None:
    metrics = parsed["shop_metrics"]
    meta = parsed["shop_meta"].get(sid)
    if not meta:
        return None
    curr_raw = metrics.get(("curr", sid), _zero_raw())
    prev_raw = metrics.get(("yoy", sid), _zero_raw())
    if not curr_raw.get("sales_yuan") and not curr_raw.get("orders"):
        return None
    return {
        **meta,
        "是否同店": sid in parsed["same_store_set"],
        "是否新店": sid not in parsed["same_store_set"],
        "指标": _derive_zh(curr_raw),
        "指标同比": _yoy_block_zh(curr_raw, prev_raw),
    }


def _top_n_stores_zh(parsed: dict, shop_ids: set[int], n: int) -> list[dict]:
    views = [v for v in (_store_view_zh(parsed, s) for s in shop_ids) if v]
    views.sort(key=lambda x: -(x["指标"].get("销售额") or 0))
    return [{"排名": i + 1, **v} for i, v in enumerate(views[:n])]


def _new_stores_zh(parsed: dict, shop_ids: set[int]) -> list[dict]:
    views = [v for v in (_store_view_zh(parsed, s) for s in shop_ids) if v and v["是否新店"]]
    views.sort(key=lambda x: -(x["指标"].get("销售额") or 0))
    return views


def _top20_brands_zh(parsed: dict, shop_ids: set[int]) -> list[dict]:
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
            yoy_label: Any = _yoy(cur, prev)
        elif prev > 0:
            yoy_label = "小基数"
        else:
            yoy_label = "新进"
        out.append({
            "排名": i + 1,
            "品牌ID": bid,
            "品牌名": b["brand_name"],
            "销售额": b["sales_yuan"],
            "占比": b["sales_yuan"] / total_sales,
            "销量": b["qty"],
            "订单量": b["orders"],
            "客单价": _safe_div(b["sales_yuan"], b["orders"]),
            "连带率": _safe_div(b["qty"], b["orders"]),
            "覆盖门店": len(b["shop_set"]),
            "同店同比": yoy_label,
        })
    return out


def _growth_zh(parsed: dict, shop_ids: set[int]) -> dict[str, Any]:
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
        "整体销售额增量": total_inc,
        "新店贡献": new_contrib,
        "新店占整体增量比": _safe_div(new_contrib, total_inc),
        "同店增量": same_inc,
        "同店占整体增量比": _safe_div(same_inc, total_inc),
    }


def _scope_summary_zh(parsed: dict, shop_ids: set[int]) -> dict[str, Any]:
    """计数 + 双口径汇总 + 同比，给 sub_breakdown 用。"""
    metrics = parsed["shop_metrics"]
    same_store = parsed["same_store_set"]
    active = {sid for (tag, sid) in metrics if tag == "curr" and sid in shop_ids}
    same_in = shop_ids & same_store

    overall_curr_raw, overall_prev_raw = _agg_raw(metrics, shop_ids)
    same_curr_raw, same_prev_raw = _agg_raw(metrics, same_in)

    return {
        "门店数": len(active),
        "同店数": len(same_in & active),
        "新店数": len(active - same_store),
        "整体": _derive_zh(overall_curr_raw),
        "整体同比": _yoy_block_zh(overall_curr_raw, overall_prev_raw),
        "同店": _derive_zh(same_curr_raw),
        "同店同比": _yoy_block_zh(same_curr_raw, same_prev_raw),
    }


def _full_view_zh(
    parsed: dict,
    *,
    scope_type: str,
    scope_label: str,
    shop_ids: set[int],
    sub_breakdown: list[dict] | None,
    sub_breakdown_key: str,
) -> dict[str, Any]:
    """region/super_region/national 用：完整中文视图。"""
    SCOPE_TYPE_ZH = {"national": "全国", "super_region": "大区", "region": "区域"}
    summary = _scope_summary_zh(parsed, shop_ids)
    return {
        "范围类型": SCOPE_TYPE_ZH.get(scope_type, scope_type),
        "范围名称": scope_label,
        **summary,
        sub_breakdown_key: sub_breakdown or [],
        "TOP5门店": _top_n_stores_zh(parsed, shop_ids, 5),
        "新店列表": _new_stores_zh(parsed, shop_ids),
        "TOP20品牌": _top20_brands_zh(parsed, shop_ids),
        "增长拆解": _growth_zh(parsed, shop_ids),
    }


def _shop_view_zh(parsed: dict, sid: int) -> dict[str, Any] | None:
    """门店级简化视图（店长版）。"""
    sv = _store_view_zh(parsed, sid)
    if sv is None:
        return None

    top_brands: list[dict] = []
    total_sales = 0.0
    for r in parsed["brand_metrics"]:
        if r["shop_id"] != sid or r["period_tag"] != "curr":
            continue
        total_sales += r["sales_yuan"]
        top_brands.append({
            "品牌ID": r["brand_id"], "品牌名": r["brand_name"],
            "销售额": r["sales_yuan"], "销量": r["qty"], "订单量": r["orders"],
            "客单价": _safe_div(r["sales_yuan"], r["orders"]),
            "连带率": _safe_div(r["qty"], r["orders"]),
        })
    top_brands.sort(key=lambda x: -x["销售额"])
    top10 = []
    for i, b in enumerate(top_brands[:10]):
        b["销售占比"] = b["销售额"] / total_sales if total_sales else None
        top10.append({"排名": i + 1, **b})

    return {
        "范围类型": "门店",
        "范围名称": sv["门店名"],
        "门店信息": {k: sv[k] for k in ("门店ID", "门店名", "区域名", "大区", "开业日期", "是否同店", "是否新店")},
        "指标": sv["指标"],
        "指标同比": sv["指标同比"],
        "TOP10品牌": top10,
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

    # ── 区域级 sub_breakdown 模板 ──
    region_summaries: dict[int, dict] = {}
    for rid, rname in REGIONS.items():
        rshops = {sid for sid, m in meta.items() if m["区域ID"] == rid}
        region_summaries[rid] = {
            "类型": "区域",
            "ID": rid,
            "名称": rname,
            **_scope_summary_zh(parsed, rshops),
        }

    # ── 全国 ──
    national_breakdown = sorted(
        region_summaries.values(),
        key=lambda x: -(x["整体"].get("销售额") or 0),
    )
    scopes["national"] = _full_view_zh(
        parsed, scope_type="national", scope_label="全国",
        shop_ids=all_shops, sub_breakdown=national_breakdown,
        sub_breakdown_key="区域明细",
    )

    # ── 大区 ──
    for sr_name, region_ids in SUPER_REGIONS.items():
        sr_shops = {sid for sid, m in meta.items() if m["区域ID"] in region_ids}
        sr_breakdown = sorted(
            (region_summaries[rid] for rid in region_ids if rid in region_summaries),
            key=lambda x: -(x["整体"].get("销售额") or 0),
        )
        scopes[f"super_region:{sr_name}"] = _full_view_zh(
            parsed, scope_type="super_region", scope_label=sr_name,
            shop_ids=sr_shops, sub_breakdown=sr_breakdown,
            sub_breakdown_key="区域明细",
        )

    # ── 区域 ──
    for rid, rname in REGIONS.items():
        rshops = {sid for sid, m in meta.items() if m["区域ID"] == rid}
        if not (rshops & active_shops):
            continue
        store_breakdown = []
        for s in sorted(rshops, key=lambda s: -(metrics.get(("curr", s), {}).get("sales_yuan", 0.0))):
            sv = _store_view_zh(parsed, s)
            if sv:
                store_breakdown.append({
                    "类型": "门店",
                    "ID": sv["门店ID"],
                    "名称": sv["门店名"],
                    "是否同店": sv["是否同店"],
                    "是否新店": sv["是否新店"],
                    "指标": sv["指标"],
                    "指标同比": sv["指标同比"],
                })
        scopes[f"region:{rid}"] = _full_view_zh(
            parsed, scope_type="region", scope_label=rname,
            shop_ids=rshops, sub_breakdown=store_breakdown,
            sub_breakdown_key="门店明细",
        )

    # ── 门店 ──
    for sid in active_shops:
        v = _shop_view_zh(parsed, sid)
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

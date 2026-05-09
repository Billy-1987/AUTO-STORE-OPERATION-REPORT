# 文件作用：元数据接口（模型清单、区域映射、门店清单、健康检查）
# 版本：v0.2.0 — 新增 /api/shops（应用 REGION_OVERRIDE/EXCLUDE_SHOPS，给前端 scope 选择器用）
# 版本：v0.1.0

from fastapi import APIRouter

from app.config import SUPPORTED_MODELS, get_settings
from app.doris.connection import query_ro
from app.pipeline.data_shaper import REGION_OVERRIDE, EXCLUDE_SHOPS

router = APIRouter(prefix="/api", tags=["meta"])


REGIONS = {
    68: "华北区", 67: "北京区", 163: "华中区", 75: "华东区",
    66: "东北区", 69: "西南区", 165: "西北区", 164: "华南区",
}
SUPER_REGIONS = {
    "华北大区": [68, 67, 163, 75, 66],
    "西南大区": [69, 165, 164],
}


@router.get("/models")
def list_models():
    s = get_settings()
    return {
        "default": s.ai_default_model,
        "supported": SUPPORTED_MODELS,
    }


@router.get("/regions")
def list_regions():
    return {"regions": REGIONS, "super_regions": SUPER_REGIONS}


@router.get("/shops")
def list_shops():
    """活跃门店清单（剔除线上汇总号 EXCLUDE_SHOPS，应用 REGION_OVERRIDE）。"""
    rows = query_ro(
        """
        SELECT s.id AS shop_id,
               s.name AS shop_name,
               si.region_Id AS region_id,
               r.name AS region_name
        FROM bigoffs_sync.b_shop s
        LEFT JOIN bigoffs_sync.shop_info si ON si.shop_id = s.id
        LEFT JOIN bigoffs_sync.region_info r ON r.id = si.region_Id
        WHERE s.status = 1
        ORDER BY si.region_Id, s.id
        """
    )
    out = []
    for r in rows:
        sid = int(r["shop_id"])
        if sid in EXCLUDE_SHOPS:
            continue
        rid = REGION_OVERRIDE.get(sid, r.get("region_id"))
        out.append({
            "shop_id": sid,
            "shop_name": r.get("shop_name") or "",
            "region_id": int(rid) if rid is not None else None,
            "region_name": REGIONS.get(int(rid)) if rid is not None else None,
        })
    return {"shops": out}


@router.get("/system/info")
def system_info():
    s = get_settings()
    return {
        "version": "0.1.0",
        "ai_base_url": s.ai_base_url,
        "default_model": s.ai_default_model,
        "doris_ro_db": s.doris_ro_db,
        "doris_rw_db": s.doris_rw_db,
        "public_base_url": s.public_base_url,
    }

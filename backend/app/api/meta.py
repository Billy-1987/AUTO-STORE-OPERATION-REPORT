# 文件作用：元数据接口（模型清单、区域映射、健康检查）
# 版本：v0.1.0

from fastapi import APIRouter

from app.config import SUPPORTED_MODELS, get_settings

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

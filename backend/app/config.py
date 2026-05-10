# 文件作用：集中读取 .env 配置，pydantic-settings 校验
# 版本：v0.3.0 — 加 MODEL_PRICING（CNY per 1M tokens，input/output），用于估算每次 run 成本
# 版本：v0.2.0 — 钉钉切到企业内部应用（工作通知），删 webhook 字段

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# 候选模型清单（控制台 A/B 用）
SUPPORTED_MODELS: list[str] = [
    "claude-sonnet-4-6",          # 生产默认
    "claude-opus-4-7",            # 高质量备选
    "claude-haiku-4-5-20251001",  # 快/便宜
    "deepseek-v4-pro",            # 国产母语
    "gpt-5.5",                    # 西方旗舰
    "gemini-3.1-pro-preview",     # Google 旗舰
    "gemini-2.5-flash",           # Google 高性价比
]


# 模型价格表（CNY 元，每 1,000,000 tokens；input / output）
# 这是按官方 list-price 估算（USD→CNY 取 7.2），ModelVerse 实际计费以账单为准。
# 未登记的模型按 0 算（前端显示 "-"）。
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # Anthropic
    "claude-sonnet-4-6":         (21.6,  108.0),   # $3 / $15
    "claude-opus-4-7":           (108.0, 540.0),   # $15 / $75
    "claude-haiku-4-5-20251001": (7.2,   36.0),    # $1 / $5
    # 国产
    "deepseek-v4-pro":           (1.0,   4.0),     # 约 ¥1 / ¥4 per 1M
    # OpenAI（旗舰估算，按 sonnet 同档）
    "gpt-5.5":                   (21.6,  108.0),
    # Google
    "gemini-3.1-pro-preview":    (14.4,  86.4),    # $2 / $12
    "gemini-2.5-flash":          (2.16,  18.0),    # $0.30 / $2.50
}


def estimate_cost_cny(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """按 MODEL_PRICING 估 CNY 成本，未登记模型返回 0.0。"""
    price = MODEL_PRICING.get(model)
    if not price:
        return 0.0
    in_per_m, out_per_m = price
    return round(prompt_tokens / 1_000_000 * in_per_m + completion_tokens / 1_000_000 * out_per_m, 4)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # AI
    ai_base_url: str = Field(default="https://api.modelverse.cn/v1")
    ai_api_key: str = Field(default="")
    ai_default_model: str = Field(default="claude-sonnet-4-6")

    # Doris RO
    doris_ro_host: str
    doris_ro_port: int = 49030
    doris_ro_user: str
    doris_ro_password: str
    doris_ro_db: str = "bigoffs_sync"

    # Doris RW (可空，待 bigoffs-db skill 初始化)
    doris_rw_host: str = ""
    doris_rw_port: int | None = None
    doris_rw_user: str = ""
    doris_rw_password: str = ""
    doris_rw_db: str = ""

    # DingTalk 企业内部应用（工作通知，私发到"工作通知"小助手）
    # 钉钉开放平台 → 应用开发 → 企业内部应用 → 凭证与基础信息
    dingtalk_app_key: str = ""
    dingtalk_app_secret: str = ""
    dingtalk_agent_id: str = ""  # 应用 AgentId，asyncsend_v2 必填

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    public_base_url: str = "http://localhost:8000"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()

# 文件作用：集中读取 .env 配置，pydantic-settings 校验
# 版本：v0.1.0 — 初始化

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
]


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

    # DingTalk
    dingtalk_webhook: str = ""
    dingtalk_secret: str = ""

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    public_base_url: str = "http://localhost:8000"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()

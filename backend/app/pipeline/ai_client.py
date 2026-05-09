# 文件作用：ModelVerse 多模型 AI 客户端 (OpenAI 协议兼容)
# 支持 5 个模型 A/B 切换，统一接口返回 (text, usage, latency_ms)
# 版本：v0.1.0 — 初始化

from __future__ import annotations

import time
from dataclasses import dataclass

from openai import OpenAI

from app.config import SUPPORTED_MODELS, get_settings


@dataclass
class CompletionResult:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int
    raw: dict


_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        s = get_settings()
        _client = OpenAI(base_url=s.ai_base_url, api_key=s.ai_api_key)
    return _client


def complete(
    prompt: str,
    *,
    model: str | None = None,
    system: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 8192,
) -> CompletionResult:
    """单轮文本补全。model 缺省走 .env DEFAULT_MODEL。"""
    s = get_settings()
    model = model or s.ai_default_model
    if model not in SUPPORTED_MODELS:
        # 不强制限制，仅警告（控制台扩展模型时方便）
        pass

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    t0 = time.perf_counter()
    resp = get_client().chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    latency_ms = int((time.perf_counter() - t0) * 1000)

    text = resp.choices[0].message.content or ""
    usage = resp.usage
    return CompletionResult(
        text=text,
        model=model,
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
        total_tokens=usage.total_tokens if usage else 0,
        latency_ms=latency_ms,
        raw=resp.model_dump(),
    )

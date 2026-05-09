# 文件作用：FastAPI 入口，挂载 API 路由 + 启动 APScheduler
# 版本：v0.1.0 — 骨架

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.meta import router as meta_router
from app.api.prompts import router as prompts_router
from app.api.recipients import router as recipients_router
from app.api.runs import router as runs_router
from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # TODO: 启动 APScheduler、初始化数据库连接池
    yield
    # TODO: 关闭资源


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="门店经营自动简报系统",
        version="0.1.0",
        lifespan=lifespan,
    )

    # 前端 dev server 跨域
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3010", "http://127.0.0.1:3010"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health():
        return {"status": "ok", "default_model": settings.ai_default_model}

    app.include_router(meta_router)
    app.include_router(runs_router)
    app.include_router(prompts_router)
    app.include_router(recipients_router)

    return app


app = create_app()

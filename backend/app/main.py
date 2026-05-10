# 文件作用：FastAPI 入口，挂载 API 路由 + 报告静态目录 + APScheduler 占位
# 版本：v0.3.0 — /reports/{id} 失败/进行中时渲染诊断页，不再返回 404 黑洞

import html as html_lib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.meta import router as meta_router
from app.api.prompts import router as prompts_router
from app.api.recipients import router as recipients_router
from app.api.runs import router as runs_router
from app.config import get_settings
from app.models.db import get_session_factory
from app.models.entities import Run

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


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

    # /reports/{run_id} → 优先返回 dispatch 阶段写盘的 HTML；
    # 还没写盘时（pending/running/failed）渲染一份诊断页，避免 404 黑洞
    @app.get("/reports/{run_id}", response_class=HTMLResponse)
    def report_page(run_id: int):
        f = REPORTS_DIR / f"{run_id}.html"
        if f.exists():
            return FileResponse(f, media_type="text/html; charset=utf-8")
        return HTMLResponse(_diagnostic_page(run_id), status_code=200)

    # 静态资源（如未来要塞图表 png/css）
    app.mount("/reports-assets", StaticFiles(directory=str(REPORTS_DIR)), name="reports-assets")

    return app


_DIAG_STAGES = (
    ("sql_dump",        "① SQL 渲染"),
    ("data_dump",       "② 数据聚合 (4 层)"),
    ("prompt_rendered", "③ Prompt 组装"),
    ("response_text",   "④ AI 输出"),
)

_STATUS_COLOR = {
    "pending":  ("#f1f5f9", "#475569", "排队中"),
    "running":  ("#e0e7ff", "#3730a3", "执行中"),
    "failed":   ("#fee2e2", "#991b1b", "失败"),
    "success":  ("#dcfce7", "#166534", "成功"),
}


def _diagnostic_page(run_id: int) -> str:
    """run 还没产出最终 HTML 时，把 run 行的 partial 字段渲染成诊断页。"""
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        run = db.get(Run, run_id)
        if run is None:
            return f"<!doctype html><meta charset=utf-8><h1>Run #{run_id} 不存在</h1>"

        bg, fg, label = _STATUS_COLOR.get(run.status, ("#f1f5f9", "#475569", run.status))
        period = ""
        if run.period_start or run.period_end:
            period = f"{run.period_start or '?'} ~ {run.period_end or '?'}"

        # 找到第一个非空阶段，便于用户定位走到哪一步
        last_filled = None
        for key, _title in _DIAG_STAGES:
            if getattr(run, key, None):
                last_filled = key

        sections: list[str] = []
        for key, title in _DIAG_STAGES:
            v = getattr(run, key, None) or ""
            badge = (
                "<span class='ok'>已产出</span>" if v
                else "<span class='skip'>未产出</span>"
            )
            body = (
                f"<pre>{html_lib.escape(v[:20000])}{'…(已截断)' if len(v) > 20000 else ''}</pre>"
                if v else "<p class='muted'>—</p>"
            )
            sections.append(
                f"<details {'open' if key == last_filled else ''}>"
                f"<summary><strong>{title}</strong> {badge}</summary>{body}</details>"
            )

        err_block = (
            f"<section class='err'><h3>错误信息</h3>"
            f"<pre>{html_lib.escape(run.error_message or '')}</pre></section>"
            if run.error_message else ""
        )

        return f"""<!doctype html>
<html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Run #{run_id} · 诊断</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;
max-width:920px;margin:32px auto;padding:0 20px;color:#0f172a;line-height:1.6}}
.tag{{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;
background:{bg};color:{fg};margin-left:8px;vertical-align:middle}}
.muted{{color:#94a3b8}}
details{{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:8px 12px;margin:8px 0}}
details[open]{{background:#fff}}
summary{{cursor:pointer;user-select:none}}
.ok{{color:#15803d;font-size:12px;margin-left:6px}}
.skip{{color:#94a3b8;font-size:12px;margin-left:6px}}
pre{{background:#0f172a;color:#e2e8f0;padding:12px;border-radius:6px;overflow:auto;max-height:480px;
font-size:12px;white-space:pre-wrap;word-break:break-all}}
.err{{background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:12px 16px;margin:16px 0}}
.err h3{{margin:0 0 8px;color:#991b1b}}
.err pre{{background:#7f1d1d}}
.meta{{color:#64748b;font-size:13px}}
</style></head><body>
<p style="font-size:13px"><a href="/" style="color:#64748b;text-decoration:none">← 控制台</a></p>
<h1>Run #{run_id} <span class="tag">{label}</span></h1>
<p class="meta">
{run.report_type} · {run.trigger_type} · 模型 <code>{run.model or '-'}</code><br>
开始 {run.started_at} · 结束 {run.finished_at or '-'} · 周期 {period or '-'}
</p>
<p class="meta">⚠️ 流水线尚未到 dispatch 阶段，下面是已落库的中间产物（按 6 步顺序）。</p>
{err_block}
{''.join(sections)}
<p class="meta" style="margin-top:24px">
对应 API：<code>GET /api/runs/{run_id}</code> · 重跑：<code>POST /api/runs/{run_id}/retry</code>
</p>
</body></html>"""


app = create_app()

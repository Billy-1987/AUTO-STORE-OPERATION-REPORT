# CLAUDE.md

门店经营自动简报系统：定时跑 SQL → AI 分析 → HTML 报告 → 钉钉分发。前端是 prompt 工程控制台（A/B 调试用），完整映射后端工作流。

---

## 红线（违反必出问题）

1. **AI 只接聚合后的数据**，永远不把行级 / 明细数据塞给模型，否则 token 爆炸 + 回答崩坏。聚合维度只有四层：门店 → 区域 → 大区 → 全国。
2. **指标基于 `b_order_list`**，不要用 `b_order`（2025-01 无数据，会让同比/同店失真）。
3. **客流区域聚合两层子查询**（先门店再区域），直接 JOIN 行级订单会重复计数。
4. **同店判定严格执行**："对应上年同期内涉及的每个自然月都有销售"。
5. **不写测试垃圾**、**不主动建分支**、**不改 proxy**、**Python 用 uv venv**（沿用 user 全局规则）。

---

## 端口约定

- **前端控制台**: `3010`（dev/prod 都是）
- **后端 API**: `8000`
- 前端通过 `NEXT_PUBLIC_API_BASE` 访问后端，CORS 白名单只放 `localhost:3010` / `127.0.0.1:3010`
- 启动：`backend/` 跑 `uvicorn app.main:app --port 8000`；`frontend/` 跑 `pnpm dev`

---

## 架构

```
backend/                     Python + FastAPI + APScheduler
├── app/
│   ├── main.py              FastAPI 入口
│   ├── config.py            .env → Settings
│   ├── doris/connection.py  Doris 连接（ro/rw）
│   ├── pipeline/            6 步流水线
│   │   ├── runner.py        串联
│   │   ├── sql_executor.py  ① 跑 SQL
│   │   ├── shaper.py        ② 聚合 + REGION_OVERRIDE  ← AI 之前的最后一关
│   │   ├── prompt.py        ③ jinja2 注入聚合数据
│   │   ├── ai_client.py     ④ ModelVerse 调用 (✅ 已就绪)
│   │   ├── renderer.py      ⑤ HTML 落库
│   │   └── dingtalk.py      ⑥ ActionCard 分发
│   ├── models/              SQLAlchemy ORM
│   ├── api/                 REST API
│   └── scheduler.py         APScheduler 定时器
├── prompts/{weekly,monthly,holiday}.md   Jinja2 模板
├── sql/{weekly,monthly,holiday}/*.sql.j2 SQL 模板
├── reports/                 生成 HTML 归档（gitignore）
└── .env                     敏感配置（gitignore）

frontend/                    Next.js 14 + shadcn/ui（控制台）
└── app/{pipelines,prompts,recipients,reports}
```

---

## 数据源

### 业务只读库（查指标）
配置文件 `.bigoffs-db`（gitignore），同步到 `backend/.env` 的 `DORIS_RO_*`。
- Host: `aidoris.bigoffs.com.cn:49030`
- DB: `bigoffs_sync`，账号: `bigoffs_readonly`

### 项目自用写库（已开通）
通过 `bigoffs-db` skill 创建，连接信息在 `backend/.env` 的 `DORIS_RW_*`。
- DB: `auto_store_operation_report_heng`
- 6 张表：`prompts` / `runs` / `recipients` / `schedules` / `reports` / `holidays`
- Doris UNIQUE KEY 模型，无 FK，关系应用层维护

### 业务核心表（指标都基于这 6 张）

| 表 | 用途 |
|----|------|
| `b_order_list` | **订单 item 级（主数据源）**：`branch_serial_no`, `shop_id`, `fact_pay_amt`(分), `pay_time`, `user_id`, `parent_order_status`(5=完成) |
| `b_order` | 仅取 `shop_name`（**2025-01 无数据**，禁用于历史） |
| `b_store_flow` | 客流：`shop_id`, `statistics_time`, `flow_in` |
| `shop_info` | 门店→区域：`shop_id`, `region_Id` |
| `region_info` | 区域名 |
| `user` | 会员：`reg_time` |

---

## 指标 SQL（口径以 bigoffs-db plugin 为准）

**禁止在本仓库硬编码 SQL 口径**。每个指标的最新 SQL 都在 `bigoffs-db` plugin 的 `bigoffs-metrics` skill 里。开发 `sql_executor.py` 时通过该 skill 获取口径并写到 `backend/sql/<report_type>/*.sql.j2`，每条 SQL 顶部注明"取自 plugin/{file}.md @ {date}"。

### plugin 最新发现的关键差异（旧 CLAUDE.md 已过时）
- 实收金额 = `fact_pay_amt + offset_amt + pay_out_coupon_amt`（不是只 `fact_pay_amt`）
- 退单过滤用 `is_refund = 0`（不是 `parent_order_status = 5`）
- 鞋服业务限定 `dim_sku_list.type = 2`
- 门店维度从 `dwd_unique_stock_list` JOIN `b_warehouse` 取

### 报告需要的指标（去 plugin 拿对应的）
销售额 / 订单量 / 件数 / 客单价 / 连带率 / 客流量 / 提袋率 / 新增会员 / 老客销比 / 同店判定

### 区域映射

```python
REGIONS = {68:"华北区", 67:"北京区", 163:"华中区", 75:"华东区",
           66:"东北区", 69:"西南区", 165:"西北区", 164:"华南区"}
SUPER_REGIONS = {"华北大区":[68,67,163,75,66], "西南大区":[69,165,164]}
REGION_OVERRIDE = {3079:163, 3066:67}      # 武汉光谷归华中、燕郊归北京
EXCLUDE_SHOPS = {3018}                     # 天津南开仁恒店是线上汇总账号，门店级分析需排除
```

---

## 报告章节骨架（prompt 模板硬骨架）

每份报告 6 章：

1. 总体概况 — 门店数 + 核心指标（整体/同店双口径，全部含同比）
2. 各区域经营表现 — 区域级汇总（含同店客流同比）
3. 销售额 TOP5 门店 — ★新店标注
4. 新增门店表现
5. 增长来源拆解 — 新店贡献 vs 同店增量
6. **深度洞察与行动建议** — AI 自由发挥，前 5 章数据驱动

---

## 触发与分发

| 类型 | Cron | 范围 | 收件人 |
|---|---|---|---|
| 周报 | 周一 06:30 | 上周 7 天 | 区域总 / 区域经理 |
| 月报 | 月初 1 号 06:30 | 上月 | 区域总 / 区域经理 / 指定店长 |
| 节假日 | 假后第一天 06:30 | 整个假期 + 同期 | 全员（可配置）|

钉钉用 **ActionCard**：摘要 + 「查看完整报告」→ `https://{public_base_url}/reports/{id}`。
收件人按 `recipients.role` 路由，每年初导入 `holidays` 表（清明/五一/端午/中秋/国庆/春节/元旦）。

---

## AI（ModelVerse 网关，OpenAI 协议）

- Base URL: `https://api.modelverse.cn/v1`
- 文档: https://www.compshare.cn/docs/modelverse/models/quick-start
- 海外备用: `api.umodelverse.ai`
- Key 在 `backend/.env::AI_API_KEY`

### 控制台 5 模型（A/B 用）

| 模型 ID | 用途 |
|---|---|
| `claude-sonnet-4-6` | **生产默认** |
| `claude-opus-4-7` | 高质量备选（节假日大报告）|
| `claude-haiku-4-5-20251001` | 快/便宜，摘要类 |
| `deepseek-v4-pro` | 国产母语；reasoning 模型，需取 `reasoning_content` |
| `gpt-5.5` | 西方旗舰对照 |

清单维护在 `backend/app/config.py::SUPPORTED_MODELS`。

---

## TODO

1. ✅ backend 骨架 + uv + 5 模型客户端
2. ✅ 写库 + 6 张表
3. ⏳ ORM 模型 + Alembic（或简化用纯 SQL）
4. ⏳ `pipeline/sql_executor.py` + `shaper.py`（重点：聚合到门店/区域/大区/全国 4 个维度后才喂 AI）
5. ⏳ weekly prompt v1（参考 `docs/` 旧 .docx 反推）
6. ⏳ 端到端跑通一次（手动触发 → AI 输出 HTML → 钉钉测试群）
7. ⏳ 前端控制台 Next.js 骨架

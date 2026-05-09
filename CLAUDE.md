# CLAUDE.md

门店经营自动简报：定时 SQL → AI → HTML → 钉钉。前端控制台调 prompt + 看流水线日志。

## 红线

1. **AI 只接聚合数据**（4 层：门店→区域→大区→全国），永远不喂行级。
2. **指标基于 `b_order_list`**；`b_order` 2025-01 无数据，会让同比/同店失真。
3. **客流区域聚合先门店再区域两层子查询**，直接 JOIN 重复计数。
4. **同店判定**：上年同期内每个自然月都有销售。
5. **SQL 口径以 `bigoffs-db` plugin 为准**（`bigoffs-metrics` skill），仓库不硬编码。
6. uv venv / 不主动建分支 / 不改 proxy / 不写测试垃圾（user 全局规则）。

## 端口

backend `8000`、frontend `3010`。

## 数据源

- 业务只读：`bigoffs_sync` @ `aidoris.bigoffs.com.cn:49030`，账号 `backend/.env::DORIS_RO_*`
- 项目写库：`auto_store_operation_report`（bigoffs-db plugin 自动建），账号 `backend/.env::DORIS_RW_*`
- 写库 6 表：`prompts / runs / recipients / schedules / reports / holidays`，UNIQUE KEY，无 FK
- 业务表/指标 SQL 走 plugin

## 区域映射（应用层硬编码）

```python
REGIONS = {68:"华北", 67:"北京", 163:"华中", 75:"华东", 66:"东北", 69:"西南", 165:"西北", 164:"华南"}
SUPER_REGIONS = {"华北大区":[68,67,163,75,66], "西南大区":[69,165,164]}
REGION_OVERRIDE = {3079:163, 3066:67}   # 光谷→华中、燕郊→北京
EXCLUDE_SHOPS = {3018}                  # 线上汇总账号，门店级分析剔除
```

## 报告章节（prompt 模板硬骨架）

1. 总体概况（整体/同店双口径，全指标同比）
2. 各区域经营（含同店客流同比）
3. 销售额 TOP5（★新店标注）
4. 新增门店
5. 增长来源拆解（新店 vs 同店）
6. 深度洞察 + 行动建议（AI 自由发挥，前 5 章数据驱动）

## 触发与分发

| 类型 | Cron | 范围 | 收件人 |
|---|---|---|---|
| 周报 | 周一 06:30 | 上周 | 区域总/区域经理 |
| 月报 | 1 号 06:30 | 上月 | + 指定店长 |
| 节假日 | 假后第一天 06:30 | 假期+同期 | 全员（可配） |

钉钉 ActionCard：摘要 + 「查看完整报告」→ `{public_base_url}/reports/{id}`。
节假日由 `holidays` 表驱动（清明/五一/端午/中秋/国庆/春节/元旦）。

## AI（ModelVerse，OpenAI 协议）

- Base `https://api.modelverse.cn/v1`，key 在 `backend/.env::AI_API_KEY`
- 模型清单 `backend/app/config.py::SUPPORTED_MODELS`：
  - `claude-sonnet-4-6` 生产默认
  - `claude-opus-4-7` 高质量
  - `claude-haiku-4-5-20251001` 快/便宜
  - `deepseek-v4-pro`（reasoning，取 `reasoning_content`）
  - `gpt-5.5` 对照

## TODO

1. ⏳ 拉 plugin 最新 SQL → `backend/sql/{weekly,monthly,holiday}/*.sql.j2`
2. ⏳ `pipeline/shaper.py` 4 层聚合（喂 AI 前最后一关）
3. ⏳ `pipeline/runner.py` 串 6 步 + APScheduler
4. ⏳ 钉钉 ActionCard + 收件人路由
5. ⏳ weekly prompt v1（用 `docs/` 旧 .docx 反推骨架）

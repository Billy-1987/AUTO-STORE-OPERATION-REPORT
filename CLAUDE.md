# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 项目性质

这是一个**经营简报自动生成工作区**，没有应用代码。工作内容是：从 bigoffs-db 数据库拉取门店经营数据，用 Python 生成 `.docx` 格式的经营简报。

所有生成逻辑通过临时 Python 脚本（写入 `/tmp/`）执行，生成的报告保存在本目录。

---

## 数据库连接

连接信息存储在 `.bigoffs-db`（已加入 `.gitignore`），通过 `bigoffs-db` plugin 的 `bigoffs-metrics` skill 访问。

**只读账号**（查询用）：
- host: `aidoris.bigoffs.com.cn`  port: `49030`
- user: `bigoffs_readonly`  password: `okbuy@20220314!!`
- 数据库: `bigoffs_sync`

连接方式是纯 Python socket 实现的 MySQL 协议（无需安装驱动），代码模板见会话记忆。

---

## 核心数据表与字段

| 表 | 用途 | 关键字段 |
|----|------|---------|
| `b_order_list` | **订单明细表（主要数据源）** item级 | `parent_serial_no`, `branch_serial_no`, `shop_id`, `fact_pay_amt`(分), `pay_time`, `user_id`, `parent_order_status`(5=完成) |
| `b_order` | 订单主表（仅用于取 shop_name，**2025-01 无数据**不要用于历史查询） | `shop_id`, `shop_name`, `fact_pay_amt`, `sku_nums`, `status`, `pay_time` |
| `b_store_flow` | 客流 | `shop_id`, `statistics_time`, `flow_in` |
| `shop_info` | 门店→区域映射 | `shop_id`, `region_Id` |
| `region_info` | 区域名称 | `id`, `name` |
| `user` | 会员 | `id`, `reg_time` |

**b_order_list 指标口径**（必须用此表，`b_order` 的 2025-01 无数据会导致同比/同店判定失真）：
- 销售额: `SUM(fact_pay_amt) / 100.0`（单位分，÷100=元）
- 订单量: `COUNT(DISTINCT branch_serial_no)`（行级表，要去重 branch）
- 销量: `COUNT(*)`（每行一件）
- 过滤: `parent_order_status = 5` + `pay_time` 在区间

**区域 ID**：68=华北区, 67=北京区, 163=华中区, 75=华东区, 66=东北区, 69=西南区, 165=西北区, 164=华南区

**大区划分**：
- 华北大区 = [68, 67, 163, 75, 66]
- 西南大区 = [69, 165, 164]

---

## 指标口径（已验证）

所有查询加 `WHERE parent_order_status = 5 AND pay_time >= '{start}' AND pay_time < '{end}'`（基于 `b_order_list`）。

| 指标 | SQL | 说明 |
|------|-----|------|
| 销售额 | `SUM(fact_pay_amt) / 100.0` | 单位分，÷100=元，÷1000000=万 |
| 订单量 | `COUNT(DISTINCT branch_serial_no)` | |
| 件数 | `COUNT(*)` | 行级，每行一件 |
| 客单价 | `SUM(fact_pay_amt)/100.0 / COUNT(DISTINCT branch_serial_no)` | |
| 连带率 | `COUNT(*) * 1.0 / COUNT(DISTINCT branch_serial_no)` | |
| 客流量 | `SUM(flow_in)` from `b_store_flow` | 区域级需两层聚合，避免重复计数 |
| 提袋率 | 订单数 / 客流量 | |
| 新增会员 | `COUNT(DISTINCT user_id)` WHERE `user.reg_time` 在统计区间内且有下单 | 误差 ~0.5% |
| 老客销比 | `user.reg_time < 统计开始日` 的用户销售额占比 | 误差 ~1-2pp |

**同店口径**：**在给定统计区间对应的上年时段内，涉及的每个自然月都有销售数据的门店。严格执行"每月都有"。** 例：统计 2026-01-01 至 2026-05-06（跨 1/2/3/4/5 月），同店必须在 2025 年 1、2、3、4、5 月**每月**都有订单。必须用 `b_order_list` 判定（`b_order` 的 2025-01 无数据会误判）。整体同比分母 = 同店集合在上年同期的数据。

---

## 已知数据问题（硬编码修正）

```python
REGION_OVERRIDE = {
    3079: 163,  # 武汉洪山光谷鲁巷店：shop_info 无映射，归入华中区
    3066: 67,   # 三河燕郊天洋广场店：DB 归华北区，实际属北京区
}
```

`shop_id=3018`（天津南开仁恒店）在 DB 中是线上汇总账号，月均 2 万单，门店级分析时数据失真，需注意。

---

## 报告格式规范

报告用 `python-docx` 生成，格式与现有 `.docx` 文件保持一致：

| 元素 | 字体 | 字号 | 颜色 |
|------|------|------|------|
| 主标题 | 微软雅黑 | 20pt | `#1F497D` 加粗 |
| 大区副标题 | 微软雅黑 | 13pt | `#2E74B5` 加粗 |
| 一级章节标题 | 微软雅黑 | 14pt | `#1F497D` 加粗 |
| 二级小节标题 | 微软雅黑 | 11pt | `#2E74B5` 加粗 |
| 正文 | 微软雅黑 | 10pt | 默认 |
| 注释 | 微软雅黑 | 8pt | `#606060` |
| 表头 | 微软雅黑 | 9pt | 白色字 + `#1F497D` 背景 |
| 表格数据 | 微软雅黑 | 9pt | 默认，隔行 `#F2F2F2` |

同比数值着色：正值红色 `#C00000`，负值绿色 `#007000`。

所有 run 必须同时设置 `w:eastAsia`、`w:ascii`、`w:hAnsi` 三个字体属性，否则中文字体不生效。

---

## 报告结构

每份报告包含以下章节（全国/大区通用）：

1. **总体概况** — 门店数说明 + 核心指标总览表（整体/同店双口径，含全部指标同比）
2. **各区域经营表现** — 区域级汇总表（含同店客流同比列）
3. **销售额 TOP5 门店** — 新店标注 ★新
4. **新增门店表现** — 仅含新店明细
5. **增长来源拆解** — 新店贡献 vs 同店增量
6. **深度洞察与行动建议** — 增长来源、同店画像、行动建议三节

---

## 生成报告的工作流

1. 用 Python socket 连接 `bigoffs_sync`，分别查询当期和上年同期数据
2. 应用 `REGION_OVERRIDE` 修正区域映射
3. 按门店聚合 → 按区域聚合 → 按大区聚合（三层）
4. 客流区域聚合必须用两层子查询（先门店聚合再区域聚合），直接 JOIN 会因订单行数导致重复计数
5. 用 `python-docx` 写入 `.docx`，脚本写到 `/tmp/gen_reports.py` 执行

生成的报告文件命名格式：`{年份}年{时段}经营简报_{范围}.docx`，保存在本目录。

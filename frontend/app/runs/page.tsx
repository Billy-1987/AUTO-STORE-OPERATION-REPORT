// 文件作用：完整 runs 列表页
// 版本：v0.6.0 — 加成本列（¥）+ 行尾删除按钮
// 版本：v0.5.0 — 加筛选器：状态 / 报告类型 / 范围 / 关键字（搜 scope_label/run id）
// 版本：v0.4.0 — 新增 scope 列（national/super_region/region/shop）+ 查看报告快捷入口
// 版本：v0.3.0 — failed 状态 hover 显示 error_message；点击跳详情；行尾"查看报告"快捷入口
"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { fmtDate, fmtNum, statusColor } from "@/lib/utils";
import { Trash2 } from "lucide-react";

const REPORT_TYPE_LABEL: Record<string, string> = {
  weekly: "周报",
  monthly: "月报",
  holiday: "节假日",
};
const SCOPE_LABEL: Record<string, string> = {
  national: "全国",
  super_region: "大区",
  region: "区域",
  shop: "门店",
};
const STATUS_LABEL: Record<string, string> = {
  pending: "等待中",
  running: "运行中",
  success: "成功",
  failed: "失败",
};

export default function RunsPage() {
  const qc = useQueryClient();
  const runs = useQuery({ queryKey: ["runs"], queryFn: api.listRuns });
  const del = useMutation({
    mutationFn: (id: number) => api.deleteRun(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["runs"] }),
  });

  const [status, setStatus] = useState<string>("all");
  const [reportType, setReportType] = useState<string>("all");
  const [scopeType, setScopeType] = useState<string>("all");
  const [keyword, setKeyword] = useState<string>("");

  const filtered = useMemo(() => {
    const all = runs.data ?? [];
    const kw = keyword.trim().toLowerCase();
    return all.filter((r) => {
      if (status !== "all" && r.status !== status) return false;
      if (reportType !== "all" && r.report_type !== reportType) return false;
      if (scopeType !== "all" && (r.scope_type ?? "") !== scopeType) return false;
      if (kw) {
        const hay = `${r.id} ${r.scope_label ?? ""} ${r.scope_id ?? ""} ${r.model ?? ""}`.toLowerCase();
        if (!hay.includes(kw)) return false;
      }
      return true;
    });
  }, [runs.data, status, reportType, scopeType, keyword]);

  const total = runs.data?.length ?? 0;
  const showing = filtered.length;

  // 各 status 的小计
  const statusCounts = useMemo(() => {
    const c: Record<string, number> = { pending: 0, running: 0, success: 0, failed: 0 };
    for (const r of runs.data ?? []) c[r.status] = (c[r.status] ?? 0) + 1;
    return c;
  }, [runs.data]);

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">运行历史</h1>
        <p className="text-sm text-slate-500 mt-1">每次 pipeline 执行 = 一条 run。Prompt 列显示这次实际用的版本（点击跳到 Prompt 详情）。</p>
      </header>

      {/* 筛选区 */}
      <section className="bg-white border border-slate-200 rounded-lg p-3 flex flex-wrap items-center gap-3 text-xs">
        <FilterPill label="状态">
          <select className="select" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="all">全部 ({total})</option>
            <option value="success">成功 ({statusCounts.success ?? 0})</option>
            <option value="failed">失败 ({statusCounts.failed ?? 0})</option>
            <option value="running">运行中 ({statusCounts.running ?? 0})</option>
            <option value="pending">等待中 ({statusCounts.pending ?? 0})</option>
          </select>
        </FilterPill>

        <FilterPill label="报告类型">
          <select className="select" value={reportType} onChange={(e) => setReportType(e.target.value)}>
            <option value="all">全部</option>
            <option value="weekly">周报</option>
            <option value="monthly">月报</option>
            <option value="holiday">节假日</option>
          </select>
        </FilterPill>

        <FilterPill label="范围">
          <select className="select" value={scopeType} onChange={(e) => setScopeType(e.target.value)}>
            <option value="all">全部</option>
            <option value="national">全国</option>
            <option value="super_region">大区</option>
            <option value="region">区域</option>
            <option value="shop">门店</option>
          </select>
        </FilterPill>

        <FilterPill label="搜索">
          <input
            className="input"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="ID / 范围名 / 模型"
            style={{ minWidth: 180 }}
          />
        </FilterPill>

        {(status !== "all" || reportType !== "all" || scopeType !== "all" || keyword) && (
          <button
            className="text-brand-600 hover:underline"
            onClick={() => { setStatus("all"); setReportType("all"); setScopeType("all"); setKeyword(""); }}
          >清空筛选</button>
        )}

        <span className="ml-auto text-slate-500">显示 {showing} / {total}</span>
      </section>

      <section className="bg-white rounded-lg border border-slate-200">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600 text-xs">
              <tr>
                <th className="text-left px-4 py-2 font-medium">ID</th>
                <th className="text-left px-4 py-2 font-medium">类型</th>
                <th className="text-left px-4 py-2 font-medium">范围</th>
                <th className="text-left px-4 py-2 font-medium">触发</th>
                <th className="text-left px-4 py-2 font-medium">模型</th>
                <th className="text-left px-4 py-2 font-medium">Prompt</th>
                <th className="text-left px-4 py-2 font-medium">状态</th>
                <th className="text-left px-4 py-2 font-medium">Tokens</th>
                <th className="text-left px-4 py-2 font-medium">成本</th>
                <th className="text-left px-4 py-2 font-medium">耗时</th>
                <th className="text-left px-4 py-2 font-medium">开始时间</th>
                <th className="text-left px-4 py-2 font-medium">报告</th>
                <th className="text-left px-4 py-2 font-medium w-10"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr key={r.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-2"><Link href={`/runs/${r.id}`} className="text-brand-600 hover:underline">#{r.id}</Link></td>
                  <td className="px-4 py-2">{REPORT_TYPE_LABEL[r.report_type] ?? r.report_type}</td>
                  <td className="px-4 py-2 text-xs">
                    <span className="font-medium">{r.scope_label || (r.scope_type === "national" ? "全国" : "-")}</span>
                    {r.scope_type && r.scope_type !== "national" && (
                      <span className="text-slate-400 ml-1">({SCOPE_LABEL[r.scope_type] ?? r.scope_type})</span>
                    )}
                  </td>
                  <td className="px-4 py-2">{r.trigger_type}</td>
                  <td className="px-4 py-2 font-mono text-xs">{r.model ?? "-"}</td>
                  <td className="px-4 py-2 text-xs">
                    {r.prompt_name ? (
                      <Link href={`/prompts?highlight=${r.prompt_id}`} className="text-brand-600 hover:underline">
                        {r.prompt_name} v{r.prompt_version}
                      </Link>
                    ) : (
                      <span className="text-slate-400">-</span>
                    )}
                  </td>
                  <td className="px-4 py-2">
                    {r.status === "failed" && r.error_message ? (
                      <Link
                        href={`/runs/${r.id}`}
                        title={r.error_message}
                        className={`inline-block px-2 py-0.5 rounded border text-xs cursor-help ${statusColor(r.status)}`}
                      >
                        {STATUS_LABEL[r.status] ?? r.status} ⓘ
                      </Link>
                    ) : (
                      <span className={`inline-block px-2 py-0.5 rounded border text-xs ${statusColor(r.status)}`}>
                        {STATUS_LABEL[r.status] ?? r.status}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2" title={
                    r.prompt_tokens != null || r.completion_tokens != null
                      ? `输入 ${fmtNum(r.prompt_tokens)} / 输出 ${fmtNum(r.completion_tokens)}`
                      : undefined
                  }>{fmtNum(r.total_tokens)}</td>
                  <td className="px-4 py-2 text-xs">
                    {r.cost_estimate != null && r.cost_estimate > 0
                      ? <span className="text-slate-700">¥{r.cost_estimate.toFixed(4)}</span>
                      : <span className="text-slate-300">-</span>}
                  </td>
                  <td className="px-4 py-2">{r.latency_ms != null ? `${(r.latency_ms / 1000).toFixed(1)}s` : "-"}</td>
                  <td className="px-4 py-2 text-xs text-slate-500">{fmtDate(r.started_at)}</td>
                  <td className="px-4 py-2 text-xs">
                    {r.status === "success" ? (
                      <a
                        href={`http://localhost:8000/reports/${r.id}`}
                        target="_blank"
                        rel="noreferrer"
                        className="text-brand-600 hover:underline"
                      >📄 看</a>
                    ) : (
                      <span className="text-slate-300">-</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <button
                      className="text-slate-400 hover:text-red-600 disabled:opacity-30"
                      disabled={r.status === "running" || (del.isPending && del.variables === r.id)}
                      title={r.status === "running" ? "运行中不允许删除" : "删除这条 run"}
                      onClick={(e) => {
                        e.stopPropagation();
                        if (confirm(`确定删除 Run #${r.id}？同时会清除报告 HTML 和 reports 行。`)) {
                          del.mutate(r.id);
                        }
                      }}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr><td colSpan={13} className="text-center text-slate-400 py-8 text-xs">
                  {total === 0 ? "暂无运行记录" : "没有符合筛选条件的记录"}
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function FilterPill({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="inline-flex items-center gap-2">
      <span className="text-slate-500">{label}</span>
      {children}
    </label>
  );
}

// 文件作用：完整 runs 列表页
// 版本：v0.1.0
"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { fmtDate, fmtNum, statusColor } from "@/lib/utils";

export default function RunsPage() {
  const runs = useQuery({ queryKey: ["runs"], queryFn: api.listRuns });

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">运行历史</h1>
        <p className="text-sm text-slate-500 mt-1">每次 pipeline 执行 = 一条 run。点击进详情可看 6 步全部输入输出。</p>
      </header>

      <section className="bg-white rounded-lg border border-slate-200">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600 text-xs">
              <tr>
                <th className="text-left px-4 py-2 font-medium">ID</th>
                <th className="text-left px-4 py-2 font-medium">报告类型</th>
                <th className="text-left px-4 py-2 font-medium">触发</th>
                <th className="text-left px-4 py-2 font-medium">模型</th>
                <th className="text-left px-4 py-2 font-medium">状态</th>
                <th className="text-left px-4 py-2 font-medium">Tokens</th>
                <th className="text-left px-4 py-2 font-medium">耗时</th>
                <th className="text-left px-4 py-2 font-medium">开始时间</th>
                <th className="text-left px-4 py-2 font-medium">结束时间</th>
              </tr>
            </thead>
            <tbody>
              {runs.data?.map((r) => (
                <tr key={r.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-2"><Link href={`/runs/${r.id}`} className="text-brand-600 hover:underline">#{r.id}</Link></td>
                  <td className="px-4 py-2">{r.report_type}</td>
                  <td className="px-4 py-2">{r.trigger_type}</td>
                  <td className="px-4 py-2 font-mono text-xs">{r.model ?? "-"}</td>
                  <td className="px-4 py-2">
                    <span className={`inline-block px-2 py-0.5 rounded border text-xs ${statusColor(r.status)}`}>
                      {r.status}
                    </span>
                  </td>
                  <td className="px-4 py-2">{fmtNum(r.total_tokens)}</td>
                  <td className="px-4 py-2">{r.latency_ms != null ? `${r.latency_ms}ms` : "-"}</td>
                  <td className="px-4 py-2 text-xs text-slate-500">{fmtDate(r.started_at)}</td>
                  <td className="px-4 py-2 text-xs text-slate-500">{fmtDate(r.finished_at)}</td>
                </tr>
              ))}
              {runs.data?.length === 0 && (
                <tr><td colSpan={9} className="text-center text-slate-400 py-8 text-xs">暂无</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

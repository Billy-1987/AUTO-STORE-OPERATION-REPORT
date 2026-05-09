// 文件作用：Run 详情页 — 6 步流水线可视化
// 版本：v0.1.0
"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { fmtDate, fmtNum, statusColor } from "@/lib/utils";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

const STEPS = [
  { key: "sql_dump",        title: "① SQL 执行",   hint: "Doris 拉取的 SQL，可能多条" },
  { key: "data_dump",       title: "② 数据整形",   hint: "REGION_OVERRIDE + 4 层聚合后的 JSON（喂给 AI 的全部内容）" },
  { key: "prompt_rendered", title: "③ Prompt 组装", hint: "jinja2 注入数据后的最终 prompt" },
  { key: "response_text",   title: "④ AI 输出",    hint: "模型返回的原文" },
  { key: "response_html",   title: "⑤ 渲染落库",   hint: "处理后的 HTML（钉钉链接指向）" },
] as const;

export default function RunDetail({ params }: { params: { id: string } }) {
  const id = Number(params.id);
  const run = useQuery({ queryKey: ["run", id], queryFn: () => api.getRun(id) });

  if (run.isLoading) return <div className="text-sm text-slate-500">加载中…</div>;
  if (run.isError) return <div className="text-sm text-red-600">加载失败：{(run.error as Error).message}</div>;
  const r = run.data!;

  return (
    <div className="space-y-5 max-w-5xl">
      <Link href="/runs" className="text-xs text-slate-500 inline-flex items-center gap-1 hover:underline">
        <ArrowLeft className="w-3 h-3" /> 返回列表
      </Link>

      <header className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold text-slate-900">Run #{r.id}</h1>
            <span className={`inline-block px-2 py-0.5 rounded border text-xs ${statusColor(r.status)}`}>{r.status}</span>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            {r.report_type} · {r.trigger_type} · 模型 <span className="font-mono">{r.model ?? "-"}</span>
          </p>
        </div>
        <div className="text-right text-xs text-slate-500 space-y-0.5">
          <div>开始 {fmtDate(r.started_at)}</div>
          <div>结束 {fmtDate(r.finished_at)}</div>
          {r.latency_ms != null && <div>耗时 {r.latency_ms} ms</div>}
        </div>
      </header>

      {/* 指标条 */}
      <section className="grid grid-cols-4 gap-3">
        <Metric label="Prompt Tokens" value={fmtNum(r.prompt_tokens)} />
        <Metric label="Completion Tokens" value={fmtNum(r.completion_tokens)} />
        <Metric label="Total Tokens" value={fmtNum(r.total_tokens)} />
        <Metric label="估算成本" value={r.cost_estimate != null ? `¥${r.cost_estimate}` : "-"} />
      </section>

      {r.error_message && (
        <section className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="text-xs text-red-700 font-medium mb-1">错误信息</div>
          <pre className="text-xs text-red-900 whitespace-pre-wrap">{r.error_message}</pre>
        </section>
      )}

      {/* 6 步可视化 */}
      <section className="space-y-3">
        {STEPS.map((step) => {
          const value = r[step.key as keyof typeof r] as string | null;
          const empty = !value;
          return (
            <details key={step.key} open={!empty} className="bg-white border border-slate-200 rounded-lg group">
              <summary className="cursor-pointer px-4 py-3 flex items-center justify-between hover:bg-slate-50">
                <div>
                  <div className="text-sm font-medium text-slate-800">{step.title}</div>
                  <div className="text-xs text-slate-500 mt-0.5">{step.hint}</div>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded border ${empty ? "bg-slate-100 text-slate-400 border-slate-200" : "bg-emerald-50 text-emerald-700 border-emerald-200"}`}>
                  {empty ? "暂无" : `${(value ?? "").length} 字符`}
                </span>
              </summary>
              {!empty && (
                <div className="border-t border-slate-100 p-3">
                  <pre className="codeblock max-h-96">{value}</pre>
                </div>
              )}
            </details>
          );
        })}

        <details className="bg-white border border-slate-200 rounded-lg">
          <summary className="cursor-pointer px-4 py-3 hover:bg-slate-50">
            <div className="text-sm font-medium text-slate-800">⑥ 钉钉分发</div>
            <div className="text-xs text-slate-500 mt-0.5">本 v0.1.0 暂未实现，pipeline 完成后此处会列出 ActionCard 推送状态 + 收件人响应</div>
          </summary>
        </details>
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-base font-semibold text-slate-900 mt-1">{value}</div>
    </div>
  );
}

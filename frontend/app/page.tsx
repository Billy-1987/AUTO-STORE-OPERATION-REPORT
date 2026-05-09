// 文件作用：Dashboard 首页 — 概览 + 触发表单 + 最近 runs
// 版本：v0.3.0 — Prompt 下拉去掉"留空"项，默认选中当前生产版本
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { fmtDate, fmtNum, statusColor } from "@/lib/utils";
import { Play, Activity } from "lucide-react";

export default function Dashboard() {
  const qc = useQueryClient();
  const sys = useQuery({ queryKey: ["sys"], queryFn: api.systemInfo });
  const models = useQuery({ queryKey: ["models"], queryFn: api.models });
  const runs = useQuery({ queryKey: ["runs"], queryFn: api.listRuns });
  const prompts = useQuery({ queryKey: ["prompts"], queryFn: () => api.listPrompts() });

  const [reportType, setReportType] = useState("weekly");
  const [model, setModel] = useState<string>("");
  const [promptId, setPromptId] = useState<number | null>(null);

  const promptOptions = useMemo(() => {
    return (prompts.data ?? [])
      .filter((p) => p.report_type === reportType)
      .sort((a, b) => b.version - a.version);
  }, [prompts.data, reportType]);

  // 切换报告类型 / prompts 加载完成时，默认选中当前生产版（找不到就第一条）
  useEffect(() => {
    if (promptOptions.length === 0) {
      setPromptId(null);
      return;
    }
    const stillValid = promptOptions.some((p) => p.id === promptId);
    if (!stillValid) {
      const active = promptOptions.find((p) => p.is_active);
      setPromptId((active ?? promptOptions[0]).id);
    }
  }, [promptOptions, promptId]);

  const trigger = useMutation({
    mutationFn: () =>
      api.triggerRun({
        report_type: reportType,
        model: model || undefined,
        prompt_id: promptId ?? undefined,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["runs"] }),
  });

  return (
    <div className="space-y-6 max-w-6xl">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Dashboard</h1>
        <p className="text-sm text-slate-500 mt-1">门店经营简报系统 · AI 工作流控制台</p>
      </header>

      {/* 系统信息卡片 */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat label="默认模型" value={sys.data?.default_model as string ?? "-"} />
        <Stat label="支持模型数" value={String(models.data?.supported.length ?? 0)} />
        <Stat label="读库" value={sys.data?.doris_ro_db as string ?? "-"} small />
        <Stat label="写库" value={sys.data?.doris_rw_db as string ?? "-"} small />
      </section>

      {/* 触发表单 */}
      <section className="bg-white rounded-lg border border-slate-200 p-5">
        <h2 className="text-base font-medium text-slate-800 mb-4 flex items-center gap-2">
          <Play className="w-4 h-4" /> 手动触发一次 pipeline
        </h2>
        <div className="flex flex-wrap gap-3 items-end">
          <Field label="报告类型">
            <select className="select" value={reportType} onChange={(e) => setReportType(e.target.value)}>
              <option value="weekly">周报</option>
              <option value="monthly">月报</option>
              <option value="holiday">节假日</option>
            </select>
          </Field>
          <Field label="模型 (留空走默认)">
            <select className="select" value={model} onChange={(e) => setModel(e.target.value)}>
              <option value="">默认 ({models.data?.default ?? "-"})</option>
              {models.data?.supported.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </Field>
          <Field label="Prompt 版本">
            {promptOptions.length === 0 ? (
              <div className="select text-xs text-amber-700 bg-amber-50 border-amber-300">⚠ 该类型暂无 prompt，请先到 Prompts 页创建</div>
            ) : (
              <select
                className="select"
                value={promptId ?? ""}
                onChange={(e) => setPromptId(Number(e.target.value))}
              >
                {promptOptions.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} v{p.version}{p.is_active ? " · 生产" : ""}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <button
            className="px-4 py-2 bg-brand-500 text-white rounded-md text-sm font-medium hover:bg-brand-600 disabled:opacity-50"
            disabled={trigger.isPending || promptOptions.length === 0}
            onClick={() => trigger.mutate()}
          >
            {trigger.isPending ? "触发中…" : "触发 Run"}
          </button>
          {trigger.isSuccess && (
            <span className="text-xs text-emerald-600">
              ✓ 已创建 run #{trigger.data.id}
              {trigger.data.prompt_name && ` · 用 ${trigger.data.prompt_name} v${trigger.data.prompt_version}`}
            </span>
          )}
        </div>
        <p className="text-xs text-slate-500 mt-3">
          v0.2.0 仅写入 pending 占位记录；未指定 Prompt 版本时自动锁定当前生产版，确保历史可追溯。
        </p>
      </section>

      {/* 最近 runs */}
      <section className="bg-white rounded-lg border border-slate-200">
        <header className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
          <h2 className="text-base font-medium text-slate-800 flex items-center gap-2">
            <Activity className="w-4 h-4" /> 最近 Runs
          </h2>
          <Link href="/runs" className="text-xs text-brand-600 hover:underline">查看全部 →</Link>
        </header>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600 text-xs">
              <tr>
                <Th>ID</Th><Th>类型</Th><Th>触发</Th><Th>模型</Th><Th>Prompt</Th><Th>状态</Th>
                <Th>Tokens</Th><Th>耗时</Th><Th>开始</Th>
              </tr>
            </thead>
            <tbody>
              {runs.data?.slice(0, 10).map((r) => (
                <tr key={r.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <Td><Link href={`/runs/${r.id}`} className="text-brand-600 hover:underline">#{r.id}</Link></Td>
                  <Td>{r.report_type}</Td>
                  <Td>{r.trigger_type}</Td>
                  <Td className="font-mono text-xs">{r.model ?? "-"}</Td>
                  <Td className="text-xs">
                    {r.prompt_name ? (
                      <Link href={`/prompts?highlight=${r.prompt_id}`} className="text-brand-600 hover:underline">
                        {r.prompt_name} v{r.prompt_version}
                      </Link>
                    ) : (
                      <span className="text-slate-400">-</span>
                    )}
                  </Td>
                  <Td>
                    <span className={`inline-block px-2 py-0.5 rounded border text-xs ${statusColor(r.status)}`}>
                      {r.status}
                    </span>
                  </Td>
                  <Td>{fmtNum(r.total_tokens)}</Td>
                  <Td>{r.latency_ms != null ? `${r.latency_ms}ms` : "-"}</Td>
                  <Td className="text-xs text-slate-500">{fmtDate(r.started_at)}</Td>
                </tr>
              ))}
              {runs.data?.length === 0 && (
                <tr><td colSpan={9} className="text-center text-slate-400 py-8 text-xs">暂无运行记录，点上方"触发 Run"试试</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Stat({ label, value, small }: { label: string; value: string; small?: boolean }) {
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-4">
      <div className="text-xs text-slate-500">{label}</div>
      <div className={`mt-1 font-semibold text-slate-900 ${small ? "text-sm font-mono" : "text-lg"}`}>{value}</div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-xs text-slate-600">
      <span>{label}</span>
      {children}
    </label>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="text-left px-4 py-2 font-medium">{children}</th>;
}

function Td({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <td className={`px-4 py-2 ${className}`}>{children}</td>;
}

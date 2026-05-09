// 文件作用：Prompt 版本管理页 — 列表 + 新建 + 激活
// 版本：v0.1.0
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/utils";

export default function PromptsPage() {
  const qc = useQueryClient();
  const prompts = useQuery({ queryKey: ["prompts"], queryFn: () => api.listPrompts() });
  const [showNew, setShowNew] = useState(false);

  return (
    <div className="space-y-4 max-w-6xl">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Prompt 版本</h1>
          <p className="text-sm text-slate-500 mt-1">每次修改保存为新版本，方便 A/B 对照与回滚</p>
        </div>
        <button className="btn-primary" onClick={() => setShowNew(!showNew)}>
          {showNew ? "取消" : "新建版本"}
        </button>
      </header>

      {showNew && <NewPromptForm onDone={() => { setShowNew(false); qc.invalidateQueries({ queryKey: ["prompts"] }); }} />}

      <section className="bg-white rounded-lg border border-slate-200">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600 text-xs">
              <tr>
                <th className="text-left px-4 py-2 font-medium">ID</th>
                <th className="text-left px-4 py-2 font-medium">名称</th>
                <th className="text-left px-4 py-2 font-medium">类型</th>
                <th className="text-left px-4 py-2 font-medium">版本</th>
                <th className="text-left px-4 py-2 font-medium">默认模型</th>
                <th className="text-left px-4 py-2 font-medium">状态</th>
                <th className="text-left px-4 py-2 font-medium">创建时间</th>
                <th className="text-left px-4 py-2 font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {prompts.data?.map((p) => (
                <tr key={p.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-2">#{p.id}</td>
                  <td className="px-4 py-2 font-medium">{p.name}</td>
                  <td className="px-4 py-2">{p.report_type}</td>
                  <td className="px-4 py-2">v{p.version}</td>
                  <td className="px-4 py-2 font-mono text-xs">{p.model ?? "-"}</td>
                  <td className="px-4 py-2">
                    {p.is_active ? (
                      <span className="px-2 py-0.5 rounded border text-xs bg-emerald-100 text-emerald-700 border-emerald-300">生产</span>
                    ) : (
                      <span className="px-2 py-0.5 rounded border text-xs bg-slate-100 text-slate-500 border-slate-300">草稿</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-xs text-slate-500">{fmtDate(p.created_at)}</td>
                  <td className="px-4 py-2"><ActivateBtn id={p.id} active={!!p.is_active} /></td>
                </tr>
              ))}
              {prompts.data?.length === 0 && (
                <tr><td colSpan={8} className="text-center text-slate-400 py-8 text-xs">暂无 prompt 模板</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function ActivateBtn({ id, active }: { id: number; active: boolean }) {
  const qc = useQueryClient();
  const m = useMutation({
    mutationFn: () => api.activatePrompt(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prompts"] }),
  });
  if (active) return <span className="text-xs text-slate-400">当前生产</span>;
  return <button className="btn text-xs" onClick={() => m.mutate()} disabled={m.isPending}>{m.isPending ? "..." : "设为生产"}</button>;
}

function NewPromptForm({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState("");
  const [reportType, setReportType] = useState("weekly");
  const [content, setContent] = useState("");
  const [description, setDescription] = useState("");
  const [setActive, setSetActive] = useState(false);

  const create = useMutation({
    mutationFn: () => api.createPrompt({ name, report_type: reportType, content, description, set_active: setActive }),
    onSuccess: onDone,
  });

  return (
    <section className="bg-white border border-slate-200 rounded-lg p-5 space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <label className="flex flex-col gap-1 text-xs text-slate-600">
          <span>名称（同名自动 +1 版本号）</span>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. weekly_v1" />
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-600">
          <span>报告类型</span>
          <select className="select" value={reportType} onChange={(e) => setReportType(e.target.value)}>
            <option value="weekly">weekly</option>
            <option value="monthly">monthly</option>
            <option value="holiday">holiday</option>
          </select>
        </label>
      </div>
      <label className="flex flex-col gap-1 text-xs text-slate-600">
        <span>描述（本次改动说明）</span>
        <input className="input" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="e.g. 加强同店分析的口径说明" />
      </label>
      <label className="flex flex-col gap-1 text-xs text-slate-600">
        <span>Prompt 内容（jinja2 模板）</span>
        <textarea className="input font-mono" rows={10} value={content} onChange={(e) => setContent(e.target.value)} placeholder="{{ data.national.sales }} ..." />
      </label>
      <label className="flex items-center gap-2 text-xs text-slate-600">
        <input type="checkbox" checked={setActive} onChange={(e) => setSetActive(e.target.checked)} />
        创建后立即设为生产版本
      </label>
      <div className="flex gap-2">
        <button className="btn-primary" disabled={create.isPending || !name || !content} onClick={() => create.mutate()}>
          {create.isPending ? "创建中…" : "创建"}
        </button>
        {create.isError && <span className="text-xs text-red-600">{(create.error as Error).message}</span>}
      </div>
    </section>
  );
}

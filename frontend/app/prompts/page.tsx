// 文件作用：Prompt 模板管理页 — 按 (报告类型 × 范围) 二维矩阵展示，原地编辑
// 版本：v0.5.0 — 去掉新建/版本/激活/删除；点行展开变成可编辑 textarea + 保存
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, type Prompt } from "@/lib/api";
import { fmtDate } from "@/lib/utils";

const REPORT_TYPE_LABEL: Record<string, string> = {
  weekly: "周报",
  monthly: "月报",
  holiday: "节假日",
};
const SCOPE_TYPE_LABEL: Record<string, string> = {
  national: "全国",
  super_region: "大区",
  region: "区域",
  shop: "门店",
};
const REPORT_TYPE_COLOR: Record<string, string> = {
  weekly: "bg-sky-50 text-sky-700 border-sky-200",
  monthly: "bg-violet-50 text-violet-700 border-violet-200",
  holiday: "bg-amber-50 text-amber-700 border-amber-200",
};
const SCOPE_TYPE_COLOR: Record<string, string> = {
  national: "bg-rose-50 text-rose-700 border-rose-200",
  super_region: "bg-indigo-50 text-indigo-700 border-indigo-200",
  region: "bg-teal-50 text-teal-700 border-teal-200",
  shop: "bg-slate-50 text-slate-700 border-slate-300",
};

const RT_ORDER: Record<string, number> = { weekly: 0, monthly: 1, holiday: 2 };
const SC_ORDER: Record<string, number> = { national: 0, super_region: 1, region: 2, shop: 3 };

export default function PromptsPage() {
  const prompts = useQuery({ queryKey: ["prompts"], queryFn: () => api.listPrompts() });
  const [openId, setOpenId] = useState<number | null>(null);

  const search = useSearchParams();
  const highlightId = search.get("highlight");
  const highlightedRowRef = useRef<HTMLTableRowElement | null>(null);

  useEffect(() => {
    if (highlightId && prompts.data) {
      const id = Number(highlightId);
      setOpenId(id);
      requestAnimationFrame(() => {
        highlightedRowRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
      });
    }
  }, [highlightId, prompts.data]);

  const grouped: Record<string, Prompt[]> = {};
  for (const p of prompts.data || []) {
    grouped[p.report_type] = grouped[p.report_type] || [];
    grouped[p.report_type].push(p);
  }
  const reportTypes = Object.keys(grouped).sort((a, b) => (RT_ORDER[a] ?? 99) - (RT_ORDER[b] ?? 99));
  for (const rt of reportTypes) {
    grouped[rt].sort((a, b) => {
      const sa = SC_ORDER[a.scope_type ?? ""] ?? 99;
      const sb = SC_ORDER[b.scope_type ?? ""] ?? 99;
      return sa - sb;
    });
  }

  return (
    <div className="space-y-5 max-w-6xl">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Prompt 模板管理</h1>
        <p className="text-sm text-slate-500 mt-1">
          每个「报告类型 × 范围」组合一份模板，原地编辑。点击行展开 → 改内容 → 保存。
        </p>
      </header>

      {/* 维度说明 */}
      <section className="bg-white border border-slate-200 rounded-lg p-4 text-xs text-slate-600">
        <div className="grid grid-cols-2 gap-6">
          <div>
            <div className="font-medium text-slate-700 mb-1.5">报告类型（决定数据时间窗口 + 章节繁简）</div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(REPORT_TYPE_LABEL).map(([k, v]) => (
                <span key={k} className={`px-2 py-0.5 rounded border text-xs ${REPORT_TYPE_COLOR[k]}`}>{v} <span className="text-slate-400 font-mono">({k})</span></span>
              ))}
            </div>
            <div className="mt-1 text-slate-500">周报/月报章节完整 8 章，节假日简化 5 章（去 TOP20 品牌、经营预警）</div>
          </div>
          <div>
            <div className="font-medium text-slate-700 mb-1.5">范围（决定数据切片和收件人）</div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(SCOPE_TYPE_LABEL).map(([k, v]) => (
                <span key={k} className={`px-2 py-0.5 rounded border text-xs ${SCOPE_TYPE_COLOR[k]}`}>{v} <span className="text-slate-400 font-mono">({k})</span></span>
              ))}
            </div>
            <div className="mt-1 text-slate-500">全国版给领导，大区版给大区总，区域版给区域经理，门店版给店长</div>
          </div>
        </div>
      </section>

      {reportTypes.map((rt) => (
        <section key={rt} className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <div className={`px-4 py-2.5 border-b border-slate-200 flex items-center gap-2 ${REPORT_TYPE_COLOR[rt] ?? ""}`}>
            <span className="font-semibold">{REPORT_TYPE_LABEL[rt] ?? rt}</span>
            <span className="text-xs opacity-60">{rt}</span>
            <span className="text-xs ml-auto opacity-70">{grouped[rt].length} 个模板</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-600 text-xs">
                <tr>
                  <th className="text-left px-4 py-2 font-medium w-8"></th>
                  <th className="text-left px-4 py-2 font-medium">范围</th>
                  <th className="text-left px-4 py-2 font-medium">名称</th>
                  <th className="text-left px-4 py-2 font-medium">默认模型</th>
                  <th className="text-left px-4 py-2 font-medium">最近修改</th>
                </tr>
              </thead>
              <tbody>
                {grouped[rt].map((p) => {
                  const isOpen = openId === p.id;
                  const isHighlighted = highlightId && Number(highlightId) === p.id;
                  return (
                    <PromptRow
                      key={p.id}
                      p={p}
                      isOpen={isOpen}
                      isHighlighted={!!isHighlighted}
                      rowRef={isHighlighted ? highlightedRowRef : undefined}
                      onToggle={() => setOpenId(isOpen ? null : p.id)}
                    />
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ))}

      {prompts.data?.length === 0 && (
        <div className="text-center text-slate-400 py-12 text-sm">暂无 prompt 模板</div>
      )}
    </div>
  );
}

function PromptRow({
  p, isOpen, isHighlighted, rowRef, onToggle,
}: {
  p: Prompt;
  isOpen: boolean;
  isHighlighted: boolean;
  rowRef?: React.RefObject<HTMLTableRowElement>;
  onToggle: () => void;
}) {
  const scopeLabel = SCOPE_TYPE_LABEL[p.scope_type ?? ""] ?? p.scope_type ?? "—";
  const scopeColor = SCOPE_TYPE_COLOR[p.scope_type ?? ""] ?? "bg-slate-50 text-slate-600 border-slate-200";

  return (
    <>
      <tr
        ref={rowRef}
        className={`border-t border-slate-100 hover:bg-slate-50 cursor-pointer ${isHighlighted ? "bg-amber-50" : ""}`}
        onClick={onToggle}
      >
        <td className="px-4 py-2 text-slate-400">{isOpen ? "▾" : "▸"}</td>
        <td className="px-4 py-2">
          <span className={`px-2 py-0.5 rounded border text-xs ${scopeColor}`}>{scopeLabel}</span>
        </td>
        <td className="px-4 py-2">
          <div className="font-medium text-slate-800">{p.name}</div>
          <div className="text-xs text-slate-400 font-mono">#{p.id}</div>
        </td>
        <td className="px-4 py-2 font-mono text-xs">{p.model ?? "-"}</td>
        <td className="px-4 py-2 text-xs text-slate-500">{fmtDate(p.updated_at)}</td>
      </tr>
      {isOpen && (
        <tr className="bg-slate-50/50">
          <td></td>
          <td colSpan={4} className="px-4 py-3">
            <PromptEditor p={p} />
          </td>
        </tr>
      )}
    </>
  );
}

function PromptEditor({ p }: { p: Prompt }) {
  const qc = useQueryClient();
  const [content, setContent] = useState(p.content ?? "");

  const dirty = content !== (p.content ?? "");

  const save = useMutation({
    mutationFn: () => api.updatePrompt(p.id, { content }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prompts"] }),
  });

  const reset = () => {
    setContent(p.content ?? "");
  };

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-1 text-xs text-slate-600">
          <span>描述（用途说明）</span>
          <div className="input bg-slate-100 text-slate-500 cursor-not-allowed select-none">
            {p.description || "—"}
          </div>
        </div>
        <div className="flex flex-col gap-1 text-xs text-slate-600">
          <span>默认模型（系统固定）</span>
          <div className="input bg-slate-100 text-slate-500 font-mono cursor-not-allowed select-none">
            {p.model || "系统默认"}
          </div>
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-1">
          <div className="text-xs text-slate-500">Prompt 内容（jinja2 模板，{content.length} 字符）</div>
          <button
            className="text-xs text-brand-600 hover:underline"
            onClick={() => navigator.clipboard.writeText(content)}
          >复制</button>
        </div>
        <textarea
          className="input font-mono w-full"
          rows={16}
          value={content}
          onChange={(e) => setContent(e.target.value)}
        />
      </div>

      <div className="flex items-center gap-3">
        <button
          className="btn-primary text-sm"
          disabled={!dirty || save.isPending}
          onClick={() => save.mutate()}
        >
          {save.isPending ? "保存中…" : "保存"}
        </button>
        <button
          className="btn text-sm"
          disabled={!dirty || save.isPending}
          onClick={reset}
        >
          还原
        </button>
        {save.isSuccess && !dirty && <span className="text-xs text-emerald-600">✓ 已保存</span>}
        {save.isError && <span className="text-xs text-red-600">{(save.error as Error).message}</span>}
        {dirty && <span className="text-xs text-amber-600">有未保存改动</span>}
      </div>
    </div>
  );
}

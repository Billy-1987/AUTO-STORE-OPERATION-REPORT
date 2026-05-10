// 文件作用：Prompt 模板管理页 — 3×4 矩阵（报告类型 × 范围），点击单元格在下方编辑
// 版本：v0.8.0 — 横纵坐标改成连续色带 + 大字号轴标签，不再是孤立小按钮
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Check, Clock, Copy, FileText } from "lucide-react";
import { api, type Prompt } from "@/lib/api";
import { fmtDate, fmtRel } from "@/lib/utils";

const REPORT_TYPES = ["weekly", "monthly", "holiday"] as const;
const SCOPE_TYPES = ["national", "super_region", "region", "shop"] as const;

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
const REPORT_ROW_TINT: Record<string, string> = {
  weekly: "bg-sky-50/60",
  monthly: "bg-violet-50/60",
  holiday: "bg-amber-50/60",
};
const REPORT_AXIS_TEXT: Record<string, string> = {
  weekly: "text-sky-800",
  monthly: "text-violet-800",
  holiday: "text-amber-800",
};
const SCOPE_AXIS_BORDER: Record<string, string> = {
  national: "border-rose-400",
  super_region: "border-indigo-400",
  region: "border-teal-400",
  shop: "border-slate-400",
};
const SCOPE_AXIS_TEXT: Record<string, string> = {
  national: "text-rose-700",
  super_region: "text-indigo-700",
  region: "text-teal-700",
  shop: "text-slate-700",
};
const SCOPE_TYPE_COLOR: Record<string, string> = {
  national: "bg-rose-50 text-rose-700 border-rose-200",
  super_region: "bg-indigo-50 text-indigo-700 border-indigo-200",
  region: "bg-teal-50 text-teal-700 border-teal-200",
  shop: "bg-slate-100 text-slate-700 border-slate-300",
};
const SCOPE_ACCENT: Record<string, string> = {
  national: "bg-rose-400",
  super_region: "bg-indigo-400",
  region: "bg-teal-400",
  shop: "bg-slate-400",
};

function fmtChars(content: string | null): string {
  const n = (content ?? "").length;
  if (n >= 10000) return `${(n / 1000).toFixed(1)}k`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

// claude-sonnet-4-6 → sonnet-4.6
function shortModel(m: string | null): string {
  if (!m) return "默认";
  return m
    .replace(/^claude-/, "")
    .replace(/-(\d+)-(\d+)/, "-$1.$2")
    .replace(/-20\d{6}$/, "");
}

export default function PromptsPage() {
  const prompts = useQuery({ queryKey: ["prompts"], queryFn: () => api.listPrompts() });
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const search = useSearchParams();
  const highlightId = search.get("highlight");

  const byKey = useMemo(() => {
    const m: Record<string, Prompt> = {};
    for (const p of prompts.data || []) {
      m[`${p.report_type}__${p.scope_type ?? ""}`] = p;
    }
    return m;
  }, [prompts.data]);

  useEffect(() => {
    if (!prompts.data || prompts.data.length === 0) return;
    if (selectedId !== null) return;
    if (highlightId) {
      const id = Number(highlightId);
      if (prompts.data.some((p) => p.id === id)) {
        setSelectedId(id);
        return;
      }
    }
    setSelectedId(prompts.data[0].id);
  }, [prompts.data, highlightId, selectedId]);

  const selected = prompts.data?.find((p) => p.id === selectedId) ?? null;

  return (
    <div className="space-y-5 max-w-6xl">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Prompt 模板管理</h1>
        <p className="text-sm text-slate-500 mt-1">
          12 个模板按「报告类型 × 范围」二维矩阵组织。点击任一格 → 下方编辑 → 保存。
        </p>
      </header>

      {/* 维度说明 */}
      <section className="bg-white border border-slate-200 rounded-lg p-4 text-xs text-slate-600">
        <div className="grid grid-cols-2 gap-6">
          <div>
            <div className="font-medium text-slate-700 mb-1.5">报告类型（决定数据时间窗口 + 章节繁简）</div>
            <div className="flex flex-wrap gap-2">
              {REPORT_TYPES.map((k) => (
                <span key={k} className={`px-2 py-0.5 rounded border text-xs ${REPORT_TYPE_COLOR[k]}`}>
                  {REPORT_TYPE_LABEL[k]} <span className="text-slate-400 font-mono">({k})</span>
                </span>
              ))}
            </div>
            <div className="mt-1 text-slate-500">周报/月报章节完整 8 章，节假日简化 5 章（去 TOP20 品牌、经营预警）</div>
          </div>
          <div>
            <div className="font-medium text-slate-700 mb-1.5">范围（决定数据切片和收件人）</div>
            <div className="flex flex-wrap gap-2">
              {SCOPE_TYPES.map((k) => (
                <span key={k} className={`px-2 py-0.5 rounded border text-xs ${SCOPE_TYPE_COLOR[k]}`}>
                  {SCOPE_TYPE_LABEL[k]} <span className="text-slate-400 font-mono">({k})</span>
                </span>
              ))}
            </div>
            <div className="mt-1 text-slate-500">全国版给领导，大区版给大区总，区域版给区域经理，门店版给店长</div>
          </div>
        </div>
      </section>

      {/* 3×4 矩阵 */}
      <section className="rounded-xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-6">
        {/* 列头：连成一条横轴 */}
        <div className="grid grid-cols-[120px_repeat(4,minmax(0,1fr))] gap-x-3 mb-4">
          <div></div>
          {SCOPE_TYPES.map((sc) => (
            <div
              key={sc}
              className={`pb-2.5 border-b-[3px] ${SCOPE_AXIS_BORDER[sc]}`}
            >
              <div className={`text-base font-semibold tracking-wide ${SCOPE_AXIS_TEXT[sc]}`}>
                {SCOPE_TYPE_LABEL[sc]}
              </div>
              <div className="text-[10px] font-mono text-slate-400 mt-0.5">{sc}</div>
            </div>
          ))}
        </div>

        {/* 行：整行是一条色带，左侧轴标签与色带融为一体 */}
        <div className="space-y-2">
          {REPORT_TYPES.map((rt) => (
            <div
              key={rt}
              className={`grid grid-cols-[120px_repeat(4,minmax(0,1fr))] gap-x-3 items-stretch rounded-xl py-3 ${REPORT_ROW_TINT[rt]}`}
            >
              <div className="flex flex-col justify-center pl-3">
                <div className={`text-xl font-semibold tracking-wide ${REPORT_AXIS_TEXT[rt]}`}>
                  {REPORT_TYPE_LABEL[rt]}
                </div>
                <div className="text-[10px] font-mono text-slate-400 mt-0.5">{rt}</div>
              </div>
              {SCOPE_TYPES.map((sc) => {
                const p = byKey[`${rt}__${sc}`];
                const isSelected = p && selectedId === p.id;
                if (!p) {
                  return (
                    <div
                      key={sc}
                      className="border border-dashed border-slate-200 rounded-lg h-[84px] flex items-center justify-center text-slate-300 text-xs bg-white/50"
                    >
                      未配置
                    </div>
                  );
                }
                return (
                  <button
                    key={sc}
                    onClick={() => setSelectedId(p.id)}
                    className={`group relative text-left rounded-lg h-[84px] pl-4 pr-3 py-2.5 bg-white transition-all duration-150 overflow-hidden ${
                      isSelected
                        ? "border-2 border-brand-500 shadow-md ring-4 ring-brand-100"
                        : "border border-slate-200 hover:border-slate-300 hover:shadow-sm hover:-translate-y-0.5"
                    }`}
                  >
                    {/* 左侧 scope 色边条 */}
                    <div className={`absolute left-0 top-0 bottom-0 w-1 ${SCOPE_ACCENT[sc]}`} />

                    {/* 顶部：字符数（主信息） */}
                    <div className="flex items-baseline gap-1.5">
                      <FileText className="w-3.5 h-3.5 text-slate-400 self-center" strokeWidth={2} />
                      <span className="text-lg font-semibold text-slate-800 tabular-nums leading-none">
                        {fmtChars(p.content)}
                      </span>
                      <span className="text-[10px] text-slate-400">字符</span>
                    </div>

                    {/* 底部：模型 + 相对时间 */}
                    <div className="absolute bottom-2.5 left-4 right-3 flex items-center justify-between text-[11px]">
                      <span className="font-mono text-slate-500 truncate">{shortModel(p.model)}</span>
                      <span className="text-slate-400 flex items-center gap-0.5 shrink-0 ml-2">
                        <Clock className="w-3 h-3" strokeWidth={2} />
                        {fmtRel(p.updated_at)}
                      </span>
                    </div>

                    {/* 选中标记 */}
                    {isSelected && (
                      <div className="absolute top-2 right-2 w-5 h-5 rounded-full bg-brand-500 text-white flex items-center justify-center shadow">
                        <Check className="w-3 h-3" strokeWidth={3} />
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      </section>

      {/* 下方编辑器 */}
      {selected ? (
        <PromptEditor key={selected.id} p={selected} />
      ) : (
        prompts.data && (
          <div className="bg-white border border-dashed border-slate-300 rounded-lg p-12 text-center text-sm text-slate-400">
            选择上方任一格子开始编辑
          </div>
        )
      )}
    </div>
  );
}

function PromptEditor({ p }: { p: Prompt }) {
  const qc = useQueryClient();
  const [content, setContent] = useState(p.content ?? "");

  const dirty = content !== (p.content ?? "");
  const rtLabel = REPORT_TYPE_LABEL[p.report_type] ?? p.report_type;
  const scLabel = SCOPE_TYPE_LABEL[p.scope_type ?? ""] ?? p.scope_type ?? "—";

  const save = useMutation({
    mutationFn: () => api.updatePrompt(p.id, { content }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prompts"] }),
  });

  const reset = () => setContent(p.content ?? "");

  return (
    <section className="bg-white border border-slate-200 rounded-xl shadow-sm p-5 space-y-3">
      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
        <div className="flex items-center gap-2">
          <span className={`px-2.5 py-1 rounded-md border text-sm font-semibold ${REPORT_TYPE_COLOR[p.report_type]}`}>{rtLabel}</span>
          <span className="text-slate-300 text-lg">×</span>
          <span className={`px-2.5 py-1 rounded-md border text-sm font-semibold ${SCOPE_TYPE_COLOR[p.scope_type ?? ""]}`}>{scLabel}</span>
          <span className="text-xs text-slate-400 font-mono ml-2">#{p.id}</span>
        </div>
        <div className="text-xs text-slate-500 flex items-center gap-3">
          <span>模型 <span className="font-mono">{p.model ?? "默认"}</span></span>
          <span className="text-slate-300">·</span>
          <span>修改于 {fmtDate(p.updated_at)}</span>
        </div>
      </div>

      {p.description && (
        <div className="text-xs text-slate-500">{p.description}</div>
      )}

      <div>
        <div className="flex items-center justify-between mb-1.5">
          <div className="text-xs text-slate-500">Prompt 内容（jinja2 模板，{content.length} 字符）</div>
          <button
            className="text-xs text-brand-600 hover:underline flex items-center gap-1"
            onClick={() => navigator.clipboard.writeText(content)}
          >
            <Copy className="w-3 h-3" /> 复制
          </button>
        </div>
        <textarea
          className="input font-mono w-full"
          rows={18}
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
    </section>
  );
}

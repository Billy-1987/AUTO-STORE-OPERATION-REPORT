// 文件作用：Dashboard 首页 — 概览 + 触发表单（报告类型 × 范围 × 范围标的）+ 最近 runs
// 版本：v0.6.0 — 删掉「高级 / 覆盖 Prompt」UI，prompt 完全由 report_type × scope_type 自动锁定
// 版本：v0.5.0 — 触发表单选择持久化到 localStorage，跨页面切换不丢
// 版本：v0.4.0 — 触发表单去掉 prompt 选择器（自动锁定生产版），新增 scope_type/scope_id 联动选择
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, type Prompt, type Shop } from "@/lib/api";
import { fmtDate, fmtNum, statusColor } from "@/lib/utils";
import { Play, Activity } from "lucide-react";

const SCOPE_LABEL: Record<string, string> = {
  national: "全国",
  super_region: "大区",
  region: "区域",
  shop: "门店",
};

const TRIGGER_FORM_STORAGE_KEY = "dashboard.triggerForm.v1";

export default function Dashboard() {
  const qc = useQueryClient();
  const sys = useQuery({ queryKey: ["sys"], queryFn: api.systemInfo });
  const models = useQuery({ queryKey: ["models"], queryFn: api.models });
  const runs = useQuery({ queryKey: ["runs"], queryFn: api.listRuns });
  const prompts = useQuery({ queryKey: ["prompts"], queryFn: () => api.listPrompts() });
  const regions = useQuery({ queryKey: ["regions"], queryFn: api.regions });
  const shops = useQuery({ queryKey: ["shops"], queryFn: api.listShops });

  const [reportType, setReportType] = useState("weekly");
  const [scopeType, setScopeType] = useState<"national" | "super_region" | "region" | "shop">("national");
  const [scopeId, setScopeId] = useState<string>("");
  const [model, setModel] = useState<string>("");
  const [hydrated, setHydrated] = useState(false);

  // localStorage 加载（只在 mount 时跑一次）
  useEffect(() => {
    try {
      const raw = localStorage.getItem(TRIGGER_FORM_STORAGE_KEY);
      if (raw) {
        const s = JSON.parse(raw);
        if (typeof s.reportType === "string") setReportType(s.reportType);
        if (typeof s.scopeType === "string") setScopeType(s.scopeType);
        if (typeof s.scopeId === "string") setScopeId(s.scopeId);
        if (typeof s.model === "string") setModel(s.model);
      }
    } catch {}
    setHydrated(true);
  }, []);

  // localStorage 持久化（hydrate 之后才写，避免初始默认值覆盖用户偏好）
  useEffect(() => {
    if (!hydrated) return;
    try {
      localStorage.setItem(
        TRIGGER_FORM_STORAGE_KEY,
        JSON.stringify({ reportType, scopeType, scopeId, model })
      );
    } catch {}
  }, [hydrated, reportType, scopeType, scopeId, model]);

  // 自动锁定的 prompt（按 report_type + scope_type 找 active）
  const lockedPrompt = useMemo<Prompt | null>(() => {
    return (
      (prompts.data ?? []).find(
        (p) => p.report_type === reportType && (p.scope_type ?? "national") === scopeType && p.is_active
      ) ?? null
    );
  }, [prompts.data, reportType, scopeType]);

  // 切换 scope 时清掉 scopeId（hydrate 之前跳过，避免清掉刚从 localStorage 恢复的值）
  useEffect(() => {
    if (!hydrated) return;
    setScopeId("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scopeType, reportType]);

  // 范围标的的可选项
  const scopeIdOptions = useMemo(() => {
    if (scopeType === "super_region") {
      return Object.keys(regions.data?.super_regions ?? {}).map((name) => ({ value: name, label: name }));
    }
    if (scopeType === "region") {
      return Object.entries(regions.data?.regions ?? {}).map(([id, name]) => ({ value: String(id), label: `${name} (${id})` }));
    }
    if (scopeType === "shop") {
      return (shops.data?.shops ?? []).map((s: Shop) => ({
        value: String(s.shop_id),
        label: `${s.shop_name} · ${s.region_name ?? "?"} (${s.shop_id})`,
      }));
    }
    return [];
  }, [scopeType, regions.data, shops.data]);

  const trigger = useMutation({
    mutationFn: () =>
      api.triggerRun({
        report_type: reportType,
        scope_type: scopeType,
        scope_id: scopeType === "national" ? null : (scopeId || null),
        model: model || undefined,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["runs"] }),
  });

  const canTrigger =
    !!lockedPrompt &&
    (scopeType === "national" || !!scopeId) &&
    !trigger.isPending;

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

          <Field label="范围">
            <select className="select" value={scopeType} onChange={(e) => setScopeType(e.target.value as typeof scopeType)}>
              <option value="national">全国</option>
              <option value="super_region">大区</option>
              <option value="region">区域</option>
              <option value="shop">门店</option>
            </select>
          </Field>

          {scopeType !== "national" && (
            <Field label={`选择${SCOPE_LABEL[scopeType]}`}>
              <select
                className="select min-w-[200px]"
                value={scopeId}
                onChange={(e) => setScopeId(e.target.value)}
              >
                <option value="">请选择…</option>
                {scopeIdOptions.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </Field>
          )}

          <Field label="模型 (留空走默认)">
            <select className="select" value={model} onChange={(e) => setModel(e.target.value)}>
              <option value="">默认 ({models.data?.default ?? "-"})</option>
              {models.data?.supported.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </Field>

          <button
            className="px-4 py-2 bg-brand-500 text-white rounded-md text-sm font-medium hover:bg-brand-600 disabled:opacity-50"
            disabled={!canTrigger}
            onClick={() => trigger.mutate()}
          >
            {trigger.isPending ? "触发中…" : "触发 Run"}
          </button>
          {trigger.isSuccess && (
            <span className="text-xs text-emerald-600">
              ✓ 已创建 run #{trigger.data.id}
            </span>
          )}
        </div>

        {/* 自动锁定的 prompt 信息 */}
        <div className="mt-3 text-xs text-slate-600">
          {lockedPrompt ? (
            <>
              将使用 prompt:{" "}
              <Link href={`/prompts?highlight=${lockedPrompt.id}`} className="font-mono text-brand-600 hover:underline">
                {lockedPrompt.name}
              </Link>
              <span className="text-slate-400 ml-1">（按「报告类型 × 范围」自动锁定）</span>
            </>
          ) : (
            <span className="text-amber-700">⚠ {SCOPE_LABEL[scopeType]} 维度暂无 {reportType} prompt，请先到 Prompts 页配置</span>
          )}
        </div>

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
                <Th>ID</Th><Th>类型</Th><Th>范围</Th><Th>触发</Th><Th>模型</Th><Th>Prompt</Th><Th>状态</Th>
                <Th>Tokens</Th><Th>耗时</Th><Th>开始</Th>
              </tr>
            </thead>
            <tbody>
              {runs.data?.slice(0, 10).map((r) => (
                <tr key={r.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <Td><Link href={`/runs/${r.id}`} className="text-brand-600 hover:underline">#{r.id}</Link></Td>
                  <Td>{r.report_type}</Td>
                  <Td className="text-xs">
                    <span className="font-medium">{r.scope_label || (r.scope_type === "national" ? "全国" : "-")}</span>
                  </Td>
                  <Td>{r.trigger_type}</Td>
                  <Td className="font-mono text-xs">{r.model ?? "-"}</Td>
                  <Td className="text-xs">
                    {r.prompt_name ? (
                      <Link href={`/prompts?highlight=${r.prompt_id}`} className="text-brand-600 hover:underline">
                        {r.prompt_name}
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
                <tr><td colSpan={10} className="text-center text-slate-400 py-8 text-xs">暂无运行记录，点上方"触发 Run"试试</td></tr>
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

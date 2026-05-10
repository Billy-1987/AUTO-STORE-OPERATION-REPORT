// 文件作用：Run 详情页 — scope 标识 + 内嵌报告预览 + 6 步流水线
// 版本：v0.4.0 — ⑥ 钉钉分发改为真实展示：dispatch_status + 收件人快照 + 钉钉响应
// 版本：v0.3.0 — 顶部加 scope 标识；新增「报告预览」区（iframe 内嵌 /reports/{id}）
// 版本：v0.2.0 — 头部展示本次实际使用的 prompt 版本（点击跳转）
"use client";

import { useQuery } from "@tanstack/react-query";
import { api, type DispatchInfo } from "@/lib/api";
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
  const dispatch = useQuery({ queryKey: ["run-dispatch", id], queryFn: () => api.getRunDispatch(id) });

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
            {r.report_type} · <span className="font-medium text-slate-700">{r.scope_label || (r.scope_type === "national" ? "全国" : r.scope_type || "-")}</span>
            {r.scope_type && r.scope_type !== "national" && (
              <span className="text-slate-400"> ({r.scope_type})</span>
            )}
            {" · "}{r.trigger_type} · 模型 <span className="font-mono">{r.model ?? "-"}</span>
            {" · "}
            Prompt {r.prompt_name ? (
              <Link href={`/prompts?highlight=${r.prompt_id}`} className="text-brand-600 hover:underline font-medium">
                {r.prompt_name} v{r.prompt_version} ↗
              </Link>
            ) : <span className="text-slate-400">未指定</span>}
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

      {r.status === "success" && (
        <section className="bg-white border border-slate-200 rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
            <div>
              <div className="text-sm font-medium text-slate-800">📄 报告预览</div>
              <div className="text-xs text-slate-500 mt-0.5">AI 渲染后的 HTML 报告（钉钉 ActionCard 跳转的目标页）</div>
            </div>
            <a
              href={`http://localhost:8000/reports/${r.id}`}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-brand-600 hover:underline"
            >新窗口打开 ↗</a>
          </div>
          <iframe
            src={`http://localhost:8000/reports/${r.id}`}
            className="w-full"
            style={{ height: "70vh", border: "0" }}
            title={`Run ${r.id} report`}
          />
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

        <DispatchPanel dispatch={dispatch.data} loading={dispatch.isLoading} />
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

const DISPATCH_LABEL: Record<DispatchInfo["status"], { text: string; cls: string }> = {
  sent:        { text: "已派发", cls: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  failed:      { text: "失败",   cls: "bg-red-50 text-red-700 border-red-200" },
  skipped:     { text: "跳过",   cls: "bg-amber-50 text-amber-700 border-amber-200" },
  pending:     { text: "待发",   cls: "bg-slate-100 text-slate-600 border-slate-200" },
  not_reached: { text: "未到达", cls: "bg-slate-100 text-slate-400 border-slate-200" },
};

function DispatchPanel({ dispatch, loading }: { dispatch?: DispatchInfo; loading: boolean }) {
  const open = !!dispatch && dispatch.status !== "not_reached";
  const label = DISPATCH_LABEL[dispatch?.status ?? "not_reached"];
  const included = dispatch?.recipients.filter((r) => r.included) ?? [];
  const skipped = dispatch?.recipients.filter((r) => !r.included) ?? [];

  return (
    <details open={open} className="bg-white border border-slate-200 rounded-lg">
      <summary className="cursor-pointer px-4 py-3 flex items-center justify-between hover:bg-slate-50">
        <div>
          <div className="text-sm font-medium text-slate-800">⑥ 钉钉分发</div>
          <div className="text-xs text-slate-500 mt-0.5">
            ActionCard 推送状态 + 命中本 scope 的订阅者
          </div>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded border ${label.cls}`}>{label.text}</span>
      </summary>

      <div className="border-t border-slate-100 p-4 space-y-4">
        {loading && <div className="text-xs text-slate-400">加载中…</div>}

        {dispatch && dispatch.status === "not_reached" && (
          <div className="text-xs text-slate-500">
            pipeline 还没走到第 7 步（dispatch），所以没有派发记录。
          </div>
        )}

        {dispatch && dispatch.status !== "not_reached" && (
          <>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <KV k="发送时间" v={dispatch.sent_at ? fmtDate(dispatch.sent_at) : "—"} />
              <KV k="实际派发" v={`${included.length} 人 / 命中 ${dispatch.recipients.length} 人`} />
              <KV
                k="task_id"
                v={String((dispatch.response as { response?: { task_id?: number } } | null)?.response?.task_id ?? "—")}
              />
              <KV
                k="errcode"
                v={String((dispatch.response as { response?: { errcode?: number } } | null)?.response?.errcode ?? "—")}
              />
            </div>

            <div>
              <div className="text-xs font-medium text-slate-700 mb-1.5">
                收件人 <span className="text-slate-400">(按订阅+scope+is_active 过滤，当前快照)</span>
              </div>
              {dispatch.recipients.length === 0 ? (
                <div className="text-xs text-slate-400 px-3 py-2 bg-slate-50 rounded">本 scope 暂无订阅者</div>
              ) : (
                <table className="w-full text-xs">
                  <thead className="text-slate-500">
                    <tr>
                      <th className="text-left py-1.5 px-2 font-normal">姓名</th>
                      <th className="text-left py-1.5 px-2 font-normal">角色</th>
                      <th className="text-left py-1.5 px-2 font-normal">userid</th>
                      <th className="text-left py-1.5 px-2 font-normal">手机号</th>
                      <th className="text-left py-1.5 px-2 font-normal w-16">入列</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...included, ...skipped].map((r) => (
                      <tr key={r.id} className="border-t border-slate-100">
                        <td className="py-1.5 px-2 text-slate-800">{r.name}</td>
                        <td className="py-1.5 px-2 text-slate-500">{r.role}</td>
                        <td className="py-1.5 px-2 font-mono text-slate-700">{r.dingtalk_userid || "—"}</td>
                        <td className="py-1.5 px-2 text-slate-500">{r.dingtalk_mobile || "—"}</td>
                        <td className="py-1.5 px-2">
                          {r.included
                            ? <span className="text-emerald-700">✓</span>
                            : <span className="text-slate-400" title="无 userid，被跳过">—</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            {dispatch.response && (
              <details className="text-xs">
                <summary className="cursor-pointer text-slate-500 hover:text-slate-800">钉钉原始响应</summary>
                <pre className="codeblock mt-2 max-h-72">{JSON.stringify(dispatch.response, null, 2)}</pre>
              </details>
            )}
          </>
        )}
      </div>
    </details>
  );
}

function KV({ k, v }: { k: string; v: string }) {
  return (
    <div className="bg-slate-50 rounded px-3 py-2">
      <div className="text-slate-500 text-[11px]">{k}</div>
      <div className="text-slate-800 font-medium mt-0.5">{v}</div>
    </div>
  );
}

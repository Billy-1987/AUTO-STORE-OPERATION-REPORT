// 文件作用：前端 API client + 类型定义
// 版本：v0.5.0 — Prompt 改原地编辑：去掉 create/activate/delete，加 updatePrompt；加 listShops
// 版本：v0.4.0 — RunSummary/RunDetail 加 scope 字段；triggerRun body 加 scope_type/scope_id

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

async function http<T>(path: string, opts?: RequestInit): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    ...opts,
    headers: { "Content-Type": "application/json", ...(opts?.headers || {}) },
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}: ${await r.text()}`);
  return r.json();
}

export type RunSummary = {
  id: number;
  trigger_type: string;
  report_type: string;
  dataset_id: number | null;
  scope_type: string | null;
  scope_id: string | null;
  scope_label: string | null;
  model: string | null;
  status: string;
  period_start: string | null;
  period_end: string | null;
  total_tokens: number | null;
  latency_ms: number | null;
  started_at: string;
  finished_at: string | null;
  error_message: string | null;
  prompt_id: number | null;
  prompt_name: string | null;
  prompt_version: number | null;
};

export type RunDetail = RunSummary & {
  sql_dump: string | null;
  data_dump: string | null;
  prompt_rendered: string | null;
  response_text: string | null;
  response_html: string | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  cost_estimate: number | null;
};

export type Prompt = {
  id: number;
  name: string;
  report_type: string;
  scope_type: string | null;
  version: number;
  content: string | null;
  description: string | null;
  model: string | null;
  is_active: number;
  created_at: string;
  updated_at: string;
};

export type Shop = {
  shop_id: number;
  shop_name: string;
  region_id: number | null;
  region_name: string | null;
};

export type Recipient = {
  id: number;
  name: string;
  role: string;
  region_ids: number[];
  shop_ids: number[];
  dingtalk_userid: string | null;
  dingtalk_mobile: string | null;
  subscribe_weekly: number;
  subscribe_monthly: number;
  subscribe_holiday: number;
  is_active: number;
};

export const api = {
  health: () => http<{ status: string; default_model: string }>("/health"),
  systemInfo: () => http<Record<string, unknown>>("/api/system/info"),
  models: () => http<{ default: string; supported: string[] }>("/api/models"),
  regions: () => http<{ regions: Record<string, string>; super_regions: Record<string, number[]> }>("/api/regions"),
  listShops: () => http<{ shops: Shop[] }>("/api/shops"),

  listRuns: () => http<RunSummary[]>("/api/runs"),
  getRun: (id: number) => http<RunDetail>(`/api/runs/${id}`),
  triggerRun: (body: { report_type: string; scope_type?: string; scope_id?: string | null; scope_label?: string; model?: string; prompt_id?: number; period_start?: string; period_end?: string; dataset_id?: number }) =>
    http<RunSummary>("/api/runs/manual", { method: "POST", body: JSON.stringify(body) }),

  listPrompts: (report_type?: string) =>
    http<Prompt[]>(`/api/prompts${report_type ? `?report_type=${report_type}` : ""}`),
  updatePrompt: (id: number, body: { content?: string; description?: string; model?: string }) =>
    http<Prompt>(`/api/prompts/${id}`, { method: "PUT", body: JSON.stringify(body) }),

  listRecipients: () => http<Recipient[]>("/api/recipients"),
  createRecipient: (body: Partial<Recipient> & { name: string; role: string }) =>
    http<Recipient>("/api/recipients", { method: "POST", body: JSON.stringify(body) }),
  deleteRecipient: (id: number) => http<{ deleted: number }>(`/api/recipients/${id}`, { method: "DELETE" }),
};

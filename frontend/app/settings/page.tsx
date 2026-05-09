// 文件作用：系统信息页（只读，方便排查配置）
// 版本：v0.1.0
"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export default function SettingsPage() {
  const sys = useQuery({ queryKey: ["sys"], queryFn: api.systemInfo });
  const models = useQuery({ queryKey: ["models"], queryFn: api.models });
  const regions = useQuery({ queryKey: ["regions"], queryFn: api.regions });

  return (
    <div className="space-y-5 max-w-4xl">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">系统信息</h1>
        <p className="text-sm text-slate-500 mt-1">运行时配置概览（敏感字段不展示）</p>
      </header>

      <Card title="系统">
        <KV data={sys.data ?? {}} />
      </Card>

      <Card title="支持的模型">
        <div className="text-sm">
          <div className="text-xs text-slate-500 mb-2">
            默认: <span className="font-mono">{models.data?.default}</span>
          </div>
          <ul className="space-y-1">
            {models.data?.supported.map((m) => (
              <li key={m} className="font-mono text-xs px-2 py-1 bg-slate-50 rounded inline-block mr-1">{m}</li>
            ))}
          </ul>
        </div>
      </Card>

      <Card title="区域映射">
        <table className="text-sm">
          <tbody>
            {Object.entries(regions.data?.regions ?? {}).map(([id, n]) => (
              <tr key={id} className="border-b border-slate-100">
                <td className="py-1.5 pr-4 font-mono text-xs text-slate-500">{id}</td>
                <td className="py-1.5">{n}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="mt-3 text-xs text-slate-500">
          <strong>大区：</strong>
          {Object.entries(regions.data?.super_regions ?? {}).map(([n, ids]) => (
            <div key={n} className="font-mono">{n} = {(ids as number[]).join(", ")}</div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="bg-white border border-slate-200 rounded-lg p-5">
      <h2 className="text-base font-medium text-slate-800 mb-3">{title}</h2>
      {children}
    </section>
  );
}

function KV({ data }: { data: Record<string, unknown> }) {
  return (
    <table className="text-sm w-full">
      <tbody>
        {Object.entries(data).map(([k, v]) => (
          <tr key={k} className="border-b border-slate-100">
            <td className="py-1.5 pr-4 font-mono text-xs text-slate-500 w-44">{k}</td>
            <td className="py-1.5 font-mono text-xs">{String(v)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

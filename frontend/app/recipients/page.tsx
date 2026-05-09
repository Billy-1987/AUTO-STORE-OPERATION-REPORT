// 文件作用：收件人管理页
// 版本：v0.1.0
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";

const ROLES = [
  { v: "regional_director", n: "区域总" },
  { v: "regional_manager", n: "区域经理" },
  { v: "store_manager", n: "门店店长" },
  { v: "colleague", n: "同事" },
];

export default function RecipientsPage() {
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["recipients"], queryFn: api.listRecipients });
  const [showNew, setShowNew] = useState(false);
  const del = useMutation({
    mutationFn: (id: number) => api.deleteRecipient(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["recipients"] }),
  });

  return (
    <div className="space-y-4 max-w-6xl">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">收件人</h1>
          <p className="text-sm text-slate-500 mt-1">钉钉推送目标列表，按角色 + 区域/门店路由</p>
        </div>
        <button className="btn-primary" onClick={() => setShowNew(!showNew)}>{showNew ? "取消" : "添加收件人"}</button>
      </header>

      {showNew && <NewForm onDone={() => { setShowNew(false); qc.invalidateQueries({ queryKey: ["recipients"] }); }} />}

      <section className="bg-white rounded-lg border border-slate-200">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600 text-xs">
              <tr>
                <th className="text-left px-4 py-2 font-medium">姓名</th>
                <th className="text-left px-4 py-2 font-medium">角色</th>
                <th className="text-left px-4 py-2 font-medium">区域</th>
                <th className="text-left px-4 py-2 font-medium">门店</th>
                <th className="text-left px-4 py-2 font-medium">钉钉 UserID</th>
                <th className="text-left px-4 py-2 font-medium">订阅</th>
                <th className="text-left px-4 py-2 font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {list.data?.map((r) => (
                <tr key={r.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-2 font-medium">{r.name}</td>
                  <td className="px-4 py-2">{ROLES.find((x) => x.v === r.role)?.n ?? r.role}</td>
                  <td className="px-4 py-2 text-xs">{r.region_ids.length ? r.region_ids.join(", ") : "-"}</td>
                  <td className="px-4 py-2 text-xs">{r.shop_ids.length ? r.shop_ids.join(", ") : "-"}</td>
                  <td className="px-4 py-2 text-xs font-mono">{r.dingtalk_userid ?? "-"}</td>
                  <td className="px-4 py-2 text-xs space-x-1">
                    {r.subscribe_weekly ? <span className="px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded">周</span> : null}
                    {r.subscribe_monthly ? <span className="px-1.5 py-0.5 bg-purple-50 text-purple-700 rounded">月</span> : null}
                    {r.subscribe_holiday ? <span className="px-1.5 py-0.5 bg-amber-50 text-amber-700 rounded">假</span> : null}
                  </td>
                  <td className="px-4 py-2">
                    <button className="text-xs text-red-600 hover:underline" onClick={() => del.mutate(r.id)}>删除</button>
                  </td>
                </tr>
              ))}
              {list.data?.length === 0 && (
                <tr><td colSpan={7} className="text-center text-slate-400 py-8 text-xs">暂无收件人</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function NewForm({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState("");
  const [role, setRole] = useState("regional_manager");
  const [regions, setRegions] = useState("");
  const [shops, setShops] = useState("");
  const [userid, setUserid] = useState("");

  const create = useMutation({
    mutationFn: () => api.createRecipient({
      name,
      role,
      region_ids: regions.split(",").map((s) => parseInt(s.trim())).filter((n) => !isNaN(n)),
      shop_ids: shops.split(",").map((s) => parseInt(s.trim())).filter((n) => !isNaN(n)),
      dingtalk_userid: userid || undefined,
    }),
    onSuccess: onDone,
  });

  return (
    <section className="bg-white border border-slate-200 rounded-lg p-5 space-y-3">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <label className="flex flex-col gap-1 text-xs text-slate-600">
          <span>姓名</span>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-600">
          <span>角色</span>
          <select className="select" value={role} onChange={(e) => setRole(e.target.value)}>
            {ROLES.map((r) => <option key={r.v} value={r.v}>{r.n}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-600">
          <span>钉钉 UserID</span>
          <input className="input" value={userid} onChange={(e) => setUserid(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-600">
          <span>区域 IDs（逗号分隔）</span>
          <input className="input" value={regions} onChange={(e) => setRegions(e.target.value)} placeholder="68, 67" />
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-600">
          <span>门店 IDs（逗号分隔）</span>
          <input className="input" value={shops} onChange={(e) => setShops(e.target.value)} placeholder="3066, 3079" />
        </label>
      </div>
      <button className="btn-primary" disabled={!name || create.isPending} onClick={() => create.mutate()}>
        {create.isPending ? "创建中…" : "创建"}
      </button>
      {create.isError && <span className="ml-3 text-xs text-red-600">{(create.error as Error).message}</span>}
    </section>
  );
}

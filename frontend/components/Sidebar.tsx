// 文件作用：左侧导航
// 版本：v0.1.0
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, FileText, Users, Settings, LayoutDashboard } from "lucide-react";
import { cn } from "@/lib/utils";

const items = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/runs", label: "运行历史", icon: Activity },
  { href: "/prompts", label: "Prompt 版本", icon: FileText },
  { href: "/recipients", label: "收件人", icon: Users },
  { href: "/settings", label: "系统信息", icon: Settings },
];

export default function Sidebar() {
  const path = usePathname();
  return (
    <aside className="w-56 shrink-0 bg-white border-r border-slate-200 flex flex-col">
      <div className="px-5 py-5 border-b border-slate-200">
        <div className="text-base font-semibold text-brand-600">经营简报</div>
        <div className="text-xs text-slate-500 mt-1">控制台 v0.1</div>
      </div>
      <nav className="flex-1 p-2 space-y-1">
        {items.map((it) => {
          const active = path === it.href || (it.href !== "/" && path.startsWith(it.href));
          const Icon = it.icon;
          return (
            <Link
              key={it.href}
              href={it.href}
              className={cn(
                "flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors",
                active ? "bg-brand-50 text-brand-700 font-medium" : "text-slate-600 hover:bg-slate-50",
              )}
            >
              <Icon className="w-4 h-4" />
              {it.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}

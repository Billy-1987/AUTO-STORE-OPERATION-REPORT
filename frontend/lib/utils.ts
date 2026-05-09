// 文件作用：UI 工具函数
// 版本：v0.1.0

import { clsx, ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function fmtDate(s: string | null | undefined): string {
  if (!s) return "-";
  const d = new Date(s);
  return d.toLocaleString("zh-CN", { hour12: false });
}

export function fmtNum(n: number | null | undefined): string {
  if (n == null) return "-";
  return n.toLocaleString("zh-CN");
}

export function statusColor(status: string): string {
  switch (status) {
    case "success": return "bg-emerald-100 text-emerald-700 border-emerald-300";
    case "failed":  return "bg-red-100 text-red-700 border-red-300";
    case "running": return "bg-blue-100 text-blue-700 border-blue-300 animate-pulse";
    case "pending": return "bg-slate-100 text-slate-600 border-slate-300";
    default:        return "bg-slate-100 text-slate-600 border-slate-300";
  }
}

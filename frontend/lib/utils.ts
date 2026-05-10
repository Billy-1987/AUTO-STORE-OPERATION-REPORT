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

export function fmtRel(s: string | null | undefined): string {
  if (!s) return "-";
  const d = new Date(s);
  const diffMs = Date.now() - d.getTime();
  const sec = Math.floor(diffMs / 1000);
  if (sec < 60) return "刚刚";
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} 分钟前`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} 小时前`;
  const day = Math.floor(hr / 24);
  if (day < 7) return `${day} 天前`;
  if (day < 30) return `${Math.floor(day / 7)} 周前`;
  return d.toLocaleDateString("zh-CN");
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

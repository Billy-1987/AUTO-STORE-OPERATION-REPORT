// 文件作用：根布局，挂导航 + Providers
// 版本：v0.1.0

import type { Metadata } from "next";
import "./globals.css";
import Providers from "@/components/Providers";
import Sidebar from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "门店经营简报控制台",
  description: "AI 工作流可视化 · 模型 A/B · Prompt 工程",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh">
      <body>
        <Providers>
          <div className="flex min-h-screen">
            <Sidebar />
            <main className="flex-1 p-6 overflow-x-auto">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}

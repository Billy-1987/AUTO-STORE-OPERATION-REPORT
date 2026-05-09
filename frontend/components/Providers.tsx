// 文件作用：React Query Provider 包装
// 版本：v0.1.0
"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export default function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => new QueryClient({
    defaultOptions: { queries: { staleTime: 5_000, refetchInterval: 5_000, retry: 1 } },
  }));
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

/**
 * SPA entry point.
 *
 * Mounts <App /> under a single React Query client. The client is configured
 * for a local research tool: data is treated as reasonably fresh (low staleness
 * churn), retries are disabled so API errors surface immediately in the UI, and
 * window-focus refetching is off to avoid noise while inspecting a turn.
 */
import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import App from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { I18nProvider } from "./i18n/I18nProvider";
// 宿主嵌入准备（?embed=aifa 时锁浅色 + 设 data-embed + 改标题）须在首次渲染前执行。
import "./lib/embedMode";
import "./index.css";
import "./aifaEmbed.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
      staleTime: 5_000,
    },
    mutations: {
      retry: false,
    },
  },
});

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error('Root element "#root" not found in index.html');
}

ReactDOM.createRoot(rootEl).render(
  <React.StrictMode>
    <ErrorBoundary>
      <I18nProvider>
        <QueryClientProvider client={queryClient}>
          <App />
        </QueryClientProvider>
      </I18nProvider>
    </ErrorBoundary>
  </React.StrictMode>,
);

import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';

import App from './App';
import './styles/index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // 与技术方案 §11.6 长任务 Job 轮询协议匹配（首版 1s/轮询）
      refetchOnWindowFocus: false,
      retry: 0,
      staleTime: 5_000,
    },
  },
});

const rootEl = document.getElementById('root');
if (!rootEl) {
  throw new Error('Missing #root element');
}

ReactDOM.createRoot(rootEl).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);

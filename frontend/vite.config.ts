import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// 与 docs/engineering/02-代码架构与目录约定.md 一致。
// 开发时通过 proxy 把 /api/v1 转发到后端 8000 端口；
// 生产环境通过 Nginx 反代，前端构建产物 dist/ 直接挂在 Nginx root。
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
});

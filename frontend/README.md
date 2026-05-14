# Frontend · React + Vite + TypeScript + Tailwind

> 通用英语对话练习产品 · C 端前端 SPA（移动端优先）。  
> 架构遵循 [`docs/engineering/02-代码架构与目录约定.md`](../docs/engineering/02-代码架构与目录约定.md)（前端四层：Page → Component → Hook → Service）。  
> 视觉基调：**干净书页风**（暖白底 + 深灰文字 + 暖橘强调色）。

## 本地开发

```bash
cd frontend
npm ci          # 或 npm install
npm run dev     # 默认 http://localhost:5173；通过 vite.config.ts proxy 转发 /api 到 8000
```

启动后浏览器打开 `http://localhost:5173`，点击"检查后端是否就绪"按钮验证 M0 链路。

## 构建生产产物

```bash
cd frontend
npm run build   # 产物在 frontend/dist/，由 Nginx 直接挂载（见 deploy/nginx-gcp.conf）
```

## 当前里程碑

- **M0**（当前）：脚手架 + P1 欢迎页 + 健康检查按钮
- **M6+**：依次填充 P2 ~ P3a 全部页面（见 `docs/engineering/01-技术方案.md` §9）

## 目录速览

```
src/
├── main.tsx              入口：装配 Router + QueryClient
├── App.tsx               路由表
├── pages/                ① 页面层（M0: WelcomePage）
├── components/           ② 组件层（M6+）
├── hooks/                ③ 业务钩子层（M6+）
├── services/             ④ 服务客户端层（M0: apiClient + healthApi）
├── types/                跨层 TS 类型（M1+ 与后端 Pydantic 一一对应）
├── store/                Zustand UI 状态（M6+）
├── styles/               Tailwind 全局
└── lib/                  共用工具
```

## 设计 token（Tailwind）

| 名称 | 值 | 用途 |
|------|----|------|
| `bg-paper` | `#fdfaf5` | 页面底色 |
| `text-ink` | `#1f1d1a` | 主文字 |
| `text-ink-soft` | `#6b6457` | 副文字 / 占位 |
| `bg-accent` | `#c2410c` | 主按钮、强调 |
| `border-border-subtle` | `#e7e1d4` | 卡片描边、分割线 |
| `text-ok` | `#2e7d32` | 成功提示 |
| `text-danger` | `#b91c1c` | 错误提示 |

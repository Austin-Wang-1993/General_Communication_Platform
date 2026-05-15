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

启动后打开 `http://localhost:5173/`：P1「知道了」→ `/scenarios`；需本机后端 `uvicorn` 在 8000 端口以调用 API。

## 构建生产产物

```bash
cd frontend
npm run build   # 产物在 frontend/dist/，由 Nginx 直接挂载（见 deploy/nginx-gcp.conf）
```

## 当前里程碑（M6 进行中）

- **P1** `/`：欢迎页、「知道了」、顶栏「调试模式」→ `/debug/`
- **P2** `/scenarios`：场景包列表、`POST` 新建、`DELETE`、底部动作表（进入 / 删除）
- **P2.1** `/scenarios/:id/setup`：五字段 + `commit-intake`，成功后启动框架 Job 并跳转轮询页
- **P2.2 / P2.4** `/scenarios/:id/jobs/:jobId/framework|world`：G10 文案轮询、`POST` 取消；框架完成后手动「下一步」启动世界 Job
- **P3 占位** `/scenarios/:id/chat`：`GET runtime`、可选「进 1-1」、回合列表只读展示

**待续**：P2.3 框架预览、P2.5 世界预览、P3 完整发送/气泡/G8 收件人、P3a 切节等（见 `docs/product/02-前端需求文档.md`）。

## 目录速览

```
src/
├── main.tsx              入口：装配 Router + QueryClient
├── App.tsx               路由表
├── pages/                ① 页面层（Welcome / Scenarios / Intake / JobWait / ChatPlaceholder）
├── components/           ② 组件层（layout/AppHeader 等）
├── hooks/                ③ 业务钩子层（预留）
├── services/             ④ API：apiClient、healthApi、scenariosApi、runtimeApi
├── types/                与后端契约对齐的 TS 类型
├── store/                Zustand（预留）
├── styles/               Tailwind 全局
└── lib/                  lifecycle 文案等
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

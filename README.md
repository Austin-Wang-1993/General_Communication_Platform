# General Communication Platform · 通用英语对话练习

一个把**英语学习**嵌入**互动剧情**的练习产品：用户用自然语言描述场景与目标，系统生成一个有章节、有人物、有任务的英文小故事；用户在故事里和 NPC 用英文聊天，按章节练习真实语境中的表达。

---

## 当前状态

**`main` 为当前完整功能线**：含 M1~M4 场景包与创作 Job、M5 运行期 **runtime / enter / turns / auto-opener**、**R1**（`POST/GET .../hints`，`hint_latest.json`）、**R2**（`POST/GET .../analytics`，`analytics.json`），以及调试页 **⑥**（NPC 单选收件人）与 **⑦**（R1/R2 调试按钮）、`apiCall` 对 **204** 空体的解析。**尚未实现**：§6.6.4 全量链式规则等。服务器请同步 **`main`**：`bash deploy/server-one-shot-sync.sh 'main'`（见 [腾讯云部署指南](docs/operations/01-腾讯云部署指南.md)）。

- 后端：FastAPI + `health` + `scenario-packages`（上述能力全集）
- 前端：Vite + React + TS + Tailwind + P1 欢迎页 + 健康检查按钮
- 调试页：`backend/app/debug_ui/`（②~⑧，含 **⑦** hints / analytics 操作区）
- 部署：`deploy/`（含 **`server-one-shot-sync.sh`** 一键同步）
- 用户操作手册：[`docs/operations/01-腾讯云部署指南.md`](docs/operations/01-腾讯云部署指南.md)

**下一步**：§6.6.4 规则校验等。

---

## 文档导览

### 产品层

| 文档 | 路径 | 给谁看 |
|------|------|--------|
| **产品需求文档**（核心，唯一字段语义真源） | [`docs/product/01-产品需求文档.md`](docs/product/01-产品需求文档.md) | 产品 / 开发 / QA |
| **前端需求文档**（C 端交互、用户故事） | [`docs/product/02-前端需求文档.md`](docs/product/02-前端需求文档.md) | 前端 / 设计 / 产品 |

### 工程层

| 文档 | 路径 | 回答的问题 |
|------|------|--------|
| **技术方案** | [`docs/engineering/01-技术方案.md`](docs/engineering/01-技术方案.md) | 选什么技术？怎么部署？怎么分期？超时怎么办？ |
| **代码架构与目录约定** | [`docs/engineering/02-代码架构与目录约定.md`](docs/engineering/02-代码架构与目录约定.md) | 代码该写在哪一层？目录长什么样？前后端字段怎么对齐？ |
| **API 接口文档** | [`docs/engineering/03-API 接口文档.md`](docs/engineering/03-API%20接口文档.md) | 每个 HTTP 接口的方法、路径、请求体、响应体、错误码是什么？ |
| **业务流程与状态机** | [`docs/engineering/04-业务流程与状态机.md`](docs/engineering/04-业务流程与状态机.md) | 状态如何迁移？§6.6.4 规则怎么执行？自动开场怎么触发？G3/G4 清库范围是什么？ |

### 运维 / 部署

| 文档 | 路径 | 给谁看 |
|------|------|--------|
| **腾讯云部署指南** | [`docs/operations/01-腾讯云部署指南.md`](docs/operations/01-腾讯云部署指南.md) | **你**（产品经理，按文档复制粘贴到 Web Shell） |

### 阅读顺序建议

- **产品经理 / 投资人**：产品需求 → 前端需求 → 技术方案（只看 §1~§3）
- **后端开发**：产品需求 → 技术方案 → 代码架构 → API 接口 → 业务流程
- **前端开发**：前端需求 → 代码架构（前端部分） → API 接口
- **运维 / 部署**：技术方案 §11

> 字段、枚举的**唯一真源**始终是**产品需求文档**；代码组织的**唯一真源**是**代码架构文档**；HTTP 接口的**唯一真源**是 **API 接口文档**。三者之间发生不一致时，**以产品需求文档为最高优先级**修复。

---

## 产品一句话

> 用户描述场景与目标 → 系统生成英文剧情世界 → **NPC 主动开场、邀请用户开口** → 用户用英文回应、推进故事 → 双轨评估（语言 + 沟通）。

## 三个核心抽象

1. **场景包**（Scenario Package）—— 每个"练习世界"独立存档、彼此隔离。
2. **章节自由推进** —— 章节有推荐叙事顺序，但用户**可以任意选节**进入练习（包括跳跃、回头复练）。
3. **进节即开场** —— 用户进入任何尚无对话的小节，系统**自动由 NPC 发起首条对话**，避免"对着空屏发呆"。

---

## 技术选型（已确定）

- **前端**：Vite + React + TypeScript + Tailwind CSS + Zustand + TanStack Query（**移动端优先**）
- **后端**：Python 3.11 + FastAPI + httpx + **DeepSeek `deepseek-chat`**
- **持久化**：纯文件 + JSON（`data/scenarios/{scenario_id}/...`），首版**不用数据库**
- **部署**：腾讯云 Ubuntu + Nginx + systemd + **纯 IP `43.155.205.89` HTTP 直连**（首版无 HTTPS）

---

## 工程顺序

> 先用**后端调试页**串通所有接口，再做 C 端前端页面。

| 阶段 | 内容 | 状态 |
|------|------|------|
| **M0** | 仓库骨架 + 健康检查 + 部署链路 | ✅ 已合并 main |
| **M1** | 场景包 CRUD | ✅ 已合并 main |
| M2 | 五字段录入 + DeepSeek 扩写 | ✅ 已合并 main |
| M3 | 框架 + 角色 Job | ✅ 已合并 main |
| M4 | 全书小节 Job + 取消清库 | ✅ 已合并 main |
| M5 | 聊天 + 自动开场 | 进行中（§4.1 runtime、§4.2 enter 已合并；对话 turns 待续） |
| M5.5 | R1 提示 + R2 复盘 | 待开始 |
| M6 ~ M9 | C 端前端 P1~P3a 全部页面 | 待开始 |

详见 [技术方案 §9](docs/engineering/01-技术方案.md)。

---

## 仓库结构速览

```
backend/                后端 FastAPI
├── app/
│   ├── main.py         入口
│   ├── config.py       env 配置
│   ├── errors.py       异常类
│   ├── routers/        ① 路由层（M0: health）
│   ├── services/       ② 业务服务层（M1+）
│   ├── repositories/   ③ 数据仓库层（M1+）
│   ├── clients/        ④ 外部客户端层（M2+）
│   ├── models/         跨层 Pydantic 模型
│   ├── validators/     业务校验
│   ├── prompts/        LLM 提示词 Markdown
│   └── debug_ui/       调试页静态资源
├── tests/              单元 + 集成测试
└── requirements.txt

frontend/               前端 React + Vite + TS + Tailwind
├── src/
│   ├── main.tsx        入口
│   ├── App.tsx         路由表
│   ├── pages/          ① 页面层（M0: WelcomePage）
│   ├── components/     ② 组件层（M6+）
│   ├── hooks/          ③ 业务钩子层（M6+）
│   ├── services/       ④ 服务客户端（M0: apiClient + healthApi）
│   ├── types/          跨层 TS 类型（M1+）
│   ├── store/          Zustand UI 状态（M6+）
│   └── styles/         Tailwind 全局
├── index.html
└── package.json

deploy/                 部署脚本
├── gcp-backend.service systemd 单元
├── nginx-gcp.conf      Nginx 站点配置
└── pull-and-restart.sh 一键拉取并重启脚本（支持分支参数）

docs/
├── product/            产品需求 + 前端需求
├── engineering/        技术方案 + 架构 + API + 业务流程
└── operations/         腾讯云部署指南（用户实操手册）
```

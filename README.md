# General Communication Platform · 通用英语对话练习

一个把**英语学习**嵌入**互动剧情**的练习产品：用户用自然语言描述场景与目标，系统生成一个有章节、有人物、有任务的英文小故事；用户在故事里和 NPC 用英文聊天，按章节练习真实语境中的表达。

---

## 当前状态

**`main` 为当前完整功能线**：含 M1~M4、M5 运行期与 R1/R2、调试页；**§6.6.4** 回合硬规则已在 **`validators/turn_rules.py`** 接入 `POST …/turns` 与自动开场落盘路径。双 NPC 小节中，`POST …/turns` 可一次同步落 **1～3** 条 NPC 续写（`npc_turns` 批处理，见 **中台文档 §6.6.6** 与技术方案 **v0.3.13**），续写 LLM 入参含 **`response_contract_guide`**（对齐 **§6.6.6（G）** 与 **F-P3-10**）；`RuntimeService` 另对 roster 中**未在本节出场**同伴的 `name` 做弱校验（对齐 **F-P3-10 / P3-10-03**），仍须满足 NPC–NPC 连续上限与交回练习者等规则。服务器请同步 **`main`**：`bash deploy/server-one-shot-sync.sh 'main'`（见 [腾讯云部署指南](docs/operations/01-腾讯云部署指南.md)）。

- 后端：FastAPI + `health` + `scenario-packages`（含 **`GET /api/v1/debug/raw-file`** 白名单 JSON，供前端 P2.3/P2.5 与调试页）
- 前端：Vite + React + TS + Tailwind；**M6 进行中**：P1~P2.1（**五字段样例底纹**：浅灰斜体、「（样例）」、聚焦清空、未改则提交；示例含「约 4 章」联调提示）、创作三步 `CreationStepper`、P2.2/P2.4 Job 轮询（成功后自动进 **P2.3 框架预览** / **P2.5 世界预览**）、**P2.3** `/framework-preview`、**P2.5** `/world-preview`（按节展开叙事/目标/出场人物；底栏仅「返回首页」「直接开启对话」）、**P3** `/chat`（首入自动 `enter(S[0])`；**用户与 NPC 气泡**均展示「发出方 → 接收方」；一次 `POST turns` 若返回多条 NPC 续写按序展示；顶栏 **返回首页 / 背景介绍 / 回答提示 R1 / 总结分析 R2 / 查看列表**；底栏 **选择信息接收人** + `POST turns`；**P3a** 章节进节）；`debugAssetsApi` + `r1r2Api` + `scenariosApi` / `runtimeApi`
- 调试页：`backend/app/debug_ui/`（②~⑧，含 **⑦** hints / analytics 操作区）
- 部署：`deploy/`（含 **`server-one-shot-sync.sh`** 一键同步）
- 用户操作手册：[`docs/operations/01-腾讯云部署指南.md`](docs/operations/01-腾讯云部署指南.md)

**下一步**：M6 续作（打磨多方对话生成质量、P3 typing 与多气泡衔接体验等）与文档随版本迭代。

---

## 文档导览

### 产品层

| 文档 | 路径 | 给谁看 |
|------|------|--------|
| **中台产品文档**（场景包字段、规则与链路真源） | [`docs/product/01-中台产品文档.md`](docs/product/01-中台产品文档.md) | 产品 / 后端 / 前端（对齐语义时） |
| **前端需求文档**（C 端体验、交互与用户故事） | [`docs/product/02-前端需求文档.md`](docs/product/02-前端需求文档.md) | 前端 / 设计 / 产品 |

### 工程层

| 文档 | 路径 | 回答的问题 |
|------|------|--------|
| **技术方案** | [`docs/engineering/01-技术方案.md`](docs/engineering/01-技术方案.md) | 选什么技术？怎么部署？怎么分期？超时怎么办？ |
| **代码架构与目录约定** | [`docs/engineering/02-代码架构与目录约定.md`](docs/engineering/02-代码架构与目录约定.md) | 代码该写在哪一层？目录长什么样？前后端字段怎么对齐？ |
| **API 接口文档** | [`docs/engineering/03-API 接口文档.md`](docs/engineering/03-API%20接口文档.md) | 每个 HTTP 接口的方法、路径、请求体、响应体、错误码是什么？ |
| **业务流程与状态机** | [`docs/engineering/04-业务流程与状态机.md`](docs/engineering/04-业务流程与状态机.md) | 状态如何迁移？§6.6.4 规则怎么执行？自动开场怎么触发？G3/G4 清库范围是什么？ |

### 商业化 / 立项（叙事与机会摘编）

| 文档 | 路径 | 给谁看 |
|------|------|--------|
| **商业化目录说明** | [`docs/commercial/README.md`](docs/commercial/README.md) | 与产品/工程真源的关系 |
| **商业化摘编与立项备忘录** | [`docs/commercial/01-商业化摘编与立项备忘录.md`](docs/commercial/01-商业化摘编与立项备忘录.md) | **投资人、合伙人**：为什么做、市场与差异、用户分层、分阶段路线、商业模式雏形、与 Demo 的对应、风险与附录 |

> 本目录为**叙事与立项辅助**；产品硬规则仍以 **中台 / 前端需求** 为准，工程落地以 **技术方案 / API** 为准。

### 运维 / 部署

| 文档 | 路径 | 给谁看 |
|------|------|--------|
| **腾讯云部署指南** | [`docs/operations/01-腾讯云部署指南.md`](docs/operations/01-腾讯云部署指南.md) | **你**（产品经理，按文档复制粘贴到 Web Shell） |

### 阅读顺序建议

- **产品经理 / 投资人**：**商业化摘编**（[`docs/commercial/01-商业化摘编与立项备忘录.md`](docs/commercial/01-商业化摘编与立项备忘录.md)）→ 中台产品文档 → 前端需求文档 → 技术方案（只看 §1~§3）
- **合伙人 / 立项沟通**：**商业化摘编**全文 → `README` 产品一句话 → 按需深入中台 §4 主线
- **后端开发**：中台产品文档 → 技术方案 → 代码架构 → API 接口 → 业务流程
- **前端开发**：前端需求文档 → 代码架构（前端部分） → API 接口
- **运维 / 部署**：技术方案 §11

> **字段、枚举与中台硬规则**的**唯一真源**是 **`01-中台产品文档.md`**；**C 端可见体验与交互故事**的**唯一真源**是 **`02-前端需求文档.md`**；代码组织的**唯一真源**是 **代码架构文档**；HTTP 接口的**唯一真源**是 **API 接口文档**。若中台与 API 对同一字段或规则表述不一致，以**中台**为准并修正 API；若中台与前端体验文档在「纯展示」层面不一致，以**不违反中台硬规则**为前提，优先保证用户可理解，并回写消除歧义。

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
| M5 | 聊天 + 自动开场 + §6.6.4 写入前校验 | ✅ 已合并 main |
| M5.5 | R1 提示 + R2 复盘 | ✅ 已合并 main |
| M6 ~ M9 | C 端前端 P1~P3a | **M6 部分已开工**（见上「前端」行） |

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

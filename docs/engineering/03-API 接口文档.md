# API 接口文档

> **文档版本**：v0.1.0  
> **更新时间**：2026-05-14  
> **关联**：`../product/01-产品需求文档.md`、`../product/02-前端需求文档.md`、`01-技术方案.md`、`02-代码架构与目录约定.md`  
> **本文是什么**：HTTP 接口的**完整契约**——每个接口的方法、路径、请求体、响应体、错误码、前置条件、PRD 字段映射、示例。  
> **本文不是什么**：不是业务流程描述（看 `04-业务流程与状态机.md`）；不是字段语义定义（看 PRD）。

---

## 0. 通用约定

### 0.1 Base URL

- 服务端 URL：`http://43.155.205.89/api/v1`（首版纯 IP + HTTP，见技术方案 §11）
- 前端通过 `import.meta.env.VITE_API_BASE` 配置（默认空字符串 = 与前端同域，由 Nginx 反代到 `/api/`）

### 0.2 鉴权

**首版无鉴权**。所有接口公开访问。后续若加用户系统再补 `Authorization: Bearer <token>` 头。

### 0.3 Content-Type

- 请求：`Content-Type: application/json; charset=utf-8`（除非另行说明）
- 响应：`Content-Type: application/json; charset=utf-8`
- 字符编码：**UTF-8**

### 0.4 时间戳

所有 `*_at` 字段为 **RFC 3339 / ISO 8601 带 Z 后缀**字符串，精度到秒。  
例：`"2026-05-14T08:30:45Z"`

### 0.5 标识符

- `scenario_id`：UUID v4 小写十六进制，36 字符，由服务端生成
- `turn_id`：UUID v4，同上
- `job_id`：UUID v4，同上
- `character_id`：用户主角为字面量 `"user"`；NPC 见 PRD §5.2

### 0.6 成功响应通用规则

- HTTP 状态码：
  - `200 OK`：读取或同步操作成功
  - `201 Created`：新资源创建成功
  - `202 Accepted`：异步任务已提交
  - `204 No Content`：删除成功
- 响应体：与各接口"成功响应"段定义一致。

### 0.7 错误响应统一格式

任何 4xx / 5xx 响应**统一**返回：

```json
{
  "error_code": "lifecycle_phase_invalid",
  "message": "场景包尚未完成创作，无法进入对话页",
  "details": { "current_phase": "creation_running" }
}
```

- `error_code`（必填，string）：本文 §0.8 定义的有限枚举，前端用此分支处理。
- `message`（必填，string）：人类可读中文描述，前端可直接 Toast。
- `details`（可选，object）：补充上下文，结构因 `error_code` 而异。

### 0.8 错误码总表

| HTTP | error_code | 含义 | 触发场景 |
|---|---|---|---|
| 400 | `invalid_request_body` | 请求体不是合法 JSON 或缺少必填键 | 各接口 |
| 404 | `scenario_not_found` | 场景包不存在或已被删除 | 几乎所有接口 |
| 404 | `chapter_not_found` | `chapter_id` 不存在于本包 framework | 运行期 |
| 404 | `section_not_found` | `section_id` 不存在于该章 | 运行期 |
| 404 | `turn_not_found` | `turn_id` 不存在 | hint 接口 |
| 404 | `job_not_found` | `job_id` 不存在或属于其他包 | Job 接口 |
| 409 | `lifecycle_phase_invalid` | 当前 `lifecycle_phase` 不允许该操作 | 几乎所有接口 |
| 409 | `framework_already_exists` | 包内已有 framework；如需重置必须传 `force_reset_creation=true` | commit-intake |
| 409 | `active_job_conflict` | 同包已有 `queued`/`running` 的 framework/world Job | `POST .../jobs/framework` / `POST .../jobs/world` |
| 409 | `sections_already_exist` | 包内已有部分小节产物；如需重生成必须传 `force_regenerate=true` | jobs/world |
| 409 | `runtime_not_awaiting_user` | 当前不在等待用户回复状态，不能发提示 | hints |
| 409 | `section_already_has_turns` | 小节已有 turn，自动开场幂等返回 | auto-opener |
| 409 | `section_no_turns_yet` | 小节尚无任何回合，无法触发本节复盘 | analytics |
| 409 | `job_already_terminal` | 该 Job 已 `succeeded`/`failed`/`canceled`，无法取消 | cancel |
| 422 | `intake_field_too_short` | `scene_brief` < 40 或 `user_goal_brief` < 10 | commit-intake |
| 422 | `intake_field_too_long` | 字段超长 | commit-intake |
| 422 | `intake_unrelated_topic` | `scene_brief` 与 `user_goal_brief` 主题完全无关 | commit-intake（业务校验） |
| 422 | `display_name_invalid` | 含控制字符或修剪后空 | 任何含显示名的接口 |
| 422 | `recipient_id_invalid` | `recipient_id` 不在当前节 `appearing_npc_ids` 中 | turns |
| 422 | `content_empty_or_too_long` | `content` 长度 < 1 或 > 8000 | turns |
| 422 | `pointer_target_invalid` | enter 目标 `(ch, sec)` 不存在 | enter |
| 422 | `npc_npc_chain_too_long` | 拟写入回合会让连续 NPC–NPC > 3（§6.6.4 规则 7） | 内部触发，对外通常表现为 NPC 续聊提前返回 |
| 504 | `llm_timeout` | 单次 LLM 调用超过 120s | 任何同步调 LLM 的接口 |
| 502 | `llm_authentication_failed` | DeepSeek 拒绝 API Key（上游 401/403） | 任何同步调 LLM 的接口（多为 Key 错误、过期或环境变量含多余空白） |
| 500 | `llm_failure` | LLM 调用返回错误或输出 schema 不合法且修复重试失败 | 同上 |
| 500 | `auto_opener_failed` | §6.6.5 自动开场失败 | enter / auto-opener |
| 500 | `repository_io_error` | JSON 文件读写失败 | 任意接口 |
| 500 | `internal_error` | 未分类错误（兜底） | 任意接口 |

> 前端 Hooks 在 `apiClient.ts` 中应**只**根据 `error_code` 分支处理，**不依赖** `message` 文本。

### 0.9 路径中的占位符

- `{scenario_id}` → UUID v4
- `{ch}` → 正整数 chapter_id
- `{sec}` → 正整数 section_id
- `{job_id}` → UUID v4
- `{turn_id}` → UUID v4

### 0.10 分页与排序

**首版不分页**。`GET .../turns` 返回该小节全部回合（按时间升序）。如果一节回合数过多导致响应过大，由 §10.2 的"上下文裁剪"在 LLM 调用层解决；前端列表仍接收全量。

### 0.11 字段命名

所有 JSON 键名均 **`snake_case`**，与 PRD 字段名**逐字一致**。

---

## 1. 健康检查

### 1.1 GET `/api/v1/health`

**作用**：服务可用性检查；M0 阶段调试页"健康检查"按钮调它。

**前置条件**：无。

**请求**：无 body。

**成功响应 200**：

```json
{
  "ok": true,
  "service": "gcp-backend",
  "version": "0.4.0",
  "server_time": "2026-05-14T08:30:45Z",
  "data_dir_writable": true,
  "deepseek_configured": true
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `ok` | bool | 总体是否健康 |
| `service` | string | 固定 `"gcp-backend"` |
| `version` | string | 后端版本号 |
| `server_time` | timestamp | 服务器时间，便于排查时差 |
| `data_dir_writable` | bool | `GCP_DATA_DIR` 是否可写 |
| `deepseek_configured` | bool | `DEEPSEEK_API_KEY` 是否非空（**不**校验 Key 能否通过 DeepSeek 鉴权；无效 Key 会在首次调用 LLM 时返回 `502` + `llm_authentication_failed`） |

**错误响应**：无业务错误；若整个服务挂掉则连不上。

---

## 2. 场景包管理

### 2.1 POST `/api/v1/scenario-packages`

**作用**：在用户点击 P2「创建新场景」时，**先**创建一个 `lifecycle_phase === "draft"` 的空包并返回 `scenario_id`；前端拿到后跳转 P2.1，后续 P2.1「下一步」时通过 `commit-intake` 锁定五字段。

**关联 PRD**：§5.4 `draft` 阶段定义；§5.5 包级元数据。

**请求体**：可为空 `{}`。可选携带一个用户希望的初始标题占位：

```json
{
  "scenario_title_hint": "（可选）"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `scenario_title_hint` | string | 否 | 仅作为后续 P2.1 表单的"场景名称"默认填充值；服务端**不**用此值生成任何业务字段；长度 ≤ 120 |

**成功响应 201**：

```json
{
  "scenario_id": "f3a1c8d2-9b4e-4f76-a3b2-5a1e8c9d3f04",
  "lifecycle_phase": "draft",
  "scenario_title": "",
  "created_at": "2026-05-14T08:30:45Z",
  "updated_at": "2026-05-14T08:30:45Z"
}
```

**错误响应**：

| 状态 | error_code |
|---|---|
| 400 | `invalid_request_body`（如 `scenario_title_hint` 超长） |
| 500 | `repository_io_error` |

---

### 2.2 GET `/api/v1/scenario-packages`

**作用**：P2 场景列表页拉取全部场景包概览。

**关联 PRD**：§5.5。

**查询参数**：无（首版不分页）。

**成功响应 200**：

```json
{
  "packages": [
    {
      "scenario_id": "f3a1c8d2-...",
      "scenario_title": "产品经理英文会议",
      "lifecycle_phase": "runtime_active",
      "current_chapter_id": 2,
      "current_section_id": 1,
      "created_at": "2026-05-10T12:00:00Z",
      "updated_at": "2026-05-14T07:50:11Z"
    },
    {
      "scenario_id": "9c2b...",
      "scenario_title": "",
      "lifecycle_phase": "draft",
      "current_chapter_id": null,
      "current_section_id": null,
      "created_at": "2026-05-14T08:30:45Z",
      "updated_at": "2026-05-14T08:30:45Z"
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `packages` | array | 按 `updated_at` **降序**（最近活动的包在最前） |
| `packages[].scenario_id` | UUID | 包主键 |
| `packages[].scenario_title` | string | 可能为空（`draft` 阶段尚未提交五字段时） |
| `packages[].lifecycle_phase` | enum 6 值 | PRD §5.4 |
| `packages[].current_chapter_id` | int / null | 仅 `runtime_active` 非 null |
| `packages[].current_section_id` | int / null | 同上 |

**错误响应**：

| 状态 | error_code |
|---|---|
| 500 | `repository_io_error` |

---

### 2.3 GET `/api/v1/scenario-packages/{scenario_id}`

**作用**：拉取单个场景包的完整摘要——元数据 + 已生成产物的存在性概览。用于 P2a / P2.5 / P3 进入时确认当前状态。

**关联 PRD**：§5.5、§6.1～§6.5 产物的存在与否。

**成功响应 200**：

```json
{
  "scenario_id": "f3a1c8d2-...",
  "scenario_title": "产品经理英文会议",
  "lifecycle_phase": "runtime_active",
  "current_chapter_id": 2,
  "current_section_id": 1,
  "runtime_awaiting_user": true,
  "created_at": "2026-05-10T12:00:00Z",
  "updated_at": "2026-05-14T07:50:11Z",
  "assets": {
    "has_intake_snapshot": true,
    "has_scenario_analysis": true,
    "has_story_framework": true,
    "has_character_roster": true,
    "section_assets_count": 6,
    "section_assets_complete": true
  }
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `runtime_awaiting_user` | bool / null | 运行期是否等待用户发言；非运行期为 null |
| `assets.section_assets_count` | int | 已生成的小节 (`narrative` + `mission` 都齐) 数量 |
| `assets.section_assets_complete` | bool | 是否已为 framework 中**每一节**都生成了 narrative + mission |

**错误响应**：

| 状态 | error_code |
|---|---|
| 404 | `scenario_not_found` |

---

### 2.4 DELETE `/api/v1/scenario-packages/{scenario_id}`

**作用**：P2b 删除确认后调用。**物理删除**该包整个目录 `data/scenarios/{scenario_id}/` 及 `index.json` 中的索引。

**关联 PRD**：§5.5。

**前置条件**：无（任意 `lifecycle_phase` 都允许删除，包括运行期）。

**请求**：无 body。

**成功响应 204**：无响应体。

**错误响应**：

| 状态 | error_code |
|---|---|
| 404 | `scenario_not_found` |
| 500 | `repository_io_error`（部分删除失败） |

> 设计说明：删除时**不**做"二次确认 token"——二次确认在前端 P2b。

---

### 2.5 POST `/api/v1/scenario-packages/{scenario_id}/commit-intake`

**作用**：P2.1「下一步」调用——校验五字段、写入 `intake.json`、扩写得到 `analysis.json`、推进生命周期到 `intake_committed`。**若包内已有 framework**（用户从 P2.3 返回 P2.1 改字段再下一步），必须传 `force_reset_creation=true` 才会执行 G3 重置创作（清下游产物）。

**关联 PRD**：§6.1.1 输入、§6.1.2 输出、§6.1.3 校验、G3。

**前置条件**：

- 包存在；
- `lifecycle_phase ∈ { draft, intake_committed, creation_failed, creation_succeeded }`；
- 若 `lifecycle_phase ∈ { creation_succeeded }` 且**已有 framework**，必须 `force_reset_creation=true`。

**请求体**：

```json
{
  "scenario_title": "产品经理英文会议",
  "user_display_name": "Austin",
  "scene_brief": "我是一家跨境电商公司的产品经理...（≥ 40 字符）",
  "user_goal_brief": "希望能用英文流畅主持周会...（≥ 10 字符）",
  "vocabulary_list": "stakeholder, alignment, blocker, OKR",
  "force_reset_creation": false
}
```

| 字段 | 类型 | 必填 | 约束（与 PRD §6.1.1 一致） |
|---|---|---|---|
| `scenario_title` | string | 是 | 修剪空白后 1~120 个 Unicode 标量值；无控制字符 |
| `user_display_name` | string | 是 | 同上 |
| `scene_brief` | string | 是 | 修剪后 40~20000；过短返回 422 `intake_field_too_short` |
| `user_goal_brief` | string | 是 | 修剪后 10~20000 |
| `vocabulary_list` | string | 是 | 长度 0~5000；可为空字符串 |
| `force_reset_creation` | bool | 否 | 默认 false；仅当包内已有 framework 时需要显式置 true |

**成功响应 200**：

```json
{
  "scenario_id": "f3a1c8d2-...",
  "lifecycle_phase": "intake_committed",
  "intake_snapshot": {
    "scenario_title": "产品经理英文会议",
    "user_display_name": "Austin",
    "scene_brief": "...",
    "user_goal_brief": "...",
    "vocabulary_list": "stakeholder, alignment, blocker, OKR"
  },
  "scenario_analysis": {
    "enriched_scene_description": "（200~20000 字英文场景叙事）",
    "enriched_user_goal": "（80~20000 字英文目标陈述）",
    "normalized_vocabulary": ["stakeholder", "alignment", "blocker", "okr"]
  },
  "reset_applied": false,
  "updated_at": "2026-05-14T08:35:12Z"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `intake_snapshot` | object | 已修剪空白、已锁定的五字段 |
| `scenario_analysis` | object | LLM 扩写结果（PRD §6.1.2） |
| `reset_applied` | bool | 是否执行了 G3 清库（true 当且仅当 `force_reset_creation` 生效） |

**错误响应**：

| 状态 | error_code |
|---|---|
| 404 | `scenario_not_found` |
| 409 | `lifecycle_phase_invalid`（如 `creation_running`） |
| 409 | `framework_already_exists`（包内已有 framework 但未传 `force_reset_creation=true`） |
| 422 | `intake_field_too_short` / `intake_field_too_long` / `display_name_invalid` / `intake_unrelated_topic` |
| 504 | `llm_timeout` |
| 502 | `llm_authentication_failed`（DeepSeek API Key 无效；请检查服务器 `DEEPSEEK_API_KEY`） |
| 500 | `llm_failure` / `repository_io_error` |

**业务行为细节**：

1. **G3 重置**：若 `force_reset_creation === true`，**原子**删除 `framework.json` / `roster.json` / `sections/*` 全部 + 所有 `jobs/*`，然后才执行扩写。
2. 扩写完成后 `lifecycle_phase` 由 `draft` / `creation_failed` / `creation_succeeded` 迁到 `intake_committed`。
3. 该接口**不**自动触发 framework job——前端 P2.1 → P2.2 时再显式调 §3.1 接口。

---

## 3. 创作期 Job（异步 + 轮询）

### 3.1 POST `/api/v1/scenario-packages/{scenario_id}/jobs/framework`

**作用**：启动"剧情框架 + 角色清单"生成（PRD §6.2 + §6.3）。立即返回 `job_id`，前端 P2.2 用 `GET .../jobs/{job_id}` 轮询进度。

**关联 PRD**：§6.2、§6.3、技术方案 §7、§9 M3。

**前置条件**：

- `lifecycle_phase ∈ { intake_committed, creation_failed }`（与 PRD §5.4 v0.5.2 `intake_committed` 语义对齐：该状态**允许**已有 framework/roster——例如 framework job 上次成功后回到 `intake_committed`、再次调用本接口表示"重生成 framework + roster"，**直接覆盖**已有 framework.json / roster.json；若用户在 P2.1 改了五字段，应走 `commit-intake` + `force_reset_creation=true` 而不是本接口）；
- 同包**不得**有未结束（`status ∈ {queued, running}`）的 framework / world job。

**请求体**：可为空 `{}`。

**成功响应 202**：

```json
{
  "job_id": "8e1c...uuid",
  "type": "framework",
  "scenario_id": "f3a1c8d2-...",
  "status": "running",
  "current_step_label": "正在生成剧情框架…",
  "created_at": "2026-05-14T08:40:00Z"
}
```

**错误响应**：

| 状态 | error_code |
|---|---|
| 404 | `scenario_not_found` |
| 409 | `lifecycle_phase_invalid` |
| 409 | `active_job_conflict` |
| 409 | `job_already_terminal`（语义上不会触发，列举完整） |

**业务行为**：

- 进入 `lifecycle_phase = "creation_running"`。
- 后台异步先调 §6.2 生成 framework，立即落盘 `framework.json`；再调 §6.3 生成 roster，落盘 `roster.json`。
- 全部成功后 Job 转 `succeeded`；任一失败转 `failed`，`lifecycle_phase = "creation_failed"`。

---

### 3.2 POST `/api/v1/scenario-packages/{scenario_id}/jobs/world`

**作用**：启动"全书小节扩写 + 任务"生成（PRD §6.4 + §6.5，循环每节）。立即返回 `job_id`，P2.4 用轮询拿进度。

**前置条件**：

- 包内已有 `framework.json` 与 `roster.json`；
- `lifecycle_phase ∈ { intake_committed, creation_failed, creation_succeeded }`（**不**含 `creation_running`——若已有 Job 在跑必须先取消）；
- 同包**不得**有未结束的 framework / world job；
- 若 `lifecycle_phase === "creation_succeeded"` 或包内已有部分 `sections/*` 产物，**必须**传 `force_regenerate=true`，后端原子清空已有 `sections/*` 再重生成（等同 G4 清库行为）；不传则返回 409 `sections_already_exist`。

**请求体**：

```json
{
  "force_regenerate": false
}
```

| 字段 | 默认 | 说明 |
|---|---|---|
| `force_regenerate` | false | 若 true 且包内已有部分 sections 资产，则**全部清空**后重生成（等同 G4 取消的清库行为） |

**成功响应 202**：

```json
{
  "job_id": "7f2d...uuid",
  "type": "world",
  "scenario_id": "f3a1c8d2-...",
  "status": "running",
  "current_step_label": "正在生成第 1 章第 1 节场景…",
  "progress_hint": "1/6",
  "created_at": "2026-05-14T08:55:00Z"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `progress_hint` | string / null | 形如 "1/6"，已完成节数 / 总节数；可空 |

**错误响应**：同 §3.1。

**业务行为**：

- 进入 `lifecycle_phase = "creation_running"`。
- 后台**按 framework 中的顺序**循环每节：先调 §6.4 生成 `narrative.json`，再调 §6.5 生成 `mission.json`；**每节落盘后立即更新 `current_step_label` / `progress_hint`**。
- 全部成功后 Job 转 `succeeded`，`lifecycle_phase = "creation_succeeded"`。

---

### 3.3 GET `/api/v1/scenario-packages/{scenario_id}/jobs/{job_id}`

**作用**：轮询 Job 状态与进度文案。前端 P2.2 / P2.4 每 1 秒调用一次。

**成功响应 200**：

```json
{
  "job_id": "8e1c...uuid",
  "type": "framework",
  "scenario_id": "f3a1c8d2-...",
  "status": "running",
  "current_step_label": "正在生成参与角色…",
  "progress_hint": null,
  "created_at": "2026-05-14T08:40:00Z",
  "updated_at": "2026-05-14T08:41:23Z",
  "finished_at": null,
  "error_code": null,
  "error_message": null
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `status` | enum | `queued` / `running` / `succeeded` / `failed` / `canceled` |
| `current_step_label` | string | G10 文案；运行期实时更新 |
| `progress_hint` | string / null | 例 "3/6"，可空 |
| `finished_at` | timestamp / null | terminal 时刻 |
| `error_code` | string / null | 失败时填充；与本文 §0.8 错误码一致 |
| `error_message` | string / null | 失败时人类可读说明 |

**错误响应**：

| 状态 | error_code |
|---|---|
| 404 | `scenario_not_found` / `job_not_found` |

---

### 3.4 POST `/api/v1/scenario-packages/{scenario_id}/jobs/{job_id}/cancel`

**作用**：P2.2 / P2.4「取消」按钮——中断正在执行的 Job，按规则清库（framework job 不清；world job 清 sections，等同 G4）。

**前置条件**：

- Job 存在且 `status ∈ { queued, running }`；
- terminal Job 返回 409 `job_already_terminal`。

**请求**：无 body。

**成功响应 200**：

```json
{
  "job_id": "7f2d...uuid",
  "status": "canceled",
  "cleared_assets": ["sections"],
  "lifecycle_phase_after": "intake_committed",
  "finished_at": "2026-05-14T08:57:30Z"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `cleared_assets` | string[] | 实际被清除的资产组：`["sections"]` for world job 取消；`[]` for framework job 取消 |
| `lifecycle_phase_after` | enum | 回退后的 phase（通常回到 `intake_committed`） |

**错误响应**：

| 状态 | error_code |
|---|---|
| 404 | `scenario_not_found` / `job_not_found` |
| 409 | `job_already_terminal` |

---

## 4. 运行期（聊天）

### 4.1 GET `/api/v1/scenario-packages/{scenario_id}/runtime`

**作用**：P3 进入时一次性拉取所需的所有运行态信息——当前指针、是否等待用户、本节叙事与任务、本节历史回合（按 §10.2 裁剪可选；首版**全量**返回）。

**前置条件**：

- `lifecycle_phase ∈ { creation_succeeded, runtime_active }`。

**成功响应 200**：

```json
{
  "scenario_id": "f3a1c8d2-...",
  "lifecycle_phase": "runtime_active",
  "current_chapter_id": 2,
  "current_section_id": 1,
  "runtime_awaiting_user": true,
  "section_narrative": {
    "scenario_id": "f3a1c8d2-...",
    "chapter_id": 2,
    "section_id": 1,
    "section_body": "（300~20000 字英文叙事母本）",
    "appearing_npc_ids": ["npc_pm_lead", "npc_engineer"]
  },
  "section_mission": {
    "scenario_id": "f3a1c8d2-...",
    "chapter_id": 2,
    "section_id": 1,
    "section_objective": "（40~1200 字英文任务陈述）"
  },
  "character_roster": { /* PRD §6.3.2 完整对象 */ },
  "turns": [
    {
      "scenario_id": "f3a1c8d2-...",
      "chapter_id": 2,
      "section_id": 1,
      "turn_id": "...",
      "created_at": "2026-05-14T09:00:00Z",
      "speaker_id": "npc_pm_lead",
      "recipient_id": "user",
      "content": "Welcome back, Austin. Ready to walk through the metrics?",
      "expects_user_response": true,
      "turn_writer": "model_npc"
    }
  ],
  "story_framework_brief": {
    "chapters": [
      { "chapter_id": 1, "chapter_title": "...", "section_count": 2 },
      { "chapter_id": 2, "chapter_title": "...", "section_count": 1 }
    ]
  }
}
```

| 字段 | 说明 |
|---|---|
| `section_narrative` / `section_mission` | 当前节完整对象（PRD §6.4.2 / §6.5.2） |
| `character_roster` | 角色全集（PRD §6.3.2） |
| `turns` | 当前节全部回合，按时间升序 |
| `story_framework_brief` | 仅章节标题与每章节数，供 P3 顶栏"背景介绍"或导航使用；详细 framework 走 §4.6 |

**错误响应**：

| 状态 | error_code |
|---|---|
| 404 | `scenario_not_found` |
| 409 | `lifecycle_phase_invalid`（包未完成创作） |

---

### 4.2 POST `/api/v1/scenario-packages/{scenario_id}/sections/{ch}/{sec}/enter`

**作用**：切节进入指定小节。**核心副作用**：若目标节 `turns.jsonl` 为 0 行，**同步触发 §6.6.5 自动开场**生成第一条 NPC 开场白，并将其包含在响应中返回。

**关联 PRD**：§5.5、§5.6、§6.6.5。

**前置条件**：

- `lifecycle_phase ∈ { creation_succeeded, runtime_active }`；
- `(ch, sec)` 在该包 framework 中存在。

**请求**：可为空 `{}`。

**成功响应 200**：

```json
{
  "scenario_id": "f3a1c8d2-...",
  "current_chapter_id": 2,
  "current_section_id": 1,
  "lifecycle_phase": "runtime_active",
  "runtime_awaiting_user": true,
  "section_narrative": { /* ... */ },
  "section_mission": { /* ... */ },
  "character_roster": { /* ... */ },
  "turns": [ /* 该节全部历史，若刚自动开场则包含新写入的首条 */ ],
  "auto_opener_triggered": true,
  "auto_opener_turn_id": "abc123-..."
}
```

| 字段 | 说明 |
|---|---|
| `auto_opener_triggered` | bool。本次调用是否触发了自动开场（仅当目标节原本 `turns === []` 时） |
| `auto_opener_turn_id` | string / null。若 `auto_opener_triggered === true`，等于响应 `turns` 中首条的 `turn_id`；否则 null |

**错误响应**：

| 状态 | error_code |
|---|---|
| 404 | `scenario_not_found` / `chapter_not_found` / `section_not_found` |
| 409 | `lifecycle_phase_invalid` |
| 422 | `pointer_target_invalid` |
| 504 | `llm_timeout`（自动开场超时） |
| 500 | `auto_opener_failed`（自动开场失败；指针**仍然更新**至目标节，但 `turns` 为空且 `auto_opener_triggered: false`；前端见 §4.3 重试） |

> **状态机副作用**（详见 `04-业务流程与状态机.md`）：
> - 第一次从 `creation_succeeded` 进入时，`lifecycle_phase` 迁移到 `runtime_active`。
> - `current_chapter_id` / `current_section_id` 更新为 `(ch, sec)`。
> - 写入首条 `turn` 后，`runtime_awaiting_user = true`。

---

### 4.3 POST `/api/v1/scenario-packages/{scenario_id}/sections/{ch}/{sec}/auto-opener`

**作用**：**显式**重试本节自动开场。当 §4.2 的 enter 返回 `auto_opener_failed` 时，前端展示重试按钮，点击调用本接口。

**前置条件**：

- `(scenario_id, ch, sec) === (current_chapter_id, current_section_id)`——只能针对当前指针所指节；
- 目标节 `turns` 数 === 0（幂等：已有回合则返回 409）。

**请求**：无 body。

**成功响应 200**：

```json
{
  "turn": { /* 新写入的首条 NPC 开场 turn */ },
  "turns": [ /* 该节当前全部回合（即只含上面这一条） */ ],
  "runtime_awaiting_user": true
}
```

**错误响应**：

| 状态 | error_code |
|---|---|
| 404 | `scenario_not_found` / `section_not_found` |
| 409 | `lifecycle_phase_invalid` / `section_already_has_turns` |
| 504 | `llm_timeout` |
| 500 | `auto_opener_failed` |

---

### 4.4 GET `/api/v1/scenario-packages/{scenario_id}/sections/{ch}/{sec}/turns`

**作用**：拉取指定小节的全量回合（按时间升序）。P3a 切节时前端会调一次；通常 §4.2 enter 已返回，再调用本接口较少。

**前置条件**：

- `(ch, sec)` 存在；
- 不要求 `(ch, sec)` 等于当前指针。

**查询参数**：

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `limit` | int | null | 不传返回全部；传则返回**最近** N 条（首版前端不传） |

**成功响应 200**：

```json
{
  "scenario_id": "f3a1c8d2-...",
  "chapter_id": 2,
  "section_id": 1,
  "turns": [ /* PRD §6.6.3 全部字段 */ ]
}
```

**错误响应**：

| 状态 | error_code |
|---|---|
| 404 | `scenario_not_found` / `chapter_not_found` / `section_not_found` |

---

### 4.5 POST `/api/v1/scenario-packages/{scenario_id}/sections/{ch}/{sec}/turns`

**作用**：用户在 P3 点击「发送」时调用——服务端写入用户回合，**同步**触发 NPC 续聊（1~3 条，受 §6.6.4 规则约束），一次性返回所有新写入的 turns。

**关联 PRD**：§6.6.3、§6.6.4 全 9 条规则。

**前置条件**：

- `(ch, sec) === (current_chapter_id, current_section_id)`（**禁止**向非当前指针节追加 turn）；
- `runtime_awaiting_user === true`；
- 最后一条 turn 的 `expects_user_response === true`。

**请求体**：

```json
{
  "content": "Thanks for joining. Could you walk us through the conversion drop?",
  "recipient_id": "npc_pm_lead"
}
```

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `content` | string | 是 | 1~8000 字符 UTF-8；不允许全空白 |
| `recipient_id` | string | 是 | 必须存在于当前节 `section_narrative.appearing_npc_ids`；**不得**为 `"user"` |

**成功响应 200**：

```json
{
  "new_turns": [
    {
      "turn_id": "user-turn-1",
      "speaker_id": "user",
      "recipient_id": "npc_pm_lead",
      "content": "Thanks for joining. Could you walk us through the conversion drop?",
      "expects_user_response": false,
      "turn_writer": "human_user",
      "created_at": "2026-05-14T09:05:12Z",
      "scenario_id": "f3a1c8d2-...",
      "chapter_id": 2,
      "section_id": 1
    },
    {
      "turn_id": "npc-turn-2",
      "speaker_id": "npc_pm_lead",
      "recipient_id": "user",
      "content": "Sure, Austin. Last week we saw a 12% drop in conversion...",
      "expects_user_response": true,
      "turn_writer": "model_npc",
      "created_at": "2026-05-14T09:05:35Z",
      "scenario_id": "f3a1c8d2-...",
      "chapter_id": 2,
      "section_id": 1
    }
  ],
  "runtime_awaiting_user": true
}
```

| 字段 | 说明 |
|---|---|
| `new_turns` | 数组首项**总是用户刚发的那条**；后续 0~3 条为 NPC 续聊（受 §6.6.4 规则 7 上限） |
| `runtime_awaiting_user` | 调用结束后是否仍等待用户；若 NPC 续聊的最后一条 `expects_user_response === true` 则为 true |

**错误响应**：

| 状态 | error_code |
|---|---|
| 404 | `scenario_not_found` / `section_not_found` |
| 409 | `lifecycle_phase_invalid` / `runtime_not_awaiting_user` |
| 422 | `recipient_id_invalid` / `content_empty_or_too_long` |
| 504 | `llm_timeout` |
| 500 | `llm_failure`（NPC 续聊失败——**用户回合已落盘**；前端应展示"NPC 没回应，点击重新生成 NPC 回合"提示） |

> **失败处理细节**：用户消息先写盘后调 LLM；若 LLM 失败，用户回合**保留**，错误响应中**仍返回**用户那条 turn 在 `new_turns[0]`，并设置 `npc_generation_failed: true`（**待定，可能不实现，由 error_code 500 + Toast 提示即可**）。

---

## 5. R1 回答提示

### 5.1 POST `/api/v1/scenario-packages/{scenario_id}/sections/{ch}/{sec}/hints`

**作用**：P3「回答提示」按钮——为用户当前面对的 NPC 提问生成英文参考表达。

**关联 PRD**：§6.7.1～§6.7.4。

**前置条件**：

- `(ch, sec)` 是当前指针；
- `runtime_awaiting_user === true`；
- 最近一条 `expects_user_response === true` 的 NPC turn 的 `turn_id` 作为 `target_turn_id` 由前端传入（避免后端推断歧义）。

**请求体**：

```json
{
  "target_turn_id": "npc-turn-2"
}
```

**成功响应 200**：

```json
{
  "scenario_id": "f3a1c8d2-...",
  "chapter_id": 2,
  "section_id": 1,
  "linked_turn_id": "npc-turn-2",
  "hint_status": "ready",
  "analysis_markdown": "...（PRD §6.7.3，40~12000 字符）...",
  "suggested_utterances": [
    "Could you give us a quick recap of last week's drop?",
    "What's your current hypothesis on why conversion dropped 12%?"
  ],
  "generated_at": "2026-05-14T09:05:50Z"
}
```

**错误响应**：

| 状态 | error_code |
|---|---|
| 404 | `scenario_not_found` / `section_not_found` / `turn_not_found` |
| 409 | `runtime_not_awaiting_user` / `lifecycle_phase_invalid` |
| 504 | `llm_timeout` |
| 500 | `llm_failure`（响应体仍为合法结构，`hint_status: "failed"`，`analysis_markdown` 为错误说明，`suggested_utterances: []`） |

---

### 5.2 GET `/api/v1/scenario-packages/{scenario_id}/sections/{ch}/{sec}/hints/latest`

**作用**：拉取当前节最新一份 hint（用户重新打开提示弹窗时使用，避免重复调 LLM）。

**成功响应 200**：

```json
{
  "linked_turn_id": "npc-turn-2",
  "hint_status": "ready",
  "analysis_markdown": "...",
  "suggested_utterances": ["..."],
  "generated_at": "2026-05-14T09:05:50Z"
}
```

**响应 204**：本节无任何 hint 历史时返回 204 No Content（**不**视为错误）。

**错误响应**：

| 状态 | error_code |
|---|---|
| 404 | `scenario_not_found` / `section_not_found` |

> **stale 自动迁移**：当用户发送了新的 user turn 后，所有 `linked_turn_id` 早于该 user turn 父回合的提示对象 `hint_status` 由服务端规则**异步**置为 `stale`（由 §4.5 turns 写入逻辑触发）。前端 `latest` 拿到 stale 时按 §6.7.1 展示"已过期"。

---

## 6. R2 本节复盘

### 6.1 POST `/api/v1/scenario-packages/{scenario_id}/sections/{ch}/{sec}/analytics`

**作用**：P3「总结分析」按钮——对当前节截至此刻的对话做总结性反馈。**同步**返回（首版）。

**关联 PRD**：§6.8.1～§6.8.4、§7 R2。

**前置条件**：

- `(ch, sec)` 是当前指针；
- 当前节 `turns.length ≥ 1`（否则返回 409 `section_no_turns_yet`）；
- `lifecycle_phase === "runtime_active"`。

**请求**：无 body。

**成功响应 200**：

```json
{
  "scenario_id": "f3a1c8d2-...",
  "chapter_id": 2,
  "section_id": 1,
  "evaluated_through_turn_id": "npc-turn-2",
  "section_analytics_status": "ready",
  "holistic_feedback_markdown": "...（200~20000 字 Markdown 复盘）...",
  "generated_at": "2026-05-14T09:15:00Z"
}
```

**响应字段**：同 PRD §6.8.3。

**业务行为**：成功时**覆盖**已有 `analytics.json`；失败时**保留**上一份成功内容（落盘逻辑：成功才写）。

**错误响应**：

| 状态 | error_code |
|---|---|
| 404 | `scenario_not_found` / `section_not_found` |
| 409 | `section_no_turns_yet` / `lifecycle_phase_invalid` |
| 504 | `llm_timeout` |
| 500 | `llm_failure` |

---

### 6.2 GET `/api/v1/scenario-packages/{scenario_id}/sections/{ch}/{sec}/analytics`

**作用**：拉取当前节最新一份成功复盘。

**成功响应 200**：

```json
{
  "linked_turn_id": "npc-turn-2",
  "section_analytics_status": "ready",
  "holistic_feedback_markdown": "...",
  "generated_at": "2026-05-14T09:15:00Z"
}
```

**响应 204**：本节尚无任何成功复盘（**不**视为错误）。

**错误响应**：

| 状态 | error_code |
|---|---|
| 404 | `scenario_not_found` / `section_not_found` |

---

## 7. 调试接口（可选，仅 /debug/ 调试页使用）

### 7.1 GET `/api/v1/debug/llm-logs`

**作用**：返回最近 N 条 LLM 调用日志，调试页"LLM 调用日志"区使用。

**查询参数**：

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `limit` | int | 50 | 1~200 |

**成功响应 200**：

```json
{
  "logs": [
    {
      "id": "log-uuid",
      "agent": "auto_opener",
      "scenario_id": "f3a1c8d2-...",
      "started_at": "2026-05-14T08:55:00Z",
      "duration_ms": 4523,
      "ok": true,
      "prompt_excerpt": "...",
      "response_excerpt": "...",
      "error_code": null
    }
  ]
}
```

> 首版日志**仅内存**保存（重启即丢失），不入盘；后续可改为按天落盘文件。

---

### 7.2 GET `/api/v1/debug/raw-file`

**作用**：返回 `data/scenarios/{id}/...` 下任意 JSON 文件的原始内容，调试页"原始 JSON 查看"使用。

**查询参数**：

| 参数 | 必填 | 说明 |
|---|---|---|
| `scenario_id` | 是 | |
| `relpath` | 是 | 相对 `data/scenarios/{id}/` 的路径，如 `framework.json` 或 `sections/ch1_sec1/turns.jsonl` |

**响应**：以 `application/json` 或 `text/plain`（JSONL 时）返回文件原始内容。

> **安全**：服务端**仅**允许 `data/scenarios/{id}/` 下白名单内的文件路径（不允许 `..` 等路径穿越）。

---

## 8. 数据契约示例：完整一个 turn 的 JSON

PRD §6.6.3 字段一一映射：

```json
{
  "scenario_id": "f3a1c8d2-9b4e-4f76-a3b2-5a1e8c9d3f04",
  "chapter_id": 2,
  "section_id": 1,
  "turn_id": "9b4e4f76-a3b2-4abc-9d3f-04f3a1c8d2bb",
  "created_at": "2026-05-14T09:05:35Z",
  "speaker_id": "npc_pm_lead",
  "recipient_id": "user",
  "content": "Sure, Austin. Last week we saw a 12% drop in conversion. Want me to break it down by funnel stage?",
  "expects_user_response": true,
  "turn_writer": "model_npc"
}
```

> **关键约束**（PRD §6.6.4 / §6.6.1 交叉）：
> - `turn_writer === "human_user"` ⟺ `speaker_id === "user"`
> - `turn_writer === "model_npc"` ⟺ `speaker_id !== "user"`
> - `expects_user_response === true` ⟹ `recipient_id === "user"`
> - `speaker_id !== recipient_id`

---

## 9. 接口与前端用户故事的追溯表

| 前端故事编号 | 调用接口 |
|---|---|
| P1-02-01「知道了」 | 无（仅路由跳转） |
| P2-01-02 列表展示 | `GET /scenario-packages` |
| P2-03-01「创建新场景」 | `POST /scenario-packages` |
| P2a-01-03 删除成功 | `DELETE /scenario-packages/{id}` |
| P2a-02-01「进入场景」 | `GET /scenario-packages/{id}` + `POST /sections/{ch}/{sec}/enter` |
| P2.1-01-03「下一步」 | `POST /scenario-packages/{id}/commit-intake` + `POST /jobs/framework` |
| P2.1-01-04「下一步」+G3 | `POST /commit-intake` with `force_reset_creation=true` |
| P2.2 轮询 | `GET /jobs/{job_id}` |
| P2.2-01-01「取消」 | `POST /jobs/{job_id}/cancel` |
| P2.3-02-01「下一步」 | `POST /jobs/world` |
| P2.4 轮询 | `GET /jobs/{job_id}` |
| P2.4-01-01「取消」 | `POST /jobs/{job_id}/cancel` |
| P2.5-02-01「完成并返回列表」 | 无业务调用，前端跳转 |
| P2.5-03-01「直接探索世界」 | `POST /sections/1/1/enter` |
| P3 进入加载 | `GET /scenario-packages/{id}/runtime` |
| P3-03-01「回答提示」 | `POST /sections/{ch}/{sec}/hints` |
| P3-04-01「总结分析」 | `POST /sections/{ch}/{sec}/analytics` |
| P3-06-01「发送」 | `POST /sections/{ch}/{sec}/turns` |
| P3-07-02「进节自动开场」 | （由 enter 接口自动触发） |
| P3-07-02b「重试本节开场」 | `POST /sections/{ch}/{sec}/auto-opener` |
| P3a-02-01「确认进入」 | `POST /sections/{ch}/{sec}/enter` |
| DBG-01-01「调试模式」 | 路由跳转 `/debug/`，独立接口见 §7 |

---

## 10. 更新记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v0.1.1 | 2026-05-14 | **交叉审阅修复**：① §3.1 `POST /jobs/framework` 前置条件细化：明确允许 `intake_committed` 状态下已有 framework 的"重生成"语义，与 PRD v0.5.2 §5.4 `intake_committed` 扩充语义对齐；② §3.2 `POST /jobs/world` 前置条件改为"已有 sections 时必须 `force_regenerate=true`"，去掉允许 `creation_running` 的歧义；③ §0.8 错误码总表加 `sections_already_exist`（HTTP 409） |
| v0.1.0 | 2026-05-14 | 初稿：全部接口完整契约（请求/响应/错误码/PRD 映射/前端故事追溯） |

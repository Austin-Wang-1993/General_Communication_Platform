# Backend · FastAPI

> 通用英语对话练习产品 · 后端服务。  
> 架构遵循 [`docs/engineering/02-代码架构与目录约定.md`](../docs/engineering/02-代码架构与目录约定.md)（后端四层：Router → Service → Repository → Client）。  
> 接口契约见 [`docs/engineering/03-API 接口文档.md`](../docs/engineering/03-API%20接口文档.md)。

## 本地开发

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 启动（开发模式，热重载）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 健康检查
curl http://localhost:8000/api/v1/health
```

## 跑测试

```bash
cd backend
pytest -q
```

## 当前里程碑

- **M1**：场景包 CRUD（`GET/POST/DELETE /api/v1/scenario-packages`）
- **M2**：`POST .../commit-intake`（五字段 + `intake.json` / `analysis.json`）
- **M3**：`POST .../jobs/framework` + `GET .../jobs/{job_id}`（异步生成 `framework.json` / `roster.json`）
- **M4**：`POST .../jobs/world` + `POST .../jobs/{job_id}/cancel`（`sections/ch*_sec*/` 小节资产）
- **M5（进行中）**：`GET .../runtime`、`POST .../enter`（自动开场）、`GET/POST .../turns`（用户 + NPC 一条）、`POST .../auto-opener`；**待续**：§6.6.4 全量链式规则、`hints` 等

## 目录速览

```
app/
├── main.py            FastAPI 应用装配
├── config.py          环境变量配置
├── errors.py          异常类与全局 handler
├── routers/           ① 路由层（M0: health）
├── services/          ② 业务服务层（M1+）
├── repositories/      ③ 数据仓库层（M1+）
├── clients/           ④ 外部客户端层（M2+）
├── models/            跨层 Pydantic 模型
├── validators/        业务校验工具
├── prompts/           LLM 提示词 Markdown
└── debug_ui/          调试页静态资源
tests/                 单元 + 集成测试
data/                  运行时数据（.gitignore）
```

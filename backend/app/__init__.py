"""通用英语对话练习 · 后端应用包。

按 `docs/engineering/02-代码架构与目录约定.md` 的四层架构组织：

- routers/      ① 路由层：HTTP 接收与响应
- services/     ② 业务服务层：PRD §6.1~§6.8 业务规则
- repositories/ ③ 数据仓库层：data/ JSON 文件读写
- clients/      ④ 外部客户端层：DeepSeek API
- models/       跨层 Pydantic 模型
- validators/   业务校验工具
- prompts/      LLM 提示词 Markdown
- debug_ui/     调试页静态资源
"""

__version__ = "0.6.5"

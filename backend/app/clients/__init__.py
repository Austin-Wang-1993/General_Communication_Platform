"""外部客户端层（④ Client）：调外部服务（DeepSeek）。

按 `02-代码架构与目录约定.md` §2.4 组织。M0 阶段为空占位；
M2+ 加入：
- llm_client.py   DeepSeek API 封装，含 §11.6 超时、§9 schema 修复重试
- prompts.py      提示词加载工具（从 backend/app/prompts/*.md 读）
"""

"""路由层（① Router）：HTTP 接收与响应；不写业务规则。

按 `02-代码架构与目录约定.md` §2.1 组织：
- health.py             健康检查（M0 已实现）
- scenario_packages.py  PRD §5.5 / §6.1 包 CRUD + commit-intake（M1+）
- creation_jobs.py      PRD §6.2~§6.5 异步 Job + 进度查询（M3+）
- runtime.py            PRD §6.6 + §6.6.5 enter / turns / auto-opener（M5）
- hints.py              PRD §6.7（M5.5）
- analytics.py          PRD §6.8（M5.5）
"""
